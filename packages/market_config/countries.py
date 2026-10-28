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
    "ID": CountryConfig(
        code="ID",
        name_en="Indonesia",
        name_zh="印度尼西亚",
        currency_code="IDR",
        currency_symbol="Rp",
        default_price=199000.0,
        locale="id-ID",
        profile_file="indonesia_consumer_products_macro_v1.json",
        administrative_label_zh="省",
        default_marketplaces=("Shopee Indonesia", "Tokopedia", "TikTok Shop Indonesia", "Lazada Indonesia"),
        search_languages=("Indonesian", "English"),
        supported_study_types=COMMON_STUDY_TYPES,
    ),
    "VN": CountryConfig(
        code="VN",
        name_en="Vietnam",
        name_zh="越南",
        currency_code="VND",
        currency_symbol="₫",
        default_price=299000.0,
        locale="vi-VN",
        profile_file="vietnam_consumer_products_macro_v1.json",
        administrative_label_zh="省/直辖市",
        default_marketplaces=("Shopee Vietnam", "TikTok Shop Vietnam", "Lazada Vietnam", "Tiki"),
        search_languages=("Vietnamese", "English"),
        supported_study_types=COMMON_STUDY_TYPES,
    ),
    "PH": CountryConfig(
        code="PH",
        name_en="Philippines",
        name_zh="菲律宾",
        currency_code="PHP",
        currency_symbol="₱",
        default_price=699.0,
        locale="en-PH",
        profile_file="philippines_consumer_products_macro_v1.json",
        administrative_label_zh="大区/省",
        default_marketplaces=("Shopee Philippines", "Lazada Philippines", "TikTok Shop Philippines"),
        search_languages=("English", "Tagalog"),
        supported_study_types=COMMON_STUDY_TYPES,
    ),
    "SG": CountryConfig(
        code="SG",
        name_en="Singapore",
        name_zh="新加坡",
        currency_code="SGD",
        currency_symbol="S$",
        default_price=29.0,
        locale="en-SG",
        profile_file="singapore_consumer_products_macro_v1.json",
        administrative_label_zh="规划区",
        default_marketplaces=("Shopee Singapore", "Lazada Singapore", "Amazon Singapore"),
        search_languages=("English", "Chinese"),
        supported_study_types=COMMON_STUDY_TYPES,
    ),
}


def get_country_config(country_code: str | None) -> CountryConfig:
    normalized = str(country_code or "TH").strip().upper()
    if normalized not in COUNTRIES:
        raise ValueError(f"Unsupported country code: {normalized}")
    return COUNTRIES[normalized]
