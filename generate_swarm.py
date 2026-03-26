#!/usr/bin/env python3
"""Generate docker-compose.swarm.yml for N headless DVD litemode instances.

Each instance gets isolated networks, volumes, container names, and port
mappings so all N instances can run concurrently on a single host.

Memory budget (no GCS, default limits):
  flight-controller : 256 MB
  companion-computer: 512 MB   ← ROS + Flask + MAVLink Router
  simulator         : 256 MB   ← minimal ROS + Flask mgmt console
  ─────────────────────────────
  per instance      : ~1 GB

  16 GB host (14 GB usable after OS)  →  ~14 instances
  32 GB host                          →  ~30 instances

GCS (QGroundControl) is excluded by default — it adds ~512 MB per instance
and is not needed for automated data collection. Pass --include-gcs to add it.

Waypoint injection (--waypoints-dir):
  Waypoints files are mounted into each companion-computer at /missions/waypoints.txt.
  Resolution order for instance N:
    1. missions/waypoints_N.txt   ← per-instance file (takes priority)
    2. missions/waypoints.txt     ← shared fallback for all instances

  Example layout for 3 instances with mixed routes:
    missions/
      waypoints.txt       ← default (instances 3+ use this)
      waypoints_1.txt     ← instance 1 flies a different route
      waypoints_2.txt     ← instance 2 flies a different route

  If neither file exists for an instance the waypoints mount is omitted and
  a warning is printed.

Usage:
    python3 generate_swarm.py                        # 14 instances, no GCS
    python3 generate_swarm.py --instances 20
    python3 generate_swarm.py --include-gcs          # add QGroundControl per instance
    python3 generate_swarm.py --ram-gb 32            # auto-size for 32 GB host
    python3 generate_swarm.py --waypoints-dir missions   # inject waypoints (default)
    python3 generate_swarm.py --no-waypoints         # skip waypoints entirely
    python3 generate_swarm.py --out custom.yml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# ── Port allocation ───────────────────────────────────────────────────────────
# Instance N (1-based) gets:
#   companion-computer : 3000 + N
#   simulator mgmt     : 8000 + N

BASE_COMPANION_PORT = 3000
BASE_SIMULATOR_PORT = 8000

# ── Subnet allocation ─────────────────────────────────────────────────────────
# Instance N gets subnet 10.13.N.0/24 with services on .2–.5

SUBNET_TEMPLATE = "10.13.{n}.0/24"
FC_IP_TEMPLATE = "10.13.{n}.2"
CC_IP_TEMPLATE = "10.13.{n}.3"
GCS_IP_TEMPLATE = "10.13.{n}.4"
SIM_IP_TEMPLATE = "10.13.{n}.5"

# ── Docker images ─────────────────────────────────────────────────────────────
IMAGES: dict[str, str] = {
    "flight-controller": "n1ckaleks/damn-vulnerable-drone-flight-controller-lite:latest",
    "companion-computer": "n1ckaleks/damn-vulnerable-drone-companion-computer-lite:latest",
    "ground-control-station": (
        "n1ckaleks/damn-vulnerable-drone-ground-control-station-lite:latest"
    ),
    "simulator": "n1ckaleks/damn-vulnerable-drone-simulator-lite:latest",
}

# ── Default memory limits (per service) ──────────────────────────────────────
# These cap runaway containers and make per-instance RAM budgeting predictable.
# Raise them if containers OOM-restart; lower them to fit more instances.
DEFAULT_MEM: dict[str, str] = {
    "flight-controller": "256m",  # ArduPilot SITL binary
    "companion-computer": "512m",  # ROS + Flask + MAVLink Router + SSH
    "ground-control-station": "512m",  # QGroundControl AppImage + graphics libs
    "simulator": "256m",  # minimal ROS base + Flask mgmt console
}

# OS + Docker daemon overhead reserved from total host RAM
_OS_OVERHEAD_GB = 2.0

# Per-instance RAM footprint (MB) used for --ram-gb auto-sizing
_MB_PER_INSTANCE_NO_GCS = 1024  # ~1 GB: FC(256) + CC(512) + SIM(256)
_MB_PER_INSTANCE_WITH_GCS = 1536  # ~1.5 GB: adds GCS(512)


def _mem_limits(service: str) -> dict[str, str]:
    """Return mem_limit and memswap_limit keys for a service."""
    limit = DEFAULT_MEM[service]
    return {
        "mem_limit": limit,
        # disable swap to prevent containers from swapping instead of restarting
        "memswap_limit": limit,
    }


def flight_controller_service(n: int) -> dict[str, Any]:
    """Build the flight-controller-lite service definition for instance N."""
    return {
        "image": IMAGES["flight-controller"],
        "container_name": f"flight-controller-lite-{n}",
        "privileged": True,
        "volumes": [f"dvd-serial-{n}:/sockets"],
        "environment": ["LITE=true"],
        "networks": {
            f"dvd-net-{n}": {"ipv4_address": FC_IP_TEMPLATE.format(n=n)},
        },
        "restart": "unless-stopped",
        **_mem_limits("flight-controller"),
    }


def resolve_waypoints(n: int, waypoints_dir: Path | None) -> str | None:
    """Return the host-side waypoints file to mount for instance N, or None.

    Checks for a per-instance file (waypoints_N.txt) first, then falls back
    to the shared waypoints.txt. Returns the path as a string suitable for a
    Docker bind-mount source, or None if no file is found.
    """
    if waypoints_dir is None:
        return None
    per_instance = waypoints_dir / f"waypoints_{n}.txt"
    if per_instance.exists():
        return str(per_instance)
    shared = waypoints_dir / "waypoints.txt"
    if shared.exists():
        return str(shared)
    return None


def companion_computer_service(n: int, waypoints_dir: Path | None) -> dict[str, Any]:
    """Build the companion-computer-lite service definition for instance N.

    Mounts a waypoints file at /missions/waypoints.txt if one is found under
    waypoints_dir. Resolution order: waypoints_N.txt → waypoints.txt.
    """
    volumes: list[str] = [f"dvd-serial-{n}:/sockets"]

    wp_host = resolve_waypoints(n, waypoints_dir)
    if wp_host is not None:
        volumes.append(f"{wp_host}:/missions/waypoints.txt:ro")

    return {
        "image": IMAGES["companion-computer"],
        "container_name": f"companion-computer-lite-{n}",
        "privileged": True,
        "extra_hosts": ["host.docker.internal:host-gateway"],
        "ports": [f"{BASE_COMPANION_PORT + n}:3000"],
        "depends_on": [f"flight-controller-lite-{n}"],
        "volumes": volumes,
        "environment": [
            "LITE=true",
            # WIFI_ENABLED intentionally omitted — no virtual WiFi in swarm
        ],
        "networks": {
            f"dvd-net-{n}": {"ipv4_address": CC_IP_TEMPLATE.format(n=n)},
        },
        "restart": "unless-stopped",
        **_mem_limits("companion-computer"),
    }


def ground_control_station_service(n: int) -> dict[str, Any]:
    """Build the ground-control-station-lite service definition for instance N.

    X11 display, GPU device, and WiFi are all stripped for headless operation.
    HEADLESS=1 instructs QGC to run without a display server.
    """
    return {
        "image": IMAGES["ground-control-station"],
        "container_name": f"ground-control-station-lite-{n}",
        "privileged": True,
        "depends_on": [f"companion-computer-lite-{n}"],
        "environment": [
            "LITE=true",
            "HEADLESS=1",
            "QT_NO_MITSHM=1",
            "XDG_RUNTIME_DIR=/tmp",
        ],
        "volumes": [
            # Qt requires /etc/machine-id — available on any Linux host
            "/etc/machine-id:/etc/machine-id:ro",
        ],
        "networks": {
            f"dvd-net-{n}": {"ipv4_address": GCS_IP_TEMPLATE.format(n=n)},
        },
        "restart": "unless-stopped",
        **_mem_limits("ground-control-station"),
    }


def simulator_service(n: int) -> dict[str, Any]:
    """Build the simulator-lite service definition for instance N."""
    cc_url = f"http://{CC_IP_TEMPLATE.format(n=n)}:3000"
    return {
        "image": IMAGES["simulator"],
        "container_name": f"simulator-lite-{n}",
        "privileged": True,
        "environment": [
            "LITE=true",
            # Override Dockerfile ENV and bridge.py default — both hardcode
            # the original single-instance subnet (10.13.0.3 / "companion-computer")
            f"MAV2REST_URL={cc_url}",
            f"COMPANION_BASE_URL={cc_url}",
        ],
        "volumes": [
            # mgmt scripts are read-only and shared across all instances
            "./simulator/mgmt:/app/simulator/mgmt:ro",
            # Docker socket needed by the simulator management console
            "/var/run/docker.sock:/var/run/docker.sock",
        ],
        "ports": [f"{BASE_SIMULATOR_PORT + n}:8000"],
        "networks": {
            f"dvd-net-{n}": {"ipv4_address": SIM_IP_TEMPLATE.format(n=n)},
        },
        "restart": "unless-stopped",
        **_mem_limits("simulator"),
    }


def instance_services(
    n: int, *, include_gcs: bool, waypoints_dir: Path | None
) -> dict[str, dict[str, Any]]:
    """Return service definitions for instance N."""
    services: dict[str, dict[str, Any]] = {
        f"flight-controller-lite-{n}": flight_controller_service(n),
        f"companion-computer-lite-{n}": companion_computer_service(n, waypoints_dir),
        f"simulator-lite-{n}": simulator_service(n),
    }
    if include_gcs:
        services[f"ground-control-station-lite-{n}"] = ground_control_station_service(n)
    return services


def instance_network(n: int) -> dict[str, Any]:
    """Return the isolated bridge network definition for instance N."""
    return {
        "name": f"dvd-net-{n}",
        "internal": False,
        "driver": "bridge",
        "ipam": {
            "config": [{"subnet": SUBNET_TEMPLATE.format(n=n)}],
        },
    }


def instance_volumes(n: int) -> dict[str, None]:
    """Return the named volume definitions for instance N."""
    return {
        f"dvd-serial-{n}": None,
        f"dvd-ardupilot-{n}": None,
    }


def generate(
    n_instances: int,
    *,
    include_gcs: bool,
    waypoints_dir: Path | None,
) -> dict[str, Any]:
    """Build the full Compose document for n_instances DVD litemode stacks."""
    services: dict[str, Any] = {}
    networks: dict[str, Any] = {}
    volumes: dict[str, Any] = {}

    for n in range(1, n_instances + 1):
        services.update(instance_services(n, include_gcs=include_gcs, waypoints_dir=waypoints_dir))
        networks[f"dvd-net-{n}"] = instance_network(n)
        volumes.update(instance_volumes(n))

    return {
        "services": services,
        "volumes": volumes,
        "networks": networks,
    }


def instances_for_ram(ram_gb: float, *, include_gcs: bool) -> int:
    """Return the safe instance count for the given host RAM."""
    usable_mb = (ram_gb - _OS_OVERHEAD_GB) * 1024
    mb_per = _MB_PER_INSTANCE_WITH_GCS if include_gcs else _MB_PER_INSTANCE_NO_GCS
    return max(1, int(usable_mb // mb_per))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate docker-compose.swarm.yml for N DVD litemode instances.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument(
        "--instances",
        type=int,
        metavar="N",
        help="Exact number of instances (default: auto-sized for 16 GB host)",
    )
    sizing.add_argument(
        "--ram-gb",
        type=float,
        metavar="GB",
        help="Auto-size instance count for this much host RAM",
    )

    parser.add_argument(
        "--include-gcs",
        action="store_true",
        default=False,
        help="Include QGroundControl (adds ~512 MB per instance)",
    )

    wp_group = parser.add_mutually_exclusive_group()
    wp_group.add_argument(
        "--waypoints-dir",
        type=Path,
        default=Path("missions"),
        metavar="DIR",
        help=(
            "Directory containing waypoints files. "
            "Per-instance file waypoints_N.txt takes priority over waypoints.txt. "
            "Mounted into each companion-computer at /missions/waypoints.txt"
        ),
    )
    wp_group.add_argument(
        "--no-waypoints",
        action="store_true",
        default=False,
        help="Skip waypoints injection entirely",
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docker-compose.swarm.yml"),
        metavar="FILE",
        help="Output file path",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Resolve instance count
    if args.ram_gb is not None:
        n = instances_for_ram(args.ram_gb, include_gcs=args.include_gcs)
        print(f"Auto-sized: {n} instances for {args.ram_gb} GB RAM")
    elif args.instances is not None:
        n = args.instances
    else:
        # Default: safe for a 16 GB host
        n = instances_for_ram(16.0, include_gcs=args.include_gcs)

    if n < 1:
        print(f"error: computed instances must be >= 1, got {n}", file=sys.stderr)
        return 1
    if n > 253:
        print(f"error: instances must be <= 253, got {n}", file=sys.stderr)
        return 1

    # Resolve waypoints directory
    waypoints_dir: Path | None
    if args.no_waypoints:
        waypoints_dir = None
    else:
        waypoints_dir = args.waypoints_dir
        if not waypoints_dir.is_dir():
            print(
                f"warning: --waypoints-dir '{waypoints_dir}' not found — "
                "waypoints will not be mounted. Create the directory or pass --no-waypoints.",
                file=sys.stderr,
            )
            waypoints_dir = None

    services_per = 3 + (1 if args.include_gcs else 0)
    mb_per = _MB_PER_INSTANCE_WITH_GCS if args.include_gcs else _MB_PER_INSTANCE_NO_GCS

    compose = generate(n, include_gcs=args.include_gcs, waypoints_dir=waypoints_dir)

    # Report which waypoints resolution each instance got
    wp_summary: dict[str, list[int]] = {"per-instance": [], "shared": [], "none": []}
    if waypoints_dir is not None:
        for i in range(1, n + 1):
            per = waypoints_dir / f"waypoints_{i}.txt"
            shared = waypoints_dir / "waypoints.txt"
            if per.exists():
                wp_summary["per-instance"].append(i)
            elif shared.exists():
                wp_summary["shared"].append(i)
            else:
                wp_summary["none"].append(i)

    gcs_note = (
        "GCS included (+512 MB/instance)"
        if args.include_gcs
        else "GCS excluded (use --include-gcs to add)"
    )
    header = (
        f"# Generated by generate_swarm.py — {n} DVD litemode instances\n"
        "# Do NOT edit by hand. Re-run: python3 generate_swarm.py [OPTIONS]\n"
        "#\n"
        f"# Services per instance : {services_per}  ({gcs_note})\n"
        f"# RAM budget            : ~{mb_per} MB/instance\n"
        "#\n"
        "# Port mapping:\n"
        f"#   companion-computer : {BASE_COMPANION_PORT + 1}"
        f"–{BASE_COMPANION_PORT + n}\n"
        f"#   simulator mgmt     : {BASE_SIMULATOR_PORT + 1}"
        f"–{BASE_SIMULATOR_PORT + n}\n"
        "#\n"
        f"# Subnets: 10.13.1.0/24 – 10.13.{n}.0/24\n"
        f"# Waypoints dir       : {waypoints_dir or 'none (--no-waypoints)'}\n\n"
    )

    output = header + yaml.dump(
        compose,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    args.out.write_text(output)

    print(f"Written {n} instances ({services_per} services each) → {args.out}")
    print(f"  RAM estimate    : ~{n * mb_per // 1024} GB / {n * mb_per} MB")
    print(f"  companion ports : {BASE_COMPANION_PORT + 1}–{BASE_COMPANION_PORT + n}")
    print(f"  simulator ports : {BASE_SIMULATOR_PORT + 1}–{BASE_SIMULATOR_PORT + n}")
    if not args.include_gcs:
        print("  GCS             : excluded (pass --include-gcs to add)")
    if waypoints_dir is not None:
        if wp_summary["per-instance"]:
            print(f"  waypoints       : per-instance for {wp_summary['per-instance']}")
        if wp_summary["shared"]:
            print(f"  waypoints       : shared fallback for instances {wp_summary['shared']}")
        if wp_summary["none"]:
            print(
                f"  waypoints       : WARNING — no file found for instances {wp_summary['none']}",
                file=sys.stderr,
            )
    else:
        print("  waypoints       : not mounted (--no-waypoints)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
