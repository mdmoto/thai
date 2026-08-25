"""Command-line entry points for refreshing market evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from data_pipeline.bot import BotStatisticsClient, write_bot_search_snapshot
from data_pipeline.consumer_products import (
    build_consumer_products_profile,
    write_profile,
)
from data_pipeline.customer_data import (
    DATASET_SCHEMAS,
    validate_customer_csv,
    write_validation_report,
)
from data_pipeline.dosm import (
    DosmCollector,
    build_malaysia_profile,
    write_profile as write_malaysia_profile,
)
from data_pipeline.moc import MocCollector, write_standalone_moc_snapshot
from data_pipeline.nso import NsoCollector
from data_pipeline.pet_water_fountains import PetWaterFountainPanel, write_panel
from data_pipeline.product_pages import PublicProductPageCollector

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_PROFILE = REPO_ROOT / "data_catalog" / "thailand_market_priors_v1.json"
DEFAULT_OUTPUT_PROFILE = (
    REPO_ROOT / "data_catalog" / "thailand_consumer_products_macro_v1.json"
)
DEFAULT_SNAPSHOT_ROOT = REPO_ROOT / "data_catalog" / "raw" / "nso"
DEFAULT_MOC_SNAPSHOT_ROOT = REPO_ROOT / "data_catalog" / "raw" / "moc"
DEFAULT_BOT_SNAPSHOT_ROOT = REPO_ROOT / "data_catalog" / "raw" / "bot"
DEFAULT_DOSM_SNAPSHOT_ROOT = REPO_ROOT / "data_catalog" / "raw" / "dosm"
DEFAULT_MALAYSIA_PROFILE = (
    REPO_ROOT / "data_catalog" / "malaysia_consumer_products_macro_v1.json"
)
DEFAULT_PET_WATER_FOUNTAIN_SOURCES = (
    REPO_ROOT / "data_catalog" / "categories" / "pet_water_fountain_sources_v1.json"
)
DEFAULT_PET_WATER_FOUNTAIN_OUTPUT = (
    REPO_ROOT / "data_catalog" / "categories" / "pet_water_fountain_th_v1.json"
)


def refresh_nso(args: argparse.Namespace) -> int:
    collector = NsoCollector()
    refresh = collector.refresh_all(Path(args.snapshot_root))
    base_profile = json.loads(Path(args.base_profile).read_text(encoding="utf-8"))
    profile = build_consumer_products_profile(
        base_profile,
        refresh["rows"],
        refresh["manifest"],
    )
    write_profile(profile, Path(args.output_profile))
    print(
        json.dumps(
            {
                "status": "ok",
                "profile": args.output_profile,
                "profile_version": profile["version"],
                "calibration_status": profile["status"],
                "manifest": refresh["manifest_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def collect_product(args: argparse.Namespace) -> int:
    collector = PublicProductPageCollector()
    record = collector.collect(args.url)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output),
                "name": record.get("name"),
                "price": record.get("price"),
                "currency": record.get("currency"),
            },
            ensure_ascii=False,
        )
    )
    return 0


def refresh_pet_water_fountains(args: argparse.Namespace) -> int:
    registry = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    collector = PublicProductPageCollector(
        minimum_interval_seconds=float(args.minimum_interval)
    )
    panel = PetWaterFountainPanel(collector=collector).collect(registry["panel_urls"])
    panel["source_registry_version"] = registry["version"]
    panel["reference_only_urls"] = registry.get("reference_only_urls", [])
    panel["collection_policy"] = registry.get("collection_policy", {})
    write_panel(panel, Path(args.output))
    print(
        json.dumps(
            {
                "status": "ok",
                "output": args.output,
                "panel_version": panel["panel_version"],
                "product_count": panel["product_count"],
                "retailer_count": panel["retailer_count"],
                "price_summary": panel["price_summary"],
                "errors": len(panel["collection_errors"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def refresh_moc(args: argparse.Namespace) -> int:
    collector = MocCollector()
    refresh = collector.refresh_macro_context(
        Path(args.snapshot_root),
        from_year=int(args.from_year),
        to_year=int(args.to_year),
        region_ids=tuple(args.region_id or range(0, 6)),
        province_codes=tuple(args.province_code),
    )
    context = refresh["manifest"]["context"]
    print(
        json.dumps(
            {
                "status": "ok",
                "manifest": refresh["manifest_path"],
                "source_count": len(refresh["manifest"]["sources"]),
                "latest_national_cpi": context.get("national_cpi"),
                "latest_consumer_confidence": context.get("consumer_confidence"),
                "quantitative_effect": context["quantitative_effect"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def validate_customer_data(args: argparse.Namespace) -> int:
    report = validate_customer_csv(args.dataset_type, Path(args.input))
    if args.output:
        write_validation_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] != "needs_action" else 2


def search_bot_series(args: argparse.Namespace) -> int:
    result = BotStatisticsClient().search_series(args.keyword)
    manifest_path = write_bot_search_snapshot(
        result,
        Path(args.snapshot_root),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "manifest": str(manifest_path),
                "keyword": args.keyword,
                "quantitative_effect": "none_series_discovery_only",
            },
            ensure_ascii=False,
        )
    )
    return 0


def search_moc_products(args: argparse.Namespace) -> int:
    result = MocCollector().search_agricultural_products(
        args.keyword,
        args.sell_type,
    )
    manifest_path = write_standalone_moc_snapshot(
        result,
        Path(args.snapshot_root),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "manifest": str(manifest_path),
                "product_count": len(result["payload"]),
                "products": result["payload"][:20],
            },
            ensure_ascii=False,
        )
    )
    return 0


def refresh_moc_agricultural_price(args: argparse.Namespace) -> int:
    result = MocCollector().fetch_agricultural_price(
        args.product_id,
        args.from_date,
        args.to_date,
    )
    manifest_path = write_standalone_moc_snapshot(
        result,
        Path(args.snapshot_root),
    )
    payload = result["payload"]
    print(
        json.dumps(
            {
                "status": "ok",
                "manifest": str(manifest_path),
                "product_id": payload.get("product_id"),
                "product_name": payload.get("product_name"),
                "observation_count": len(payload.get("price_list") or []),
                "price_min_avg": payload.get("price_min_avg"),
                "price_max_avg": payload.get("price_max_avg"),
            },
            ensure_ascii=False,
        )
    )
    return 0


def refresh_malaysia(args: argparse.Namespace) -> int:
    refresh = DosmCollector().refresh_all(Path(args.snapshot_root))
    base_profile = json.loads(Path(args.base_profile).read_text(encoding="utf-8"))
    profile = build_malaysia_profile(
        base_profile,
        refresh["rows"],
        refresh["manifest"],
    )
    write_malaysia_profile(profile, Path(args.output_profile))
    print(
        json.dumps(
            {
                "status": "ok",
                "country_code": "MY",
                "profile": args.output_profile,
                "profile_version": profile["version"],
                "population_total": profile["population"][
                    "registered_population_total"
                ],
                "manifest": refresh["manifest_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    nso_parser = subparsers.add_parser(
        "refresh-nso",
        help="Refresh official NSO macro snapshots and rebuild the consumer profile",
    )
    nso_parser.add_argument(
        "--snapshot-root",
        default=str(DEFAULT_SNAPSHOT_ROOT),
    )
    nso_parser.add_argument(
        "--base-profile",
        default=str(DEFAULT_BASE_PROFILE),
    )
    nso_parser.add_argument(
        "--output-profile",
        default=str(DEFAULT_OUTPUT_PROFILE),
    )
    nso_parser.set_defaults(handler=refresh_nso)

    page_parser = subparsers.add_parser(
        "collect-product",
        help="Extract robots-permitted structured metadata from one public product page",
    )
    page_parser.add_argument("--url", required=True)
    page_parser.add_argument("--output", required=True)
    page_parser.set_defaults(handler=collect_product)

    pet_parser = subparsers.add_parser(
        "refresh-pet-water-fountains",
        help="Refresh the Thailand pet water-fountain public offer panel",
    )
    pet_parser.add_argument(
        "--sources",
        default=str(DEFAULT_PET_WATER_FOUNTAIN_SOURCES),
    )
    pet_parser.add_argument(
        "--output",
        default=str(DEFAULT_PET_WATER_FOUNTAIN_OUTPUT),
    )
    pet_parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.6,
        help="Minimum delay between page requests in seconds",
    )
    pet_parser.set_defaults(handler=refresh_pet_water_fountains)

    moc_parser = subparsers.add_parser(
        "refresh-moc",
        help="Refresh versioned Thailand MOC CPI and consumer-confidence snapshots",
    )
    moc_parser.add_argument(
        "--snapshot-root",
        default=str(DEFAULT_MOC_SNAPSHOT_ROOT),
    )
    moc_parser.add_argument("--from-year", type=int, required=True)
    moc_parser.add_argument("--to-year", type=int, required=True)
    moc_parser.add_argument(
        "--region-id",
        type=int,
        action="append",
        default=None,
        choices=range(0, 6),
        help="Repeat to select regions; default collects all 0-5",
    )
    moc_parser.add_argument(
        "--province-code",
        action="append",
        default=[],
        help="Optional repeatable MOC province code",
    )
    moc_parser.set_defaults(handler=refresh_moc)

    moc_product_parser = subparsers.add_parser(
        "search-moc-products",
        help="Search the official MOC agricultural product catalogue",
    )
    moc_product_parser.add_argument("--keyword", required=True)
    moc_product_parser.add_argument(
        "--sell-type",
        choices=("retail", "wholesale"),
        default="retail",
    )
    moc_product_parser.add_argument(
        "--snapshot-root",
        default=str(DEFAULT_MOC_SNAPSHOT_ROOT),
    )
    moc_product_parser.set_defaults(handler=search_moc_products)

    moc_price_parser = subparsers.add_parser(
        "refresh-moc-agricultural-price",
        help="Refresh one official MOC daily agricultural price series",
    )
    moc_price_parser.add_argument("--product-id", required=True)
    moc_price_parser.add_argument("--from-date", required=True)
    moc_price_parser.add_argument("--to-date", required=True)
    moc_price_parser.add_argument(
        "--snapshot-root",
        default=str(DEFAULT_MOC_SNAPSHOT_ROOT),
    )
    moc_price_parser.set_defaults(handler=refresh_moc_agricultural_price)

    customer_parser = subparsers.add_parser(
        "validate-customer-data",
        help="Validate a de-identified customer calibration CSV before import",
    )
    customer_parser.add_argument(
        "--dataset-type",
        required=True,
        choices=sorted(DATASET_SCHEMAS),
    )
    customer_parser.add_argument("--input", required=True)
    customer_parser.add_argument("--output")
    customer_parser.set_defaults(handler=validate_customer_data)

    bot_parser = subparsers.add_parser(
        "search-bot-series",
        help="Discover official BOT statistics series using BOT_API_KEY",
    )
    bot_parser.add_argument("--keyword", required=True)
    bot_parser.add_argument(
        "--snapshot-root",
        default=str(DEFAULT_BOT_SNAPSHOT_ROOT),
    )
    bot_parser.set_defaults(handler=search_bot_series)

    malaysia_parser = subparsers.add_parser(
        "refresh-malaysia",
        help="Refresh official Malaysia DOSM snapshots and rebuild the MY profile",
    )
    malaysia_parser.add_argument(
        "--snapshot-root",
        default=str(DEFAULT_DOSM_SNAPSHOT_ROOT),
    )
    malaysia_parser.add_argument(
        "--base-profile",
        default=str(DEFAULT_BASE_PROFILE),
    )
    malaysia_parser.add_argument(
        "--output-profile",
        default=str(DEFAULT_MALAYSIA_PROFILE),
    )
    malaysia_parser.set_defaults(handler=refresh_malaysia)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
