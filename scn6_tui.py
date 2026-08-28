"""Minimal read-only SCN6 monitor.

This is deliberately separate from the CLI. It uses only SCN6Driver and is
intended as the base for a future richer htop-style TUI.
"""
import os
import time

from scn6_driver import SCN6Driver
from scn6_dll import MAX_AXIS_COUNT, axis_name


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    driver = SCN6Driver()
    try:
        while True:
            if not driver.initialized:
                driver.initialize()
            clear()
            print("SCN6 MONITOR v20")
            print("=" * 72)
            print(f"COM6 / 115200 / TMBS state={driver.communication_state()}")
            print("\nAXIS SERVO RUN ALARM ORIGIN PFIN POSITION")
            print("---- ----- --- ----- ------ ---- --------")
            for axis in range(MAX_AXIS_COUNT):
                if not driver.axes[axis].connected:
                    continue
                status = driver.read_axis_status(axis)
                if not status:
                    continue
                print(f" {axis_name(axis):>2}   {status['servo']}     {status['run']}    "
                      f"{status['alarm']}      {status['origin']}      {status['pfin']}    "
                      f"{status.get('position', 'n/a')}")
            print("\nPress Ctrl+C to exit.")
            time.sleep(1.0)
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            if driver.initialized:
                driver.close_tmbs()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
