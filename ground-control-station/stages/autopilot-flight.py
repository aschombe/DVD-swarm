import os as _os
import sys
import time

from pymavlink import mavutil

_instance = _os.getenv("SWARM_INSTANCE", "0")
# Use TCP 5760 on companion — UDP 14550 is held by mavproxy.py at GCS startup
connection_string = f"tcp:10.13.{_instance}.3:5760"


def read_waypoints(filename):
    waypoints = []
    with open(filename) as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                lat, lon, alt = map(float, line.split(","))
                waypoints.append((lat, lon, alt))
    return waypoints


def connect_to_drone(connection_string, timeout=30, retries=5):
    for attempt in range(retries):
        try:
            print(f"Attempt {attempt + 1} of {retries} to connect to drone")
            master = mavutil.mavlink_connection(connection_string)
            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Timed out waiting for heartbeat")

                msg = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
                if msg:
                    print("Connected to drone")
                    return master
                else:
                    print("Waiting for heartbeat...")

        except TimeoutError as e:
            print(str(e))
        except Exception as e:
            print(f"Unexpected error: {str(e)}")

        time.sleep(5)  # Wait before retrying

    raise ConnectionError("Failed to connect to the drone after multiple attempts")


# Read waypoints from file - zigzag/square pattern at 10m altitude, ~55m between points
waypoints = read_waypoints("/opt/gcs/missions/waypoints_custom_zigzag_square.txt")

master = connect_to_drone(connection_string)
# Start mission upload
master.waypoint_clear_all_send()
master.mav.mission_count_send(master.target_system, master.target_component, len(waypoints))

# Upload waypoints — use msg.seq to handle FC retransmits correctly
uploaded = 0
while uploaded < len(waypoints):
    msg = master.recv_match(type=["MISSION_REQUEST"], blocking=True, timeout=5)
    if msg is None:
        print(f"Timeout waiting for MISSION_REQUEST (uploaded {uploaded}/{len(waypoints)})")
        break
    seq = msg.seq
    if seq >= len(waypoints):
        print(f"FC requested out-of-range seq {seq}, aborting")
        break
    lat, lon, alt = waypoints[seq]
    master.mav.mission_item_int_send(
        master.target_system,
        master.target_component,
        seq,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
        0,
        0,
        0,
        0,
        0,
        0,
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
    )
    uploaded = seq + 1

# Check for mission acceptance
ack_msg = master.recv_match(type=["MISSION_ACK"], blocking=True, timeout=10)
if ack_msg is not None and ack_msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
    print("Mission uploaded successfully")
else:
    print(f"Mission upload failed: ack={ack_msg}")
    sys.exit(1)

# Switch to AUTO mode
master.set_mode_auto()
print("AUTO mode set, mission started")
