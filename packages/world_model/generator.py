"""Synthetic Thailand market population with explicit calibration lineage.

The generator creates a joint micro-population from a versioned calibration
profile. The bundled profile combines official aggregate margins with explicit
behavior and choice priors; it is not official household microdata. Callers can
replace or override the profile without changing the simulation engine.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from simulation_core.calibration import load_calibration_profile
from world_model.category_profiles import load_category_profile


WORLD_MODEL_VERSION = "TH-WORLD-2026.07.4"

REGION_PROVINCES = {
    "Bangkok Metro": ["Bangkok", "Nonthaburi", "Pathum Thani", "Samut Prakan"],
    "Central": ["Ayutthaya", "Nakhon Pathom", "Saraburi"],
    "North": ["Chiang Mai", "Chiang Rai", "Lampang"],
    "Northeast": ["Khon Kaen", "Nakhon Ratchasima", "Udon Thani"],
    "East / EEC": ["Chonburi", "Rayong", "Chachoengsao"],
    "South": ["Phuket", "Songkhla", "Surat Thani"],
}

INCOME_ORDER = ["LOW", "MID_LOW", "MID_HIGH", "HIGH", "LUXURY"]


def _clip01(values: np.ndarray, low: float = 0.02, high: float = 0.98) -> np.ndarray:
    return np.clip(values, low, high)


class PopulationGenerator:
    def __init__(
        self,
        seed: int = 42,
        calibration_profile: Optional[Mapping[str, Any]] = None,
    ):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.profile = (
            dict(calibration_profile)
            if calibration_profile is not None
            else load_calibration_profile()
        )

    def _draw_income_tiers(self, regions: np.ndarray) -> np.ndarray:
        population = self.profile["population"]
        regional_distributions = population.get("income_tier_by_region")
        if regional_distributions:
            result = np.empty(len(regions), dtype=object)
            for region in np.unique(regions):
                mask = regions == region
                distribution = regional_distributions[str(region)]
                result[mask] = self.rng.choice(
                    INCOME_ORDER,
                    size=int(mask.sum()),
                    p=[distribution[tier] for tier in INCOME_ORDER],
                )
            return result

        base = np.array(
            [population["income_tier"][tier] for tier in INCOME_ORDER],
            dtype=float,
        )
        centered_tier = np.arange(len(INCOME_ORDER), dtype=float) - 2.0
        multipliers = population["region_income_multiplier"]
        result = np.empty(len(regions), dtype=object)

        for region in np.unique(regions):
            mask = regions == region
            region_multiplier = float(multipliers[region])
            adjusted = base * np.power(region_multiplier, centered_tier)
            adjusted = adjusted / adjusted.sum()
            result[mask] = self.rng.choice(
                INCOME_ORDER,
                size=int(mask.sum()),
                p=adjusted,
            )
        return result

    def _draw_provinces(self, regions: np.ndarray) -> np.ndarray:
        provinces = np.empty(len(regions), dtype=object)
        calibrated = self.profile["population"].get("province_by_region", {})
        for region in np.unique(regions):
            mask = regions == region
            if str(region) in calibrated:
                province_distribution = calibrated[str(region)]
                labels = list(province_distribution)
                probabilities = list(province_distribution.values())
            else:
                labels = REGION_PROVINCES[str(region)]
                probabilities = None
            provinces[mask] = self.rng.choice(
                labels,
                size=int(mask.sum()),
                p=probabilities,
            )
        return provinces

    def _category_engagement(
        self,
        study_type: str,
        online_purchase_frequency: np.ndarray,
        coffee_visits_weekly: np.ndarray,
        dining_out_weekly: np.ndarray,
        nightlife_monthly: np.ndarray,
    ) -> np.ndarray:
        normalized = (study_type or "PRODUCT_VALIDATION").upper()
        if normalized == "CAFE":
            raw = coffee_visits_weekly / 7.0
        elif normalized == "RESTAURANT":
            raw = dining_out_weekly / 6.0
        elif normalized == "BAR":
            raw = nightlife_monthly / 4.0
        elif normalized in {"VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO"}:
            raw = (coffee_visits_weekly + dining_out_weekly) / 12.0
        elif normalized == "RETAIL":
            raw = online_purchase_frequency / 7.0
        else:
            raw = online_purchase_frequency / 8.0
        return _clip01(raw + self.rng.normal(0.0, 0.08, len(raw)))

    def generate(
        self,
        size: int,
        study_type: str = "PRODUCT_VALIDATION",
        category: Optional[str] = None,
    ) -> pd.DataFrame:
        """Generate a reproducible synthetic micro-population."""
        if size <= 0:
            raise ValueError("Population size must be positive")

        population = self.profile["population"]
        behavior = self.profile["behavior"]

        age_labels = list(population["age_group"])
        gender_labels = list(population["gender"])
        region_labels = list(population["region"])

        age_groups = self.rng.choice(
            age_labels,
            size=size,
            p=list(population["age_group"].values()),
        )
        genders = self.rng.choice(
            gender_labels,
            size=size,
            p=list(population["gender"].values()),
        )
        regions = self.rng.choice(
            region_labels,
            size=size,
            p=list(population["region"].values()),
        )
        provinces = self._draw_provinces(regions)
        income_tiers = self._draw_income_tiers(regions)

        income_midpoint = np.array(
            [population["income_monthly_thb"][tier] for tier in income_tiers],
            dtype=float,
        )
        if population.get("income_tier_by_region"):
            region_level_multiplier = np.array(
                [
                    population["region_income_multiplier"][region]
                    for region in regions
                ],
                dtype=float,
            )
            province_level_multiplier = np.array(
                [
                    population.get("province_income_multiplier", {}).get(
                        province,
                        1.0,
                    )
                    for province in provinces
                ],
                dtype=float,
            )
        else:
            region_level_multiplier = np.ones(size, dtype=float)
            province_level_multiplier = np.ones(size, dtype=float)
        monthly_income = (
            income_midpoint
            * region_level_multiplier
            * province_level_multiplier
            * self.rng.lognormal(
                mean=-0.5 * 0.22**2,
                sigma=0.22,
                size=size,
            )
        )
        household_size_by_province = population.get(
            "household_size_by_province",
            {},
        )
        household_size_center = np.array(
            [
                household_size_by_province.get(province, 2.6)
                for province in provinces
            ],
            dtype=float,
        )
        household_size = np.clip(
            np.rint(
                self.rng.normal(
                    household_size_center,
                    0.65,
                    size,
                )
            ),
            1,
            8,
        ).astype(int)
        equivalized_income = monthly_income / np.sqrt(household_size)

        province_disposable = population.get(
            "province_disposable_income_share",
            {},
        )
        if province_disposable:
            disposable_center = np.array(
                [
                    province_disposable.get(
                        province,
                        behavior["disposable_income_share"]["mean"],
                    )
                    for province in provinces
                ],
                dtype=float,
            )
            disposable_noise = max(
                0.025,
                float(behavior["disposable_income_share"]["sd"]) * 0.5,
            )
        else:
            disposable_center = np.full(
                size,
                behavior["disposable_income_share"]["mean"],
                dtype=float,
            )
            disposable_noise = float(
                behavior["disposable_income_share"]["sd"]
            )
        disposable_share = np.clip(
            self.rng.normal(
                disposable_center,
                disposable_noise,
                size,
            ),
            0.04,
            0.55,
        )
        disposable_income = monthly_income * disposable_share

        income_index = np.array(
            [INCOME_ORDER.index(tier) for tier in income_tiers],
            dtype=float,
        )
        age_young = np.isin(age_groups, ["18-24", "25-34"]).astype(float)
        age_senior = np.isin(age_groups, ["55+"]).astype(float)

        online_affinity = self.rng.beta(
            *behavior["online_affinity_beta"],
            size=size,
        )
        online_affinity = _clip01(
            online_affinity + 0.1 * age_young - 0.12 * age_senior
        )
        review_sensitivity = _clip01(
            self.rng.beta(*behavior["review_sensitivity_beta"], size=size)
        )
        novelty_seeking = _clip01(
            self.rng.beta(*behavior["novelty_seeking_beta"], size=size)
            + 0.08 * age_young
            - 0.06 * age_senior
        )
        social_influence = _clip01(
            self.rng.beta(*behavior["social_influence_beta"], size=size)
            + 0.08 * age_young
        )
        local_brand_trust = _clip01(
            self.rng.beta(*behavior["local_brand_trust_beta"], size=size)
        )

        price_sensitivity = _clip01(
            0.88 - 0.16 * income_index + self.rng.normal(0.0, 0.09, size)
        )
        brand_sensitivity = _clip01(
            0.28 + 0.12 * income_index + self.rng.normal(0.0, 0.1, size)
        )
        convenience_preference = _clip01(
            0.42
            + 0.32 * online_affinity
            + self.rng.normal(0.0, 0.1, size)
        )
        quality_sensitivity = _clip01(
            0.35
            + 0.1 * income_index
            + 0.18 * review_sensitivity
            + self.rng.normal(0.0, 0.08, size)
        )

        tourist_probability = np.array(
            [population["tourist_share_by_region"][region] for region in regions]
        )
        is_tourist = self.rng.random(size) < tourist_probability

        has_pets = self.rng.random(size) < float(
            behavior["pet_ownership_probability"]
        )
        pet_spend_monthly = np.where(
            has_pets,
            np.clip(
                self.rng.lognormal(mean=6.35, sigma=0.55, size=size),
                150,
                15_000,
            ),
            0,
        )
        coffee_visits_weekly = self.rng.poisson(
            behavior["coffee_visits_weekly_lambda"],
            size=size,
        )
        dining_out_weekly = self.rng.poisson(
            behavior["dining_out_weekly_lambda"],
            size=size,
        )
        nightlife_monthly = self.rng.poisson(
            behavior["nightlife_monthly_lambda"],
            size=size,
        )
        online_purchase_frequency = self.rng.poisson(
            1.5 + 4.5 * online_affinity,
            size=size,
        )
        category_engagement = self._category_engagement(
            study_type,
            online_purchase_frequency,
            coffee_visits_weekly,
            dining_out_weekly,
            nightlife_monthly,
        )
        category_profile = load_category_profile(category)
        category_key = str(category_profile["category_key"])
        eligibility_profile = category_profile["eligibility"]
        if eligibility_profile.get("field") == "has_pets":
            category_eligible = has_pets
            pet_spend_intensity = np.clip(
                np.log1p(pet_spend_monthly) / np.log1p(15_000.0),
                0.0,
                1.0,
            )
            engagement_profile = category_profile["engagement"]
            category_engagement = np.clip(
                category_eligible.astype(float)
                * (
                    float(engagement_profile["online_purchase_weight"])
                    * category_engagement
                    + float(engagement_profile["pet_spend_weight"])
                    * pet_spend_intensity
                ),
                0.0,
                0.98,
            )
        else:
            category_eligible = np.ones(size, dtype=bool)

        distance_km = np.clip(self.rng.gamma(shape=2.0, scale=1.6, size=size), 0.1, 20)
        travel_tolerance_km = np.clip(
            2.0
            + 4.0 * convenience_preference
            + 2.0 * category_engagement
            + self.rng.normal(0.0, 0.8, size),
            1.0,
            15.0,
        )
        promptpay_preference = _clip01(
            0.25 + 0.65 * online_affinity + self.rng.normal(0.0, 0.08, size)
        )
        cod_preference = _clip01(
            0.75
            - 0.6 * online_affinity
            + 0.15 * price_sensitivity
            + self.rng.normal(0.0, 0.08, size)
        )

        frame = pd.DataFrame(
            {
                "person_id": [f"TH_{index + 1:07d}" for index in range(size)],
                "age_group": age_groups,
                "gender": genders,
                "region": regions,
                "province": provinces,
                "income_tier": income_tiers,
                "monthly_income_thb": np.round(monthly_income, 0),
                "household_monthly_income_thb": np.round(monthly_income, 0),
                "equivalized_income_thb": np.round(equivalized_income, 0),
                "household_size": household_size,
                "disposable_income_thb": np.round(disposable_income, 0),
                "is_tourist": is_tourist,
                "price_sensitivity": np.round(price_sensitivity, 4),
                "brand_sensitivity": np.round(brand_sensitivity, 4),
                "quality_sensitivity": np.round(quality_sensitivity, 4),
                "novelty_seeking": np.round(novelty_seeking, 4),
                "review_sensitivity": np.round(review_sensitivity, 4),
                "convenience_preference": np.round(
                    convenience_preference,
                    4,
                ),
                "social_influence": np.round(social_influence, 4),
                "local_brand_trust": np.round(local_brand_trust, 4),
                "online_affinity": np.round(online_affinity, 4),
                "promptpay_preference": np.round(promptpay_preference, 4),
                "cod_preference": np.round(cod_preference, 4),
                "has_pets": has_pets,
                "pet_spend_monthly": np.round(pet_spend_monthly, 0),
                "coffee_freq_weekly": coffee_visits_weekly,
                "nightlife_freq_monthly": nightlife_monthly,
                "dining_out_weekly": dining_out_weekly,
                "online_purchase_freq_monthly": online_purchase_frequency,
                "category_engagement": np.round(category_engagement, 4),
                "category_eligible": category_eligible,
                "category_key": category_key,
                "category_profile_version": category_profile["version"],
                "category_eligibility_status": eligibility_profile["status"],
                "distance_km": np.round(distance_km, 3),
                "travel_tolerance_km": np.round(travel_tolerance_km, 3),
                "sample_weight": np.ones(size, dtype=float),
                "study_type_profile": (study_type or "PRODUCT_VALIDATION").upper(),
                "world_model_version": WORLD_MODEL_VERSION,
                "calibration_profile_version": self.profile["version"],
                "calibration_status": self.profile["status"],
            }
        )
        frame["segment_id"] = self._assign_segments(frame)
        return frame

    def _assign_segments(self, frame: pd.DataFrame) -> np.ndarray:
        conditions = [
            (frame["income_tier"].isin(["HIGH", "LUXURY"]))
            & (frame["online_affinity"] >= 0.55),
            (frame["age_group"].isin(["18-24", "25-34"]))
            & (frame["novelty_seeking"] >= 0.6),
            frame["price_sensitivity"] >= 0.72,
            (frame["online_affinity"] < 0.42)
            & (frame["local_brand_trust"] >= 0.55),
        ]
        labels = [
            "AFFLUENT_DIGITAL",
            "TREND_EXPLORER",
            "VALUE_SEEKER",
            "LOCAL_TRUST_OFFLINE",
        ]
        return np.select(conditions, labels, default="MAINSTREAM")

    def segment_population(self, frame: pd.DataFrame) -> List[Dict[str, Any]]:
        total_weight = float(frame["sample_weight"].sum())
        output: List[Dict[str, Any]] = []
        for segment_id, group in frame.groupby("segment_id", sort=True):
            weight = float(group["sample_weight"].sum())
            output.append(
                {
                    "segment_id": segment_id,
                    "name": segment_id.replace("_", " ").title(),
                    "size": int(round(weight)),
                    "share": round(weight / total_weight, 4),
                    "avg_price_sensitivity": round(
                        float(np.average(
                            group["price_sensitivity"],
                            weights=group["sample_weight"],
                        )),
                        3,
                    ),
                    "avg_category_engagement": round(
                        float(np.average(
                            group["category_engagement"],
                            weights=group["sample_weight"],
                        )),
                        3,
                    ),
                }
            )
        return output

    def stratified_sample(
        self,
        frame: pd.DataFrame,
        sample_size: int,
        strata: Optional[Sequence[str]] = None,
        seed: Optional[int] = None,
    ) -> pd.DataFrame:
        """Sample representative rows and attach population expansion weights."""
        if sample_size <= 0:
            return frame.iloc[0:0].copy()
        if sample_size >= len(frame):
            sampled = frame.copy()
            sampled["expansion_weight"] = sampled["sample_weight"]
            return sampled

        if strata is None:
            if sample_size < 30:
                strata = ("region",)
            elif sample_size < 100:
                strata = ("region", "income_tier")
            else:
                strata = ("region", "income_tier", "age_group")

        random_state = self.seed if seed is None else seed
        grouped: List[Tuple[Any, pd.DataFrame]] = list(
            frame.groupby(list(strata), observed=True, sort=True)
        )
        sizes = np.array([len(group) for _, group in grouped], dtype=int)
        ideal = sample_size * sizes / sizes.sum()
        allocation = np.floor(ideal).astype(int)

        if sample_size >= len(grouped):
            allocation = np.maximum(allocation, 1)

        allocation = np.minimum(allocation, sizes)
        while allocation.sum() > sample_size:
            candidates = np.where(allocation > 1)[0]
            if len(candidates) == 0:
                candidates = np.where(allocation > 0)[0]
            index = candidates[np.argmax(allocation[candidates] - ideal[candidates])]
            allocation[index] -= 1
        while allocation.sum() < sample_size:
            candidates = np.where(allocation < sizes)[0]
            index = candidates[np.argmax(ideal[candidates] - allocation[candidates])]
            allocation[index] += 1

        sampled_groups: List[pd.DataFrame] = []
        for group_index, ((_, group), count) in enumerate(zip(grouped, allocation)):
            if count <= 0:
                continue
            part = group.sample(
                n=int(count),
                replace=False,
                random_state=random_state + group_index,
            ).copy()
            population_weight = float(group["sample_weight"].sum())
            part["expansion_weight"] = population_weight / float(count)
            sampled_groups.append(part)

        return pd.concat(sampled_groups, ignore_index=True)
