"""EPICS PVAccess server for CAEN EASY-DRIVER power supply."""
# pylint: disable=invalid-name,broad-exception-caught
__version__ = 'v0.1.0 2026-09-23'

import argparse
import re
import socket
import sys

from epicsdev import epicsdev as edev

DEFAULT_HOST = '192.168.0.10'
DEFAULT_PORT = 10001
DEFAULT_TIMEOUT = 2.0

pargs = None


class C_:
    """Namespace for module state."""

    sock = None
    model = 'UNKNOWN'
    firmware = 'N/A'
    setpoint_range = 10.0


def handle_exception(where: str):
    """Report exception context through logging/status PVs."""
    edev.printe(f'{where}: {sys.exc_info()[1]}')


def _read_line() -> str:
    if C_.sock is None:
        raise RuntimeError('Socket is not connected')

    data = bytearray()
    while True:
        ch = C_.sock.recv(1)
        if not ch:
            break
        data.extend(ch)
        if ch == b'\r' or ch == b'\n':
            break
    return data.decode('ascii', errors='ignore').strip()


def _connect():
    try:
        C_.sock = socket.create_connection((pargs.host, pargs.port), timeout=pargs.timeout)
        C_.sock.settimeout(pargs.timeout)
        edev.printi(f'Connected to EASY-DRIVER at {pargs.host}:{pargs.port}')
    except OSError:
        handle_exception(f'connecting to {pargs.host}:{pargs.port}')
        sys.exit(1)


def _send(cmd: str) -> str:
    if C_.sock is None:
        raise RuntimeError('Socket is not connected')
    wire = f'{cmd}\r'.encode('ascii', errors='ignore')
    C_.sock.sendall(wire)
    reply = _read_line()
    if reply == '':
        raise RuntimeError(f'Empty reply for command {cmd!r}')
    return reply


def _is_ack(reply: str) -> bool:
    r = str(reply).strip().upper()
    return r == '#AK' or r.endswith(':#AK')


def _is_nak(reply: str) -> bool:
    r = str(reply).strip().upper()
    return r == '#NAK' or r.endswith(':#NAK')


def _parse_first_float(text: str, default=None):
    m = re.search(r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?', str(text))
    if not m:
        return default
    try:
        return float(m.group(0))
    except ValueError:
        return default


def _value_after_colon(reply: str) -> str:
    s = str(reply).strip()
    if ':' in s:
        return s.split(':')[-1].strip()
    return s


def _parse_status_bits(reply: str) -> int:
    """Parse '#MST:xx' (hex) and return int value for status register."""
    s = _value_after_colon(reply)
    s = s.replace('0x', '').replace('0X', '').strip()
    if re.fullmatch(r'[0-9a-fA-F]{1,2}', s):
        return int(s, 16)
    m = re.search(r'\d+', s)
    if m:
        return int(m.group(0))
    raise ValueError(f'Cannot parse status register from {reply!r}')


def _query_float(cmd: str, default=None):
    try:
        return _parse_first_float(_send(cmd), default=default)
    except Exception:
        handle_exception(f'in _query_float({cmd})')
        return default


def _query_text(cmd: str, default='') -> str:
    try:
        return _send(cmd)
    except Exception:
        handle_exception(f'in _query_text({cmd})')
        return default


def _infer_range_from_model(model: str, fallback: float) -> float:
    """Infer current range from model code, e.g. 0520->5A, 1020->10A, 0112->1A."""
    mcode = re.search(r'(?<!\d)(\d{4})(?!\d)', str(model))
    if not mcode:
        return fallback
    amps_txt = mcode.group(1)[:2]
    try:
        amps = float(int(amps_txt))
    except ValueError:
        return fallback
    return amps if amps > 0 else fallback


def _refresh_status_bits():
    try:
        status = _parse_status_bits(_send('MST'))
        edev.publish('SupplyOn', 1 if (status & (1 << 0)) else 0, ifChanged=True)
        edev.publish('GenericFault', 1 if (status & (1 << 1)) else 0, ifChanged=True)
        edev.publish('DCunderV', 1 if (status & (1 << 2)) else 0, ifChanged=True)
        edev.publish('FETovertemp', 1 if (status & (1 << 3)) else 0, ifChanged=True)
        edev.publish('ShuntOvertemp', 1 if (status & (1 << 4)) else 0, ifChanged=True)
        edev.publish('ExternalInterlock1', 1 if (status & (1 << 5)) else 0, ifChanged=True)
    except Exception:
        handle_exception('in _refresh_status_bits')


def _read_pid_and_slew_cells():
    for pv_name, cell in [('ControllerKp', 13), ('ControllerKi', 14), ('ControllerKd', 15)]:
        v = _query_float(f'MRG:{cell}', edev.pvv(pv_name))
        if v is not None:
            edev.publish(pv_name, v, ifChanged=True)


def set_enable(value, *_):
    try:
        on = str(value).strip().upper() in ('1', 'ON', 'TRUE')
        cmd = 'MON' if on else 'MOFF'
        reply = _send(cmd)
        if _is_nak(reply):
            raise RuntimeError(f'{cmd} rejected: {reply}')
        if not _is_ack(reply):
            raise RuntimeError(f'Unexpected reply to {cmd}: {reply}')
        edev.publish('Enable', 1 if on else 0, ifChanged=True)
        _refresh_status_bits()
    except Exception:
        handle_exception('in set_enable')


def set_reset(_value, *_):
    try:
        reply = _send('MRESET')
        if not _is_ack(reply):
            raise RuntimeError(f'Unexpected reply to MRESET: {reply}')
        _refresh_status_bits()
    except Exception:
        handle_exception('in set_reset')


def set_slew_control(value, *_):
    """0: immediate (MWI), 1: rate limited (MRM)."""
    try:
        enabled = str(value).strip().upper() in ('1', 'ON', 'TRUE', 'RATE LIMIT')
        v = 1 if enabled else 0
        edev.publish('SlewControl', v, ifChanged=True)
        edev.publish('SlewControlRBV', v, ifChanged=True)
    except Exception:
        handle_exception('in set_slew_control')


def set_setpoint(value, *_):
    try:
        current = float(value)
        if abs(current) > C_.setpoint_range:
            raise ValueError(f'Setpoint {current} is out of range ±{C_.setpoint_range} A')
        use_ramp = str(edev.pvv('SlewControl')).strip().upper() in ('1', 'ON', 'TRUE', 'RATE LIMIT')
        cmd = f'MRM:{current:.6f}' if use_ramp else f'MWI:{current:.6f}'
        reply = _send(cmd)
        if _is_nak(reply):
            raise RuntimeError(f'{cmd} rejected: {reply}')
        if not _is_ack(reply):
            raise RuntimeError(f'Unexpected reply to {cmd}: {reply}')
        edev.publish('Setpoint', current, ifChanged=True)
        _refresh_status_bits()
    except Exception:
        handle_exception('in set_setpoint')


def _set_cell_value(pv_name: str, cell: int, value):
    """Write user cell with MWG then apply with MPUP (requires output OFF)."""
    val = float(value)
    reply = _send(f'MWG:{cell}:{val:.8g}')
    if _is_nak(reply):
        raise RuntimeError(f'MWG:{cell} rejected: {reply}')
    if not _is_ack(reply):
        raise RuntimeError(f'Unexpected reply to MWG:{cell}: {reply}')

    apply_reply = _send('MPUP')
    if _is_nak(apply_reply):
        raise RuntimeError('MPUP rejected (turn output OFF first)')
    if not _is_ack(apply_reply):
        raise RuntimeError(f'Unexpected reply to MPUP: {apply_reply}')
    edev.publish(pv_name, val, ifChanged=True)


def set_controller_kp(value, *_):
    try:
        _set_cell_value('ControllerKp', 13, value)
    except Exception:
        handle_exception('in set_controller_kp')


def set_controller_ki(value, *_):
    try:
        _set_cell_value('ControllerKi', 14, value)
    except Exception:
        handle_exception('in set_controller_ki')


def set_controller_kd(value, *_):
    try:
        _set_cell_value('ControllerKd', 15, value)
    except Exception:
        handle_exception('in set_controller_kd')


def myPVDefs():
    """PV definitions matching misc/devEasyDriver.db records."""
    F, U, LL, LH, SET = 'features', 'units', 'limitLow', 'limitHigh', 'setter'
    rng = float(C_.setpoint_range)

    return [
        ['Version', 'Version information', 'N/A'],
        ['Enable', 'Turn supply off/on', ['Off', 'On'], {F: 'WD', SET: set_enable}],
        ['Reset', 'Reset supply', ['Reset', 'Reset'], {F: 'WD', SET: set_reset}],
        ['SlewControl', 'Disable/Enable slew rate control', ['Immediate', 'Rate Limit'], {F: 'WD', SET: set_slew_control}],
        ['Setpoint', 'Current setpoint', 0.0, {F: 'W', U: 'A', LL: -rng, LH: rng, SET: set_setpoint}],
        ['BulkVoltage', 'Bulk supply voltage', 0.0, {U: 'V'}],
        ['RegulatorTemp', 'MOSFET regulator temperature', 0.0, {U: 'C'}],
        ['ShuntTemp', 'Shunt temperature', 0.0, {U: 'C'}],
        ['OutputVoltage', 'Supply output voltage', 0.0, {U: 'V'}],
        ['SupplyOn', 'Supply on?', ['Off', 'On']],
        ['GenericFault', 'Generic fault status', ['Good', 'Fault']],
        ['FETovertemp', 'MOSFET overtemperature?', ['Good', 'MOSFET Overtemp']],
        ['ShuntOvertemp', 'Shunt overtemperature?', ['Good', 'Shunt Overtemp']],
        ['DCunderV', 'DC undervoltage?', ['Good', 'DC Undervoltage']],
        ['ExternalInterlock1', 'External Interlock 1 status', ['Good', 'Error']],
        ['CurrentRBV', 'Current readback', 0.0, {U: 'A', LL: -rng, LH: rng}],
        ['SlewControlRBV', 'Slew rate control readback', ['Immediate', 'Rate Limit']],
        ['ControllerKp', 'Proportional gain', 0.0, {F: 'W', SET: set_controller_kp}],
        ['ControllerKi', 'Integral gain', 0.0, {F: 'W', SET: set_controller_ki}],
        ['ControllerKd', 'Derivative gain', 0.0, {F: 'W', SET: set_controller_kd}],
    ]


def refresh_static():
    """Read version and initialize static-compatible values."""
    ver = _query_text('MVER', 'N/A')
    edev.publish('Version', ver)

    m = re.search(r'#?MVER:EASY-DRIVER:([^:]+):([^\s\r\n]+)', ver)
    if m:
        C_.model = m.group(1)
        C_.firmware = m.group(2)

    edev.publish('SlewControl', 1, ifChanged=True)
    edev.publish('SlewControlRBV', 1, ifChanged=True)

    _read_pid_and_slew_cells()
    _refresh_status_bits()


def poll():
    """Main fast polling hook."""
    edev.publish('CurrentRBV', _query_float('MRI', edev.pvv('CurrentRBV')), ifChanged=True)
    edev.publish('BulkVoltage', _query_float('MRP', edev.pvv('BulkVoltage')), ifChanged=True)
    edev.publish('RegulatorTemp', _query_float('MRT', edev.pvv('RegulatorTemp')), ifChanged=True)
    edev.publish('ShuntTemp', _query_float('MRTS', edev.pvv('ShuntTemp')), ifChanged=True)
    edev.publish('OutputVoltage', _query_float('MRV', edev.pvv('OutputVoltage')), ifChanged=True)
    _refresh_status_bits()


def periodic_update():
    """Slower update hook."""
    _read_pid_and_slew_cells()


def serverStateChanged(newState: str):
    if newState == 'Start':
        edev.printi('Start requested')
        _refresh_status_bits()
    elif newState == 'Stop':
        edev.printi('Stop requested')
    elif newState == 'Exit':
        edev.printi('Exit requested')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=__version__,
    )
    parser.add_argument('-a', '--autosave', nargs='?', default='', help='Autosave control. If omitted, autosave is enabled with default directory.')
    parser.add_argument('-c', '--recall', action='store_false', help='If given: do not restore initial PV values from autosave cache.')
    parser.add_argument('-d', '--device', default='caen_edrv', help='Device name, PV prefix is <device><index>:')
    parser.add_argument('-i', '--index', default='0', help='Device index, PV prefix is <device><index>:')
    parser.add_argument('-p', '--putlogPV', nargs='?', default='', help='PV name for logging put operations. Empty means default putlog:dump.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity (-vv for more).')
    parser.add_argument('--host', default=DEFAULT_HOST, help='EASY-DRIVER host name or IP address')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='EASY-DRIVER TCP port')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT, help='TCP timeout in seconds')
    parser.add_argument('--range', type=float, default=0.0, help='Current setpoint range in A. If 0, infer from model code.')

    pargs = parser.parse_args()
    if pargs.putlogPV == '':
        pargs.putlogPV = 'putlog:dump'
    pargs.prefix = f'{pargs.device}{pargs.index}:'

    _connect()

    initial_ver = _query_text('MVER', 'N/A')
    mver = re.search(r'#?MVER:EASY-DRIVER:([^:]+):', initial_ver)
    model_guess = mver.group(1) if mver else 'UNKNOWN'
    C_.setpoint_range = float(pargs.range) if pargs.range > 0 else _infer_range_from_model(model_guess, 10.0)

    pvs = edev.init_epicsdev(
        pargs.prefix,
        myPVDefs(),
        pargs.verbose,
        serverStateChanged,
        '',
        pargs.autosave,
        pargs.recall,
        pargs.putlogPV,
    )
    refresh_static()

    edev.publish('VERSION', __version__)
    edev.set_server('Start')

    server = edev.Server(providers=[pvs])
    edev.printi(f'Server for {pargs.prefix} started. Sleeping per cycle: {repr(edev.pvv("sleep"))} S.')
    while True:
        state = edev.serverState()
        if state.startswith('Exit'):
            break
        if not state.startswith('Stop'):
            poll()
        if not edev.sleep():
            periodic_update()

    try:
        if C_.sock is not None:
            C_.sock.close()
    except OSError:
        pass

    edev.printi('Server is exited')

