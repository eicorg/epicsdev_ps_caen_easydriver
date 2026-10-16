"""Operator interface generator for CAEN EASY-DRIVER"""
__version__ = 'v0.0.3 2026-10-16'# InstrCmd added
# pylint: disable=invalid-name,broad-exception-caught

import argparse
from pathlib import Path

import phoebusgen.screen
import phoebusgen.widget

DEVICE = "caen_edrv"
INSTANCE = "0"
TITLE = DEVICE+INSTANCE
PREFIX = f'pva://{TITLE}:'

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=__version__,
    )
    parser.add_argument("-t", "--title", default=TITLE, help="Screen title")
    parser.add_argument("prefix", nargs="?", default=PREFIX,
        help=(
            "PV prefix used for all widget PV names. "
        ),
    )
    return parser.parse_args()

def _add_items(widget, values: str) -> None:
    for item in values.split(", "):
        widget.item(item)

def main() -> None:
    pargs = _parse_args()
    prefix = pargs.prefix

    screen = phoebusgen.screen.Screen(pargs.title, f"{TITLE}.bob")
    screen.width(1080)
    screen.height(660)

    w = phoebusgen.widget
    widgets = {
        "title": w.Label("title", pargs.title, 20, 10, 230, 30),
        "Model_lbl": w.Label("Model_lbl", "Model:", 270, 14, 45, 20),
        "Model": w.TextUpdate("Model", f"{prefix}Model", 320, 14, 160, 20),
        "Version_lbl": w.Label("Version_lbl", "FW:", 500, 14, 30, 20),
        "Version": w.TextUpdate("Version", f"{prefix}Version", 535, 14, 160, 20),
        "dateTime": w.TextUpdate("dateTime", f"{prefix}dateTime", 800, 14, 260, 20),
    }
    y = 45
    widgets.update({
        "srvStatus_lbl": w.Label("srvStatus_lbl", "Server:", 20, y, 50, 20),
        "srvStatus": w.TextUpdate("srvStatus", f"{prefix}status", 75, y, 985, 20),
    })
    y += 40
    widgets.update({
        "state_lbl": w.Label("state_lbl", "Run/Stop:", 20, y, 65, 20),
        "server": w.ComboBox("server", f"{prefix}server", 90, y, 110, 20),
        "sleep_lbl": w.Label("sleep_lbl", "Sleep:", 410, y, 40, 20),
        "sleep": w.TextEntry("sleep", f"{prefix}sleep", 450, y, 50, 20),
        "cycleTime_lbl": w.Label("cycleTime_lbl", "Period:", 510, y, 50, 20),
        "cycleTime": w.TextUpdate("cycleTime", f"{prefix}cycleTime", 560, y, 60, 20),
        "hb_lbl": w.Label("hb_lbl", "HB:", 640, y, 30, 20),
        "HEARTBEAT": w.TextUpdate("HEARTBEAT", f"{prefix}HEARTBEAT", 670, y, 70, 20),
    })

    y += 40
    widgets.update({
        "host_lbl": w.Label("host_lbl", "Host:", 20, y, 40, 20),
        "host": w.TextUpdate("host", f"{prefix}host", 70, y, 230, 20),
        "port_lbl": w.Label("port_lbl", "Port:", 320, y, 40, 20),
        "port": w.TextUpdate("port", f"{prefix}port", 365, y, 70, 20),
        "Connected_lbl": w.Label("Connected_lbl", "Connected:", 460, y, 90, 20),
        "Connected": w.TextUpdate("Connected", f"{prefix}Connected", 555, y, 45, 20),
        "Identification_lbl": w.Label("Identification_lbl", "Identification:", 20, y+30, 100, 20),
        "Identification": w.TextUpdate("Identification", f"{prefix}Identification", 125, y+30, 935, 20),
    })
    y += 80
    widgets.update({
        "Enable_lbl": w.Label("Enable_lbl", "Enable:", 20, y, 60, 20),
        "Enable": w.ComboBox("Enable", f"{prefix}Enable", 85, y, 95, 20),
        "Reset_lbl": w.Label("Reset_lbl", "Reset (1):", 220, y, 80, 20),
        "Reset": w.TextEntry("Reset", f"{prefix}Reset", 305, y, 95, 20),
    })
    y += 40
    widgets.update({
        "CurrentRBV_lbl": w.Label("CurrentRBV_lbl", "Output Current (A):", 20, y, 200, 20),
        "OutputVoltage_lbl": w.Label("OutputVoltage_lbl", "Output Voltage (V):", 220, y, 200, 20),
        "CurrentRBV": w.Meter("CurrentRBV", f"{prefix}CurrentRBV", 20, y+20, 200, 100),
        "OutputVoltage": w.Meter("OutputVoltage", f"{prefix}OutputVoltage", 220, y+20, 200, 100),
    })
    y += 120
    widgets["SetpointSlider"] = w.ScaledSlider(
        "SetpointSlider", f"{prefix}Setpoint", 20, y, 400, 40)
    y += 40
    for name, label, editable in (
            ("Setpoint", "Accepted SP (A):", True),
            ("CurrentLimit", "Current limit (A):", False),
            ("SlewControl", "Slew control:", True),
            ("SlewControlRBV", "Slew mode RBV:", False),
            ("SlewRate", "Slew rate (A/s):", True),
            ("SlewRateRBV", "Rate RBV (A/s):", False)):
        widgets[f"{name}_lbl"] = w.Label(f"{name}_lbl", label, 20, y, 140, 20)
        widget_type = w.ComboBox if name == "SlewControl" else (
            w.TextEntry if editable else w.TextUpdate)
        widgets[name] = widget_type(name, f"{prefix}{name}", 165, y, 235, 20)
        y += 30

    widgets.update({
        "cmd_lbl": w.Label("cmd_lbl", "Command:", 20, y, 70, 20),
        "instrCmdS": w.TextEntry("instrCmdS", f"{prefix}instrCmdS", 90, y, 230, 20),
        "reply_lbl": w.Label("reply_lbl", "Reply:", 330, y, 45, 20),
        "instrCmdR": w.TextUpdate("instrCmdR", f"{prefix}instrCmdR", 375, y, 685, 20),
    })

    y = 245
    for name, label in (
            ("BulkVoltage", "DC-link (V):"),
            ("RegulatorTemp", "MOSFET temp (C):"),
            ("ShuntTemp", "Shunt temp (C):")):
        widgets[f"{name}_lbl"] = w.Label(f"{name}_lbl", label, 460, y, 150, 20)
        widgets[name] = w.TextUpdate(name, f"{prefix}{name}", 615, y, 125, 20)
        y += 30

    y += 40
    widgets["PID_lbl"] = w.Label("PID_lbl", "Stored PID gains (output off)", 460, y, 280, 20)
    y += 30
    for name, label in (("ControllerKp", "Kp:"), ("ControllerKi", "Ki:"), ("ControllerKd", "Kd:")):
        widgets[f"{name}_lbl"] = w.Label(f"{name}_lbl", label, 460, y, 150, 20)
        widgets[name] = w.TextEntry(name, f"{prefix}{name}", 615, y, 125, 20)
        y += 30

    y = 205
    widgets.update({
        "Status_lbl": w.Label("Status_lbl", "Status register:", 780, y, 150, 20),
        "Status": w.TextUpdate("Status", f"{prefix}Status", 935, y, 125, 20),
        "StatusBits": w.ByteMonitor("StatusBits", f"{prefix}Status", 780, y+30, 280, 25),
    })
    widgets["StatusBits"].num_bits(8)
    widgets["StatusBits"].horizontal(True)
    y += 80
    for name, label in (
            ("SupplyOn", "Output enabled:"),
            ("GenericFault", "Latched fault:"),
            ("DCunderV", "DC-link undervoltage:"),
            ("FETovertemp", "MOSFET overtemp:"),
            ("ShuntOvertemp", "Shunt overtemp:"),
            ("ExternalInterlock1", "External interlock:")):
        widgets[f"{name}_lbl"] = w.Label(f"{name}_lbl", label, 780, y, 210, 20)
        widgets[name] = w.TextUpdate(name, f"{prefix}{name}", 1000, y, 60, 20)
        y += 30

    _add_items(widgets["server"], "Start, Stop, Clear, Exit, Started, Stopped, Exited")
    _add_items(widgets["Enable"], "Off, On")
    _add_items(widgets["SlewControl"], "Immediate, Rate Limit")

    for name in (
            "Setpoint", "CurrentLimit", "SlewRate", "SlewRateRBV", "BulkVoltage",
            "ControllerKp", "ControllerKi", "ControllerKd"):
        widgets[name].format("Engineering")
        widgets[name].precision(3)
    for name in ("RegulatorTemp", "ShuntTemp", "sleep", "cycleTime"):
        widgets[name].format("Decimal")
        widgets[name].precision(1)
    for name in ("HEARTBEAT", "port", "Connected", "Reset", "SlewControlRBV", "Status",
                 "SupplyOn", "GenericFault", "DCunderV", "FETovertemp",
                 "ShuntOvertemp", "ExternalInterlock1"):
        widgets[name].format("Decimal")
        widgets[name].precision(0)

    screen.add_widget(list(widgets.values()))

    out = Path(__file__).with_name(f"{TITLE}.bob")
    screen.write_screen(str(out))

if __name__ == "__main__":
    main()