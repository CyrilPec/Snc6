import argparse
import sys

import serial
from lark.exceptions import LarkError

from gcode.parser import GCodeParser
from gcode.interpreter import GCodeInterpreter
from machine import SCN6Machine


class SCN6Server:

    def __init__(
        self,
        port,
        baudrate=115200,
        axis_map=None,
        initialize=True,
    ):
        self.port = port
        self.baudrate = baudrate

        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0.1,
            write_timeout=1.0,
        )

        self.machine = SCN6Machine(
            axis_map=axis_map
        )

        self.parser = GCodeParser()

        self.interpreter = GCodeInterpreter(
            self.machine
        )

        if initialize:
            initialized, history = (
                self.machine.initialize()
            )

            if not initialized:
                raise RuntimeError(
                    f"SCN6 initialization failed: {history}"
                )

    def send(self, message):
        data = (message + "\n").encode("ascii")
        self.serial.write(data)
        self.serial.flush()

    def execute_line(self, line):

        line = line.strip()

        if not line:
            return None

        try:
            command = self.parser.parse(line)

            result = self.interpreter.execute(
                command
            )

            if isinstance(result, str):
                return result

            return "ok"

        except LarkError as exc:
            return f"error: gcode parse: {exc}"

        except Exception as exc:
            return f"error: {exc}"

    def run(self):

        print(
            f"SCN6 server listening on "
            f"{self.port} @ {self.baudrate}"
        )

        try:
            while True:

                raw = self.serial.readline()

                if not raw:
                    continue

                try:
                    line = raw.decode(
                        "ascii",
                        errors="replace",
                    ).strip()
                except Exception:
                    self.send("error: invalid serial data")
                    continue

                if not line:
                    continue

                print(f"> {line}")

                response = self.execute_line(line)

                if response is not None:
                    print(f"< {response}")
                    self.send(response)

        except KeyboardInterrupt:
            print("\nStopping server.")

        finally:
            self.close()

    def close(self):

        try:
            self.machine.close()
        except Exception as exc:
            print(
                f"SCN6 close warning: {exc}",
                file=sys.stderr,
            )

        try:
            self.serial.close()
        except Exception:
            pass


def main():

    parser = argparse.ArgumentParser(
        description="SCN6 G-code serial server"
    )

    parser.add_argument(
        "port",
        help="Serial port connected to SimulIDE Mega",
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
    )

    parser.add_argument(
        "--axis-x",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--axis-y",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--axis-z",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--axis-a",
        type=int,
        default=3,
    )

    args = parser.parse_args()

    axis_map = {
        "X": args.axis_x,
        "Y": args.axis_y,
        "Z": args.axis_z,
        "A": args.axis_a,
    }

    server = SCN6Server(
        port=args.port,
        baudrate=args.baud,
        axis_map=axis_map,
    )

    server.run()


if __name__ == "__main__":
    main()
