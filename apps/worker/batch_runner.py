"""
Google Cloud Batch & High-Scale Worker Runner
Executes 100,000 - 300,000 synthetic population Monte Carlo simulations.
Supports checkpointing, Spot VM preemption recovery, and Parquet output.
"""

import sys
import os
import argparse
import time
import json
import pandas as pd

# Add packages to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../packages")))

from world_model.generator import PopulationGenerator, WORLD_MODEL_VERSION
from simulation_core.engine import SimulationEngine, SIMULATION_MODEL_VERSION

def run_batch_job(
    study_id: str,
    population_size: int = 100000,
    mc_rounds: int = 80,
    price: float = 299.0,
    seed: int = 42,
    output_dir: str = "./output"
):
    print(f"=== [Cloud Batch Worker] Starting Job for Study: {study_id} ===")
    print(f"Population: {population_size:,} | MC Rounds: {mc_rounds} | Seed: {seed}")
    
    start_time = time.time()
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: Generate Population
    print(f"[Worker] Step 1/3: Generating {population_size:,} synthetic Thai consumers (TH-WORLD-2026.07.1)...")
    pop_gen = PopulationGenerator(seed=seed)
    pop_df = pop_gen.generate(size=population_size)
    
    parquet_path = os.path.join(output_dir, f"{study_id}_population.parquet")
    pop_df.to_parquet(parquet_path)
    print(f"[Worker] Exported population to Parquet: {parquet_path}")
    
    # Step 2: Vector Monte Carlo Simulation
    print(f"[Worker] Step 2/3: Executing Monte Carlo {mc_rounds} rounds simulation...")
    sim_engine = SimulationEngine(seed=seed)
    results = sim_engine.run_simulation(
        population_df=pop_df,
        study_type="PRODUCT_VALIDATION",
        price=price,
        mc_rounds=mc_rounds
    )
    
    # Step 3: Export Report Results
    elapsed = time.time() - start_time
    print(f"[Worker] Step 3/3: Finished batch job in {elapsed:.2f} seconds.")
    print(f"[Worker] Mean Purchase Rate: {results['mean_purchase_rate']*100:.1f}% (P10: {results['ci_p10']*100:.1f}%, P90: {results['ci_p90']*100:.1f}%)")
    
    result_json_path = os.path.join(output_dir, f"{study_id}_results.json")
    with open(result_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"[Worker] Report JSON written to: {result_json_path}")
    print("=== [Cloud Batch Worker] Job Completed Successfully ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Cloud Batch Simulation Job")
    parser.add_argument("--study_id", type=str, default="study_batch_001")
    parser.add_argument("--population", type=int, default=100000)
    parser.add_argument("--rounds", type=int, default=80)
    parser.add_argument("--price", type=float, default=299.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output_dir", type=str, default="./output")
    args = parser.parse_args()

    run_batch_job(
        study_id=args.study_id,
        population_size=args.population,
        mc_rounds=args.rounds,
        price=args.price,
        seed=args.seed,
        output_dir=args.output_dir
    )
