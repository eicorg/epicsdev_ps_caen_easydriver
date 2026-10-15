"""EPICS PVAccess server for CAEN EASY-DRIVER power supplies."""
# pylint: disable=invalid-name,broad-exception-caught
__version__ = 'v0.0.2 2026-10-15'# error handling improvements
#TODO determine limits for Current and Voltage

import argparse
from dataclasses import dataclass
from functools import partial
import math
import socket
import threading
import time
import sys

from epicsdev import epicsdev as edev

DEVICE = 'caen_edrv'
STATUS_BITS = (
    ('SupplyOn', 'Output enabled', 0),
    ('GenericFault', 'Latched fault', 1),
    ('DCunderV', 'DC-link undervoltage', 2),
    ('FETovertemp', 'MOSFET overtemperature', 3),
    ('ShuntOvertemp', 'Shunt overtemperature', 4),
    ('ExternalInterlock1', 'External interlock tripped', 5),
)
GAIN_CELLS = {'ControllerKp': 13, 'ControllerKi': 14, 'ControllerKd': 15}

#````````````````````````````````````````````````````````````````````````````
# Definitions of PVs, their types, units, limits, and setter functions are
# defined in the myPVDefs() function below.
def myPVDefs():
    """Return Easy-driver PVs, using the hardware current limit."""
    F, T, U, LL, LH = 'features', 'type', 'units', 'limitLow', 'limitHigh'
    SET = 'setter'

    pv_defs = [
['dateTime', 'Server local date/time', 'N/A'],
['host', 'EASY-DRIVER host', C_.pargs.host],
['port', 'EASY-DRIVER TCP port', C_.pargs.port, {T: 'u32'}],
['Connected', 'Last polling cycle succeeded', 0, {T: 'u8'}],
['Version', 'Module firmware version', C_.initial['Version']],
['Model', 'EASY-DRIVER model', C_.initial['Model']],
['Identification', 'Module identification', C_.initial['Identification']],
['CurrentLimit', 'Maximum allowed current magnitude', C_.currentLimit,
    {T: 'f64', U: 'A'}],
['Enable', 'Turn supply off/on', ['Off', 'On'],
    {F: 'WD', SET: _set_enable}],
['Reset', 'Reset module status register (write 1)', 0,
    {F: 'W', T: 'u8', LL: 0, LH: 1, SET: _set_reset}],
['SlewControl', 'Current setpoint update mode', ['Immediate', 'Rate Limit'],
    {F: 'WD', SET: _set_slew_control}],
['SlewControlRBV', 'Server current setpoint update mode', 0, {T: 'u8'}],
['Setpoint', 'Last accepted current setpoint (not hardware readback)', 0.0,
    {F: 'W', T: 'f64', U: 'A', LL: -C_.currentLimit, LH: C_.currentLimit,
     SET: _set_setpoint}],
['SlewRate', 'Ramp slew rate', C_.initial['SlewRate'],
    {F: 'W', T: 'f64', U: 'A/s', LL: 0.0, LH: 1000.0, SET: _set_slew_rate}],
['SlewRateRBV', 'Hardware ramp slew rate', C_.initial['SlewRate'],
    {T: 'f64', U: 'A/s'}],
['CurrentRBV', 'Measured output current', 0.0, {T: 'f64', U: 'A'}],
['OutputVoltage', 'Measured output voltage', 0.0, {T: 'f64', U: 'V'}],
['BulkVoltage', 'DC-link voltage', 0.0, {T: 'f64', U: 'V'}],
['RegulatorTemp', 'MOSFET heatsink temperature', 0.0, {T: 'f64', U: 'C'}],
['ShuntTemp', 'Shunt resistor temperature', 0.0, {T: 'f64', U: 'C'}],
['Status', 'Module status register', 0, {T: 'u8'}],
    ]
    for name, description, _bit in STATUS_BITS:
        pv_defs.append([name, description, 0, {T: 'u8'}])
    for name, cell in GAIN_CELLS.items():
        pv_defs.append([name, 'Stored PID gain (writes require output off)',
                        C_.initial[name],
                        {F: 'W', T: 'f64', SET: partial(_set_gain, cell=cell)}])
    return pv_defs
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

@dataclass(slots=True)
class C_:
    """Container for module state variables."""
    pargs = None
    sock = None
    lock = threading.RLock()
    currentLimit = 0.0
    initial = {}
    slewControl = 0

def _disconnect():
    """Discard a connection whose reply stream may be out of sync."""
    if C_.sock is not None:
        C_.sock.close()
        C_.sock = None

def _send(command: str) -> str:
    """Exchange one CR-terminated ASCII command and reply, without retrying writes."""
    edev.printvv(f'Sending command: {command}')
    if not command or any(char in command for char in '\r\n\x00'):
        raise ValueError('Command must be a single nonempty ASCII line')
    wire = (command + '\r').encode('ascii')
    with C_.lock:
        try:
            if C_.sock is None:
                edev.printvv(f'No existing connection, creating a new one {C_.pargs.host, C_.pargs.port}, timeout={C_.pargs.timeout}')
                try:
                    C_.sock = socket.create_connection(
                        (C_.pargs.host, C_.pargs.port), timeout=C_.pargs.timeout)
                    edev.printvv(f'Created new connection to {(C_.pargs.host, C_.pargs.port)}')
                except OSError as e:
                    edev.printvv(f'Failed to create connection: to {(C_.pargs.host, C_.pargs.port)}, error: {e}')
                    sys.exit(1)
            C_.sock.settimeout(C_.pargs.timeout)
            deadline = time.monotonic() + C_.pargs.timeout
            edev.printvv(f'Sending command to device: {wire}')
            C_.sock.sendall(wire)
            edev.printvv(f'Waiting for reply from device for command: {command}')
            data = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f'Timeout waiting for {command}')
                C_.sock.settimeout(remaining)
                chunk = C_.sock.recv(1)
                if not chunk:
                    raise ConnectionError('EASY-DRIVER closed the connection')
                if chunk in (b'\r', b'\n'):
                    if data:
                        break
                    continue
                data.extend(chunk)
                if len(data) > 4096:
                    raise ValueError('EASY-DRIVER reply exceeds 4096 bytes')
            reply = data.decode('ascii').strip()
        except (OSError, ValueError):
            edev.printw(f'Error occurred while sending command: {command}')
            _disconnect()
            raise
        if reply.startswith('#NAK'):
            raise RuntimeError(f'{command}: device rejected command ({reply})')
        edev.printvv(f'reply: {reply}')
        return reply

def _ack(command: str):
    """Require the documented acknowledgement for a write."""
    reply = _send(command)
    if reply != '#AK':
        raise ValueError(f'{command}: expected #AK, received {reply!r}')

def _query_float(command: str) -> float:
    """Parse a telemetry reply or the bare ASCII contents of an EEPROM cell."""
    reply = _send(command)
    if command.startswith('MRG:'):
        payload = reply
    else:
        prefix = f'#{command}:'
        if command == 'MRTS' and reply.startswith('#MRT:'):
            prefix = '#MRT:'
        if not reply.startswith(prefix):
            raise ValueError(f'{command}: unexpected reply {reply!r}')
        payload = reply[len(prefix):]
    value = float(payload)
    if not math.isfinite(value):
        raise ValueError(f'{command}: non-finite value')
    return value

def _query_status() -> int:
    """Read the two hexadecimal digits of the eight-bit status register."""
    reply = _send('MST')
    if (not reply.startswith('#MST:') or len(reply) != 7
            or any(char not in '0123456789abcdefABCDEF' for char in reply[5:])):
        raise ValueError(f'MST: unexpected reply {reply!r}')
    return int(reply[5:], 16)

def _publish_status(status: int):
    edev.publish('Status', status, ifChanged=True)
    for name, _description, bit in STATUS_BITS:
        edev.publish(name, (status >> bit) & 1, ifChanged=True)
    edev.publish('Enable', status & 1, ifChanged=True)

def _enum_index(value, choices) -> int:
    text = str(value)
    if text in choices:
        return choices.index(text)
    if text in ('0', '1'):
        return int(text)
    raise ValueError(f'Expected one of {choices}, received {value!r}')

def _finite(value) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Value must be finite')
    return number

def _set_enable(value, *_):
    enabled = _enum_index(value, ('Off', 'On'))
    with C_.lock:
        _ack('MON' if enabled else 'MOFF')
        if enabled:
            edev.publish('Setpoint', 0.0)

def _set_reset(value, *_):
    if _enum_index(value, ('0', '1')):
        _ack('MRESET')

def _set_slew_control(value, *_):
    with C_.lock:
        C_.slewControl = _enum_index(value, ('Immediate', 'Rate Limit'))
        edev.publish('SlewControlRBV', C_.slewControl, ifChanged=True)

def _set_setpoint(value, *_):
    current = _finite(value)
    if not -C_.currentLimit <= current <= C_.currentLimit:
        raise ValueError(f'Current must be within +/-{C_.currentLimit} A')
    with C_.lock:
        command = 'MRM' if C_.slewControl else 'MWI'
        _ack(f'{command}:{current:.12g}')

def _set_slew_rate(value, *_):
    rate = _finite(value)
    if not 0.0 <= rate <= 1000.0:
        raise ValueError('Slew rate must be within 0 to 1000 A/s')
    _ack(f'MWSR:{rate:.12g}')

def _set_gain(value, *_, cell: int):
    gain = _finite(value)
    with C_.lock:
        if _query_status() & 1:
            raise RuntimeError('PID gains can only be changed while the output is off')
        _ack(f'MWG:{cell}:{gain:.12g}')
        _ack('MPUP')

def _read_initial():
    """Read configuration without changing the output or EEPROM."""
    reply = _send('MVER')
    parts = reply.split(':')
    if len(parts) != 4 or parts[:2] != ['#MVER', 'EASY-DRIVER']:
        raise ValueError(f'MVER: unexpected reply {reply!r}')
    C_.initial = {'Model': parts[2], 'Version': parts[3]}
    reply = _send('MRID')
    if not reply.startswith('#MRID:'):
        raise ValueError(f'MRID: unexpected reply {reply!r}')
    C_.initial['Identification'] = reply[6:]
    hardware_limit = _query_float('MRG:4')
    if hardware_limit <= 0.0:
        raise ValueError('EEPROM maximum current must be positive')
    C_.currentLimit = hardware_limit
    if C_.pargs.current_range is not None:
        C_.currentLimit = min(C_.currentLimit, C_.pargs.current_range)
    C_.initial['SlewRate'] = _query_float('MRSR')
    for name, cell in GAIN_CELLS.items():
        C_.initial[name] = _query_float(f'MRG:{cell}')

def poll():
    """Publish readbacks, retaining the last valid values on communication failure."""
    try:
        with C_.lock:
            _publish_status(_query_status())
            for name, command in (
                    ('CurrentRBV', 'MRI'), ('OutputVoltage', 'MRV'),
                    ('BulkVoltage', 'MRP'), ('RegulatorTemp', 'MRT'),
                    ('ShuntTemp', 'MRTS'), ('SlewRateRBV', 'MRSR')):
                edev.publish(name, _query_float(command), ifChanged=True)
            edev.publish('Connected', 1, ifChanged=True)
    except (OSError, ValueError, RuntimeError) as exc:
        edev.publish('Connected', 0, ifChanged=True)
        edev.printe(f'EASY-DRIVER polling: {exc}')

def periodic_update():
    """Update server time without accessing hardware while polling is stopped."""
    edev.publish('dateTime', time.strftime('%Y-%m-%d %H:%M:%S'), ifChanged=True)

def serverStateChanged(newState: str):
    """Callback for server state transitions."""
    if newState == 'Start':
        edev.printi('Start requested')
    elif newState == 'Stop':
        edev.printi('Stop requested')
    elif newState == 'Exit':
        edev.printi('Exit requested')

def _positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise argparse.ArgumentTypeError('Value must be finite and positive')
    return number

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=f'{__version__}, epicsdev:{edev.__version__}',
    )
    parser.add_argument('-a', '--autosave', nargs='?', default='', help=
'Autosave control. If omitted, autosave is enabled with default directory.')
    parser.add_argument('-c', '--recall', action='store_false', help=
'If given: do not restore initial PV values from autosave cache.')
    parser.add_argument('-i', '--instance', default='0', help=
'Device instance.')
    parser.add_argument('-p', '--putlogPV', nargs='?', default='', help=
'PV name for logging put operations. Empty means default putlog:dump.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help=
'Increase verbosity (-vv for more).')
    parser.add_argument('device', nargs='?', default=DEVICE, help=
'Device name, the prefix for all generated PVs <prefix><instance>:')

    parser.add_argument('--host', default='192.168.0.10', help=
'EASY-DRIVER hostname or IP address.')
    parser.add_argument('--port', type=int, default=10001, help=
'EASY-DRIVER TCP port.')
    parser.add_argument('--timeout', type=_positive, default=2.0, help=
'TCP command timeout in seconds.')
    parser.add_argument('--range', dest='current_range', type=_positive, help=
'Restrict current magnitude in A (cannot exceed the hardware limit).')

    # Parse command-line arguments and store them in the module state container.
    C_.pargs = parser.parse_args()
    if not 1 <= C_.pargs.port <= 65535:
        parser.error('--port must be within 1 to 65535')
    if C_.pargs.putlogPV == '':
        C_.pargs.putlogPV = 'putlog:dump'
    C_.pargs.prefix = f'{C_.pargs.device.rstrip(":")}{C_.pargs.instance}:'

    edev.printi(f'Initializing EASY-DRIVER... {C_.pargs.host}:{C_.pargs.port}')
    try:
        _read_initial()
    except (OSError, ValueError, RuntimeError) as exc:
        _disconnect()
        parser.exit(1, f'Cannot initialize EASY-DRIVER: {exc}\n')

    C_.PvDefs = myPVDefs()

    # Initialize the EPICS PVAccess server with the defined PVs.
    PVs = edev.init_epicsdev(
        C_.pargs.prefix,
        C_.PvDefs,
        C_.pargs.verbose,
        serverStateChanged,
        None,
        C_.pargs.autosave,
        C_.pargs.recall,
        C_.pargs.putlogPV,
    )
    print(f'Using PV prefix: {C_.pargs.prefix}')

    for initial_name in ('SlewRate', *GAIN_CELLS):
        edev.publish(initial_name, C_.initial[initial_name])
    edev.publish('Setpoint', 0.0)
    edev.publish('Reset', 0)
    _set_slew_control(edev.pvv('SlewControl'))

    # Start the server and print initial status.
    edev.publish('VERSION', __version__)
    edev.set_server('Start')
    server = edev.Server(providers=[PVs])
    edev.printi((f'Server for {C_.pargs.prefix} started. Sleeping per cycle: '
                 f'{repr(edev.pvv("sleep"))} S.'))

    # Main server loop. Polls for updates and handles server state transitions.
    try:
        while True:
            state = edev.serverState()
            if state.startswith('Exit'):
                break
            if not state.startswith('Stop'):
                poll()
            if not edev.sleep():
                periodic_update()
    except KeyboardInterrupt:
        edev.printi('Keyboard interrupt received, exiting main loop...')
        edev.set_server('Exit')
    finally:
        with C_.lock:
            _disconnect()

    edev.printi('Server is exited')
