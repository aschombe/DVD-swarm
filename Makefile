COMPOSE_FILE  := docker-compose.swarm.yml
INSTANCES     ?= 14
RAM_GB        ?= 16
PYTHON        := python3

.PHONY: help generate generate-ram pull up down status logs sysctl-check

help:
	@echo "DVD Swarm — headless litemode instances"
	@echo ""
	@echo "  make generate                  Auto-size for $(RAM_GB) GB RAM (~$(INSTANCES) instances, no GCS)"
	@echo "  make generate INSTANCES=20     Override instance count explicitly"
	@echo "  make generate RAM_GB=32        Auto-size for a different host"
	@echo "  make generate INCLUDE_GCS=1    Add QGroundControl (+512 MB/instance)"
	@echo ""
	@echo "  make pull                      Pull all lite images (run once before 'up')"
	@echo "  make up                        Start all instances detached"
	@echo "  make down                      Stop and remove all instances + volumes"
	@echo "  make status                    Show running DVD container count"
	@echo "  make logs                      Stream logs from all instances"
	@echo "  make sysctl-check              Warn if inotify limits may be too low"
	@echo ""
	@echo "Memory per instance (no GCS): ~1 GB  |  with GCS: ~1.5 GB"
	@echo "Recommended for 16 GB host  : 14 instances (no GCS)"

# ── Generate ──────────────────────────────────────────────────────────────────

_GCS_FLAG := $(if $(INCLUDE_GCS),--include-gcs,)

generate:
ifdef INSTANCES
	$(PYTHON) generate_swarm.py --instances $(INSTANCES) $(_GCS_FLAG) --out $(COMPOSE_FILE)
else
	$(PYTHON) generate_swarm.py --ram-gb $(RAM_GB) $(_GCS_FLAG) --out $(COMPOSE_FILE)
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
