"""Build a consumer-products calibration profile from official NSO margins."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import numpy as np


PROFILE_VERSION = "TH-CONSUMER-MACRO-2026.07.1"
TIER_ORDER = ["LOW", "MID_LOW", "MID_HIGH", "HIGH", "LUXURY"]
HOUSEHOLD_TIER_FIELDS = {
    "LOW": ("INCOME_PER_HH2", "INCOME_PER_HH3", "INCOME_PER_HH4", "INCOME_PER_HH5"),
    "MID_LOW": ("INCOME_PER_HH6", "INCOME_PER_HH7"),
    "MID_HIGH": ("INCOME_PER_HH8",),
    "HIGH": ("INCOME_PER_HH9",),
    "LUXURY": ("INCOME_PER_HH10",),
}
TIER_MIDPOINTS = {
    "LOW": 7_500.0,
    "MID_LOW": 20_000.0,
    "MID_HIGH": 40_000.0,
    "HIGH": 75_000.0,
    "LUXURY": 130_000.0,
}


PROVINCE_GROUPS: Dict[str, Dict[str, str]] = {
    "Bangkok Metro": {
        "กรุงเทพมหานคร": "Bangkok",
        "สมุทรปราการ": "Samut Prakan",
        "นนทบุรี": "Nonthaburi",
        "ปทุมธานี": "Pathum Thani",
    },
    "Central": {
        "พระนครศรีอยุธยา": "Ayutthaya",
        "อ่างทอง": "Ang Thong",
        "ลพบุรี": "Lopburi",
        "สิงห์บุรี": "Sing Buri",
        "ชัยนาท": "Chai Nat",
        "สระบุรี": "Saraburi",
        "จันทบุรี": "Chanthaburi",
        "ตราด": "Trat",
        "ปราจีนบุรี": "Prachin Buri",
        "นครนายก": "Nakhon Nayok",
        "สระแก้ว": "Sa Kaeo",
        "ราชบุรี": "Ratchaburi",
        "กาญจนบุรี": "Kanchanaburi",
        "สุพรรณบุรี": "Suphan Buri",
        "นครปฐม": "Nakhon Pathom",
        "สมุทรสาคร": "Samut Sakhon",
        "สมุทรสงคราม": "Samut Songkhram",
        "เพชรบุรี": "Phetchaburi",
        "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
    },
    "East / EEC": {
        "ชลบุรี": "Chon Buri",
        "ระยอง": "Rayong",
        "ฉะเชิงเทรา": "Chachoengsao",
    },
    "Northeast": {
        "นครราชสีมา": "Nakhon Ratchasima",
        "บุรีรัมย์": "Buri Ram",
        "สุรินทร์": "Surin",
        "ศรีสะเกษ": "Si Sa Ket",
        "อุบลราชธานี": "Ubon Ratchathani",
        "ยโสธร": "Yasothon",
        "ชัยภูมิ": "Chaiyaphum",
        "อำนาจเจริญ": "Amnat Charoen",
        "บึงกาฬ": "Bueng Kan",
        "หนองบัวลำภู": "Nong Bua Lam Phu",
        "ขอนแก่น": "Khon Kaen",
        "อุดรธานี": "Udon Thani",
        "เลย": "Loei",
        "หนองคาย": "Nong Khai",
        "มหาสารคาม": "Maha Sarakham",
        "ร้อยเอ็ด": "Roi Et",
        "กาฬสินธุ์": "Kalasin",
        "สกลนคร": "Sakon Nakhon",
        "นครพนม": "Nakhon Phanom",
        "มุกดาหาร": "Mukdahan",
    },
    "North": {
        "เชียงใหม่": "Chiang Mai",
        "ลำพูน": "Lamphun",
        "ลำปาง": "Lampang",
        "อุตรดิตถ์": "Uttaradit",
        "แพร่": "Phrae",
        "น่าน": "Nan",
        "พะเยา": "Phayao",
        "เชียงราย": "Chiang Rai",
        "แม่ฮ่องสอน": "Mae Hong Son",
        "นครสวรรค์": "Nakhon Sawan",
        "อุทัยธานี": "Uthai Thani",
        "กำแพงเพชร": "Kamphaeng Phet",
        "ตาก": "Tak",
        "สุโขทัย": "Sukhothai",
        "พิษณุโลก": "Phitsanulok",
        "พิจิตร": "Phichit",
        "เพชรบูรณ์": "Phetchabun",
    },
    "South": {
        "นครศรีธรรมราช": "Nakhon Si Thammarat",
        "กระบี่": "Krabi",
        "พังงา": "Phang Nga",
        "ภูเก็ต": "Phuket",
        "สุราษฎร์ธานี": "Surat Thani",
        "ระนอง": "Ranong",
        "ชุมพร": "Chumphon",
        "สงขลา": "Songkhla",
        "สตูล": "Satun",
        "ตรัง": "Trang",
        "พัทลุง": "Phatthalung",
        "ปัตตานี": "Pattani",
        "ยะลา": "Yala",
        "นราธิวาส": "Narathiwat",
    },
}

THAI_TO_REGION = {
    thai_name: region
    for region, provinces in PROVINCE_GROUPS.items()
    for thai_name in provinces
}
THAI_TO_ENGLISH = {
    thai_name: english_name
    for provinces in PROVINCE_GROUPS.values()
    for thai_name, english_name in provinces.items()
}
SES_REGION_CODE = {
    "Bangkok Metro": 1,
    "Central": 2,
    "East / EEC": 2,
    "North": 3,
    "Northeast": 4,
    "South": 5,
}


class CalibrationBuildError(ValueError):
    """Raised when official margins cannot produce a safe profile."""


def _normalize_province(value: Any) -> str:
    name = str(value or "").strip()
    return name[7:] if name.startswith("จังหวัด") else name


def _latest_year(rows: Iterable[Mapping[str, Any]], field: str) -> int:
    years = [int(str(row[field])) for row in rows if row.get(field) not in (None, "")]
    if not years:
        raise CalibrationBuildError(f"No valid years found in field {field}")
    return max(years)


def _normalize_distribution(values: Mapping[str, float]) -> Dict[str, float]:
    total = float(sum(values.values()))
    if total <= 0:
        raise CalibrationBuildError("Cannot normalize an empty distribution")
    return {key: float(value) / total for key, value in values.items()}


def _weighted_mean(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    common = set(values) & set(weights)
    denominator = sum(weights[key] for key in common)
    if denominator <= 0:
        raise CalibrationBuildError("No overlapping values and weights")
    return sum(values[key] * weights[key] for key in common) / denominator


def _population_margins(
    rows: List[Mapping[str, Any]],
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]], Dict[str, float], int]:
    year = _latest_year(rows, "YEAR")
    province_totals: Dict[str, float] = {}
    national_sex: Dict[str, float] = {}
    for row in rows:
        if int(str(row["YEAR"])) != year or str(row["DISTRIC"]).strip() != "รวม":
            continue
        province = _normalize_province(row["PROVINCE"])
        sex = str(row["SEX"]).strip()
        value = float(row["VALUE"])
        if province == "ทั่วประเทศ":
            if sex in {"ชาย", "หญิง"}:
                national_sex[sex] = value
            continue
        if sex == "รวม":
            province_totals[province] = value

    expected = set(THAI_TO_REGION)
    missing = sorted(expected - set(province_totals))
    unexpected = sorted(set(province_totals) - expected)
    if missing or unexpected or len(province_totals) != 77:
        raise CalibrationBuildError(
            f"Province mapping mismatch; missing={missing}, unexpected={unexpected}"
        )

    region_counts: Dict[str, float] = {region: 0.0 for region in PROVINCE_GROUPS}
    province_by_region: Dict[str, Dict[str, float]] = {
        region: {} for region in PROVINCE_GROUPS
    }
    english_population: Dict[str, float] = {}
    for thai_name, population in province_totals.items():
        region = THAI_TO_REGION[thai_name]
        english_name = THAI_TO_ENGLISH[thai_name]
        region_counts[region] += population
        english_population[english_name] = population
        province_by_region[region][english_name] = population

    for region, values in province_by_region.items():
        province_by_region[region] = _normalize_distribution(values)

    if set(national_sex) != {"ชาย", "หญิง"}:
        raise CalibrationBuildError("National male/female totals are unavailable")
    official_binary = _normalize_distribution(national_sex)
    gender = {
        "Female": official_binary["หญิง"] * 0.99,
        "Male": official_binary["ชาย"] * 0.99,
        "Non-binary": 0.01,
    }
    return (
        _normalize_distribution(region_counts),
        province_by_region,
        gender,
        year,
    )


def _income_tiers(
    rows: List[Mapping[str, Any]],
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]], int]:
    year = _latest_year(rows, "YEAR")
    latest = [row for row in rows if int(str(row["YEAR"])) == year]
    by_code = {int(row["CODE_REGION"]): row for row in latest}
    if set(range(6)) - set(by_code):
        raise CalibrationBuildError("Income distribution is missing an NSO region")

    def tiers(row: Mapping[str, Any]) -> Dict[str, float]:
        raw = {
            tier: sum(float(row.get(field) or 0.0) for field in fields)
            for tier, fields in HOUSEHOLD_TIER_FIELDS.items()
        }
        return _normalize_distribution(raw)

    national = tiers(by_code[0])
    regional = {
        region: tiers(by_code[code])
        for region, code in SES_REGION_CODE.items()
    }
    return national, regional, year


def _province_finances(
    rows: List[Mapping[str, Any]],
    english_population: Mapping[str, float],
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], int]:
    year = _latest_year(rows, "year")
    income: Dict[str, float] = {}
    expense: Dict[str, float] = {}
    for row in rows:
        if int(str(row["year"])) != year:
            continue
        if row.get("soc_eco_class1") != "รวมทั้งสิ้น":
            continue
        if row.get("soc_eco_class2") != "รวมทั้งสิ้น":
            continue
        thai_name = _normalize_province(row["province"])
        if thai_name not in THAI_TO_ENGLISH:
            continue
        english_name = THAI_TO_ENGLISH[thai_name]
        metric = str(row["mthincome_mthexp_totaldebt_pctexptoincome"])
        if metric == "รายได้ทั้งสิ้นต่อเดือน":
            income[english_name] = float(row["value"])
        elif metric == "ค่าใช้จ่ายทั้งสิ้นต่อเดือน":
            expense[english_name] = float(row["value"])

    expected = set(english_population)
    if set(income) != expected or set(expense) != expected:
        raise CalibrationBuildError("Province income/expense coverage is incomplete")

    region_income: Dict[str, float] = {}
    province_income_multiplier: Dict[str, float] = {}
    disposable_share: Dict[str, float] = {}
    for region, mapping in PROVINCE_GROUPS.items():
        english_names = [THAI_TO_ENGLISH[name] for name in mapping]
        weights = {name: english_population[name] for name in english_names}
        regional_mean = _weighted_mean(income, weights)
        region_income[region] = regional_mean
        for name in english_names:
            province_income_multiplier[name] = income[name] / regional_mean
            disposable_share[name] = float(
                np.clip(1.0 - expense[name] / max(income[name], 1.0), 0.04, 0.45)
            )
    return region_income, province_income_multiplier, disposable_share, year


def _household_sizes(
    rows: List[Mapping[str, Any]],
) -> Tuple[Dict[str, float], int]:
    year = _latest_year(rows, "Year")
    sizes: Dict[str, float] = {}
    for row in rows:
        if int(str(row["Year"])) != year:
            continue
        thai_name = _normalize_province(row["Province"])
        if thai_name in THAI_TO_ENGLISH:
            sizes[THAI_TO_ENGLISH[thai_name]] = float(row["Value"])
    if len(sizes) != 77:
        raise CalibrationBuildError(
            f"Household-size coverage is {len(sizes)} provinces, expected 77"
        )
    return sizes, year


def build_consumer_products_profile(
    base_profile: Mapping[str, Any],
    rows: Mapping[str, List[Mapping[str, Any]]],
    source_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    profile = copy.deepcopy(dict(base_profile))
    population_rows = rows["registered_population"]
    (
        region,
        province_by_region,
        gender,
        population_year,
    ) = _population_margins(population_rows)

    english_population: Dict[str, float] = {}
    latest_population_year = _latest_year(population_rows, "YEAR")
    for row in population_rows:
        if (
            int(str(row["YEAR"])) == latest_population_year
            and str(row["DISTRIC"]).strip() == "รวม"
            and str(row["SEX"]).strip() == "รวม"
        ):
            thai_name = _normalize_province(row["PROVINCE"])
            if thai_name in THAI_TO_ENGLISH:
                english_population[THAI_TO_ENGLISH[thai_name]] = float(row["VALUE"])

    income_tier, income_tier_by_region, income_year = _income_tiers(
        rows["household_income_distribution"]
    )
    (
        regional_income,
        province_income_multiplier,
        province_disposable_share,
        finance_year,
    ) = _province_finances(
        rows["province_income_expense"],
        english_population,
    )
    household_size, household_size_year = _household_sizes(rows["household_size"])

    region_income_multiplier: Dict[str, float] = {}
    for region_name, distribution in income_tier_by_region.items():
        implied = sum(
            distribution[tier] * TIER_MIDPOINTS[tier] for tier in TIER_ORDER
        )
        region_income_multiplier[region_name] = regional_income[region_name] / implied

    national_population = sum(english_population.values())
    disposable_values = np.array(
        [province_disposable_share[name] for name in english_population],
        dtype=float,
    )
    disposable_weights = np.array(
        [english_population[name] for name in english_population],
        dtype=float,
    )
    disposable_weights = disposable_weights / disposable_weights.sum()
    disposable_mean = float(np.sum(disposable_values * disposable_weights))
    disposable_sd = float(
        math.sqrt(
            np.sum(
                disposable_weights
                * np.square(disposable_values - disposable_mean)
            )
        )
    )

    observed_sources = []
    for source_name, source in source_manifest["sources"].items():
        observed_sources.append(
            {
                "source_id": source["source_id"],
                "source_type": "official_public_aggregate",
                "observed": True,
                "dataset_id": source["dataset_id"],
                "dataset_page": source["dataset_page"],
                "api_url": source["api_url"],
                "license": source["license"],
                "fetched_at": source["fetched_at"],
                "record_count": source["record_count"],
                "sha256": source["sha256"],
                "snapshot_path": source["snapshot_path"],
                "pipeline_key": source_name,
            }
        )

    profile["version"] = PROFILE_VERSION
    profile["base_profile_version"] = base_profile.get("version")
    profile["status"] = "official_macro_calibrated_choice_prior"
    profile["claim"] = (
        "Thailand regional population, binary sex margins, household-income "
        "bands, province income, expenditure residual and household size are "
        "calibrated from versioned NSO public aggregates. Age, behavioral "
        "traits and all discrete-choice coefficients remain unvalidated priors."
    )
    profile["sources"] = observed_sources + [
        source
        for source in base_profile.get("sources", [])
        if not source.get("observed")
    ]
    profile["limitations"] = [
        "Official inputs are aggregate margins, not household microdata; joint dependencies are synthesized.",
        "Registered-population regional shares cover all ages while the simulated decision population starts at age 18.",
        "NSO reports binary sex; the 1% non-binary share remains an explicit engineering prior.",
        "Income and expenditure describe households, not individual wages.",
        "Behavioral traits and category engagement remain development priors.",
        "Choice coefficients, WTP and conversion rates have not been fitted to observed product choices or sales.",
        "Marketplace page prices and review metadata are evidence, not transaction volume or conversion data.",
        "Forecast intervals remain prior-predictive and are not validated forecast intervals.",
    ]
    population = profile["population"]
    population["region"] = region
    population["gender"] = gender
    population["income_tier"] = income_tier
    population["income_tier_by_region"] = income_tier_by_region
    population["income_monthly_thb"] = TIER_MIDPOINTS
    population["region_income_multiplier"] = region_income_multiplier
    population["official_region_household_income_thb"] = regional_income
    population["province_by_region"] = province_by_region
    population["province_income_multiplier"] = province_income_multiplier
    population["province_disposable_income_share"] = province_disposable_share
    population["household_size_by_province"] = household_size
    population["income_basis"] = "household_monthly_income"
    population["official_reference_years"] = {
        "registered_population": population_year - 543,
        "household_income_distribution": income_year - 543,
        "province_income_expense": finance_year - 543,
        "household_size": household_size_year - 543,
    }
    population["registered_population_total"] = int(round(national_population))

    profile["behavior"]["disposable_income_share"] = {
        "mean": disposable_mean,
        "sd": max(0.035, disposable_sd),
        "basis": "one_minus_total_household_expenditure_divided_by_income",
    }
    profile["observed_dimensions"] = [
        "region_population_share",
        "province_population_share",
        "binary_sex_share",
        "household_income_tier_share",
        "province_average_household_income",
        "province_household_expenditure_residual",
        "province_average_household_size",
    ]
    profile["unobserved_dimensions"] = [
        "age_distribution",
        "psychographics",
        "category_penetration",
        "brand_preference",
        "choice_coefficients",
        "purchase_conversion",
        "repeat_purchase",
    ]
    return profile


def write_profile(profile: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
