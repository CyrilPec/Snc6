import ctypes
import os
import shlex
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
# ============================================================
# SCN6 / TMBSCOM.DLL multi-axis driver v18
#
# py -3.12-32 scn6_tmbs_motion_v15.py
#
# PURPOSE
# -------
# v14 adds an explicit TMBSCOM memory-API layer.
#
# The documented Termi-BUS manual describes:
#   Q1 = EEPROM -> Window
#   Q2 = Window -> Execution
#   Q3 = EEPROM -> Window -> Execution
#
# This version does not invent Q1/Q2/Q3 serial frames. It exposes
# the existing TMBSCOM.DLL memory functions so their exact behavior
# can be tested before implementing higher-level buffered execution.
#
# This version changes the v12 driver from "one configured axis"
# into a multi-axis driver.
#
# Supported axis numbers:
#     0 ... F   (0 ... 15)
#
# The driver keeps the working v12 direct-DLL motion functions:
#     move_inc()
#     move_abs()
#     move_point()
#     move_org()
#     check_status()
#     check_pfin()
#     check_alrm()
#     read_svmem()
#
# IMPORTANT ARCHITECTURE
# ---------------------
# There are now two kinds of motion commands:
#
# 1. DIRECT MOTION
#       move_abs 0 10000 CONFIRM
#
#    This immediately sends the move for one axis.
#
# 2. PREPARED / BUFFERED MOTION
#       prepare_abs 0 10000
#       prepare_abs 1 20000
#       prepare_abs 2 -5000
#       show_buffer
#       start_all CONFIRM
#
#    The Python driver stores the requested moves first.
#
# IMPORTANT LIMITATION OF THIS VERSION
# -------------------------------------
# TMBSCOM.DLL v2.00 exposes move_abs/move_inc/etc., but it does
# NOT expose the Termi-BUS "h" and "t" buffered-command functions
# described by EE06426I-EN section 5.10.3.
#
# Therefore start_all() in THIS VERSION dispatches the prepared
# axes through the documented DLL move_abs/move_inc functions in
# rapid succession. This is NOT claimed to be true hardware-
# synchronized execution.
#
# The next synchronization step is to implement the documented
# Termi-BUS buffered h/t mechanism (or another documented DLL API
# if the installed DLL provides one).
#
# We deliberately do NOT construct raw Termi-BUS frames here.
#
# SAFETY
# ------
# - Read-only commands do not require CONFIRM.
# - Physical motion requires CONFIRM.
# - Servo changes require CONFIRM.
# - Alarm reset requires CONFIRM.
# - Homing requires CONFIRM.
# - Controller memory/parameter/point writes require CONFIRM.
#
# Python:
#     32-bit Python required
#
# DLL:
#     Tmbscom.DLL
# ============================================================
# ------------------------------------------------------------
# Controller configuration
# ------------------------------------------------------------
DLL_NAME = "Tmbscom.DLL"
COM_PORT = "COM6"
BAUD_CODE = 0x14       # TMBS_BAUD_115200 = 115200 bps
NRT = 2
RESET = False
AUTOMATIC = False
MAX_AXIS_COUNT = 16
AXIS_NUMBERS = tuple(range(MAX_AXIS_COUNT))
# ------------------------------------------------------------
# Documented virtual-memory addresses used by v12
# ------------------------------------------------------------
PNOW_MEMORY_ADDRESS = 0x7400     # Absolute/current position
VM_VNOW = 0x7401                 # Current velocity
VM_STAT = 0x7403                 # Status
VM_ALRM = 0x7404                 # Alarm information
VM_STA2 = 0x7408                 # Additional status
VM_PNTM = 0x7415                 # Position/motion information
# ------------------------------------------------------------
# Execution-data area: Bank 30
# ------------------------------------------------------------
# The TMBSCOM manual defines Bank 30 as the common execution
# data area.  The virtual address is the actual address passed
# to read_svmem().  These are READ-ONLY profile/status reads.
#
# Bank 30 base = 0x7800.
# Servo movement parameters in the execution area include:
#   INP, VCMD, ACMD, SPOW, DPOW, PLG0, MXAC, PLG1
# plus the common control parameters.
#
# Q1/Q2/Q3 transfer data between EEPROM, Window and Execution.
# This driver does not fabricate Q1/Q2/Q3 wire frames.
EXECUTION_DATA_BANK_BASE_ADDRESS = 0x7800
EXECUTION_PROFILE_ADDRESSES = {
    0x7800: "CNTM",
    0x7801: "CNTL",
    0x7802: "LIMM",
    0x7803: "LIML",
    0x7804: "ZONM",
    0x7805: "ZONL",
    0x7806: "ORG",
    0x7807: "PHSP",
    0x7808: "FPIO",
    0x7809: "BRSL",
    0x780A: "OVCM",
    0x780B: "OACC",
    0x780C: "RTIM",
    0x780D: "INP",
    0x780E: "VCMD",
    0x780F: "ACMD",
    0x7810: "SPOW",
    0x7811: "DPOW",
    0x7812: "PLG0",
    0x7813: "MXAC",
    0x7814: "CPAC",
    0x7815: "PSWT",
    0x7818: "ZRMK",
    0x7819: "ODPW",
    0x781A: "OTIM",
    0x781B: "PLG1",
    0x781C: "PLJL",
    0x781D: "FLSL",
    0x781E: "FLFC",
}
# ------------------------------------------------------------
# TMBSCOM return values
# ------------------------------------------------------------
SIO_ERROR = 0
SIO_DONE = 1
TMBS_STATE_NAMES = {
    -1: "SIO_COMUSED",
    -2: "SIO_TIMEOUT",
    -5: "SIO_INVALID_PARAM",
    -6: "SIO_NOTSUPORT_TO",
    -8: "SIO_NOTSUPORT_BAUD",
    -9: "SIO_NOTSUPORT_PARA",
    -10: "SIO_NO_CONFIGFILE",
    -12: "TMBS_INIT_ERROR / COM OPEN FAILURE",
    2: "TMBS_INIT_ERROR",
    3: "TMBS_OPENING",
    4: "TMBS_RUNNING",
}
# ------------------------------------------------------------
# Axis state kept by the Python driver
# ------------------------------------------------------------
@dataclass
class AxisState:
    axis_number: int
    connected: bool = False
    # Local bookkeeping only.
    # Actual controller position is read through PNOW.
    commanded_position: Optional[int] = None
    # Prepared motion for start_all().
    prepared_motion: Optional[str] = None
    prepared_value: Optional[int] = None
# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------
def raw_hex(buffer):
    return " ".join(f"{byte:02X}" for byte in bytes(buffer))
def status_name(value):
    return TMBS_STATE_NAMES.get(value, f"UNKNOWN({value})")
def parse_integer(value):
    return int(value, 0)
def parse_axis(value):
    """
    Accept:
        0
        1
        ...
        9
        A
        B
        ...
        F
    Also accepts Python-style integer notation such as 0xA.
    """
    text = value.strip().upper()
    if len(text) == 1 and text in "0123456789ABCDEF":
        axis_number = int(text, 16)
    else:
        axis_number = int(text, 0)
    if axis_number < 0 or axis_number >= MAX_AXIS_COUNT:
        raise ValueError("axis must be in range 0..F")
    return axis_number
def axis_name(axis_number):
    return format(axis_number, "X")
# ------------------------------------------------------------
# TMBSCOM COMPACK structure
# ------------------------------------------------------------
class COMPACK(ctypes.Structure):
    _fields_ = [
        ("address", ctypes.c_int * 32),
        ("data", ctypes.c_long * 32),
    ]
def create_empty_compack():
    communication_packet = COMPACK()
    for index in range(32):
        communication_packet.address[index] = -1
        communication_packet.data[index] = 0
    return communication_packet
def create_compack(address_data_pairs):
    if len(address_data_pairs) > 32:
        raise ValueError("maximum is 32 address/data pairs")
    communication_packet = create_empty_compack()
    for index, (address, data) in enumerate(address_data_pairs):
        communication_packet.address[index] = address
        communication_packet.data[index] = data
    return communication_packet
# ------------------------------------------------------------
# Main controller class
# ------------------------------------------------------------
class TmbsController:
    def __init__(self):
        dll_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            DLL_NAME,
        )
        self.dll_path = dll_path
        self.dll = ctypes.WinDLL(dll_path)
        self.initialized = False
        self.axes_info = [-1] * MAX_AXIS_COUNT
        self.axes = {
            axis_number: AxisState(axis_number)
            for axis_number in AXIS_NUMBERS
        }
        self.last_status = {}
        self.bind_dll_functions()
    # --------------------------------------------------------
    # DLL binding
    # --------------------------------------------------------
    def bind_dll_functions(self):
        controller = self.dll
        # Communication
        self.init_tmbs_config = controller.init_tmbs_config
        self.init_tmbs_config.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self.init_tmbs_config.restype = ctypes.c_int
        self.init_tmbs = controller.init_tmbs
        self.init_tmbs.argtypes = []
        self.init_tmbs.restype = ctypes.c_int
        self.init_sio = controller.init_sio
        self.init_sio.argtypes = []
        self.init_sio.restype = ctypes.c_int
        self.init_sio_tbus = getattr(controller, "init_sio_tbus", None)
        if self.init_sio_tbus:
            self.init_sio_tbus.argtypes = []
            self.init_sio_tbus.restype = ctypes.c_int
        self.close_tmbs = controller.close_tmbs
        self.close_tmbs.argtypes = []
        self.close_tmbs.restype = ctypes.c_int
        self.reopen_tmbs = getattr(controller, "reopen_tmbs", None)
        if self.reopen_tmbs:
            self.reopen_tmbs.argtypes = []
            self.reopen_tmbs.restype = ctypes.c_int
        self.get_tmbs_state = controller.get_tmbs_state
        self.get_tmbs_state.argtypes = []
        self.get_tmbs_state.restype = ctypes.c_int
        self.get_current_baud = controller.get_current_baud
        self.get_current_baud.argtypes = []
        self.get_current_baud.restype = ctypes.c_int
        self.get_sio_error = controller.get_sio_error
        self.get_sio_error.argtypes = []
        self.get_sio_error.restype = ctypes.c_int
        self.get_com_errlog = controller.get_com_errlog
        self.get_com_errlog.argtypes = []
        self.get_com_errlog.restype = ctypes.c_int
        self.get_axes = controller.get_axes
        self.get_axes.argtypes = [ctypes.POINTER(ctypes.c_ushort)]
        self.get_axes.restype = ctypes.c_int
        # Motion
        self.move_point = getattr(controller, "move_point", None)
        if self.move_point:
            self.move_point.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.move_point.restype = ctypes.c_int
        self.move_abs = getattr(controller, "move_abs", None)
        if self.move_abs:
            self.move_abs.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.move_abs.restype = ctypes.c_int
        self.move_inc = getattr(controller, "move_inc", None)
        if self.move_inc:
            self.move_inc.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.move_inc.restype = ctypes.c_int
        self.move_org = getattr(controller, "move_org", None)
        if self.move_org:
            self.move_org.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.move_org.restype = None
        self.move_rotate = getattr(controller, "move_rotate", None)
        if self.move_rotate:
            self.move_rotate.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.move_rotate.restype = ctypes.c_int
        self.move_jog = getattr(controller, "move_jog", None)
        if self.move_jog:
            self.move_jog.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.move_jog.restype = ctypes.c_int
        self.follow_position = getattr(
            controller,
            "follow_position",
            None,
        )
        if self.follow_position:
            self.follow_position.argtypes = [ctypes.c_int]
            self.follow_position.restype = ctypes.c_int
        # Status
        self.check_pfin = getattr(controller, "check_pfin", None)
        self.check_status = getattr(controller, "check_status", None)
        self.check_run = getattr(controller, "check_run", None)
        self.check_son = getattr(controller, "check_son", None)
        self.check_alrm = getattr(controller, "check_alrm", None)
        self.check_org = getattr(controller, "check_org", None)
        for dll_function in (
            self.check_pfin,
            self.check_status,
            self.check_run,
            self.check_son,
            self.check_alrm,
            self.check_org,
        ):
            if dll_function:
                dll_function.argtypes = [ctypes.c_int]
                dll_function.restype = ctypes.c_int
        self.get_status = controller.get_status
        self.get_status.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        self.get_status.restype = ctypes.c_int
        # Servo/state-changing functions
        self.write_position = getattr(
            controller,
            "write_position",
            None,
        )
        if self.write_position:
            self.write_position.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_position.restype = ctypes.c_int
        self.set_son = getattr(controller, "set_son", None)
        if self.set_son:
            self.set_son.argtypes = [ctypes.c_int]
            self.set_son.restype = ctypes.c_int
        self.set_soff = getattr(controller, "set_soff", None)
        if self.set_soff:
            self.set_soff.argtypes = [ctypes.c_int]
            self.set_soff.restype = ctypes.c_int
        self.reset_alarm = getattr(
            controller,
            "reset_alarm",
            None,
        )
        if self.reset_alarm:
            self.reset_alarm.argtypes = [ctypes.c_int]
            self.reset_alarm.restype = ctypes.c_int
        # Execution-area parameter functions
        self.write_velocity = getattr(
            controller,
            "write_velocity",
            None,
        )
        if self.write_velocity:
            self.write_velocity.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.write_velocity.restype = ctypes.c_int
        self.write_inpos = getattr(
            controller,
            "write_inpos",
            None,
        )
        if self.write_inpos:
            self.write_inpos.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_inpos.restype = ctypes.c_int
        self.write_fzone = getattr(
            controller,
            "write_fzone",
            None,
        )
        if self.write_fzone:
            self.write_fzone.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_fzone.restype = ctypes.c_int
        self.write_rzone = getattr(
            controller,
            "write_rzone",
            None,
        )
        if self.write_rzone:
            self.write_rzone.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_rzone.restype = ctypes.c_int
        self.select_svparm = getattr(
            controller,
            "select_svparm",
            None,
        )
        if self.select_svparm:
            self.select_svparm.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.select_svparm.restype = ctypes.c_int
        self.write_trqlim = getattr(
            controller,
            "write_trqlim",
            None,
        )
        if self.write_trqlim:
            self.write_trqlim.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.write_trqlim.restype = ctypes.c_int
        self.reset_memory = getattr(
            controller,
            "reset_memory",
            None,
        )
        if self.reset_memory:
            self.reset_memory.argtypes = [ctypes.c_int]
            self.reset_memory.restype = ctypes.c_int
        # Virtual memory
        self.read_svmem = getattr(
            controller,
            "read_svmem",
            None,
        )
        if self.read_svmem:
            self.read_svmem.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_long),
            ]
            self.read_svmem.restype = ctypes.c_int
        self.write_svmem = getattr(
            controller,
            "write_svmem",
            None,
        )
        if self.write_svmem:
            self.write_svmem.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_svmem.restype = ctypes.c_int
        # Parameter and PTP point memory
        self.read_param = getattr(
            controller,
            "read_param",
            None,
        )
        if self.read_param:
            self.read_param.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.read_param.restype = ctypes.c_int
        self.write_param = getattr(
            controller,
            "write_param",
            None,
        )
        if self.write_param:
            self.write_param.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.write_param.restype = ctypes.c_int
        self.read_point = getattr(
            controller,
            "read_point",
            None,
        )
        if self.read_point:
            self.read_point.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.read_point.restype = ctypes.c_int
        self.write_point = getattr(
            controller,
            "write_point",
            None,
        )
        if self.write_point:
            self.write_point.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.write_point.restype = ctypes.c_int
        self.load_param = getattr(
            controller,
            "load_param",
            None,
        )
        if self.load_param:
            self.load_param.argtypes = [ctypes.c_int]
            self.load_param.restype = ctypes.c_int
        self.save_param = getattr(
            controller,
            "save_param",
            None,
        )
        if self.save_param:
            self.save_param.argtypes = [ctypes.c_int]
            self.save_param.restype = ctypes.c_int
        self.save_point = getattr(
            controller,
            "save_point",
            None,
        )
        if self.save_point:
            self.save_point.argtypes = [ctypes.c_int]
            self.save_point.restype = ctypes.c_int
    # --------------------------------------------------------
    # Communication
    # --------------------------------------------------------
    def communication_state(self):
        return self.get_tmbs_state()
    
    def initialize(self):
        """
        Establish communication and discover connected axes.

        TMBSCOM initialization is asynchronous. The first
        init_tmbs_config() call may leave communication in
        TMBS_OPENING (3). A second initialization attempt
        is required after TMBSCOM has had time to complete
        its startup sequence.
        """
        axis_array = (ctypes.c_int * MAX_AXIS_COUNT)(
            *([-1] * MAX_AXIS_COUNT)
        )

        history = []

        # ------------------------------------------------------------
        # First initialization attempt
        # ------------------------------------------------------------
        result = self.init_tmbs_config(
            COM_PORT.encode("ascii"),
            BAUD_CODE,
            NRT,
            int(RESET),
            int(AUTOMATIC),
            axis_array,
        )

        history.append(result)

        current_state = self.communication_state()

        if current_state == 4:
            self.axes_info = list(axis_array)
            self.initialized = True
            self.refresh_connected_axes()
            return history

        # Fatal initialization errors.
        if current_state in (-12, 2):
            self.axes_info = list(axis_array)
            self.initialized = False
            return history

        # ------------------------------------------------------------
        # TMBSCOM needs time to complete the asynchronous opening.
        # The working CLI requires a separate initialization call
        # after this delay.
        # ------------------------------------------------------------
        time.sleep(5.0)

        # ------------------------------------------------------------
        # Second initialization attempt
        # ------------------------------------------------------------
        result = self.init_tmbs_config(
            COM_PORT.encode("ascii"),
            BAUD_CODE,
            NRT,
            int(RESET),
            int(AUTOMATIC),
            axis_array,
        )

        history.append(result)

        current_state = self.communication_state()

        if current_state == 4:
            self.axes_info = list(axis_array)
            self.initialized = True
            self.refresh_connected_axes()
            return history

        # ------------------------------------------------------------
        # Final polling after the second initialization attempt.
        # ------------------------------------------------------------
        POLL_DELAY = 0.005
        MAX_POLLS = 200

        for _ in range(MAX_POLLS):
            current_state = self.communication_state()

            if current_state == 4:
                self.axes_info = list(axis_array)
                self.initialized = True
                self.refresh_connected_axes()
                return history

            if current_state in (-12, 2):
                break

            time.sleep(POLL_DELAY)

        self.axes_info = list(axis_array)
        self.initialized = False

        return history


    def refresh_connected_axes(self):
        """
        Ask TMBSCOM for the actual axis information.
        """
        if not self.initialized:
            return SIO_ERROR
        axis_array = (ctypes.c_ushort * MAX_AXIS_COUNT)()
        result = self.get_axes(axis_array)
        for axis_number in AXIS_NUMBERS:
            self.axes[axis_number].connected = False
        if result == SIO_DONE:
            values = list(axis_array)
            for axis_number in AXIS_NUMBERS:
                # IMPORTANT:
                # get_axes() returns the axis map as an unsigned
                # 16-bit value in our ctypes binding.
                #
                # The controller reports:
                #     0x0000       = axis present / usable
                #     0xFFFF       = axis not present
                #
                # c_ushort converts the documented -1 value into
                # 65535, so DO NOT use "value != 0" here.
                self.axes_info[axis_number] = values[axis_number]
                self.axes[axis_number].connected = (
                    values[axis_number] == 0
                )
        return result
    # --------------------------------------------------------
    # Axis validation
    # --------------------------------------------------------
    def require_initialized(self):
        if not self.initialized:
            print("ERROR: run 'init' first.")
            return False
        return True
    def require_axis(self, axis_number):
        if axis_number not in AXIS_NUMBERS:
            print(f"ERROR: axis {axis_number:X} is outside 0..F.")
            return False
        return True
    def axis_is_connected(self, axis_number):
        if not self.require_axis(axis_number):
            return False
        return self.axes[axis_number].connected
    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------
    def read_axis_status(self, axis_number):
        """
        Read status for one axis.
        check_status() must be called before check_pfin(), because
        the TMBSCOM manual says check_pfin() uses the DLL's internal
        movement-status monitor.
        """
        if not self.require_initialized():
            return None
        if not self.require_axis(axis_number):
            return None
        if self.check_status:
            self.check_status(axis_number)
        raw_status = (ctypes.c_ubyte * 4)()
        result = self.get_status(
            axis_number,
            raw_status,
        )
        def check(dll_function):
            if dll_function is None:
                return None
            return dll_function(axis_number)
        status = {
            "axis": axis_number,
            "result": result,
            "raw": bytes(raw_status),
            "servo": check(self.check_son),
            "run": check(self.check_run),
            "alarm": check(self.check_alrm),
            "origin": check(self.check_org),
            "pfin": check(self.check_pfin),
        }
        self.last_status[axis_number] = status
        return status
    def read_all_axis_status(self):
        result = {}
        for axis_number in AXIS_NUMBERS:
            if self.axes[axis_number].connected:
                status = self.read_axis_status(axis_number)
                if status is not None:
                    result[axis_number] = status
        return result
    def axis_is_safe_to_move(self, axis_number):
        status = self.read_axis_status(axis_number)
        if status is None:
            return False, None
        if status["result"] != SIO_DONE:
            print(
                f"ERROR: status read failed for axis "
                f"{axis_number:X}."
            )
            return False, status
        if status["alarm"] == SIO_DONE:
            print(
                f"ERROR: alarm is active on axis "
                f"{axis_number:X}."
            )
            return False, status
        if status["servo"] != SIO_DONE:
            print(
                f"ERROR: servo is OFF on axis "
                f"{axis_number:X}."
            )
            return False, status
        return True, status
    # --------------------------------------------------------
    # Position readback
    # --------------------------------------------------------
    def read_controller_position(self, axis_number):
        """
        Read PNOW from the documented internal status memory.
        """
        if not self.require_initialized():
            return None, "not initialized"
        if self.read_svmem is None:
            return None, "read_svmem export not present"
        destination = ctypes.c_long(0)
        result = self.read_svmem(
            axis_number,
            PNOW_MEMORY_ADDRESS,
            ctypes.byref(destination),
        )
        if result != SIO_DONE:
            return (
                None,
                f"read_svmem returned {result}",
            )
        return int(destination.value), None
    # --------------------------------------------------------
    # Direct single-axis motion
    # --------------------------------------------------------
    def direct_move_absolute(
        self,
        axis_number,
        position,
    ):
        """
        Send an immediate absolute move to one axis.
        """
        if self.move_abs is None:
            print("ERROR: move_abs export not present.")
            return SIO_ERROR
        safe, _ = self.axis_is_safe_to_move(axis_number)
        if not safe:
            return SIO_ERROR
        result = self.move_abs(
            axis_number,
            ctypes.c_long(position),
        )
        if result == SIO_DONE:
            self.axes[
                axis_number
            ].commanded_position = position
        return result
    def direct_move_incremental(
        self,
        axis_number,
        distance,
    ):
        """
        Send an immediate incremental move to one axis.
        """
        if self.move_inc is None:
            print("ERROR: move_inc export not present.")
            return SIO_ERROR
        safe, _ = self.axis_is_safe_to_move(axis_number)
        if not safe:
            return SIO_ERROR
        result = self.move_inc(
            axis_number,
            ctypes.c_long(distance),
        )
        if result == SIO_DONE:
            old_position = self.axes[
                axis_number
            ].commanded_position
            if old_position is not None:
                self.axes[
                    axis_number
                ].commanded_position = (
                    old_position + distance
                )
        return result
    # --------------------------------------------------------
    # Prepared multi-axis motion buffer
    # --------------------------------------------------------
    def clear_motion_buffer(self):
        """
        Remove all locally prepared moves.
        No controller movement is generated.
        """
        for axis_state in self.axes.values():
            axis_state.prepared_motion = None
            axis_state.prepared_value = None
    def prepare_absolute_move(
        self,
        axis_number,
        position,
    ):
        """
        Prepare an absolute move locally.
        IMPORTANT:
        This command does NOT move the actuator.
        """
        if not self.require_initialized():
            return False
        if not self.require_axis(axis_number):
            return False
        self.axes[
            axis_number
        ].prepared_motion = "absolute"
        self.axes[
            axis_number
        ].prepared_value = position
        return True
    def prepare_incremental_move(
        self,
        axis_number,
        distance,
    ):
        """
        Prepare an incremental move locally.
        IMPORTANT:
        This command does NOT move the actuator.
        """
        if not self.require_initialized():
            return False
        if not self.require_axis(axis_number):
            return False
        self.axes[
            axis_number
        ].prepared_motion = "incremental"
        self.axes[
            axis_number
        ].prepared_value = distance
        return True
    def prepared_axes(self):
        return [
            axis_number
            for axis_number in AXIS_NUMBERS
            if self.axes[
                axis_number
            ].prepared_motion is not None
        ]
    def start_prepared_moves(self):
        """
        Execute all prepared moves.
        IMPORTANT:
        This is the v13 fallback implementation using the
        documented TMBSCOM DLL movement functions.
        It dispatches each prepared move rapidly in sequence.
        It does NOT claim hardware-level synchronization.
        True synchronized execution will be added when the
        documented Termi-BUS h/t buffering path is connected.
        """
        axes_to_move = self.prepared_axes()
        if not axes_to_move:
            print("ERROR: no prepared moves.")
            return False
        # Safety preflight BEFORE any physical movement.
        for axis_number in axes_to_move:
            safe, _ = self.axis_is_safe_to_move(axis_number)
            if not safe:
                print(
                    "START ABORTED: preflight failed for "
                    f"axis {axis_number:X}."
                )
                return False
        print("\n## STARTING PREPARED MULTI-AXIS MOVE")
        print("------------------------------------")
        print("Execution method: TMBSCOM DLL rapid dispatch")
        print("Synchronization: NOT hardware-synchronized in v13")
        print()
        all_accepted = True
        for axis_number in axes_to_move:
            axis_state = self.axes[axis_number]
            if axis_state.prepared_motion == "absolute":
                result = self.move_abs(
                    axis_number,
                    ctypes.c_long(
                        axis_state.prepared_value
                    ),
                )
                print(
                    f"axis {axis_name(axis_number)}: "
                    f"move_abs({axis_state.prepared_value}) "
                    f"-> {result}"
                )
                if result == SIO_DONE:
                    axis_state.commanded_position = (
                        axis_state.prepared_value
                    )
            elif axis_state.prepared_motion == "incremental":
                result = self.move_inc(
                    axis_number,
                    ctypes.c_long(
                        axis_state.prepared_value
                    ),
                )
                print(
                    f"axis {axis_name(axis_number)}: "
                    f"move_inc({axis_state.prepared_value}) "
                    f"-> {result}"
                )
                if result == SIO_DONE:
                    if axis_state.commanded_position is not None:
                        axis_state.commanded_position += (
                            axis_state.prepared_value
                        )
            else:
                print(
                    f"ERROR: unknown prepared operation on "
                    f"axis {axis_number:X}."
                )
                result = SIO_ERROR
            if result != SIO_DONE:
                all_accepted = False
                print(
                    f"ERROR: axis {axis_number:X} did not "
                    "accept its movement."
                )
                break
        return all_accepted
    # --------------------------------------------------------
    # Wait for all axes
    # --------------------------------------------------------
    def wait_for_prepared_axes(
        self,
        timeout=30.0,
        interval=0.05,
    ):
        """
        Monitor all axes that were part of the prepared move.
        Completion requires:
            PFIN = 1 on every participating axis
        Any ALARM immediately fails the operation.
        """
        axes_to_monitor = self.prepared_axes()
        if not axes_to_monitor:
            print("ERROR: no prepared axes to monitor.")
            return False
        print("\n## MONITORING PREPARED AXES")
        print("---------------------------")
        start_time = time.monotonic()
        while (
            time.monotonic() - start_time
            < timeout
        ):
            all_finished = True
            for axis_number in axes_to_monitor:
                status = self.read_axis_status(axis_number)
                if status is None:
                    return False
                print(
                    f"{datetime.now():%H:%M:%S} "
                    f"axis={axis_name(axis_number)} "
                    f"run={status['run']} "
                    f"alarm={status['alarm']} "
                    f"pfin={status['pfin']} "
                    f"raw={raw_hex(status['raw'])}"
                )
                if status["alarm"] == SIO_DONE:
                    print(
                        f"ALARM detected on axis "
                        f"{axis_name(axis_number)}."
                    )
                    return False
                if status["pfin"] != SIO_DONE:
                    all_finished = False
            if all_finished:
                print("\nALL PREPARED AXES REPORT PFIN=1.")
                return True
            time.sleep(interval)
        print(
            f"\nTIMEOUT: not all axes reached PFIN=1 "
            f"within {timeout:.1f} seconds."
        )
        return False
