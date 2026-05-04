"""
Firmware Log Parser

Reads a sensor log file (UART-style output) and extracts structured metrics:
  - Total reads / writes
  - Error counts by type (NACK, invalid register, etc.)
  - Per-register access frequency
  - Time range covered by the log

Usage:
    python3 tools/log_parser.py sensor_run.log
    python3 tools/log_parser.py sensor_run.log --json report.json
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


# Regex patterns for log lines
# Example matched lines:
#   [2026-05-04 07:50:11,234] INFO: READ  reg 0x00 -> 0x018C
#   [2026-05-04 07:50:11,234] WRITE reg 0x01 <- 0x0060
#   [2026-05-04 07:50:11,234] WARNING: NACK on read reg 0x00 (injected fault)
RE_TIMESTAMP = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\]")
RE_READ      = re.compile(r"INFO: READ\s+reg 0x([0-9A-Fa-f]{2})")
RE_WRITE     = re.compile(r"INFO: WRITE reg 0x([0-9A-Fa-f]{2})")
RE_NACK      = re.compile(r"WARNING: NACK on (read|write) reg 0x([0-9A-Fa-f]{2})")
RE_FAILED    = re.compile(r"ERROR: Read FAILED")
RE_RETRY     = re.compile(r"WARNING: Attempt (\d+) failed")


def parse_log(log_path: Path) -> dict:
    """Parse a log file and return aggregated statistics."""
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    metrics = {
        "total_lines": 0,
        "reads": 0,
        "writes": 0,
        "nacks": 0,
        "failed_calls": 0,
        "retry_attempts": 0,
        "register_access": defaultdict(int),
        "first_timestamp": None,
        "last_timestamp": None,
    }
    error_types = Counter()

    with log_path.open("r") as f:
        for line in f:
            metrics["total_lines"] += 1

            # Capture earliest and latest timestamps
            ts = RE_TIMESTAMP.search(line)
            if ts:
                if metrics["first_timestamp"] is None:
                    metrics["first_timestamp"] = ts.group(1)
                metrics["last_timestamp"] = ts.group(1)

            # READ events
            m = RE_READ.search(line)
            if m:
                metrics["reads"] += 1
                metrics["register_access"][f"0x{m.group(1).upper()}"] += 1
                continue

            # WRITE events
            m = RE_WRITE.search(line)
            if m:
                metrics["writes"] += 1
                metrics["register_access"][f"0x{m.group(1).upper()}"] += 1
                continue

            # NACK warnings
            m = RE_NACK.search(line)
            if m:
                metrics["nacks"] += 1
                error_types[f"NACK_{m.group(1)}"] += 1
                continue

            # Final failure (retries exhausted)
            if RE_FAILED.search(line):
                metrics["failed_calls"] += 1
                continue

            # Individual retry attempts
            if RE_RETRY.search(line):
                metrics["retry_attempts"] += 1

    metrics["register_access"] = dict(metrics["register_access"])
    metrics["error_types"] = dict(error_types)
    metrics["recovery_rate_pct"] = round(
        (metrics["reads"] + metrics["writes"]) /
        max(metrics["reads"] + metrics["writes"] + metrics["failed_calls"], 1)
        * 100, 2
    )
    return metrics


def print_report(metrics: dict, log_path: Path):
    """Pretty-print parsed metrics."""
    print(f"\n=== Log Analysis: {log_path.name} ===")
    print(f"Lines parsed:       {metrics['total_lines']}")
    print(f"Time range:         {metrics['first_timestamp']}  ->  {metrics['last_timestamp']}")
    print(f"Reads (success):    {metrics['reads']}")
    print(f"Writes (success):   {metrics['writes']}")
    print(f"NACKs encountered:  {metrics['nacks']}")
    print(f"Retry attempts:     {metrics['retry_attempts']}")
    print(f"Failed calls:       {metrics['failed_calls']}")
    print(f"Recovery rate:      {metrics['recovery_rate_pct']}%")

    if metrics["register_access"]:
        print("\nRegister access frequency:")
        for reg, count in sorted(metrics["register_access"].items()):
            print(f"  {reg}:  {count}")

    if metrics["error_types"]:
        print("\nError breakdown:")
        for err, count in metrics["error_types"].items():
            print(f"  {err}:  {count}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Parse firmware sensor logs")
    parser.add_argument("log_file", help="Path to log file")
    parser.add_argument("--json", help="Optional JSON output path")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    metrics = parse_log(log_path)
    print_report(metrics, log_path)

    if args.json:
        Path(args.json).write_text(json.dumps(metrics, indent=2))
        print(f"JSON report saved to: {args.json}")


if __name__ == "__main__":
    main()
