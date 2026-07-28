"""Command-line entry points for refreshing market evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from data_pipeline.consumer_products import (
    build_consumer_products_profile,
    write_profile,
)
from data_pipeline.nso import NsoCollector
from data_pipeline.pet_water_fountains import PetWaterFountainPanel, write_panel
from data_pipeline.product_pages import PublicProductPageCollector


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_PROFILE = REPO_ROOT / "data_catalog" / "thailand_market_priors_v1.json"
DEFAULT_OUTPUT_PROFILE = (
    REPO_ROOT / "data_catalog" / "thailand_consumer_products_macro_v1.json"
)
DEFAULT_SNAPSHOT_ROOT = REPO_ROOT / "data_catalog" / "raw" / "nso"
DEFAULT_PET_WATER_FOUNTAIN_SOURCES = (
    REPO_ROOT / "data_catalog" / "categories" / "pet_water_fountain_sources_v1.json"
)
DEFAULT_PET_WATER_FOUNTAIN_OUTPUT = (
    REPO_ROOT / "data_catalog" / "categories" / "pet_water_fountain_th_v1.json"
)


def refresh_nso(args: argparse.Namespace) -> int:
    collector = NsoCollector()
    refresh = collector.refresh_all(Path(args.snapshot_root))
    base_profile = json.loads(
        Path(args.base_profile).read_text(encoding="utf-8")
    )
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
    panel = PetWaterFountainPanel(collector=collector).collect(
        registry["panel_urls"]
    )
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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
