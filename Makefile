COMPOSE_FILE  := docker-compose.swarm.yml
INSTANCES     ?= 9
RAM_GB        ?= 16
PYTHON        := python3
NUM_WAYPOINTS ?= 10

.PHONY: help generate generate-ram pull up down status logs sysctl-check

help:
	@echo "DVD Swarm — headless litemode instances"
	@echo ""
	@echo "  make generate                  Auto-size for $(RAM_GB) GB RAM (~9 instances, with GCS)"
	@echo "  make generate NO_GCS=1         Omit QGroundControl (~14 instances)"
	@echo "  make generate INSTANCES=5      Override instance count explicitly"
	@echo "  make generate RAM_GB=32        Auto-size for a different host"
	@echo ""
	@echo "  make pull                      Pull all lite images (run once before 'up')"
	@echo "  make up                        Start all instances detached"
	@echo "  make down                      Stop and remove all instances + volumes"
	@echo "  make status                    Show running DVD container count"
	@echo "  make logs                      Stream logs from all instances"
	@echo "  make sysctl-check              Warn if inotify limits may be too low"
	@echo ""
	@echo "Memory per instance: ~1.5 GB with GCS (default) | ~1 GB no GCS"
	@echo "Recommended for 16 GB host: 9 instances (with GCS)  |  14 instances (no GCS)"

# ── Generate ──────────────────────────────────────────────────────────────────

# GCS is on by default; NO_GCS=1 turns it off
_NO_GCS_FLAG := $(if $(NO_GCS),--no-gcs,)

generate:
ifdef INSTANCES
	$(PYTHON) generate_swarm.py --instances $(INSTANCES) $(_NO_GCS_FLAG) --num-waypoints $(NUM_WAYPOINTS) --out $(COMPOSE_FILE)
else
	$(PYTHON) generate_swarm.py --ram-gb $(RAM_GB) $(_NO_GCS_FLAG) --num-waypoints $(NUM_WAYPOINTS) --out $(COMPOSE_FILE)
endif

# ── Image management ──────────────────────────────────────────────────────────

pull: $(COMPOSE_FILE)
	docker compose -f $(COMPOSE_FILE) pull

# ── Lifecycle ─────────────────────────────────────────────────────────────────

up: $(COMPOSE_FILE)
	docker compose -f $(COMPOSE_FILE) up -d

down: $(COMPOSE_FILE)
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans

# ── Observability ─────────────────────────────────────────────────────────────

status:
	@echo "Running DVD containers:"
	@echo "  flight-controllers    : $$(docker ps -q --filter 'name=flight-controller-lite-' | wc -l)"
	@echo "  companion-computers   : $$(docker ps -q --filter 'name=companion-computer-lite-' | wc -l)"
	@echo "  ground-control-stns   : $$(docker ps -q --filter 'name=ground-control-station-lite-' | wc -l)"
	@echo "  simulators            : $$(docker ps -q --filter 'name=simulator-lite-' | wc -l)"

logs: $(COMPOSE_FILE)
	docker compose -f $(COMPOSE_FILE) logs -f

# ── Host prerequisites ────────────────────────────────────────────────────────

sysctl-check:
	@echo "=== inotify limits ==="
	@echo "  max_user_instances : $$(cat /proc/sys/fs/inotify/max_user_instances)  (need ≥1024 for 14 instances)"
	@echo "  max_user_watches   : $$(cat /proc/sys/fs/inotify/max_user_watches)"
	@echo ""
	@echo "To raise (temporary):"
	@echo "  sudo sysctl -w fs.inotify.max_user_instances=8192"
	@echo "  sudo sysctl -w fs.inotify.max_user_watches=524288"

# ── Ensure compose file exists before using it ───────────────────────────────

$(COMPOSE_FILE):
	@echo "$(COMPOSE_FILE) not found — run 'make generate' first"
	@exit 1
