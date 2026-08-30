"""
scn6_server.py

32-bit Python bridge between Blender and CyrilPec/Snc6.

Blender (64-bit)
      |
      | JSON Lines via stdin/stdout
      v
scn6_server.py (32-bit Python)
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
SCN6 actuator

Protocol examples:

    {"id":1,"cmd":"ping"}

    {"id":2,"cmd":"connect"}

    {"id":3,"cmd":"axes"}

    {"id":4,"cmd":"position","axis":0}

    {"id":5,"cmd":"status","axis":0}

    {"id":6,"cmd":"move","axis":0,"position":10000}

    {"id":7,"cmd":"prepare_abs","axis":0,"position":10000}

    {"id":8,"cmd":"prepare_abs","axis":1,"position":12000}

    {"id":9,"cmd":"execute"}

    {"id":10,"cmd":"stop"}

    {"id":11,"cmd":"disconnect"}

IMPORTANT:

- This file must run under 32-bit Python.
- scn6_driver.py and scn6_dll.py should be importable.
- Tmbscom.DLL should be where scn6_dll.py expects it.
- stdout is ONLY the JSON protocol.
- diagnostics go to stderr.
"""

from __future__ import annotations

import json
import sys
import traceback


# ---------------------------------------------------------------------------
# Import Cyril's existing driver
# ---------------------------------------------------------------------------

try:
    from scn6_driver import SCN6Driver
except Exception as exc:
    SCN6Driver = None
    IMPORT_ERROR = str(exc)


class SCN6Bridge:
    """
    Thin wrapper around Cyril's existing SCN6Driver.

    We deliberately do NOT duplicate the TMBSCOM logic here.
    """

    def __init__(self):
        self.driver = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self):
        if self.driver is not None:
            if getattr(self.driver, "initialized", False):
                return {
                    "connected": True,
                    "already_connected": True,
                }

        if SCN6Driver is None:
            raise RuntimeError(
                "Could not import scn6_driver.py: "
                + IMPORT_ERROR
            )

        self.driver = SCN6Driver()

        # Cyril's TmbsController performs actual TMBSCOM
        # initialization here.
        history = self.driver.initialize()

        initialized = bool(
            getattr(self.driver, "initialized", False)
        )

        if not initialized:
            # Communication state is useful for diagnosing
            # COM/TMBSCOM initialization problems.
            try:
                state = self.driver.communication_state()
            except Exception:
                state = None

            raise RuntimeError(
                f"TMBSCOM initialization failed "
                f"(state={state}, history={history})"
            )

        return {
            "connected": True,
            "already_connected": False,
            "communication_state": self.driver.communication_state(),
            "axes": self.connected_axes(),
            "initialization_history": history,
        }

    def disconnect(self):
        if self.driver is None:
            return {
                "connected": False,
                "already_disconnected": True,
            }

        try:
            # TmbsController binds close_tmbs directly from the DLL.
            close_tmbs = getattr(
                self.driver,
                "close_tmbs",
                None,
            )

            result = None

            if callable(close_tmbs):
                result = close_tmbs()

        finally:
            self.driver = None

        return {
            "connected": False,
            "result": result,
        }

    def require_driver(self):
        if self.driver is None:
            raise RuntimeError("SCN6 driver is not connected.")

        if not getattr(self.driver, "initialized", False):
            raise RuntimeError("SCN6 driver is not initialized.")

        return self.driver

    # ------------------------------------------------------------------
    # Axis discovery
    # ------------------------------------------------------------------

    def connected_axes(self):
        driver = self.require_driver()

        result = []

        # Cyril's driver exposes .axes through TmbsController.
        for axis_number, axis_state in driver.axes.items():
            if axis_state.connected:
                result.append(axis_number)

        return result

    def axis_info(self):
        driver = self.require_driver()

        result = {}

        for axis_number, axis_state in driver.axes.items():
            result[str(axis_number)] = {
                "axis": axis_number,
                "connected": bool(axis_state.connected),
                "commanded_position": (
                    axis_state.commanded_position
                ),
                "prepared_motion": (
                    axis_state.prepared_motion
                ),
                "prepared_value": (
                    axis_state.prepared_value
                ),
            }

        return result

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    def position(self, axis):
        driver = self.require_driver()

        axis = int(axis)

        value = driver.axis_position(axis)

        # Current Cyril implementation returns:
        #
        #     (position, error)
        #
        # from read_controller_position().
        if isinstance(value, tuple):
            position, error = value

            return {
                "axis": axis,
                "position": position,
                "error": error,
            }

        return {
            "axis": axis,
            "position": value,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self, axis):
        driver = self.require_driver()

        axis = int(axis)

        status = driver.axis_status(axis)

        return {
            "axis": axis,
            "status": status,
        }

    def all_status(self):
        driver = self.require_driver()

        return driver.read_all_axis_status()

    # ------------------------------------------------------------------
    # Direct movement
    # ------------------------------------------------------------------

    def move_absolute(self, axis, position):
        driver = self.require_driver()

        axis = int(axis)
        position = int(round(position))

        # This is Cyril's existing direct hardware command.
        #
        # It performs the driver's safety check before calling
        # TMBSCOM move_abs().
        result = driver.direct_move_absolute(
            axis,
            position,
        )

        return {
            "axis": axis,
            "position": position,
            "result": result,
            "accepted": bool(result == 1),
        }

    def move_incremental(self, axis, distance):
        driver = self.require_driver()

        axis = int(axis)
        distance = int(round(distance))

        result = driver.direct_move_incremental(
            axis,
            distance,
        )

        return {
            "axis": axis,
            "distance": distance,
            "result": result,
            "accepted": bool(result == 1),
        }

    # ------------------------------------------------------------------
    # Prepared multi-axis movement
    # ------------------------------------------------------------------

    def clear_prepared(self):
        driver = self.require_driver()

        driver.clear_motion_buffer()

        return {
            "cleared": True,
        }

    def prepare_absolute(self, axis, position):
        driver = self.require_driver()

        axis = int(axis)
        position = int(round(position))

        result = driver.prepare_absolute(
            axis,
            position,
        )

        return {
            "axis": axis,
            "position": position,
            "prepared": bool(result),
        }

    def prepare_incremental(self, axis, distance):
        driver = self.require_driver()

        axis = int(axis)
        distance = int(round(distance))

        result = driver.prepare_incremental(
            axis,
            distance,
        )

        return {
            "axis": axis,
            "distance": distance,
            "prepared": bool(result),
        }

    def prepared_axes(self):
        driver = self.require_driver()

        return driver.prepared_axes()

    def execute_prepared(self):
        driver = self.require_driver()

        result = driver.execute_prepared()

        return {
            "executed": bool(result),
            "prepared_axes": driver.prepared_axes(),
        }

    def wait_prepared(
        self,
        timeout=30.0,
        interval=0.05,
    ):
        driver = self.require_driver()

        result = driver.wait_for_prepared_axes(
            timeout=float(timeout),
            interval=float(interval),
        )

        return {
            "completed": bool(result),
        }

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def stop(self, axis=None):
        """
        There is currently no generic driver.stop() method in
        Cyril's SCN6Driver/TmbsController.

        Therefore this intentionally does NOT invent a stop command.

        For now, return an explicit error so Blender cannot mistakenly
        believe an emergency stop was performed.
        """

        raise RuntimeError(
            "No generic stop() operation exists in the current "
            "CyrilPec/Snc6 driver API. Do not emulate STOP with "
            "another movement command."
        )


# ===========================================================================
# JSON SERVER
# ===========================================================================

class SCN6Server:

    def __init__(self):
        self.bridge = SCN6Bridge()
        self.running = True

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    @staticmethod
    def send(data):
        """
        Send exactly one JSON object.

        stdout is the IPC channel.
        """

        text = json.dumps(
            data,
            separators=(",", ":"),
            default=str,
        )

        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    @staticmethod
    def log(message):
        """
        Never write diagnostics to stdout.
        """

        sys.stderr.write(
            "[SCN6_SERVER] "
            + str(message)
            + "\n"
        )

        sys.stderr.flush()

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def handle(self, request):

        request_id = request.get("id")

        command = request.get("cmd")

        if not command:
            self.send({
                "id": request_id,
                "ok": False,
                "error": "Missing command.",
            })
            return

        try:

            # ----------------------------------------------------------
            # ping
            # ----------------------------------------------------------

            if command == "ping":

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": "pong",
                })

            # ----------------------------------------------------------
            # connect
            # ----------------------------------------------------------

            elif command == "connect":

                result = self.bridge.connect()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # disconnect
            # ----------------------------------------------------------

            elif command == "disconnect":

                result = self.bridge.disconnect()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # axes
            # ----------------------------------------------------------

            elif command == "axes":

                result = self.bridge.connected_axes()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "axes": result,
                })

            # ----------------------------------------------------------
            # axis_info
            # ----------------------------------------------------------

            elif command == "axis_info":

                result = self.bridge.axis_info()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "axes": result,
                })

            # ----------------------------------------------------------
            # position
            # ----------------------------------------------------------

            elif command == "position":

                axis = request["axis"]

                result = self.bridge.position(axis)

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # status
            # ----------------------------------------------------------

            elif command == "status":

                axis = request.get("axis")

                if axis is None:
                    result = self.bridge.all_status()

                else:
                    result = self.bridge.status(axis)

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # move
            # ----------------------------------------------------------

            elif command == "move":

                axis = request["axis"]
                position = request["position"]

                result = self.bridge.move_absolute(
                    axis,
                    position,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # move_inc
            # ----------------------------------------------------------

            elif command == "move_inc":

                axis = request["axis"]
                distance = request["distance"]

                result = self.bridge.move_incremental(
                    axis,
                    distance,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # clear
            # ----------------------------------------------------------

            elif command == "clear":

                result = self.bridge.clear_prepared()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # prepare_abs
            # ----------------------------------------------------------

            elif command == "prepare_abs":

                axis = request["axis"]
                position = request["position"]

                result = self.bridge.prepare_absolute(
                    axis,
                    position,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # prepare_inc
            # ----------------------------------------------------------

            elif command == "prepare_inc":

                axis = request["axis"]
                distance = request["distance"]

                result = self.bridge.prepare_incremental(
                    axis,
                    distance,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # prepared_axes
            # ----------------------------------------------------------

            elif command == "prepared_axes":

                result = self.bridge.prepared_axes()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "axes": result,
                })

            # ----------------------------------------------------------
            # execute
            # ----------------------------------------------------------

            elif command == "execute":

                result = self.bridge.execute_prepared()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # wait
            # ----------------------------------------------------------

            elif command == "wait":

                timeout = request.get(
                    "timeout",
                    30.0,
                )

                interval = request.get(
                    "interval",
                    0.05,
                )

                result = self.bridge.wait_prepared(
                    timeout,
                    interval,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # stop
            # ----------------------------------------------------------

            elif command == "stop":

                result = self.bridge.stop(
                    request.get("axis")
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # exit
            # ----------------------------------------------------------

            elif command == "exit":

                try:
                    self.bridge.disconnect()
                finally:
                    self.send({
                        "id": request_id,
                        "ok": True,
                        "result": "bye",
                    })

                    self.running = False

            # ----------------------------------------------------------
            # unknown
            # ----------------------------------------------------------

            else:

                self.send({
                    "id": request_id,
                    "ok": False,
                    "error": (
                        f"Unknown command: {command}"
                    ),
                })

        except Exception as exc:

            self.log(
                f"{command} failed: {exc}"
            )

            self.send({
                "id": request_id,
                "ok": False,
                "error": str(exc),
            })

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):

        self.log("starting")

        while self.running:

            line = sys.stdin.readline()

            if not line:
                break

            line = line.strip()

            if not line:
                continue

            try:
                request = json.loads(line)

            except json.JSONDecodeError as exc:

                self.send({
                    "id": None,
                    "ok": False,
                    "error": (
                        f"Invalid JSON: {exc}"
                    ),
                })

                continue

            if not isinstance(request, dict):

                self.send({
                    "id": None,
                    "ok": False,
                    "error": (
                        "Request must be a JSON object."
                    ),
                })

                continue

            self.handle(request)

        try:
            self.bridge.disconnect()
        except Exception as exc:
            self.log(
                f"disconnect failed: {exc}"
            )

        self.log("stopped")


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main():

    server = SCN6Server()

    try:

        server.run()

    except KeyboardInterrupt:

        server.log("keyboard interrupt")

    except Exception as exc:

        server.log(
            f"fatal error: {exc}"
        )

        traceback.print_exc(
            file=sys.stderr
        )

        try:
            server.bridge.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
