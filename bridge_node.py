"""
bridge_node.py

Blender-side bridge for SCN6.

Purpose
-------
Runs inside Blender's normal 64-bit Python environment and manages
one shared 32-bit scn6_server.py process.

Architecture:

    Blender 64-bit
          |
          | bridge_node.py
          |
          | JSON Lines
          v
    scn6_server.py
       32-bit Python
          |
          v
    scn6_driver.py
          |
          v
    scn6_dll.py
          |
          v
    Tmbscom.DLL
          |
          v
       SCN6


IMPORTANT
---------
This module does NOT talk to Tmbscom.DLL directly.

It only manages the 32-bit SCN6 server process.

All SCN6 Axis nodes share this single bridge.


Commands supported by scn6_server.py:

    ping
    connect
    disconnect
    axes
    axis_info
    position
    status
    move
    move_inc
    clear
    prepare_abs
    prepare_inc
    prepared_axes
    execute
    wait
    stop
    exit
"""

from __future__ import annotations

import bpy

import json
import os
import queue
import subprocess
import threading
import time


# ============================================================================
# CONFIGURATION
# ============================================================================

# ---------------------------------------------------------------------------
# 32-bit Python used to run scn6_server.py
# ---------------------------------------------------------------------------

SCN6_PYTHON = r"C:\Users\DarkLight\AppData\Local\Programs\Python\Python312-32\python.exe"


# ---------------------------------------------------------------------------
# Location of scn6_server.py
# ---------------------------------------------------------------------------

SCN6_SERVER = r"C:\SCN6\scn6_server.py"


# ---------------------------------------------------------------------------
# Communication interval
#
# 0.05 = 20 Hz
# ---------------------------------------------------------------------------

BRIDGE_RATE = 0.05


# ============================================================================
# BRIDGE
# ============================================================================

class SCN6Bridge:
    """
    Singleton-style bridge.

    There must only be ONE instance/process for the entire Blender session.

    SCN6 nodes do NOT create their own processes.

    Example:

        SCN6 Axis 0
        SCN6 Axis 1
        SCN6 Axis 2
        SCN6 Axis 3

    all use:

        SCN6Bridge.instance()
    """

    _instance = None

    # ----------------------------------------------------------------------
    # Singleton
    # ----------------------------------------------------------------------

    @classmethod
    def instance(cls):

        if cls._instance is None:

            cls._instance = cls()

        return cls._instance

    # ----------------------------------------------------------------------
    # Constructor
    # ----------------------------------------------------------------------

    def __init__(self):

        self.process = None

        self.reader_thread = None

        self.stderr_thread = None

        self.response_queue = queue.Queue()

        self.pending_requests = {}

        self.request_id = 0

        self.lock = threading.RLock()

        self.running = False

        self.connected = False

        self.server_connected = False

        self.last_error = ""

        self.last_start_time = 0.0

        # --------------------------------------------------------------
        # Axis state
        #
        # Example:
        #
        # {
        #     0: {
        #         "position": 1234,
        #         "error": 0,
        #         "status": ...
        #     }
        # }
        # --------------------------------------------------------------

        self.axis_states = {}

        # --------------------------------------------------------------
        # Axes currently used by Blender nodes.
        # --------------------------------------------------------------

        self.active_axes = set()

        # --------------------------------------------------------------
        # Latest desired command per axis.
        #
        # Only the newest command is retained.
        # --------------------------------------------------------------

        self.command_queue = {}

    # ======================================================================
    # LOGGING
    # ======================================================================

    def log(self, message):

        print(
            "[SCN6 BRIDGE] "
            + str(message)
        )

    # ======================================================================
    # NEXT REQUEST ID
    # ======================================================================

    def next_request_id(self):

        with self.lock:

            self.request_id += 1

            return self.request_id

    # ======================================================================
    # START SERVER
    # ======================================================================

    def start(self):

        with self.lock:

            # Already running.

            if self.process is not None:

                if self.process.poll() is None:

                    return True

                self.process = None

            # Validate Python executable.

            if not os.path.isfile(
                SCN6_PYTHON
            ):

                self.last_error = (
                    "32-bit Python not found: "
                    + SCN6_PYTHON
                )

                self.log(
                    self.last_error
                )

                return False

            # Validate server.

            if not os.path.isfile(
                SCN6_SERVER
            ):

                self.last_error = (
                    "scn6_server.py not found: "
                    + SCN6_SERVER
                )

                self.log(
                    self.last_error
                )

                return False

            try:

                self.process = subprocess.Popen(

                    [
                        SCN6_PYTHON,
                        SCN6_SERVER,
                    ],

                    stdin=subprocess.PIPE,

                    stdout=subprocess.PIPE,

                    stderr=subprocess.PIPE,

                    text=True,

                    bufsize=1,

                    universal_newlines=True,
                )

            except Exception as exc:

                self.last_error = str(
                    exc
                )

                self.log(
                    "Failed to start server: "
                    + self.last_error
                )

                self.process = None

                return False

            self.running = True

            self.last_start_time = (
                time.time()
            )

            # ----------------------------------------------------------
            # stdout reader
            # ----------------------------------------------------------

            self.reader_thread = (
                threading.Thread(
                    target=self._stdout_reader,
                    daemon=True,
                    name="SCN6-stdout",
                )
            )

            self.reader_thread.start()

            # ----------------------------------------------------------
            # stderr reader
            # ----------------------------------------------------------

            self.stderr_thread = (
                threading.Thread(
                    target=self._stderr_reader,
                    daemon=True,
                    name="SCN6-stderr",
                )
            )

            self.stderr_thread.start()

            self.log(
                "scn6_server.py started."
            )

            return True

    # ======================================================================
    # STDOUT READER
    # ======================================================================

    def _stdout_reader(self):

        process = self.process

        if process is None:
            return

        try:

            while True:

                line = process.stdout.readline()

                if not line:
                    break

                line = line.strip()

                if not line:
                    continue

                try:

                    response = json.loads(
                        line
                    )

                    self.response_queue.put(
                        response
                    )

                except Exception as exc:

                    self.log(
                        "Invalid server JSON: "
                        + str(exc)
                    )

        except Exception as exc:

            self.log(
                "stdout reader stopped: "
                + str(exc)
            )

        self.running = False

    # ======================================================================
    # STDERR READER
    # ======================================================================

    def _stderr_reader(self):

        process = self.process

        if process is None:
            return

        try:

            while True:

                line = process.stderr.readline()

                if not line:
                    break

                line = line.strip()

                if line:

                    self.log(
                        "SERVER: "
                        + line
                    )

        except Exception:
            pass

    # ======================================================================
    # SEND REQUEST
    # ======================================================================

    def send(
        self,
        command,
    ):
        """
        Send one JSON command to scn6_server.py.

        Returns request ID.
        """

        if not self.start():

            return None

        request_id = (
            self.next_request_id()
        )

        command = dict(
            command
        )

        command["id"] = request_id

        try:

            line = json.dumps(
                command,
                separators=(",", ":"),
            )

            with self.lock:

                self.process.stdin.write(
                    line + "\n"
                )

                self.process.stdin.flush()

            return request_id

        except Exception as exc:

            self.last_error = str(
                exc
            )

            self.log(
                "Send failed: "
                + self.last_error
            )

            self.running = False

            return None

    # ======================================================================
    # PROCESS RESPONSES
    # ======================================================================

    def process_responses(self):

        while True:

            try:

                response = (
                    self.response_queue
                    .get_nowait()
                )

            except queue.Empty:

                break

            self._handle_response(
                response
            )

    # ======================================================================
    # RESPONSE HANDLER
    # ======================================================================

    def _handle_response(
        self,
        response,
    ):

        request_id = response.get(
            "id"
        )

        if not response.get(
            "ok",
            False,
        ):

            error = response.get(
                "error",
                "Unknown SCN6 error.",
            )

            self.last_error = str(
                error
            )

            self.log(
                "Server error: "
                + self.last_error
            )

            return

        result = response.get(
            "result"
        )

        # --------------------------------------------------------------
        # Position response
        # --------------------------------------------------------------

        if isinstance(
            result,
            dict,
        ):

            if (
                "axis" in result
                and "position" in result
            ):

                axis = int(
                    result["axis"]
                )

                self.axis_states[
                    axis
                ] = {
                    "position": float(
                        result["position"]
                    ),

                    "error": result.get(
                        "error"
                    ),

                    "updated": time.time(),
                }

        # --------------------------------------------------------------
        # Connect response
        # --------------------------------------------------------------

        if isinstance(
            result,
            dict,
        ):

            if result.get(
                "connected"
            ) is True:

                self.server_connected = True

                self.connected = True

    # ======================================================================
    # CONNECT
    # ======================================================================

    def connect(self):

        request_id = self.send({
            "cmd": "connect",
        })

        return request_id is not None

    # ======================================================================
    # DISCONNECT
    # ======================================================================

    def disconnect(self):

        self.server_connected = False
        self.connected = False

        self.send({
            "cmd": "disconnect",
        })

    # ======================================================================
    # PING
    # ======================================================================

    def ping(self):

        return self.send({
            "cmd": "ping",
        })

    # ======================================================================
    # GET AXES
    # ======================================================================

    def axes(self):

        return self.send({
            "cmd": "axes",
        })

    # ======================================================================
    # GET POSITION
    # ======================================================================

    def request_position(
        self,
        axis,
    ):

        axis = int(axis)

        self.active_axes.add(
            axis
        )

        return self.send({
            "cmd": "position",
            "axis": axis,
        })

    # ======================================================================
    # GET CACHED POSITION
    # ======================================================================

    def get_position(
        self,
        axis,
    ):

        axis = int(axis)

        state = (
            self.axis_states.get(
                axis
            )
        )

        if state is None:

            return 0.0

        return float(
            state.get(
                "position",
                0.0,
            )
        )

    # ======================================================================
    # GET ERROR
    # ======================================================================

    def get_position_error(
        self,
        axis,
    ):

        axis = int(axis)

        state = (
            self.axis_states.get(
                axis
            )
        )

        if state is None:

            return None

        return state.get(
            "error"
        )

    # ======================================================================
    # QUEUE MOVE
    # ======================================================================

    def queue_move(
        self,
        axis,
        position,
    ):
        """
        Queue latest desired position.

        Multiple Blender nodes can call this.

        Example:

            Axis 0 -> 10000
            Axis 1 -> 12000
            Axis 2 -> 11500

        Only the latest command for each axis is kept.
        """

        axis = int(axis)

        position = float(
            position
        )

        self.active_axes.add(
            axis
        )

        self.command_queue[
            axis
        ] = position

    # ======================================================================
    # SEND QUEUED MOVES
    # ======================================================================

    def flush_moves(self):

        if not self.command_queue:
            return

        commands = list(
            self.command_queue.items()
        )

        self.command_queue.clear()

        for axis, position in commands:

            self.send({
                "cmd": "move",

                "axis": axis,

                "position": position,
            })

    # ======================================================================
    # INCREMENTAL MOVE
    # ======================================================================

    def move_incremental(
        self,
        axis,
        distance,
    ):

        return self.send({

            "cmd": "move_inc",

            "axis": int(axis),

            "distance": float(
                distance
            ),
        })

    # ======================================================================
    # PREPARE ABSOLUTE
    # ======================================================================

    def prepare_absolute(
        self,
        axis,
        position,
    ):

        return self.send({

            "cmd": "prepare_abs",

            "axis": int(axis),

            "position": float(
                position
            ),
        })

    # ======================================================================
    # PREPARE INCREMENTAL
    # ======================================================================

    def prepare_incremental(
        self,
        axis,
        distance,
    ):

        return self.send({

            "cmd": "prepare_inc",

            "axis": int(axis),

            "distance": float(
                distance
            ),
        })

    # ======================================================================
    # CLEAR PREPARED
    # ======================================================================

    def clear_prepared(self):

        return self.send({
            "cmd": "clear",
        })

    # ======================================================================
    # EXECUTE PREPARED
    # ======================================================================

    def execute_prepared(self):

        return self.send({
            "cmd": "execute",
        })

    # ======================================================================
    # WAIT
    # ======================================================================

    def wait(
        self,
        timeout=30.0,
        interval=0.05,
    ):

        return self.send({

            "cmd": "wait",

            "timeout": float(
                timeout
            ),

            "interval": float(
                interval
            ),
        })

    # ======================================================================
    # STOP
    # ======================================================================

    def stop(self):

        self.command_queue.clear()

        return self.send({
            "cmd": "stop",
        })

    # ======================================================================
    # SHUTDOWN
    # ======================================================================

    def shutdown(self):

        self.command_queue.clear()

        process = self.process

        if process is None:
            return

        self.log(
            "Stopping SCN6 bridge."
        )

        try:

            self.send({
                "cmd": "disconnect",
            })

            time.sleep(0.05)

            self.send({
                "cmd": "exit",
            })

        except Exception:
            pass

        try:

            process.terminate()

        except Exception:
            pass

        self.process = None

        self.running = False

        self.connected = False

        self.server_connected = False


# ============================================================================
# GLOBAL ACCESS
# ============================================================================

def get_bridge():

    return SCN6Bridge.instance()


# ============================================================================
# BLENDER TIMER
# ============================================================================

def scn6_bridge_timer():

    bridge = get_bridge()

    try:

        # --------------------------------------------------------------
        # 1. Process responses from server.
        # --------------------------------------------------------------

        bridge.process_responses()

        # --------------------------------------------------------------
        # 2. Send latest commands.
        # --------------------------------------------------------------

        bridge.flush_moves()

        # --------------------------------------------------------------
        # 3. Poll actual position for active axes.
        # --------------------------------------------------------------

        if bridge.running:

            for axis in list(
                bridge.active_axes
            ):

                bridge.request_position(
                    axis
                )

    except Exception as exc:

        bridge.log(
            "Timer error: "
            + str(exc)
        )

    return BRIDGE_RATE


# ============================================================================
# BLENDER OPERATORS
# ============================================================================

class SCN6_OT_StartBridge(
    bpy.types.Operator
):

    bl_idname = "scn6.start_bridge"

    bl_label = "Start SCN6 Bridge"

    bl_description = (
        "Start the 32-bit SCN6 bridge"
    )

    def execute(
        self,
        context,
    ):

        bridge = get_bridge()

        if bridge.start():

            self.report(
                {"INFO"},
                "SCN6 bridge started.",
            )

        else:

            self.report(
                {"ERROR"},
                bridge.last_error,
            )

        return {"FINISHED"}


class SCN6_OT_Connect(
    bpy.types.Operator
):

    bl_idname = "scn6.connect"

    bl_label = "Connect SCN6"

    bl_description = (
        "Initialize TMBSCOM and connect SCN6"
    )

    def execute(
        self,
        context,
    ):

        bridge = get_bridge()

        if bridge.connect():

            self.report(
                {"INFO"},
                "SCN6 connect command sent.",
            )

        else:

            self.report(
                {"ERROR"},
                bridge.last_error,
            )

        return {"FINISHED"}


class SCN6_OT_Disconnect(
    bpy.types.Operator
):

    bl_idname = "scn6.disconnect"

    bl_label = "Disconnect SCN6"

    def execute(
        self,
        context,
    ):

        bridge = get_bridge()

        bridge.disconnect()

        self.report(
            {"INFO"},
            "SCN6 disconnect command sent.",
        )

        return {"FINISHED"}


class SCN6_OT_Stop(
    bpy.types.Operator
):

    bl_idname = "scn6.stop"

    bl_label = "STOP SCN6"

    bl_description = (
        "Stop SCN6 motion"
    )

    def execute(
        self,
        context,
    ):

        bridge = get_bridge()

        bridge.stop()

        self.report(
            {"WARNING"},
            "SCN6 stop command sent.",
        )

        return {"FINISHED"}


# ============================================================================
# UI PANEL
# ============================================================================

class SCN6_PT_Bridge(
    bpy.types.Panel
):

    bl_label = "SCN6 Bridge"

    bl_idname = "SCN6_PT_Bridge"

    bl_space_type = "NODE_EDITOR"

    bl_region_type = "UI"

    bl_category = "SCN6"

    def draw(
        self,
        context,
    ):

        layout = self.layout

        bridge = get_bridge()

        # --------------------------------------------------------------
        # Server state
        # --------------------------------------------------------------

        if bridge.running:

            layout.label(
                text="Bridge running",
                icon="CHECKMARK",
            )

        else:

            layout.label(
                text="Bridge offline",
                icon="ERROR",
            )

        # --------------------------------------------------------------
        # Connection state
        # --------------------------------------------------------------

        if bridge.connected:

            layout.label(
                text="SCN6 connected",
                icon="LINKED",
            )

        else:

            layout.label(
                text="SCN6 disconnected",
                icon="UNLINKED",
            )

        layout.separator()

        # --------------------------------------------------------------
        # Buttons
        # --------------------------------------------------------------

        row = layout.row()

        row.operator(
            "scn6.start_bridge",
            icon="PLAY",
        )

        row.operator(
            "scn6.connect",
            icon="LINKED",
        )

        row = layout.row()

        row.operator(
            "scn6.disconnect",
            icon="UNLINKED",
        )

        row.operator(
            "scn6.stop",
            icon="CANCEL",
        )

        # --------------------------------------------------------------
        # Active axes
        # --------------------------------------------------------------

        layout.separator()

        layout.label(
            text="Active axes:"
        )

        if bridge.active_axes:

            for axis in sorted(
                bridge.active_axes
            ):

                position = (
                    bridge.get_position(
                        axis
                    )
                )

                row = layout.row()

                row.label(
                    text=(
                        f"Axis {axis}: "
                        f"{position:.3f}"
                    )
                )

        else:

            layout.label(
                text="No axes"
            )

        # --------------------------------------------------------------
        # Error
        # --------------------------------------------------------------

        if bridge.last_error:

            layout.separator()

            box = layout.box()

            box.label(
                text="Last error:",
                icon="ERROR",
            )

            box.label(
                text=bridge.last_error
            )


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (

    SCN6_OT_StartBridge,

    SCN6_OT_Connect,

    SCN6_OT_Disconnect,

    SCN6_OT_Stop,

    SCN6_PT_Bridge,
)


def register():

    for cls in classes:

        bpy.utils.register_class(
            cls
        )

    # Start timer.

    if not bpy.app.timers.is_registered(
        scn6_bridge_timer
    ):

        bpy.app.timers.register(

            scn6_bridge_timer,

            first_interval=BRIDGE_RATE,

            persistent=False,
        )

    print(
        "[SCN6] bridge_node.py registered."
    )


def unregister():

    # Stop timer.

    if bpy.app.timers.is_registered(
        scn6_bridge_timer
    ):

        bpy.app.timers.unregister(
            scn6_bridge_timer
        )

    # Shutdown bridge.

    try:

        bridge = get_bridge()

        bridge.shutdown()

    except Exception:
        pass

    # Unregister Blender classes.

    for cls in reversed(
        classes
    ):

        bpy.utils.unregister_class(
            cls
        )

    print(
        "[SCN6] bridge_node.py unregistered."
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    register()
