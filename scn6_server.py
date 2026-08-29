
"""
SCN6 TCP server for CyrilPec/Snc6.

Protocol:
    One JSON object per line, one JSON response per line.

Example:
    {"cmd":"init"}
    {"cmd":"axes"}
    {"cmd":"status","axis":0}
    {"cmd":"position","axis":0}
    {"cmd":"move_abs","axis":0,"position":10000,"confirm":true}
    {"cmd":"move_inc","axis":0,"distance":1000,"confirm":true}
    {"cmd":"servo_on","axis":0,"confirm":true}
    {"cmd":"servo_off","axis":0,"confirm":true}
    {"cmd":"reset_alarm","axis":0,"confirm":true}

Server:
    127.0.0.1:8765

IMPORTANT:
    The CyrilPec SCN6 driver currently requires 32-bit Python and
    Tmbscom.DLL on Windows.
"""

from __future__ import annotations

import json
import socket
import threading
import traceback
from typing import Any

from scn6_driver import SCN6Driver


# ============================================================
# Configuration
# ============================================================

HOST = "127.0.0.1"
PORT = 8765

# Require explicit confirmation for anything that can physically
# move or change the actuator state.
REQUIRE_CONFIRM = True

# Only one SCN6 operation should execute at a time.
# This protects the DLL/controller from simultaneous commands
# coming from Factorio and SimulIDE.
DRIVER_LOCK = threading.RLock()


# ============================================================
# Helpers
# ============================================================

def json_safe(value: Any) -> Any:
    """
    Convert SCN6/DLL return values into JSON-compatible values.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, bytes):
        return value.hex(" ")

    if isinstance(value, bytearray):
        return bytes(value).hex(" ")

    if isinstance(value, dict):
        return {
            str(k): json_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            json_safe(v)
            for v in value
        ]

    # ctypes values
    if hasattr(value, "value"):
        try:
            return json_safe(value.value)
        except Exception:
            pass

    return str(value)


def ok(**data):
    return {
        "ok": True,
        **data,
    }


def error(message, **data):
    return {
        "ok": False,
        "error": message,
        **data,
    }


def require_confirm(command: dict) -> None:
    """
    Raise an exception if physical/state-changing operation
    does not contain confirm=true.
    """

    if not REQUIRE_CONFIRM:
        return

    if command.get("confirm") is not True:
        raise ValueError(
            "This command requires \"confirm\": true"
        )


def get_axis(command: dict) -> int:
    """
    Parse axis number.

    Accepts:
        0
        1
        15
        "A"
        "F"
    """

    if "axis" not in command:
        raise ValueError("missing axis")

    axis = command["axis"]

    if isinstance(axis, str):
        axis = axis.strip().upper()

        if len(axis) == 1 and axis in "0123456789ABCDEF":
            axis = int(axis, 16)
        else:
            axis = int(axis, 0)

    axis = int(axis)

    if not 0 <= axis <= 15:
        raise ValueError("axis must be between 0 and 15")

    return axis


# ============================================================
# SCN6 server
# ============================================================

class SCN6Server:

    def __init__(self):
        self.driver: SCN6Driver | None = None
        self.initialized = False

    # --------------------------------------------------------
    # Driver
    # --------------------------------------------------------

    def ensure_driver(self):
        if self.driver is None:
            print("Loading SCN6 driver...")
            self.driver = SCN6Driver()

        return self.driver

    def cmd_init(self):
        driver = self.ensure_driver()

        with DRIVER_LOCK:
            history = driver.initialize()

            self.initialized = bool(driver.initialized)

            axes = [
                axis
                for axis, state in driver.axes.items()
                if state.connected
            ]

        return ok(
            initialized=self.initialized,
            axes=axes,
            initialization_history=history,
        )

    def require_initialized(self):
        if not self.initialized or self.driver is None:
            raise RuntimeError(
                "SCN6 is not initialized. Send {\"cmd\":\"init\"} first."
            )

        return self.driver

    # --------------------------------------------------------
    # Information
    # --------------------------------------------------------

    def cmd_axes(self):
        driver = self.require_initialized()

        with DRIVER_LOCK:
            driver.refresh_connected_axes()

            axes = [
                axis
                for axis, state in driver.axes.items()
                if state.connected
            ]

        return ok(
            axes=axes,
            axes_hex=[
                format(axis, "X")
                for axis in axes
            ],
        )

    def cmd_status(self, command):
        driver = self.require_initialized()
        axis = get_axis(command)

        with DRIVER_LOCK:
            status = driver.axis_status(axis)

        return ok(
            axis=axis,
            status=json_safe(status),
        )

    def cmd_all_status(self):
        driver = self.require_initialized()

        with DRIVER_LOCK:
            status = driver.read_all_axis_status()

        return ok(
            status=json_safe(status),
        )

    def cmd_position(self, command):
        driver = self.require_initialized()
        axis = get_axis(command)

        with DRIVER_LOCK:
            position, err = driver.axis_position(axis)

        if err:
            return error(
                err,
                axis=axis,
            )

        return ok(
            axis=axis,
            position=position,
        )

    # --------------------------------------------------------
    # Motion
    # --------------------------------------------------------

    def cmd_move_abs(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if "position" not in command:
            raise ValueError("missing position")

        position = int(command["position"])

        with DRIVER_LOCK:
            result = driver.direct_move_absolute(
                axis,
                position,
            )

        return ok(
            axis=axis,
            position=position,
            result=json_safe(result),
        )

    def cmd_move_inc(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if "distance" not in command:
            raise ValueError("missing distance")

        distance = int(command["distance"])

        with DRIVER_LOCK:
            result = driver.direct_move_incremental(
                axis,
                distance,
            )

        return ok(
            axis=axis,
            distance=distance,
            result=json_safe(result),
        )

    # --------------------------------------------------------
    # Prepared multi-axis motion
    # --------------------------------------------------------

    def cmd_prepare_abs(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if "position" not in command:
            raise ValueError("missing position")

        position = int(command["position"])

        with DRIVER_LOCK:
            result = driver.prepare_absolute(
                axis,
                position,
            )

        return ok(
            axis=axis,
            position=position,
            prepared=bool(result),
        )

    def cmd_prepare_inc(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if "distance" not in command:
            raise ValueError("missing distance")

        distance = int(command["distance"])

        with DRIVER_LOCK:
            result = driver.prepare_incremental(
                axis,
                distance,
            )

        return ok(
            axis=axis,
            distance=distance,
            prepared=bool(result),
        )

    def cmd_prepared(self):
        driver = self.require_initialized()

        with DRIVER_LOCK:
            axes = driver.prepared_axes()

        return ok(
            axes=axes,
        )

    def cmd_clear_buffer(self):
        require_confirm(command={})

        driver = self.require_initialized()

        with DRIVER_LOCK:
            driver.clear_motion_buffer()

        return ok(
            cleared=True,
        )

    def cmd_start(self, command):
        require_confirm(command)

        driver = self.require_initialized()

        with DRIVER_LOCK:
            result = driver.execute_prepared()

        return ok(
            started=bool(result),
            result=json_safe(result),
        )

    def cmd_wait(self, command):
        driver = self.require_initialized()

        timeout = float(
            command.get("timeout", 30.0)
        )

        interval = float(
            command.get("interval", 0.05)
        )

        with DRIVER_LOCK:
            result = driver.wait_for_prepared_axes(
                timeout=timeout,
                interval=interval,
            )

        return ok(
            finished=bool(result),
        )

    # --------------------------------------------------------
    # Servo
    # --------------------------------------------------------

    def cmd_servo_on(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if driver.set_son is None:
            raise RuntimeError(
                "set_son is not available in Tmbscom.DLL"
            )

        with DRIVER_LOCK:
            result = driver.set_son(axis)

        return ok(
            axis=axis,
            result=json_safe(result),
        )

    def cmd_servo_off(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if driver.set_soff is None:
            raise RuntimeError(
                "set_soff is not available in Tmbscom.DLL"
            )

        with DRIVER_LOCK:
            result = driver.set_soff(axis)

        return ok(
            axis=axis,
            result=json_safe(result),
        )

    # --------------------------------------------------------
    # Alarm
    # --------------------------------------------------------

    def cmd_reset_alarm(self, command):
        require_confirm(command)

        driver = self.require_initialized()
        axis = get_axis(command)

        if driver.reset_alarm is None:
            raise RuntimeError(
                "reset_alarm is not available in Tmbscom.DLL"
            )

        with DRIVER_LOCK:
            result = driver.reset_alarm(axis)

        return ok(
            axis=axis,
            result=json_safe(result),
        )

    # --------------------------------------------------------
    # Communication
    # --------------------------------------------------------

    def cmd_communication_state(self):
        driver = self.ensure_driver()

        with DRIVER_LOCK:
            state = driver.communication_state()

        return ok(
            state=state,
        )

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    def cmd_shutdown(self):
        print("Shutdown requested.")

        if self.driver is not None:
            with DRIVER_LOCK:
                try:
                    self.driver.close_tmbs()
                except Exception:
                    traceback.print_exc()

        self.initialized = False

        return ok(
            shutdown=True,
        )

    # --------------------------------------------------------
    # Command dispatcher
    # --------------------------------------------------------

    def execute(self, command: dict):

        if not isinstance(command, dict):
            raise ValueError(
                "command must be a JSON object"
            )

        cmd = command.get("cmd")

        if not cmd:
            raise ValueError("missing cmd")

        cmd = str(cmd).lower()

        commands = {
            "init": self.cmd_init,
            "axes": self.cmd_axes,
            "status": self.cmd_status,
            "all_status": self.cmd_all_status,
            "position": self.cmd_position,

            "move_abs": self.cmd_move_abs,
            "move_inc": self.cmd_move_inc,

            "prepare_abs": self.cmd_prepare_abs,
            "prepare_inc": self.cmd_prepare_inc,
            "prepared": self.cmd_prepared,
            "clear_buffer": self.cmd_clear_buffer,
            "start": self.cmd_start,
            "wait": self.cmd_wait,

            "servo_on": self.cmd_servo_on,
            "servo_off": self.cmd_servo_off,

            "reset_alarm": self.cmd_reset_alarm,

            "communication_state":
                self.cmd_communication_state,

            "shutdown": self.cmd_shutdown,
        }

        handler = commands.get(cmd)

        if handler is None:
            raise ValueError(
                f"unknown command: {cmd}"
            )

        return handler(command)


# ============================================================
# TCP client handler
# ============================================================

def handle_client(
    connection: socket.socket,
    address,
    server: SCN6Server,
):
    print(f"Client connected: {address}")

    try:
        connection.settimeout(None)

        buffer = b""

        while True:

            data = connection.recv(4096)

            if not data:
                break

            buffer += data

            while b"\n" in buffer:

                raw, buffer = buffer.split(
                    b"\n",
                    1,
                )

                raw = raw.strip()

                if not raw:
                    continue

                try:
                    command = json.loads(
                        raw.decode("utf-8")
                    )

                    print(
                        f"[{address}] "
                        f"{command}"
                    )

                    result = server.execute(
                        command
                    )

                except Exception as exc:

                    print(
                        f"ERROR from {address}: "
                        f"{exc}"
                    )

                    traceback.print_exc()

                    result = error(
                        str(exc)
                    )

                response = (
                    json.dumps(
                        json_safe(result),
                        separators=(",", ":"),
                    )
                    + "\n"
                )

                connection.sendall(
                    response.encode("utf-8")
                )

                if (
                    isinstance(command, dict)
                    and command.get("cmd") == "shutdown"
                ):
                    return

    except ConnectionResetError:
        print(
            f"Client disconnected: {address}"
        )

    except Exception:
        traceback.print_exc()

    finally:
        try:
            connection.close()
        except Exception:
            pass

        print(
            f"Client closed: {address}"
        )


# ============================================================
# Server main loop
# ============================================================

def main():

    print()
    print("====================================")
    print("        SCN6 TCP SERVER")
    print("====================================")
    print()
    print(f"Listening on {HOST}:{PORT}")
    print("Protocol: JSON lines")
    print()
    print("Start with:")
    print('  {"cmd":"init"}')
    print()
    print("Motion requires:")
    print('  "confirm":true')
    print()

    server = SCN6Server()

    tcp = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    tcp.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    tcp.bind(
        (HOST, PORT)
    )

    tcp.listen(8)

    print(
        f"Server ready on "
        f"{HOST}:{PORT}"
    )

    try:

        while True:

            connection, address = tcp.accept()

            thread = threading.Thread(
                target=handle_client,
                args=(
                    connection,
                    address,
                    server,
                ),
                daemon=True,
            )

            thread.start()

    except KeyboardInterrupt:

        print()
        print("Ctrl+C received.")

    finally:

        try:
            tcp.close()
        except Exception:
            pass

        if server.driver is not None:

            with DRIVER_LOCK:

                try:
                    server.driver.close_tmbs()
                except Exception:
                    traceback.print_exc()

        print("SCN6 server stopped.")


if __name__ == "__main__":
    main()
