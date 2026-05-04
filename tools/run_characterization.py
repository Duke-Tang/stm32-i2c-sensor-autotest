"""
Characterization Test Runner

Sweeps fault rates and reports driver performance:
  - success rate
  - average retries per call
  - p99 latency
  - human-readable table + machine-readable JSON

Usage:
    python3 tools/run_characterization.py
    python3 tools/run_characterization.py --trials 5000 --output report.json
"""
import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

# Allow running this file directly from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from device.i2c_sensor_sim import I2CSensorSim
from device.i2c_driver import I2CDriver


def run_trial(fault_rate: float, trials: int, seed: int = 42) -> dict:
    """Run a single fault-rate scenario and return measured metrics."""
    random.seed(seed)
    sensor = I2CSensorSim(fault_rate=fault_rate)
    driver = I2CDriver(sensor, max_retries=3, backoff_ms=1)

    successes = 0
    failures = 0
    latencies_ms = []

    for _ in range(trials):
        start = time.perf_counter()
        try:
            driver.read_temperature()
            successes += 1
        except IOError:
            failures += 1
        latencies_ms.append((time.perf_counter() - start) * 1000)

    avg_retries = (
        driver.stats["total_retries"] / trials if trials > 0 else 0.0
    )
    p99 = (
        statistics.quantiles(latencies_ms, n=100)[98]
        if len(latencies_ms) >= 100
        else max(latencies_ms)
    )

    return {
        "fault_rate": fault_rate,
        "trials": trials,
        "successes": successes,
        "failures": failures,
        "success_rate_pct": round(successes / trials * 100, 3),
        "avg_retries_per_call": round(avg_retries, 3),
        "avg_latency_ms": round(statistics.mean(latencies_ms), 3),
        "p99_latency_ms": round(p99, 3),
    }


def print_table(results: list):
    """Pretty-print results as a fixed-width table."""
    header = (
        f"{'Fault Rate':>12} | {'Trials':>7} | {'Success %':>10} | "
        f"{'Fails':>6} | {'Avg Retry':>10} | {'Avg ms':>8} | {'p99 ms':>8}"
    )
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['fault_rate']:>12.2f} | {r['trials']:>7} | "
            f"{r['success_rate_pct']:>9.2f}% | {r['failures']:>6} | "
            f"{r['avg_retries_per_call']:>10.3f} | "
            f"{r['avg_latency_ms']:>8.3f} | {r['p99_latency_ms']:>8.3f}"
        )
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Characterize I2C driver behavior under varying fault rates"
    )
    parser.add_argument(
        "--trials", type=int, default=1000,
        help="Number of read attempts per fault rate (default: 1000)"
    )
    parser.add_argument(
        "--output", type=str, default="characterization_report.json",
        help="JSON output file path"
    )
    args = parser.parse_args()

    fault_rates = [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70]
    print(
        f"Running characterization: {args.trials} trials per fault rate, "
        f"{len(fault_rates)} scenarios"
    )

    results = []
    for fr in fault_rates:
        print(f"  Testing fault_rate={fr:.2f} ...", end=" ", flush=True)
        result = run_trial(fault_rate=fr, trials=args.trials)
        results.append(result)
        print(f"success={result['success_rate_pct']:.2f}%")

    print_table(results)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"JSON report written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()