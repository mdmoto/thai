"""Category adapter for Thailand pet water-fountain competitor evidence."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import httpx

from data_pipeline.product_pages import (
    ProductPageError,
    PublicProductPageCollector,
)


CATEGORY_VERSION = "TH-PET-WATER-FOUNTAIN-2026.07.2"
CATEGORY_KEY = "PET_WATER_FOUNTAIN"

SEARCH_TERMS = {
    "th": [
        "น้ำพุแมว",
        "น้ำพุแมวอัตโนมัติ",
        "เครื่องให้น้ำแมวอัตโนมัติ",
        "น้ำพุสัตว์เลี้ยง",
        "น้ำพุแมวไร้สาย",
    ],
    "en": [
        "cat water fountain Thailand",
        "smart pet water fountain Thailand",
        "wireless pet drinking fountain Thailand",
    ],
}

KNOWN_BRANDS = (
    "ALECTRIC",
    "CATIT",
    "ELSPET",
    "HOMERUNPET",
    "NOTTY",
    "PANDO",
    "PETKIT",
    "PETSNOWY",
    "THAI SUN SPORT",
)


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _category_prior_attributes(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Map observed seller claims into explicit, unvalidated model priors."""
    claims = record.get("page_claims") or {}
    stages = float(claims.get("filtration_stages") or 2.0)
    capacity = float(claims.get("capacity_liters") or 2.0)
    warranty = float(claims.get("warranty_years") or 0.0)
    rating = record.get("rating")

    quality_score = _clip(
        0.42
        + 0.035 * _clip(stages - 2.0, 0.0, 3.0)
        + 0.08 * bool(claims.get("uv_sterilization"))
        + 0.06 * bool(claims.get("stainless_surface"))
        + 0.05 * bool(claims.get("food_grade"))
        + 0.05 * bool(claims.get("low_water_protection"))
        + 0.05 * _clip(warranty, 0.0, 2.0),
    )
    convenience_score = _clip(
        0.40
        + 0.12 * bool(claims.get("app_connected"))
        + 0.10 * bool(claims.get("battery_powered"))
        + 0.06 * bool(claims.get("sensor"))
        + 0.04 * bool(claims.get("low_water_protection"))
        + 0.04 * _clip(capacity - 1.5, 0.0, 2.0),
    )
    review_score = (
        _clip(float(rating) / 5.0)
        if rating not in (None, "")
        else 0.5
    )
    claim_fields = (
        "capacity_liters",
        "filtration_stages",
        "warranty_years",
        "app_connected",
        "battery_powered",
        "uv_sterilization",
        "stainless_surface",
        "food_grade",
        "low_water_protection",
        "sensor",
    )
    observed_claim_fields = [
        field
        for field in claim_fields
        if claims.get(field) not in (None, False, "")
    ]
    return {
        "quality_score": round(quality_score, 4),
        "convenience_score": round(convenience_score, 4),
        "review_score": round(review_score, 4),
        "localization_score": 0.58 if warranty >= 1 else 0.48,
        "design_score": 0.6 if claims.get("app_connected") else 0.52,
        "mapping_status": "category_attribute_prior_unvalidated",
        "observed_claim_fields": observed_claim_fields,
        "unobserved_claim_fields": sorted(
            set(claim_fields) - set(observed_claim_fields)
        ),
        "mapping_basis": [
            "filtration_stages",
            "uv_sterilization",
            "material_claims",
            "low_water_protection",
            "warranty",
            "app_or_battery_convenience",
            "capacity",
        ],
    }


def _price_summary(prices: List[float]) -> Dict[str, float]:
    ordered = sorted(prices)

    def percentile(fraction: float) -> float:
        position = (len(ordered) - 1) * fraction
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return (
            ordered[lower] * (upper - position)
            + ordered[upper] * (position - lower)
        )

    return {
        "minimum_thb": round(ordered[0], 2),
        "p25_thb": round(percentile(0.25), 2),
        "median_thb": round(statistics.median(ordered), 2),
        "p75_thb": round(percentile(0.75), 2),
        "maximum_thb": round(ordered[-1], 2),
    }


def _infer_brand(record: Mapping[str, Any]) -> Optional[str]:
    if record.get("brand"):
        return str(record["brand"]).strip().upper()
    name = str(record.get("name") or "").upper()
    for brand in KNOWN_BRANDS:
        if brand in name:
            return brand
    return None


def _representative_choice_set(
    competitors: Sequence[Mapping[str, Any]],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    ordered = sorted(competitors, key=lambda item: float(item["price"]))
    if len(ordered) <= limit:
        return [dict(item) for item in ordered]
    indices = {
        round(index * (len(ordered) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [dict(ordered[index]) for index in sorted(indices)]


def _median_attribute_profile(
    products: Sequence[Mapping[str, Any]],
) -> Dict[str, float]:
    fields = (
        "quality_score",
        "review_score",
        "design_score",
        "convenience_score",
        "localization_score",
    )
    return {
        field: round(
            statistics.median(
                float(product["category_attributes"][field])
                for product in products
            ),
            4,
        )
        for field in fields
    }


class PetWaterFountainPanel:
    def __init__(
        self,
        collector: Optional[PublicProductPageCollector] = None,
    ):
        self.collector = collector or PublicProductPageCollector()

    def collect(self, urls: Sequence[str]) -> Dict[str, Any]:
        products: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        seen_pages = set()
        for url in urls:
            if url in seen_pages:
                continue
            seen_pages.add(url)
            try:
                record = self.collector.collect(url)
            except (ProductPageError, httpx.HTTPError) as error:
                errors.append(
                    {
                        "url": url,
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
                continue
            if record.get("currency") not in (None, "THB"):
                errors.append(
                    {
                        "url": url,
                        "error_type": "CurrencyMismatch",
                        "message": f"Expected THB, got {record.get('currency')}",
                    }
                )
                continue
            if record.get("price") is None:
                errors.append(
                    {
                        "url": url,
                        "error_type": "MissingPrice",
                        "message": "No public structured price was available",
                    }
                )
                continue
            record["brand"] = _infer_brand(record)
            record["category_key"] = CATEGORY_KEY
            record["category_attributes"] = _category_prior_attributes(record)
            products.append(record)

        if len(products) < 5:
            raise ProductPageError(
                f"Only {len(products)} valid products were collected; at least 5 are required"
            )

        prices = [float(product["price"]) for product in products]
        competitor_data = []
        for product in products:
            attributes = product["category_attributes"]
            competitor = self.collector.to_competitor_data(product)
            competitor.update(
                {
                    "quality_score": attributes["quality_score"],
                    "convenience_score": attributes["convenience_score"],
                    "review_score": attributes["review_score"],
                    "localization_score": attributes["localization_score"],
                    "design_score": attributes["design_score"],
                    "data_quality": (
                        "public_price_and_seller_claims_with_unvalidated_"
                        "category_attribute_mapping"
                    ),
                }
            )
            competitor["evidence"]["category_mapping_status"] = attributes[
                "mapping_status"
            ]
            competitor["evidence"]["observed_claim_fields"] = attributes[
                "observed_claim_fields"
            ]
            competitor["evidence"]["unobserved_claim_fields"] = attributes[
                "unobserved_claim_fields"
            ]
            competitor_data.append(competitor)

        price_summary = _price_summary(prices)
        benchmark_attributes = _median_attribute_profile(products)
        benchmark_attributes.update(
            {
                "clarity_score": 0.65,
                "social_proof_score": 0.35,
                "brand_strength": 0.2,
            }
        )
        professional_choice_set = _representative_choice_set(
            competitor_data,
            limit=5,
        )
        return {
            "schema_version": "1",
            "panel_version": CATEGORY_VERSION,
            "category_key": CATEGORY_KEY,
            "category_name_zh": "宠物智能饮水机",
            "category_name_th": "น้ำพุสัตว์เลี้ยงอัตโนมัติ",
            "market": "Thailand",
            "currency": "THB",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "search_terms": SEARCH_TERMS,
            "product_count": len(products),
            "offer_count": len(products),
            "retailer_count": len(
                {product["source_domain"] for product in products}
            ),
            "price_summary": price_summary,
            "products": products,
            "simulation_competitors": competitor_data,
            "professional_choice_set": professional_choice_set,
            "benchmark_study_input": {
                "name": "泰国宠物智能饮水机新品基准",
                "product_name": "New Entrant Pet Water Fountain",
                "study_type": "PRODUCT_VALIDATION",
                "plan_code": "PROFESSIONAL",
                "category": CATEGORY_KEY,
                "price": price_summary["median_thb"],
                "reference_price": price_summary["median_thb"],
                "brand_awareness": 0.12,
                "product_attributes": benchmark_attributes,
                "competitor_data": professional_choice_set,
            },
            "benchmark_assumptions": {
                "focal_price": "observed_public_offer_median",
                "focal_attributes": (
                    "median_of_unvalidated_category_attribute_mappings"
                ),
                "brand_awareness": (
                    "new_entrant_engineering_prior_not_observed"
                ),
                "competitor_selection": (
                    "five_price_quantile_offers_for_professional_plan"
                ),
            },
            "collection_errors": errors,
            "coverage": {
                "observed": [
                    "public_offer_price",
                    "availability",
                    "seller_or_brand_feature_claims",
                    "page_hash",
                ],
                "not_observed": [
                    "units_sold",
                    "conversion_rate",
                    "true_brand_awareness",
                    "market_share",
                    "returns",
                    "repeat_purchase",
                ],
                "claim": (
                    "The panel is a public offer and product-claim snapshot, "
                    "not a transaction or market-share dataset."
                ),
            },
        }


def write_panel(panel: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(panel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
