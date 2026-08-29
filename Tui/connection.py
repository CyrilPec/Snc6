from scn6_dll import AXIS_NUMBERS, axis_name, status_name
from scn6_driver import SCN6Driver

class ConnectionMixin:
    def require_driver(self):
        if self.driver is None or not self.driver.initialized:
            self.log_message("ERROR: run CONNECT/initialize first.")
            return None
        return self.driver

    def connect_driver(self):
        if self.driver is not None:
            self.log_message("Driver is already connected.")
            return
        port = self.query_one("#port").value.strip()
        baud = self.query_one("#baud").value.strip()
        self.log_message(f"Connecting to SCN6 on {port} @ {baud}...")
        try:
            # Hardware/DLL ownership remains in SCN6Driver.
            self.driver = SCN6Driver()
            history = self.driver.initialize()
            if not self.driver.initialized:
                self.log_message(f"SCN6 initialization failed: {history[-1] if history else None}")
                self.driver = None
                self.set_status("Connection failed", "$error")
                return
            self.driver.refresh_connected_axes()
            connected = [axis_name(a) for a in AXIS_NUMBERS if self.driver.axes[a].connected]
            state = self.driver.communication_state()
            self.set_status("CONNECTED", "$success")
            self.log_message(f"TMBSCOM state: {state} ({status_name(state)})")
            self.log_message("Connected axes: " + (", ".join(connected) if connected else "none"))
            self.update_status()
        except Exception as exc:
            self.log_message(f"ERROR connecting to SCN6: {exc}")
            self.driver = None
            self.set_status("Connection failed", "$error")

    def close_driver(self):
        if self.driver is None:
            return
        try:
            if self.driver.initialized:
                self.driver.close_tmbs()
        except Exception as exc:
            self.log_message(f"Error closing SCN6: {exc}")
        finally:
            self.driver = None

    def disconnect_driver(self):
        self.log_message("Disconnecting SCN6...")
        self.close_driver()
        self.set_status("DISCONNECTED")
        for axis in AXIS_NUMBERS:
            self.update_axis_row(axis, None, None)
        self.log_message("SCN6 disconnected.")
