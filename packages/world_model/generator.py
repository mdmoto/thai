"""
Thailand World Model Population Generator (Version TH-WORLD-2026.07.1)
Generates synthetic Thai consumers based on demographic distributions,
psychographic behavior parameters, and industry-specific profiles.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

WORLD_MODEL_VERSION = "TH-WORLD-2026.07.1"

PROVINCES = ["Bangkok", "Chiang Mai", "Phuket", "Chonburi", "Khon Kaen", "Nonthaburi"]
PROVINCE_PROBS = [0.45, 0.20, 0.15, 0.10, 0.05, 0.05]

INCOME_TIERS = ["LOW (<15k THB)", "MID_LOW (15-30k THB)", "MID_HIGH (30-60k THB)", "HIGH (60-120k THB)", "LUXURY (>120k THB)"]
INCOME_PROBS = [0.25, 0.35, 0.25, 0.10, 0.05]

AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_PROBS = [0.20, 0.35, 0.25, 0.12, 0.08]


class PopulationGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def generate(self, size: int, study_type: str = "PRODUCT_VALIDATION") -> pd.DataFrame:
        """Generates a synthetic population dataframe of specified size."""
        person_ids = [f"TH_{i+1:07d}" for i in range(size)]
        
        # Demographic fields
        ages = self.rng.choice(AGE_GROUPS, size=size, p=AGE_PROBS)
        genders = self.rng.choice(["Female", "Male", "Non-binary"], size=size, p=[0.54, 0.43, 0.03])
        provinces = self.rng.choice(PROVINCES, size=size, p=PROVINCE_PROBS)
        income_tiers = self.rng.choice(INCOME_TIERS, size=size, p=INCOME_PROBS)
        is_tourist = self.rng.choice([False, True], size=size, p=[0.88, 0.12])

        # Psychographic parameters [0.0 - 1.0]
        # Price sensitivity varies inversely with income
        income_idx = [INCOME_TIERS.index(t) for t in income_tiers]
        base_price_sens = 0.9 - (np.array(income_idx) * 0.18)
        price_sensitivity = np.clip(base_price_sens + self.rng.normal(0, 0.1, size=size), 0.05, 0.98)
        
        brand_sensitivity = np.clip(0.3 + (np.array(income_idx) * 0.12) + self.rng.normal(0, 0.1, size=size), 0.1, 0.95)
        novelty_seeking = np.clip(self.rng.beta(2, 2, size=size), 0.05, 0.95)
        review_sensitivity = np.clip(self.rng.beta(3, 1.5, size=size), 0.1, 0.99)
        convenience_preference = np.clip(self.rng.beta(2.5, 2, size=size), 0.1, 0.98)
        social_influence = np.clip(self.rng.beta(2, 3, size=size), 0.05, 0.95)

        # Category specific fields
        has_pets = self.rng.choice([True, False], size=size, p=[0.42, 0.58])
        pet_spend_monthly = np.where(has_pets, np.clip(self.rng.lognormal(6.5, 0.5, size=size), 200, 15000), 0)

        coffee_freq_weekly = self.rng.poisson(lam=4.2, size=size)
        nightlife_freq_monthly = self.rng.poisson(lam=2.1, size=size)
        dining_out_weekly = self.rng.poisson(lam=5.5, size=size)

        df = pd.DataFrame({
            "person_id": person_ids,
            "age_group": ages,
            "gender": genders,
            "province": provinces,
            "income_tier": income_tiers,
            "is_tourist": is_tourist,
            "price_sensitivity": np.round(price_sensitivity, 3),
            "brand_sensitivity": np.round(brand_sensitivity, 3),
            "novelty_seeking": np.round(novelty_seeking, 3),
            "review_sensitivity": np.round(review_sensitivity, 3),
            "convenience_preference": np.round(convenience_preference, 3),
            "social_influence": np.round(social_influence, 3),
            "has_pets": has_pets,
            "pet_spend_monthly": np.round(pet_spend_monthly, 0),
            "coffee_freq_weekly": coffee_freq_weekly,
            "nightlife_freq_monthly": nightlife_freq_monthly,
            "dining_out_weekly": dining_out_weekly,
            "world_model_version": WORLD_MODEL_VERSION
        })

        return df

    def segment_population(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Segments population into 5 commercial segments."""
        total = len(df)
        
        seg1 = df[(df["has_pets"] == True) & (df["gender"] == "Female")]
        seg2 = df[(df["income_tier"].isin(["MID_HIGH (30-60k THB)", "HIGH (60-120k THB)", "LUXURY (>120k THB)"]))]
        seg3 = df[(df["age_group"].isin(["18-24", "25-34"]))]
        seg4 = df[(df["province"] != "Bangkok")]
        
        segments = [
          {
            "segment_id": "seg_01",
            "name": "宠物专属主妇",
            "size": len(seg1),
            "share": round(len(seg1) / total, 3),
            "avg_price_sensitivity": round(float(seg1["price_sensitivity"].mean()), 2) if len(seg1) > 0 else 0.5,
          },
          {
            "segment_id": "seg_02",
            "name": "都市白领消费人群",
            "size": len(seg2),
            "share": round(len(seg2) / total, 3),
            "avg_price_sensitivity": round(float(seg2["price_sensitivity"].mean()), 2) if len(seg2) > 0 else 0.4,
          },
          {
            "segment_id": "seg_03",
            "name": "年轻单身潮流受众",
            "size": len(seg3),
            "share": round(len(seg3) / total, 3),
            "avg_price_sensitivity": round(float(seg3["price_sensitivity"].mean()), 2) if len(seg3) > 0 else 0.6,
          },
          {
            "segment_id": "seg_04",
            "name": "区域外省家庭人口",
            "size": len(seg4),
            "share": round(len(seg4) / total, 3),
            "avg_price_sensitivity": round(float(seg4["price_sensitivity"].mean()), 2) if len(seg4) > 0 else 0.7,
          },
        ]
        return segments
