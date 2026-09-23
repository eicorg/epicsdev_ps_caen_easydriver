# epicsdev_ps_caen_easydriver

EPICS PVAccess server for **CAEN EASY-DRIVER** power supplies.

This server implements remote control over TCP/IP using the EASY-DRIVER command set from:

- `misc/EASY-DRIVER - User's Manual V2.pdf`

and exposes the same operational PV names as in:

- `misc/devEasyDriver.db`

## Implemented PVs

The server hosts these PVs (same names as the DB records):

- `Version`
- `Enable`
- `Reset`
- `SlewControl`
- `Setpoint`
- `BulkVoltage`
- `RegulatorTemp`
- `ShuntTemp`
- `OutputVoltage`
- `SupplyOn`
- `GenericFault`
- `FETovertemp`
- `ShuntOvertemp`
- `DCunderV`
- `ExternalInterlock1`
- `CurrentRBV`
- `SlewControlRBV`
- `ControllerKp`
- `ControllerKi`
- `ControllerKd`

## Command mapping summary

Runtime polling and status use:

- `MST` → status bits
- `MRI` → current readback
- `MRV` → output voltage
- `MRP` → bulk/DC-link voltage
- `MRT` → MOSFET temperature
- `MRTS` → shunt temperature
- `MVER` → version/model string

Control operations use:

- `MON` / `MOFF` → enable/disable output
- `MRESET` → reset status/fault state
- `MWI` / `MRM` → setpoint write (immediate/ramped)
- `MWG` + `MPUP` → controller gains (`Kp`, `Ki`, `Kd`)
- `MRG` → read stored gain values

## Running

Example:

```bash
python -m epicsdev_ps_caen_easydriver --host 192.168.0.10 --port 10001
```

Useful options:

- `-d, --device` device prefix base (default: `caen_edrv`)
- `-i, --index` device index (default: `0`)
- `--host` EASY-DRIVER IP/host
- `--port` EASY-DRIVER TCP port
- `--timeout` socket timeout
- `--range` override setpoint range in A

The published PV prefix is:

- `<device><index>:`

With defaults, PVs are published as:

- `caen_edrv0:<PVName>`
