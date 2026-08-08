"""Measure cached vs uncached catalog read latency.

Usage:
    python scripts/benchmark.py --runs 50
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.redis_service import cache  # noqa: E402


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(int(len(ordered) * pct / 100), len(ordered) - 1)
    return ordered[index]


def summarise(label: str, samples: list[float]) -> dict:
    return {
        "label": label,
        "mean": statistics.mean(samples),
        "median": statistics.median(samples),
        "p95": percentile(samples, 95),
        "min": min(samples),
        "max": max(samples),
    }


def run(runs: int) -> None:
    app = create_app()
    client = app.test_client()

    if not cache.available:
        print("WARNING: Redis is not reachable — cached numbers will be meaningless.\n")

    uncached: list[float] = []
    cached: list[float] = []

    print(f"Running {runs} iteration(s) against /api/products ...\n")
    for _ in range(runs):
        # Cold read: clear the cache so MySQL is hit.
        cache.invalidate("products:*")
        start = time.perf_counter()
        client.get("/api/products?limit=20")
        uncached.append((time.perf_counter() - start) * 1000)

        # Warm read: identical query, now served by Redis.
        start = time.perf_counter()
        client.get("/api/products?limit=20")
        cached.append((time.perf_counter() - start) * 1000)

    cold = summarise("MySQL (cold)", uncached)
    warm = summarise("Redis (cached)", cached)

    header = f"{'Scenario':<18}{'mean':>10}{'median':>10}{'p95':>10}{'min':>10}{'max':>10}"
    print(header)
    print("-" * len(header))
    for row in (cold, warm):
        print(
            f"{row['label']:<18}"
            f"{row['mean']:>9.2f}m{row['median']:>9.2f}m"
            f"{row['p95']:>9.2f}m{row['min']:>9.2f}m{row['max']:>9.2f}m"
        )

    speedup = cold["mean"] / warm["mean"] if warm["mean"] else 0
    reduction = (1 - warm["mean"] / cold["mean"]) * 100 if cold["mean"] else 0
    print(f"\nSpeed-up: {speedup:.1f}x   Latency reduction: {reduction:.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark the cache layer.")
    parser.add_argument("--runs", type=int, default=50)
    run(parser.parse_args().runs)
