"""SCN6 command-line interface.  No DLL calls are defined here."""
import ctypes
import os
import shlex
import sys
import time
from datetime import datetime
from scn6_dll import *  # command layer uses the tested data/format helpers
from scn6_driver import SCN6Driver
def print_status(controller, axis_number):
    status = controller.read_axis_status(axis_number)
    if status is None:
        return
    print("\n## AXIS STATUS")
    print("----------------")
    print(
        f"axis       : {axis_name(axis_number)} "
        f"({axis_number})"
    )
    print(
        f"get_status : {status['result']} "
        f"(0x{status['result'] & 0xFFFFFFFF:08X})"
    )
    print(
        f"servo      : {status['servo']}"
    )
    print(
        f"run        : {status['run']}"
    )
    print(
        f"alarm      : {status['alarm']}"
    )
    print(
        f"origin     : {status['origin']}"
    )
    print(
        f"pfin       : {status['pfin']}"
    )
    print(
        f"raw bytes  : {raw_hex(status['raw'])}"
    )
    actual_position, error = (
        controller.read_controller_position(
            axis_number
        )
    )
    if error:
        print(
            f"PNOW       : unavailable ({error})"
        )
    else:
        print(f"PNOW       : {actual_position}")
def print_all_status(controller):
    print("\n## ALL CONNECTED AXIS STATUS")
    print("----------------------------")
    for axis_number in AXIS_NUMBERS:
        if not controller.axes[
            axis_number
        ].connected:
            continue
        status = controller.read_axis_status(
            axis_number
        )
        if status is None:
            continue
        position, error = (
            controller.read_controller_position(
                axis_number
            )
        )
        position_text = (
            str(position)
            if error is None
            else "unavailable"
        )
        print(
            f"axis {axis_name(axis_number)} | "
            f"servo={status['servo']} "
            f"run={status['run']} "
            f"alarm={status['alarm']} "
            f"pfin={status['pfin']} "
            f"PNOW={position_text} "
            f"raw={raw_hex(status['raw'])}"
        )
def print_axes(controller):
    if not controller.require_initialized():
        return
    result = controller.refresh_connected_axes()
    print("\n## CONNECTED AXES")
    print("-----------------")
    print(
        f"get_axes return: {result} "
        f"(success={result == SIO_DONE})"
    )
    print()
    for axis_number in AXIS_NUMBERS:
        state = controller.axes[axis_number]
        print(
            f"axis {axis_name(axis_number)} "
            f"({axis_number:2d}) : "
            f"{'AVAILABLE' if state.connected else 'not available'} "
            f"raw={controller.axes_info[axis_number]}"
        )
def print_prepared_moves(controller):
    print("\n## PREPARED MOTION BUFFER")
    print("-------------------------")
    axes_to_move = controller.prepared_axes()
    if not axes_to_move:
        print("No prepared motion.")
        return
    for axis_number in axes_to_move:
        state = controller.axes[axis_number]
        print(
            f"axis {axis_name(axis_number)} : "
            f"{state.prepared_motion} "
            f"value={state.prepared_value}"
        )
def print_diagnostics(controller):
    state = controller.communication_state()
    print("\n## DIAGNOSTICS")
    print("--------------")
    print(
        f"DLL              : {controller.dll_path}"
    )
    print(
        f"Python           : "
        f"{ctypes.sizeof(ctypes.c_void_p) * 8}-bit"
    )
    print(f"COM port         : {COM_PORT}")
    print(f"baud code        : 0x{BAUD_CODE:02X}")
    print("baud             : 115200")
    print(f"NRT              : {NRT}")
    print(f"RESET            : {RESET}")
    print(f"AUTOMATIC        : {AUTOMATIC}")
    print(f"initialized      : {controller.initialized}")
    print(f"TMBSCOM state    : {state}")
    print(
        f"TMBSCOM state    : {status_name(state)}"
    )
    print(
        f"SIO error        : "
        f"{controller.get_sio_error()}"
    )
    print(
        f"COM error log    : "
        f"{controller.get_com_errlog()}"
    )
# ------------------------------------------------------------
# DLL export report
# ------------------------------------------------------------
def print_dll_exports(controller):
    names = [
        "init_tmbs_config",
        "init_tmbs",
        "init_sio",
        "init_sio_tbus",
        "close_tmbs",
        "reopen_tmbs",
        "get_tmbs_state",
        "get_current_baud",
        "get_sio_error",
        "get_com_errlog",
        "get_axes",
        "move_point",
        "move_abs",
        "move_inc",
        "move_org",
        "move_rotate",
        "move_jog",
        "check_pfin",
        "check_status",
        "follow_position",
        "write_position",
        "set_son",
        "set_soff",
        "reset_alarm",
        "write_velocity",
        "write_inpos",
        "write_fzone",
        "write_rzone",
        "select_svparm",
        "write_trqlim",
        "reset_memory",
        "check_run",
        "check_son",
        "check_alrm",
        "check_org",
        "get_status",
        "read_svmem",
        "write_svmem",
        "read_param",
        "write_param",
        "read_point",
        "write_point",
        "load_param",
        "save_param",
        "save_point",
    ]
    print("\n## TMBSCOM DLL EXPORT MAP")
    print("-------------------------")
    for name in names:
        function = getattr(
            controller,
            name,
            None,
        )
        print(
            f"{name:22s}: "
            f"{'AVAILABLE' if function else 'NOT FOUND'}"
        )
# ------------------------------------------------------------
# Commands
# ------------------------------------------------------------
def command_init(controller, parts):
    if len(parts) != 1:
        print("Usage: init")
        return
    print("\n## INITIALIZE TMBSCOM")
    print("---------------------")
    print(f"COM port       : {COM_PORT}")
    print("baud           : 115200")
    print(f"baud code      : 0x{BAUD_CODE:02X}")
    print(f"NRT            : {NRT}")
    print(f"RESET          : {RESET}")
    print(f"AUTOMATIC      : {AUTOMATIC}")
    history = controller.initialize()
    print(
        f"\nfinal init result : "
        f"{history[-1] if history else 'NO RESULT'}"
    )
    print(
        f"communication state: "
        f"{controller.communication_state()} "
        f"({status_name(controller.communication_state())})"
    )
    print(
        f"initialized       : "
        f"{controller.initialized}"
    )
    if controller.initialized:
        print("\nConnected axes:")
        print_axes(controller)
def command_status(controller, parts):
    if len(parts) != 2:
        print("Usage: status <axis>")
        return
    axis_number = parse_axis(parts[1])
    print_status(
        controller,
        axis_number,
    )
def command_status_all(controller, parts):
    if len(parts) != 1:
        print("Usage: status_all")
        return
    if not controller.require_initialized():
        return
    print_all_status(controller)
def command_position(controller, parts):
    if len(parts) != 2:
        print("Usage: position <axis>")
        return
    axis_number = parse_axis(parts[1])
    if not controller.require_initialized():
        return
    position, error = (
        controller.read_controller_position(
            axis_number
        )
    )
    print("\n## CONTROLLER POSITION")
    print(
        f"axis : {axis_name(axis_number)} "
        f"({axis_number})"
    )
    if error:
        print(f"PNOW : unavailable ({error})")
    else:
        print(f"PNOW : {position}")
def command_read_status_memory(controller, parts):
    if len(parts) != 2:
        print(
            "Usage: read_status_memory <axis>"
        )
        return
    axis_number = parse_axis(parts[1])
    if not controller.require_initialized():
        return
    if controller.read_svmem is None:
        print(
            "ERROR: read_svmem export not present."
        )
        return
    print("\n## STATUS MEMORY")
    print(
        f"axis {axis_name(axis_number)} "
        f"({axis_number})"
    )
    addresses = [
        (
            PNOW_MEMORY_ADDRESS,
            "PNOW 0x7400",
        ),
        (
            VM_VNOW,
            "VNOW 0x7401",
        ),
        (
            VM_STAT,
            "STAT 0x7403",
        ),
        (
            VM_ALRM,
            "ALRM 0x7404",
        ),
        (
            VM_STA2,
            "STA2 0x7408",
        ),
        (
            VM_PNTM,
            "PNTM 0x7415",
        ),
    ]
    for address, label in addresses:
        destination = ctypes.c_long(0)
        result = controller.read_svmem(
            axis_number,
            address,
            ctypes.byref(destination),
        )
        print(
            f"{label:16s}: "
            f"return={result} "
            f"value={destination.value} "
            f"(0x{destination.value & 0xFFFFFFFF:08X})"
        )
def command_move_inc(controller, parts):
    if len(parts) != 4:
        print(
            "Usage: move_inc "
            "<axis> <pulses> CONFIRM"
        )
        return
    if parts[3].upper() != "CONFIRM":
        print(
            "ERROR: physical motion requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    distance = parse_integer(parts[2])
    print("\n## GUARDED INCREMENTAL MOVE")
    print("----------------------------")
    print(
        f"axis     : {axis_name(axis_number)} "
        f"({axis_number})"
    )
    print(
        f"distance : {distance} controller "
        "position-count units"
    )
    result = controller.direct_move_incremental(
        axis_number,
        distance,
    )
    print(
        f"move_inc : {result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
    print(
        f"accepted : {result == SIO_DONE}"
    )
    if result == SIO_DONE:
        position, error = (
            controller.read_controller_position(
                axis_number
            )
        )
        if error:
            print(
                f"PNOW     : unavailable ({error})"
            )
        else:
            print(f"PNOW     : {position}")
def command_move_abs(controller, parts):
    if len(parts) != 4:
        print(
            "Usage: move_abs "
            "<axis> <position> CONFIRM"
        )
        return
    if parts[3].upper() != "CONFIRM":
        print(
            "ERROR: physical motion requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    position = parse_integer(parts[2])
    print("\n## GUARDED ABSOLUTE MOVE")
    print("-------------------------")
    print(
        f"axis     : {axis_name(axis_number)} "
        f"({axis_number})"
    )
    print(f"position : {position}")
    result = controller.direct_move_absolute(
        axis_number,
        position,
    )
    print(
        f"move_abs : {result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
    print(
        f"accepted : {result == SIO_DONE}"
    )
    if result == SIO_DONE:
        position_readback, error = (
            controller.read_controller_position(
                axis_number
            )
        )
        if error:
            print(
                f"PNOW     : unavailable ({error})"
            )
        else:
            print(
                f"PNOW     : {position_readback}"
            )
def command_prepare_abs(controller, parts):
    if len(parts) != 3:
        print(
            "Usage: prepare_abs "
            "<axis> <position>"
        )
        return
    axis_number = parse_axis(parts[1])
    position = parse_integer(parts[2])
    if controller.prepare_absolute_move(
        axis_number,
        position,
    ):
        print(
            f"Prepared axis {axis_name(axis_number)} "
            f"absolute position {position}."
        )
        print(
            "No physical movement was issued."
        )
def command_prepare_inc(controller, parts):
    if len(parts) != 3:
        print(
            "Usage: prepare_inc "
            "<axis> <distance>"
        )
        return
    axis_number = parse_axis(parts[1])
    distance = parse_integer(parts[2])
    if controller.prepare_incremental_move(
        axis_number,
        distance,
    ):
        print(
            f"Prepared axis {axis_name(axis_number)} "
            f"incremental distance {distance}."
        )
        print(
            "No physical movement was issued."
        )
def command_clear_buffer(controller, parts):
    if len(parts) != 1:
        print("Usage: clear_buffer")
        return
    controller.clear_motion_buffer()
    print(
        "Prepared motion buffer cleared."
    )
    print(
        "No controller movement was issued."
    )
def command_show_buffer(controller, parts):
    if len(parts) != 1:
        print("Usage: show_buffer")
        return
    print_prepared_moves(controller)
def command_start_all(controller, parts):
    if len(parts) != 2:
        print(
            "Usage: start_all CONFIRM"
        )
        return
    if parts[1].upper() != "CONFIRM":
        print(
            "ERROR: physical motion requires "
            "CONFIRM."
        )
        return
    axes_to_move = controller.prepared_axes()
    if not axes_to_move:
        print(
            "ERROR: no prepared axes."
        )
        return
    print("\n## START ALL PREPARED AXES")
    print("---------------------------")
    print(
        "WARNING: v13 uses rapid DLL dispatch."
    )
    print(
        "WARNING: this is NOT the final "
        "hardware-synchronized h/t implementation."
    )
    print()
    print_prepared_moves(controller)
    print(
        "\nAll axes will be preflight-checked "
        "before the first move."
    )
    answer = input(
        "\nType START again to physically execute: "
    ).strip()
    if answer.upper() != "START":
        print("START cancelled.")
        return
    accepted = controller.start_prepared_moves()
    print(
        f"\nall commands accepted : {accepted}"
    )
    if not accepted:
        print(
            "Motion sequence was not fully accepted."
        )
        return
    print(
        "\nThe driver will now monitor all "
        "prepared axes."
    )
    completed = controller.wait_for_prepared_axes(
        timeout=30.0,
        interval=0.05,
    )
    print(
        f"\nall axes completed : {completed}"
    )
    if completed:
        print_all_status(controller)
    controller.clear_motion_buffer()
def command_servo(controller, parts, turn_on):
    if len(parts) != 3:
        print(
            f"Usage: "
            f"{'servo_on' if turn_on else 'servo_off'} "
            "<axis> CONFIRM"
        )
        return
    if parts[2].upper() != "CONFIRM":
        print(
            "ERROR: state-changing command "
            "requires CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    dll_function = (
        controller.set_son
        if turn_on
        else controller.set_soff
    )
    if dll_function is None:
        print(
            "ERROR: required DLL export is "
            "not present."
        )
        return
    result = dll_function(axis_number)
    print(
        f"{'servo_on' if turn_on else 'servo_off'} "
        f"axis {axis_name(axis_number)}: "
        f"{result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
def command_alarm_reset(controller, parts):
    if len(parts) != 3:
        print(
            "Usage: alarm_reset "
            "<axis> CONFIRM"
        )
        return
    if parts[2].upper() != "CONFIRM":
        print(
            "ERROR: alarm reset requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    if controller.reset_alarm is None:
        print(
            "ERROR: reset_alarm export not present."
        )
        return
    before = controller.read_axis_status(
        axis_number
    )
    result = controller.reset_alarm(
        axis_number
    )
    print(
        f"reset_alarm axis "
        f"{axis_name(axis_number)}: "
        f"{result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
    time.sleep(0.1)
    after = controller.read_axis_status(
        axis_number
    )
    if before and after:
        print(
            f"alarm before : {before['alarm']}"
        )
        print(
            f"alarm after  : {after['alarm']}"
        )
def command_home(controller, parts):
    if len(parts) != 4:
        print(
            "Usage: home <axis> <mode> CONFIRM"
        )
        return
    if parts[3].upper() != "CONFIRM":
        print(
            "ERROR: homing requires CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    mode = parse_integer(parts[2])
    if controller.move_org is None:
        print(
            "ERROR: move_org export not present."
        )
        return
    status = controller.read_axis_status(
        axis_number
    )
    if status is None:
        return
    if status["alarm"] == SIO_DONE:
        print(
            "ERROR: alarm is active. "
            "Reset it first."
        )
        return
    if status["servo"] != SIO_DONE:
        print(
            "ERROR: servo is OFF."
        )
        return
    print("\n## GUARDED HOMING")
    print(
        f"axis : {axis_name(axis_number)}"
    )
    print(f"mode : {mode} (0x{mode:X})")
    print(
        "WARNING: homing can physically move "
        "the actuator."
    )
    controller.move_org(
        axis_number,
        mode,
    )
    print(
        "Homing command issued."
    )
    start_time = time.monotonic()
    while time.monotonic() - start_time < 30:
        current = controller.read_axis_status(
            axis_number
        )
        if current is None:
            return
        print(
            f"{datetime.now():%H:%M:%S} "
            f"axis={axis_name(axis_number)} "
            f"alarm={current['alarm']} "
            f"pfin={current['pfin']} "
            f"origin={current['origin']}"
        )
        if current["alarm"] == SIO_DONE:
            print(
                "ALARM detected during homing."
            )
            return
        if current["pfin"] == SIO_DONE:
            print(
                "Homing completion reported "
                "with PFIN=1."
            )
            return
        time.sleep(0.1)
    print(
        "Homing timeout."
    )
def command_read_param(controller, parts):
    if len(parts) != 2:
        print("Usage: read_param <axis>")
        return
    axis_number = parse_axis(parts[1])
    if not controller.require_initialized():
        return
    if controller.read_param is None:
        print(
            "ERROR: read_param export not present."
        )
        return
    packet = create_empty_compack()
    result = controller.read_param(
        axis_number,
        ctypes.byref(packet),
    )
    print(
        f"\nread_param axis "
        f"{axis_name(axis_number)}: "
        f"{result}"
    )
    if result == SIO_DONE:
        print_compack(
            "MOVEMENT PARAMETERS",
            packet,
        )
def print_compack(label, packet):
    print(f"\n## {label}")
    for index in range(32):
        if packet.address[index] != -1:
            print(
                f"[{index:02d}] "
                f"address=0x"
                f"{packet.address[index] & 0xFFFFFFFF:08X} "
                f"data={packet.data[index]} "
                f"(0x"
                f"{packet.data[index] & 0xFFFFFFFF:08X})"
            )
def command_read_point(controller, parts):
    if len(parts) != 3:
        print(
            "Usage: read_point "
            "<axis> <point>"
        )
        return
    axis_number = parse_axis(parts[1])
    point_number = parse_integer(parts[2])
    if not controller.require_initialized():
        return
    if controller.read_point is None:
        print(
            "ERROR: read_point export not present."
        )
        return
    packet = create_empty_compack()
    result = controller.read_point(
        axis_number,
        point_number,
        ctypes.byref(packet),
    )
    print(
        f"\nread_point axis "
        f"{axis_name(axis_number)} "
        f"point {point_number}: "
        f"{result}"
    )
    if result == SIO_DONE:
        print_compack(
            f"POINT {point_number}",
            packet,
        )
def command_read_svmem(controller, parts):
    """Read one TMBSCOM SVMEM value without modifying controller memory."""
    if len(parts) != 3:
        print("Usage: read_svmem <axis> <address>")
        return
    axis_number = parse_axis(parts[1])
    address = parse_integer(parts[2])
    if not controller.require_initialized():
        return
    result = controller.read_svmem(axis_number, address)
    print("\n## SVMEM READ")
    print("---------------")
    print(f"axis    : {axis_name(axis_number)} ({axis_number})")
    print(f"address : 0x{address:X} ({address})")
    print(f"value   : {result} (0x{result & 0xFFFFFFFF:08X})")
def command_write_svmem(controller, parts):
    """Write one SVMEM value; explicit confirmation is mandatory."""
    if len(parts) != 5 or parts[4].upper() != "CONFIRM":
        print("Usage: write_svmem <axis> <address> <value> CONFIRM")
        return
    axis_number = parse_axis(parts[1])
    address = parse_integer(parts[2])
    value = parse_integer(parts[3])
    if not controller.require_initialized():
        return
    print("\n## GUARDED SVMEM WRITE")
    print("----------------------")
    print(f"axis    : {axis_name(axis_number)} ({axis_number})")
    print(f"address : 0x{address:X} ({address})")
    print(f"value   : {value} (0x{value & 0xFFFFFFFF:08X})")
    print("WARNING: this writes controller memory.")
    result = controller.write_svmem(axis_number, address, value)
    print(
        f"write_svmem: {result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
def command_select_svparm(controller, parts):
    """Select the servo parameter group through the TMBSCOM API."""
    if len(parts) != 4 or parts[3].upper() != "CONFIRM":
        print("Usage: select_svparm <axis> <parameter> CONFIRM")
        return
    axis_number = parse_axis(parts[1])
    parameter = parse_integer(parts[2])
    if not controller.require_initialized():
        return
    result = controller.select_svparm(axis_number, parameter)
    print(
        f"select_svparm axis {axis_name(axis_number)}: "
        f"{result} (0x{result & 0xFFFFFFFF:08X})"
    )
def command_write_trqlim(controller, parts):
    """Write torque limit through the TMBSCOM API."""
    if len(parts) != 4 or parts[3].upper() != "CONFIRM":
        print("Usage: write_trqlim <axis> <value> CONFIRM")
        return
    axis_number = parse_axis(parts[1])
    value = parse_integer(parts[2])
    if not controller.require_initialized():
        return
    print("\n## GUARDED TORQUE-LIMIT WRITE")
    print("-----------------------------")
    print(f"axis  : {axis_name(axis_number)} ({axis_number})")
    print(f"value : {value}")
    print("WARNING: this writes a servo control parameter.")
    result = controller.write_trqlim(axis_number, value)
    print(
        f"write_trqlim axis {axis_name(axis_number)}: "
        f"{result} (0x{result & 0xFFFFFFFF:08X})"
    )
def read_execution_profile_values(controller, axis_number):
    """
    Read the documented common execution-data area (Bank 30).
    TMBSCOM.DLL read_svmem() performs the actual virtual-memory
    read. No raw Termi-BUS frame is constructed.
    """
    if not controller.require_initialized():
        return None
    if controller.read_svmem is None:
        print("ERROR: read_svmem export not present.")
        return None
    results = []
    for address, parameter_name in EXECUTION_PROFILE_ADDRESSES.items():
        destination = ctypes.c_long(0)
        result = controller.read_svmem(
            axis_number,
            address,
            ctypes.byref(destination),
        )
        results.append({
            "address": address,
            "name": parameter_name,
            "result": result,
            "value": destination.value,
        })
    return results
def command_read_execution_profile(controller, parts):
    """
    Read the common execution-data profile from Bank 30.
    Usage:
        read_execution_profile <axis>
    The command is read-only. It directly uses the documented
    TMBSCOM.DLL read_svmem(axis, address, dst) API.
    """
    if len(parts) != 2:
        print("Usage: read_execution_profile <axis>")
        return
    axis_number = parse_axis(parts[1])
    if not controller.require_axis(axis_number):
        return
    results = read_execution_profile_values(
        controller,
        axis_number,
    )
    if results is None:
        return
    print("\n## EXECUTION DATA AREA - BANK 30")
    print("--------------------------------")
    print(
        f"axis : {axis_name(axis_number)} ({axis_number})"
    )
    print(
        "source : TMBSCOM.DLL read_svmem()"
    )
    print()
    for item in results:
        if item["result"] == SIO_DONE:
            print(
                f"0x{item['address']:08X}  "
                f"{item['name']:6s}  "
                f"{item['value']:12d}  "
                f"0x{item['value'] & 0xFFFFFFFF:08X}"
            )
        else:
            print(
                f"0x{item['address']:08X}  "
                f"{item['name']:6s}  "
                f"READ ERROR ({item['result']})"
            )
def command_execution_status(controller, parts):
    """
    Read execution/status information for every connected axis.
    This command is intentionally read-only.
    """
    if len(parts) != 1:
        print("Usage: execution_status")
        return
    if not controller.require_initialized():
        return
    available_axes = [
        axis_number
        for axis_number in AXIS_NUMBERS
        if controller.axes[axis_number].connected
    ]
    if not available_axes:
        print("No available axes.")
        return
    print("\n## EXECUTION STATUS")
    print("-------------------")
    for axis_number in available_axes:
        status = controller.read_axis_status(axis_number)
        position, position_error = (
            controller.read_controller_position(axis_number)
        )
        if status is None:
            continue
        position_text = (
            str(position)
            if position_error is None
            else "unavailable"
        )
        print(
            f"axis {axis_name(axis_number)} | "
            f"servo={status['servo']} "
            f"run={status['run']} "
            f"alarm={status['alarm']} "
            f"origin={status['origin']} "
            f"pfin={status['pfin']} "
            f"PNOW={position_text} "
            f"raw={raw_hex(status['raw'])}"
        )
def command_memory_api(controller, parts):
    """
    Exercise the TMBSCOM memory-management API.
    This intentionally exposes the DLL functions by their semantic
    names. It does NOT manufacture Q1/Q2/Q3 serial frames.
    Commands:
        load_param <axis> CONFIRM
        save_param <axis> CONFIRM
        save_point <axis> CONFIRM
        reset_memory <axis> CONFIRM
    These are state-changing controller operations, so CONFIRM is
    mandatory.
    """
    if len(parts) != 3 or parts[2].upper() != "CONFIRM":
        print(
            "Usage: "
            "<load_param|save_param|save_point|reset_memory> "
            "<axis> CONFIRM"
        )
        return
    operation = parts[0].lower()
    axis_number = parse_axis(parts[1])
    if not controller.require_initialized():
        return
    function = getattr(controller, operation, None)
    if function is None:
        print(
            f"ERROR: {operation} export not present."
        )
        return
    print("\n## TMBSCOM MEMORY API")
    print(f"operation : {operation}")
    print(f"axis      : {axis_name(axis_number)} ({axis_number})")
    print("This command calls TMBSCOM.DLL directly.")
    print("No raw Termi-BUS frame is constructed.")
    result = function(axis_number)
    print(
        f"{operation} axis {axis_name(axis_number)}: "
        f"{result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
def print_memory_api(controller):
    print("\n## TMBSCOM MEMORY API EXPORTS")
    print("-----------------------------")
    names = (
        "reset_memory",
        "read_svmem",
        "write_svmem",
        "read_param",
        "write_param",
        "read_point",
        "write_point",
        "load_param",
        "save_param",
        "save_point",
        "select_svparm",
        "write_trqlim",
    )
    for name in names:
        function = getattr(controller, name, None)
        print(
            f"{name:16s}: "
            f"{'AVAILABLE' if function else 'NOT FOUND'}"
        )
    print()
    print("These are DLL APIs exposed by the current driver binding.")
    print("Q1/Q2/Q3 are Termi-BUS memory commands documented by")
    print("EE06426I-EN; this diagnostic does not fake their wire format.")
def command_write_velocity(controller, parts):
    if len(parts) != 5:
        print(
            "Usage: write_velocity "
            "<axis> <velocity> <accel> CONFIRM"
        )
        return
    if parts[4].upper() != "CONFIRM":
        print(
            "ERROR: parameter write requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    velocity = parse_integer(parts[2])
    acceleration = parse_integer(parts[3])
    if controller.write_velocity is None:
        print(
            "ERROR: write_velocity export "
            "not present."
        )
        return
    result = controller.write_velocity(
        axis_number,
        velocity,
        acceleration,
    )
    print(
        f"write_velocity axis "
        f"{axis_name(axis_number)}: "
        f"{result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
def command_write_param(controller, parts):
    if len(parts) < 5:
        print(
            "Usage: write_param "
            "<axis> <address> <data> "
            "[<address> <data> ...] CONFIRM"
        )
        return
    if parts[-1].upper() != "CONFIRM":
        print(
            "ERROR: parameter write requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    data_tokens = parts[2:-1]
    if len(data_tokens) % 2:
        print(
            "ERROR: address/data pairs are required."
        )
        return
    try:
        pairs = []
        for index in range(
            0,
            len(data_tokens),
            2,
        ):
            pairs.append(
                (
                    parse_integer(
                        data_tokens[index]
                    ),
                    parse_integer(
                        data_tokens[index + 1]
                    ),
                )
            )
    except ValueError as error:
        print(f"ERROR: {error}")
        return
    if controller.write_param is None:
        print(
            "ERROR: write_param export "
            "not present."
        )
        return
    packet = create_compack(pairs)
    print_compack(
        "PARAMETER WRITE",
        packet,
    )
    result = controller.write_param(
        axis_number,
        ctypes.byref(packet),
    )
    print(
        f"write_param axis "
        f"{axis_name(axis_number)}: "
        f"{result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
def command_write_point(controller, parts):
    if len(parts) < 6:
        print(
            "Usage: write_point "
            "<axis> <point> "
            "<address> <data> "
            "[<address> <data> ...] CONFIRM"
        )
        return
    if parts[-1].upper() != "CONFIRM":
        print(
            "ERROR: point write requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    point_number = parse_integer(parts[2])
    data_tokens = parts[3:-1]
    if len(data_tokens) % 2:
        print(
            "ERROR: address/data pairs are required."
        )
        return
    try:
        pairs = []
        for index in range(
            0,
            len(data_tokens),
            2,
        ):
            pairs.append(
                (
                    parse_integer(
                        data_tokens[index]
                    ),
                    parse_integer(
                        data_tokens[index + 1]
                    ),
                )
            )
    except ValueError as error:
        print(f"ERROR: {error}")
        return
    if controller.write_point is None:
        print(
            "ERROR: write_point export "
            "not present."
        )
        return
    packet = create_compack(pairs)
    print_compack(
        "PTP POINT WRITE",
        packet,
    )
    result = controller.write_point(
        axis_number,
        point_number,
        ctypes.byref(packet),
    )
    print(
        f"write_point axis "
        f"{axis_name(axis_number)} "
        f"point {point_number}: "
        f"{result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
def command_read_memory(controller, parts):
    if len(parts) != 3:
        print(
            "Usage: read_memory "
            "<axis> <hex-address>"
        )
        return
    axis_number = parse_axis(parts[1])
    address = parse_integer(parts[2])
    if not controller.require_initialized():
        return
    if controller.read_svmem is None:
        print(
            "ERROR: read_svmem export "
            "not present."
        )
        return
    destination = ctypes.c_long(0)
    result = controller.read_svmem(
        axis_number,
        address,
        ctypes.byref(destination),
    )
    print(
        f"\nread_svmem axis "
        f"{axis_name(axis_number)}"
    )
    print(
        f"address : 0x{address:08X}"
    )
    print(
        f"return  : {result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
    print(
        f"data    : {destination.value} "
        f"(0x{destination.value & 0xFFFFFFFF:08X})"
    )
def command_write_memory(controller, parts):
    if len(parts) != 5:
        print(
            "Usage: write_memory "
            "<axis> <hex-address> "
            "<value> CONFIRM"
        )
        return
    if parts[4].upper() != "CONFIRM":
        print(
            "ERROR: memory write requires "
            "CONFIRM."
        )
        return
    axis_number = parse_axis(parts[1])
    address = parse_integer(parts[2])
    value = parse_integer(parts[3])
    if controller.write_svmem is None:
        print(
            "ERROR: write_svmem export "
            "not present."
        )
        return
    print("\n## GUARDED MEMORY WRITE")
    print(
        f"axis    : {axis_name(axis_number)}"
    )
    print(
        f"address : 0x{address:08X}"
    )
    print(f"value   : {value}")
    result = controller.write_svmem(
        axis_number,
        address,
        ctypes.c_long(value),
    )
    print(
        f"write_svmem: {result} "
        f"(0x{result & 0xFFFFFFFF:08X})"
    )
# ------------------------------------------------------------
# Help
# ------------------------------------------------------------
def print_help():
    print(
r"""
SCN6 TMBSCOM DRIVER v18
=======================
AXIS FORMAT
-----------
Axis numbers are hexadecimal:
    0 1 2 3 4 5 6 7 8 9 A B C D E F
READ-ONLY
---------
init
axes
status <axis>
status_all
position <axis>
read_status_memory <axis>
read_param <axis>
read_point <axis> <point>
read_memory <axis> <hex-address>
memory_api
load_param <axis> CONFIRM
save_param <axis> CONFIRM
save_point <axis> CONFIRM
reset_memory <axis> CONFIRM
read_svmem <axis> <address>
write_svmem <axis> <address> <value> CONFIRM
select_svparm <axis> <parameter> CONFIRM
write_trqlim <axis> <value> CONFIRM
execution_status
read_execution_profile <axis>
diag
exports
show_buffer
help
DIRECT MOTION
-------------
move_inc <axis> <pulses> CONFIRM
move_abs <axis> <position> CONFIRM
These send the movement immediately through
TMBSCOM.DLL.
PREPARED MULTI-AXIS MOTION
---------------------------
prepare_abs <axis> <position>
    Prepare one axis locally.
    No physical movement.
prepare_inc <axis> <distance>
    Prepare one axis locally.
    No physical movement.
show_buffer
    Display all prepared axes.
clear_buffer
    Delete all prepared moves.
    No physical movement.
start_all CONFIRM
    Preflight all prepared axes, then dispatch
    the prepared movements through TMBSCOM.DLL.
    IMPORTANT:
    v13 currently uses rapid DLL dispatch.
    This is NOT yet hardware-synchronized.
    The documented EE06426I h/t buffering mechanism
    is the next synchronization implementation.
PARAMETERS / MEMORY
-------------------
write_velocity <axis> <velocity> <accel> CONFIRM
write_param <axis> <address> <data> ... CONFIRM
write_point <axis> <point> <address> <data> ... CONFIRM
write_memory <axis> <hex-address> <value> CONFIRM
SERVO / RECOVERY
----------------
servo_on <axis> CONFIRM
servo_off <axis> CONFIRM
alarm_reset <axis> CONFIRM
home <axis> <mode> CONFIRM
IMPORTANT
---------
Run:
    init
    axes
    status_all
before physical testing.
The controller PNOW value is read from virtual
memory address 0x7400.
PFIN and ALARM are read per axis.
Every state-changing operation requires CONFIRM.
No raw Termi-BUS serial frame is constructed by
this version.
"""
    )
# ------------------------------------------------------------
# Command-line parser
# ------------------------------------------------------------
def parse_command_line(line):
    """Convert one SCN6 console line into command tokens.
    This parser belongs only to the human CLI. It does not construct
    or modify Termi-BUS frames and has no effect on the TMBSCOM API.
    """
    return shlex.split(line, posix=True)
# ------------------------------------------------------------
# Command specification system
# ------------------------------------------------------------
#
# The CLI syntax is described once here instead of making the
# dispatcher know about every command's argument rules.
#
# This is deliberately small:
#   AXIS     = hexadecimal axis 0..F
#   INT      = signed/unsigned integer
#   HEX      = hexadecimal memory address/value
#   CONFIRM  = literal CONFIRM
#   TEXT     = any non-empty token
#
# The existing command handlers remain responsible for the actual
# SCN6/TMBSCOM operation. This keeps the tested DLL code unchanged.
# ------------------------------------------------------------
@dataclass(frozen=True)
class CommandSpec:
    syntax: tuple
    description: str = ""
    def validate(self, parts):
        """Validate tokens after the command name."""
        args = parts[1:]
        # Validate a compact grammar with optional repeated tokens.
        # Example:
        #   ("AXIS", "HEX", "INT...", "CONFIRM")
        # means:
        #   axis, address, one-or-more integers, CONFIRM
        def minimum_arguments(tokens):
            total = 0
            for token in tokens:
                if token.endswith("..."):
                    total += 1
                else:
                    total += 1
            return total
        minimum = minimum_arguments(self.syntax)
        if len(args) < minimum:
            raise ValueError(
                f"Usage: {parts[0]} " + " ".join(self.syntax)
            )
        # Validate fixed tokens from left to right. A repeated token
        # consumes everything up to the fixed tokens that follow it.
        position = 0
        for index, token in enumerate(self.syntax):
            if token.endswith("..."):
                base = token[:-3]
                # If this is the final grammar item, consume the rest.
                if index == len(self.syntax) - 1:
                    while position < len(args):
                        validate_token(base, args[position])
                        position += 1
                    return
                # Otherwise leave enough tokens for all remaining
                # fixed grammar items.
                remaining_fixed = len(self.syntax) - index - 1
                repeat_count = len(args) - position - remaining_fixed
                if repeat_count < 1:
                    raise ValueError(
                        f"Usage: {parts[0]} " + " ".join(self.syntax)
                    )
                for _ in range(repeat_count):
                    validate_token(base, args[position])
                    position += 1
                continue
            validate_token(token, args[position])
            position += 1
        if position != len(args):
            raise ValueError(
                f"Usage: {parts[0]} " + " ".join(self.syntax)
            )
def validate_token(token_type, value):
    """Validate one command argument without touching the DLL."""
    token_type = token_type.upper()
    if token_type == "AXIS":
        parse_axis(value)
        return
    if token_type in ("INT", "INTEGER"):
        parse_integer(value)
        return
    if token_type == "HEX":
        # Accept the same integer syntax used elsewhere, including
        # 0x-prefixed values.
        int(value, 0)
        return
    if token_type == "CONFIRM":
        if value.upper() != "CONFIRM":
            raise ValueError("This command requires CONFIRM.")
        return
    if token_type in ("TEXT", "ANY"):
        if not value:
            raise ValueError("Argument cannot be empty.")
        return
    raise ValueError(f"Unknown command argument type: {token_type}")
# Command syntax is defined once here.
COMMAND_SPECS = {
    "init": CommandSpec(()),
    "axes": CommandSpec(()),
    "help": CommandSpec(()),
    "?": CommandSpec(()),
    "status": CommandSpec(("AXIS",)),
    "status_all": CommandSpec(()),
    "position": CommandSpec(("AXIS",)),
    "pos": CommandSpec(("AXIS",)),
    "read_status_memory": CommandSpec(("AXIS",)),
    "read_param": CommandSpec(("AXIS",)),
    "read_point": CommandSpec(("AXIS", "INT")),
    "read_memory": CommandSpec(("AXIS", "HEX")),
    "memory_api": CommandSpec(()),
    "read_svmem": CommandSpec(("AXIS", "HEX")),
    "write_svmem": CommandSpec(("AXIS", "HEX", "INT", "CONFIRM")),
    "select_svparm": CommandSpec(("AXIS", "INT", "CONFIRM")),
    "write_trqlim": CommandSpec(("AXIS", "INT", "CONFIRM")),
    "execution_status": CommandSpec(()),
    "read_execution_profile": CommandSpec(("AXIS",)),
    "load_param": CommandSpec(("AXIS", "CONFIRM")),
    "save_param": CommandSpec(("AXIS", "CONFIRM")),
    "save_point": CommandSpec(("AXIS", "CONFIRM")),
    "reset_memory": CommandSpec(("AXIS", "CONFIRM")),
    "write_param": CommandSpec(("AXIS", "HEX", "INT...", "CONFIRM")),
    "write_point": CommandSpec(("AXIS", "INT", "HEX", "INT...", "CONFIRM")),
    "write_velocity": CommandSpec(("AXIS", "INT", "INT", "CONFIRM")),
    "write_memory": CommandSpec(("AXIS", "HEX", "INT", "CONFIRM")),
    "move_inc": CommandSpec(("AXIS", "INT", "CONFIRM")),
    "move_abs": CommandSpec(("AXIS", "INT", "CONFIRM")),
    "prepare_abs": CommandSpec(("AXIS", "INT")),
    "prepare_inc": CommandSpec(("AXIS", "INT")),
    "show_buffer": CommandSpec(()),
    "clear_buffer": CommandSpec(()),
    "start_all": CommandSpec(("CONFIRM",)),
    "servo_on": CommandSpec(("AXIS", "CONFIRM")),
    "servo_off": CommandSpec(("AXIS", "CONFIRM")),
    "alarm_reset": CommandSpec(("AXIS", "CONFIRM")),
    "home": CommandSpec(("AXIS", "INT", "CONFIRM")),
    "diag": CommandSpec(()),
    "exports": CommandSpec(()),
}
# ------------------------------------------------------------
# Command dispatcher
# ------------------------------------------------------------
def dispatch_command(controller, parts):
    """Validate a command against its specification, then dispatch it."""
    if not parts:
        return
    command = parts[0].lower()
    command_handlers = {
        "help": lambda controller, parts: print_help(),
        "?": lambda controller, parts: print_help(),
        "init": command_init,
        "axes": lambda controller, parts: print_axes(controller),
        "status": command_status,
        "status_all": command_status_all,
        "position": command_position,
        "pos": command_position,
        "read_status_memory": command_read_status_memory,
        "read_param": command_read_param,
        "read_point": command_read_point,
        "read_memory": command_read_memory,
        "write_memory": command_write_memory,
        "memory_api": print_memory_api,
        "read_svmem": command_read_svmem,
        "write_svmem": command_write_svmem,
        "select_svparm": command_select_svparm,
        "write_trqlim": command_write_trqlim,
        "execution_status": command_execution_status,
        "read_execution_profile": command_read_execution_profile,
        "load_param": command_memory_api,
        "save_param": command_memory_api,
        "save_point": command_memory_api,
        "reset_memory": command_memory_api,
        "write_param": command_write_param,
        "write_point": command_write_point,
        "write_velocity": command_write_velocity,
        "move_inc": command_move_inc,
        "move_abs": command_move_abs,
        "prepare_abs": command_prepare_abs,
        "prepare_inc": command_prepare_inc,
        "show_buffer": command_show_buffer,
        "clear_buffer": command_clear_buffer,
        "start_all": command_start_all,
        "servo_on": lambda controller, parts: command_servo(
            controller, parts, True
        ),
        "servo_off": lambda controller, parts: command_servo(
            controller, parts, False
        ),
        "alarm_reset": command_alarm_reset,
        "home": command_home,
        "diag": print_diagnostics,
        "exports": print_dll_exports,
    }
    command_handler = command_handlers.get(command)
    if command_handler is None:
        print(f"Unknown command: {command}")
        print("Type 'help' for available commands.")
        return
    specification = COMMAND_SPECS.get(command)
    if specification is not None:
        try:
            specification.validate(parts)
        except (ValueError, TypeError) as error:
            print(f"ERROR: {error}")
            return
    command_handler(controller, parts)
def main():
    print("SCN6 TMBSCOM multi-axis driver v21")
    print("===================================")
    python_bits = ctypes.sizeof(ctypes.c_void_p) * 8
    print(f"Python: {sys.version.split()[0]} ({python_bits}-bit)")
    dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DLL_NAME)
    print(f"DLL: {dll_path}\n")
    if os.name != "nt":
        print("ERROR: this driver requires Windows.")
        return 1
    if python_bits != 32:
        print("ERROR: Tmbscom.DLL is Win32. Run with 32-bit Python.")
        return 1
    try:
        controller = SCN6Driver()
    except Exception as error:
        print(f"ERROR loading Tmbscom.DLL: {error}")
        return 1
    print("Tmbscom.DLL loaded successfully.")
    print(f"SCN6 COM port: {COM_PORT}")
    print("Configuration: 115200 / NRT=2 / RESET=FALSE / AUTOMATIC=FALSE")
    print("Axis range supported by driver: 0..F\n")
    print("Architecture: CLI -> SCN6Driver -> TmbsSCOM DLL")
    print("No raw Termi-BUS serial frames are constructed.")
    print("Type 'init', then 'axes' and 'status_all'.")
    print("Type 'help' for commands.")
    try:
        while True:
            try:
                line = input("\nSCN6> ").strip()
            except EOFError:
                break
            if not line:
                continue
            try:
                parts = parse_command_line(line)
            except ValueError as error:
                print(f"ERROR: invalid command line: {error}")
                continue
            if not parts:
                continue
            if parts[0].lower() in ("quit", "exit"):
                break
            try:
                dispatch_command(controller, parts)
            except KeyboardInterrupt:
                print("\nCommand interrupted.")
            except Exception as error:
                print(f"ERROR: {type(error).__name__}: {error}")
    finally:
        try:
            if controller.initialized:
                controller.close_tmbs()
        except Exception:
            pass
    return 0
if __name__ == "__main__":
    raise SystemExit(main())