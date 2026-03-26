# simulator/mgmt/routes/utils.py
import os

import docker

# LITE flag used for container naming and template toggles
LITE = str(os.getenv("LITE", "")).lower() in ("1", "true", "yes", "on")

# SWARM_INSTANCE is injected by generate_swarm.py for multi-instance deployments.
# When set, container names are suffixed with the instance number so each
# simulator-lite-N only execs into its own flight-controller-lite-N / gcs-lite-N.
SWARM_INSTANCE = os.getenv("SWARM_INSTANCE", "")


def get_container(name: str):
    """Return docker container object for the given base name.

    Appends '-lite' when LITE is set, then appends '-{SWARM_INSTANCE}' when
    running inside a swarm so each simulator targets only its own containers.
    """
    full_name = f"{name}-lite" if LITE else name
    if SWARM_INSTANCE:
        full_name = f"{full_name}-{SWARM_INSTANCE}"
    client = docker.from_env()
    return client.containers.get(full_name)
