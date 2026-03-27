from pathlib import Path

LOGS_DIR = Path("/ardupilot/logs")

log_files = sorted(LOGS_DIR.glob("*.BIN"))
if not log_files:
    print("No log files found in", LOGS_DIR)
else:
    print(f"Post-flight analysis: {len(log_files)} log file(s)")
    for f in log_files:
        size_mb = f.stat().st_size / 1_048_576
        print(f"  {f.name}  {size_mb:.1f} MB")
    total_mb = sum(f.stat().st_size for f in log_files) / 1_048_576
    print(f"Total: {total_mb:.1f} MB  →  configs/data/raw/instance-N/")
