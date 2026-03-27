# simulator/mgmt/routes/telemetry.py
import logging
import os

import requests

# python-socketio client (to receive from Companion Computer)
from .utils import SWARM_INSTANCE

log = logging.getLogger(__name__)

DEFAULT_COMPANION = "http://10.13.0.3:3000"

COMPANION_BASE_URL = os.getenv("COMPANION_BASE_URL", DEFAULT_COMPANION)

# Public-facing URL the *browser* uses to reach the companion computer Socket.IO.
# In a swarm, instance N maps companion port 3000 → host port 3000+N.
# Single-instance (SWARM_INSTANCE="") stays on port 3000.
_instance_num = int(SWARM_INSTANCE) if SWARM_INSTANCE else 0
CC_URL_PUBLIC = f"http://localhost:{3000 + _instance_num}"


# ---------- Public helpers used by other modules ----------
def start_companion_telemetry(data: dict):
    url = f"{COMPANION_BASE_URL}/telemetry/start-telemetry"
    try:
        r = requests.post(url, json=data, timeout=10)
        log.info("[telemetry] start -> %s %s", r.status_code, r.text[:200])
    except Exception:
        pass


def stop_companion_telemetry():
    url = f"{COMPANION_BASE_URL}/telemetry/stop-telemetry"
    try:
        r = requests.post(url, timeout=10)
        log.info("[telemetry] stop -> %s %s", r.status_code, r.text[:200])
    except Exception:
        pass
