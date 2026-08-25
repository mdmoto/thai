"""Supported country definitions kept outside the simulation engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CountryConfig:
    code: str
    name_en: str
    name_zh: str
    currency_code: str
    currency_symbol: str
    default_price: float
    locale: str
    profile_file: str
    administrative_label_zh: str
    default_marketplaces: tuple[str, ...]
    search_languages: tuple[str, ...]
    supported_study_types: tuple[str, ...]


COMMON_STUDY_TYPES = (
    "PRODUCT_VALIDATION",
    "PRICING_STUDY",
    "VENUE_STUDY",
    "SITE_COMPARISON",
    "CREATIVE_TEST",
    "OPERATING_SCENARIO",
)


COUNTRIES = {
    "TH": CountryConfig(
        code="TH",
        name_en="Thailand",
        name_zh="泰国",
        currency_code="THB",
        currency_symbol="฿",
        default_price=299.0,
        locale="th-TH",
        profile_file="thailand_consumer_products_macro_v1.json",
        administrative_label_zh="府",
        default_marketplaces=("Shopee Thailand", "Lazada Thailand", "TikTok Shop Thailand"),
        search_languages=("Thai", "English"),
        supported_study_types=COMMON_STUDY_TYPES,
    ),
    "MY": CountryConfig(
        code="MY",
        name_en="Malaysia",
        name_zh="马来西亚",
        currency_code="MYR",
        currency_symbol="RM",
        default_price=59.0,
        locale="ms-MY",
        profile_file="malaysia_consumer_products_macro_v1.json",
        administrative_label_zh="州/联邦直辖区",
        default_marketplaces=("Shopee Malaysia", "Lazada Malaysia", "TikTok Shop Malaysia"),
        search_languages=("Malay", "English", "Chinese"),
        supported_study_types=COMMON_STUDY_TYPES,
    ),
}


def get_country_config(country_code: str | None) -> CountryConfig:
    normalized = str(country_code or "TH").strip().upper()
    if normalized not in COUNTRIES:
        raise ValueError(f"Unsupported country code: {normalized}")
    return COUNTRIES[normalized]
