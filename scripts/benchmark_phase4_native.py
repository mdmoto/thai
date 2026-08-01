#!/usr/bin/env python3
"""Measure native population and quantitative simulation resource use.

Each population size runs in a fresh subprocess so peak RSS is comparable.
This benchmark deliberately excludes public-web collection and LLM calls; it
measures the deterministic native compute layer that must fit inside the
Cloud Run Job resource envelope.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from simulation_core.calibration import load_calibration_profile
from simulation_core.config import PLAN_CONFIG_VERSION, get_plan_config
from simulation_core.engine import SimulationEngine
from world_model.generator import PopulationGenerator, WORLD_MODEL_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POPULATIONS = (100, 5_000, 20_000, 100_000, 300_000)


def _memory_sampler(
    process: psutil.Process,
    stop: threading.Event,
    peak: list[int],
) -> None:
    while not stop.wait(0.05):
        try:
            rss = int(process.memory_info().rss)
        except (psutil.Error, OSError):
            return
        if rss > peak[0]:
            peak[0] = rss


def _competitors() -> list[dict[str, Any]]:
    return [
        {
            "name": f"benchmark_competitor_{index + 1}",
            "price": 990.0 + index * 85.0,
            "awareness": 0.42 + index * 0.05,
            "quality_score": 0.56 + index * 0.04,
            "review_score": 0.58 + index * 0.035,
            "brand_strength": 0.50 + index * 0.05,
        }
        for index in range(5)
    ]


def run_child(population_size: int, rounds: int, seed: int) -> dict[str, Any]:
    os.environ["ENABLE_TINYTROUPE"] = "false"
    os.environ["ENABLE_OASIS"] = "false"
    process = psutil.Process(os.getpid())
    baseline_rss = int(process.memory_info().rss)
    peak_rss = [baseline_rss]
    stop = threading.Event()
    sampler = threading.Thread(
        target=_memory_sampler,
        args=(process, stop, peak_rss),
        daemon=True,
    )
    sampler.start()

    profile = load_calibration_profile()
    cpu_started = time.process_time()
    wall_started = time.perf_counter()
    population_started = time.perf_counter()
    population = PopulationGenerator(
        seed=seed,
        calibration_profile=profile,
    ).generate(
        population_size,
        study_type="PRODUCT_VALIDATION",
        category="PET_WATER_FOUNTAIN",
    )
    population_seconds = time.perf_counter() - population_started
    dataframe_bytes = int(population.memory_usage(index=True, deep=True).sum())

    simulation_started = time.perf_counter()
    result = SimulationEngine(
        seed=seed,
        calibration_profile=profile,
    ).run_simulation(
        population_df=population,
        study_type="PRODUCT_VALIDATION",
        price=1_290.0,
        ref_price=1_190.0,
        brand_awareness=0.18,
        mc_rounds=rounds,
        competitors=_competitors(),
        plan_code="PROFESSIONAL",
        variable_cost=520.0,
    )
    simulation_seconds = time.perf_counter() - simulation_started
    total_seconds = time.perf_counter() - wall_started
    cpu_seconds = time.process_time() - cpu_started
    result_bytes = len(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    )
    final_rss = int(process.memory_info().rss)
    peak_rss[0] = max(peak_rss[0], final_rss)
    stop.set()
    sampler.join(timeout=1.0)

    plan = get_plan_config("PROFESSIONAL")
    return {
        "schema_version": "phase4-native-benchmark-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_scope": "native_compute_only_no_web_no_llm",
        "population_size": population_size,
        "mc_rounds": rounds,
        "scenario_count": len(result.get("scenarios", [])),
        "elasticity_point_count": len(result.get("price_elasticity", [])),
        "evaluated_variant_count": (
            len(result.get("scenarios", []))
            + len(result.get("price_elasticity", []))
        ),
        "competitor_count": 5,
        "seed": seed,
        "plan_code": plan.code,
        "plan_config_version": PLAN_CONFIG_VERSION,
        "world_model_version": WORLD_MODEL_VERSION,
        "model_family": plan.model_family,
        "timing_seconds": {
            "population_generation": round(population_seconds, 4),
            "quantitative_simulation": round(simulation_seconds, 4),
            "total": round(total_seconds, 4),
            "process_cpu": round(cpu_seconds, 4),
        },
        "memory_mib": {
            "baseline_rss": round(baseline_rss / 2**20, 3),
            "peak_rss": round(peak_rss[0] / 2**20, 3),
            "final_rss": round(final_rss / 2**20, 3),
            "population_dataframe_deep": round(dataframe_bytes / 2**20, 3),
        },
        "result_payload_kib": round(result_bytes / 2**10, 3),
        "mean_purchase_rate": result.get("mean_purchase_rate"),
        "external_api_calls": 0,
        "llm_calls": 0,
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "logical_cpu_count": psutil.cpu_count(logical=True),
        },
    }


def run_parent(
    populations: list[int],
    rounds: int,
    seed: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for population_size in populations:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            "--population",
            str(population_size),
            "--mc-rounds",
            str(rounds),
            "--seed",
            str(seed),
        ]
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"benchmark failed for population={population_size}: "
                f"{completed.stderr[-2000:]}"
            )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        results.append(json.loads(lines[-1]))
    return {
        "schema_version": "phase4-native-benchmark-suite-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope_disclosure": (
            "Local technical baseline for deterministic native compute only; "
            "not an end-to-end customer-run duration or Cloud Run measurement."
        ),
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--population", type=int)
    parser.add_argument(
        "--populations",
        default=",".join(str(value) for value in DEFAULT_POPULATIONS),
    )
    parser.add_argument("--mc-rounds", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.child:
        if not args.population or args.population <= 0:
            raise ValueError("--population must be positive in child mode")
        payload = run_child(args.population, args.mc_rounds, args.seed)
    else:
        populations = [
            int(item.strip())
            for item in str(args.populations).split(",")
            if item.strip()
        ]
        payload = run_parent(populations, args.mc_rounds, args.seed)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
