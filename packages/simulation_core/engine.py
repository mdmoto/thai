"""
Simulation Engine Core
Combines World Model synthetic population, representative LLM Agent responses,
and Monte Carlo iterations to evaluate purchase, visit, and revenue metrics.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

SIMULATION_MODEL_VERSION = "SIM-1.2.0"

class SimulationEngine:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def run_simulation(
        self,
        population_df: pd.DataFrame,
        study_type: str,
        price: float = 299.0,
        ref_price: float = 280.0,
        brand_awareness: float = 0.43,
        mc_rounds: int = 50,
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Runs vector Monte Carlo simulation across synthetic population.
        """
        n = len(population_df)
        price_sens = population_df["price_sensitivity"].values
        brand_sens = population_df["brand_sensitivity"].values
        review_sens = population_df["review_sensitivity"].values
        novelty = population_df["novelty_seeking"].values
        
        price_gap = np.log(max(0.1, price) / max(0.1, ref_price))

        # Core utility formula
        # U = functional_fit - beta_price * price_sens * price_gap + brand_boost + review_effect
        base_utility = (
            0.5 
            + 0.6 * novelty 
            - 1.8 * price_sens * price_gap 
            + 0.4 * brand_sens 
            + 0.3 * review_sens
        )

        mc_purchase_rates = []
        mc_revenue_indices = []

        for round_idx in range(mc_rounds):
            round_seed = self.seed + round_idx
            round_rng = np.random.default_rng(round_seed)
            
            # Stochastic noise for exposure, social proof, and weather
            exposure_noise = round_rng.normal(0, 0.15, size=n)
            threshold_noise = round_rng.logistic(0, 0.3, size=n)
            
            logit_p = base_utility + exposure_noise
            p_purchase = 1.0 / (1.0 + np.exp(-logit_p))
            
            # Filter by exposure
            exposed_mask = round_rng.uniform(0, 1, size=n) < brand_awareness
            actual_purchased = (p_purchase > (0.5 + threshold_noise)) & exposed_mask
            
            p_rate = np.mean(actual_purchased)
            mc_purchase_rates.append(p_rate)
            mc_revenue_indices.append(p_rate * price)

        mean_purchase_rate = float(np.mean(mc_purchase_rates))
        p10 = float(np.percentile(mc_purchase_rates, 10))
        p90 = float(np.percentile(mc_purchase_rates, 90))

        # Run Scenarios
        scenario_results = []
        if not scenarios:
            scenarios = [
                {"name": "基准方案 A\nTHB 299 / 全渠道", "price": price, "awareness": brand_awareness},
                {"name": "方案 B\nTHB 249 / Lazada 主推", "price": price * 0.83, "awareness": brand_awareness * 1.15},
                {"name": "方案 C\nTHB 339 / 高端定位", "price": price * 1.13, "awareness": brand_awareness * 0.9},
                {"name": "方案 D\nTHB 299 / 全渠道 + KOL 推广", "price": price, "awareness": brand_awareness * 1.35},
            ]

        for sc in scenarios:
            sc_price = sc.get("price", price)
            sc_awareness = min(0.95, sc.get("awareness", brand_awareness))
            sc_gap = np.log(max(0.1, sc_price) / max(0.1, ref_price))
            
            sc_utility = (
                0.5 
                + 0.6 * novelty 
                - 1.8 * price_sens * sc_gap 
                + 0.4 * brand_sens 
                + 0.3 * review_sens
            )
            sc_p = 1.0 / (1.0 + np.exp(-sc_utility))
            sc_rate = float(np.mean(sc_p * sc_awareness))
            
            scenario_results.append({
                "name": sc["name"],
                "purchase_rate": round(sc_rate, 3),
                "revenue_idx": round((sc_rate * sc_price) / (mean_purchase_rate * price) * 100, 1) if mean_purchase_rate > 0 else 100,
                "margin_idx": round((sc_rate * (sc_price * 0.5)) / (mean_purchase_rate * (price * 0.5)) * 100, 1) if mean_purchase_rate > 0 else 100
            })

        return {
            "simulation_model_version": SIMULATION_MODEL_VERSION,
            "population_size": n,
            "mc_rounds": mc_rounds,
            "mean_purchase_rate": round(mean_purchase_rate, 3),
            "ci_p10": round(p10, 3),
            "ci_p90": round(p90, 3),
            "scenarios": scenario_results
        }
