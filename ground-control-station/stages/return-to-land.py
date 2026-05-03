import os
import time

from pymavlink import mavutil


def set_rtl_altitude(master, rtl_alt_cm):
    """Set the RTL altitude."""
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        b"RTL_ALT",
        rtl_alt_cm,
        mavutil.mavlink.MAV_PARAM_TYPE_INT32,
    )
    # Wait for the parameter to be set
    time.sleep(2)


def set_mode_rtl(master):
    """Set the drone's mode to RTL (Return to Launch)."""
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mavutil.mavlink.COPTER_MODE_RTL,
    )


# Connect to companion computer's mavlink-routerd TCP port directly.
# UDP 14550 is held by mavproxy.py in this container — use TCP 5760 instead.
_instance = os.getenv("SWARM_INSTANCE", "0")
connection_string = f"tcp:10.13.{_instance}.3:5760"
master = mavutil.mavlink_connection(connection_string)
master.wait_heartbeat()
print("Connected to drone")

# Set RTL altitude (e.g., 5000 cm for 50 meters)
set_rtl_altitude(master, 275)
print("RTL altitude set to 50 meters")

# Set mode to RTL
set_mode_rtl(master)
print("Returning to Launch")
