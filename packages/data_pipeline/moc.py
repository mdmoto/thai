"""Versioned collectors for Thailand Ministry of Commerce open data.

The macro context is intentionally descriptive.  It is attached to reports for
provenance and scenario interpretation, but it does not alter demand or choice
coefficients until a backtest establishes an empirical mapping.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import httpx

MOC_API_BASE = "https://dataapi.moc.go.th"
MOC_OPEN_DATA_BASE = "https://data.moc.go.th/OpenData"
DEFAULT_USER_AGENT = "ThailandMarketTwin/2.0 (+data-provenance)"


class MocDataSourceError(RuntimeError):
    """Raised when an official response cannot be safely accepted."""


@dataclass(frozen=True)
class MocSource:
    source_id: str
    endpoint: str
    documentation: str
    title: str
    required_fields: tuple[str, ...]
    response_type: str = "list"

    @property
    def api_url(self) -> str:
        return f"{MOC_API_BASE}/{self.endpoint}"


SOURCES: Dict[str, MocSource] = {
    "regional_cpi": MocSource(
        source_id="MOC_CPIG_INDEXES",
        endpoint="cpig-indexes",
        documentation=f"{MOC_OPEN_DATA_BASE}/CPIGIndexes",
        title="Thailand general consumer price index by region",
        required_fields=(
            "index_id",
            "region_id",
            "region_name",
            "year",
            "month",
            "price_index",
            "mom",
            "yoy",
        ),
    ),
    "province_cpi": MocSource(
        source_id="MOC_CPIP_INDEXES",
        endpoint="cpip-indexes",
        documentation=f"{MOC_OPEN_DATA_BASE}/CPIPIndexes",
        title="Thailand general consumer price index by province",
        required_fields=("province_code", "year", "month", "price_index"),
    ),
    "consumer_confidence": MocSource(
        source_id="MOC_CCI_INDEXES",
        endpoint="cci-indexes",
        documentation=f"{MOC_OPEN_DATA_BASE}/CCIIndexes",
        title="Thailand consumer confidence index",
        required_fields=(
            "year",
            "month",
            "index_all",
            "index_current",
            "index_future",
        ),
    ),
    "agricultural_products": MocSource(
        source_id="MOC_GIS_PRODUCTS",
        endpoint="gis-products",
        documentation=f"{MOC_OPEN_DATA_BASE}/GISProducts",
        title="Thailand agricultural product catalogue",
        required_fields=("product_id", "product_name"),
    ),
    "agricultural_price": MocSource(
        source_id="MOC_GIS_PRODUCT_PRICE",
        endpoint="gis-product-price",
        documentation=f"{MOC_OPEN_DATA_BASE}/GISProductPrice",
        title="Thailand daily agricultural product price",
        required_fields=(
            "product_id",
            "product_name",
            "unit",
            "price_min_avg",
            "price_max_avg",
            "price_list",
        ),
        response_type="object",
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _safe_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


class MocCollector:
    def __init__(
        self,
        timeout_seconds: float = 45.0,
        attempts: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        client: Optional[httpx.Client] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.attempts = max(1, attempts)
        self.user_agent = user_agent
        self._client = client

    def _get(self, source: MocSource, params: Mapping[str, Any]) -> Any:
        client = self._client or httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        should_close = self._client is None
        last_error: Optional[Exception] = None
        try:
            for attempt in range(self.attempts):
                try:
                    response = client.get(source.api_url, params=dict(params))
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "json" not in content_type.lower():
                        raise MocDataSourceError(
                            f"{source.source_id} returned unsupported content type "
                            f"{content_type}"
                        )
                    if len(response.content) > 25_000_000:
                        raise MocDataSourceError(
                            f"{source.source_id} exceeded the 25 MB safety limit"
                        )
                    return response.json()
                except (httpx.HTTPError, json.JSONDecodeError) as error:
                    last_error = error
                    if attempt + 1 < self.attempts:
                        time.sleep(0.4 * (2**attempt))
        finally:
            if should_close:
                client.close()
        raise MocDataSourceError(f"Unable to fetch {source.source_id}: {last_error}")

    @staticmethod
    def _validate(source: MocSource, payload: Any) -> Any:
        if source.response_type == "object":
            if not isinstance(payload, Mapping):
                raise MocDataSourceError(
                    f"{source.source_id} did not return a JSON object"
                )
            normalized: Any = dict(payload)
            candidates = [normalized]
        else:
            if not isinstance(payload, list):
                raise MocDataSourceError(
                    f"{source.source_id} did not return a JSON list"
                )
            normalized = [dict(row) for row in payload if isinstance(row, Mapping)]
            if len(normalized) != len(payload):
                raise MocDataSourceError(f"{source.source_id} contains non-object rows")
            if not normalized:
                raise MocDataSourceError(f"{source.source_id} returned no records")
            candidates = normalized[: min(100, len(normalized))]

        missing = [
            field
            for field in source.required_fields
            if any(field not in row for row in candidates)
        ]
        if missing:
            raise MocDataSourceError(
                f"{source.source_id} is missing expected fields: {missing}"
            )
        return normalized

    def fetch(self, source_name: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        if source_name not in SOURCES:
            raise KeyError(f"Unknown MOC source: {source_name}")
        source = SOURCES[source_name]
        payload = self._validate(source, self._get(source, params))
        canonical = _canonical_json_bytes(payload)
        record_count = len(payload) if isinstance(payload, list) else 1
        return {
            "source": source,
            "payload": payload,
            "manifest": {
                "source_id": source.source_id,
                "title": source.title,
                "documentation": source.documentation,
                "api_url": source.api_url,
                "query": dict(params),
                "license": "Thailand Government Open Data terms",
                "retrieval_method": "official_public_api",
                "observed": True,
                "fetched_at": _utc_now(),
                "record_count": record_count,
                "sha256": hashlib.sha256(canonical).hexdigest(),
            },
        }

    def fetch_regional_cpi(
        self,
        region_id: int,
        from_year: int,
        to_year: int,
        index_id: str = "0000000000000000",
    ) -> Dict[str, Any]:
        if from_year > to_year:
            raise MocDataSourceError("from_year must not be after to_year")
        if region_id not in range(0, 6):
            raise MocDataSourceError("region_id must be between 0 and 5")
        return self.fetch(
            "regional_cpi",
            {
                "region_id": int(region_id),
                "index_id": index_id,
                "from_year": int(from_year),
                "to_year": int(to_year),
            },
        )

    def fetch_consumer_confidence(
        self,
        from_year: int,
        to_year: int,
        from_month: int = 1,
        to_month: int = 12,
    ) -> Dict[str, Any]:
        if from_year > to_year:
            raise MocDataSourceError("from_year must not be after to_year")
        if not 1 <= from_month <= 12 or not 1 <= to_month <= 12:
            raise MocDataSourceError("month must be between 1 and 12")
        return self.fetch(
            "consumer_confidence",
            {
                "from_month": int(from_month),
                "to_month": int(to_month),
                "from_year": int(from_year),
                "to_year": int(to_year),
            },
        )

    def fetch_province_cpi(
        self,
        province_code: str,
        from_year: int,
        to_year: int,
        index_id: str = "0000000000000000",
    ) -> Dict[str, Any]:
        if from_year > to_year:
            raise MocDataSourceError("from_year must not be after to_year")
        if not str(province_code).strip():
            raise MocDataSourceError("province_code cannot be empty")
        return self.fetch(
            "province_cpi",
            {
                "province_code": province_code,
                "index_id": index_id,
                "from_year": int(from_year),
                "to_year": int(to_year),
            },
        )

    def search_agricultural_products(
        self,
        keyword: str,
        sell_type: str = "retail",
    ) -> Dict[str, Any]:
        if sell_type not in {"retail", "wholesale"}:
            raise MocDataSourceError("sell_type must be retail or wholesale")
        if not keyword.strip():
            raise MocDataSourceError("keyword cannot be empty")
        return self.fetch(
            "agricultural_products",
            {"keyword": keyword, "sell_type": sell_type},
        )

    def fetch_agricultural_price(
        self,
        product_id: str,
        from_date: str,
        to_date: str,
    ) -> Dict[str, Any]:
        try:
            start = date.fromisoformat(from_date)
            end = date.fromisoformat(to_date)
        except ValueError as error:
            raise MocDataSourceError("dates must use YYYY-MM-DD") from error
        if start > end:
            raise MocDataSourceError("from_date must not be after to_date")
        if not product_id.strip():
            raise MocDataSourceError("product_id cannot be empty")
        return self.fetch(
            "agricultural_price",
            {
                "product_id": product_id,
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    @staticmethod
    def write_snapshot(result: Mapping[str, Any], target_dir: Path) -> Dict[str, Any]:
        source: MocSource = result["source"]
        manifest = dict(result["manifest"])
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = hashlib.sha256(_canonical_json_bytes(manifest["query"])).hexdigest()[
            :10
        ]
        data_path = target_dir / f"{source.endpoint}-{suffix}.json.gz"
        temporary_path = target_dir / f".{data_path.name}.tmp"
        temporary_path.write_bytes(
            gzip.compress(
                _canonical_json_bytes(result["payload"]),
                compresslevel=9,
                mtime=0,
            )
        )
        temporary_path.replace(data_path)
        manifest["snapshot_path"] = str(data_path)
        return manifest

    def refresh_macro_context(
        self,
        snapshot_root: Path,
        from_year: int,
        to_year: int,
        region_ids: Sequence[int] = (0, 1, 2, 3, 4, 5),
        province_codes: Sequence[str] = (),
    ) -> Dict[str, Any]:
        generated_at = _utc_now()
        target_dir = snapshot_root / generated_at[:10]
        manifests: List[Dict[str, Any]] = []
        cpi_rows: List[Dict[str, Any]] = []
        for region_id in region_ids:
            result = self.fetch_regional_cpi(region_id, from_year, to_year)
            manifests.append(self.write_snapshot(result, target_dir))
            cpi_rows.extend(result["payload"])

        confidence = self.fetch_consumer_confidence(from_year, to_year)
        manifests.append(self.write_snapshot(confidence, target_dir))
        confidence_rows = list(confidence["payload"])

        for province_code in province_codes:
            result = self.fetch_province_cpi(
                province_code,
                from_year,
                to_year,
            )
            manifests.append(self.write_snapshot(result, target_dir))

        context = build_macro_context(cpi_rows, confidence_rows, generated_at)
        manifest = {
            "schema_version": "1",
            "pipeline": "thailand_moc_macro_context",
            "generated_at": generated_at,
            "from_year": int(from_year),
            "to_year": int(to_year),
            "sources": manifests,
            "context": context,
        }
        manifest_path = target_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"manifest": manifest, "manifest_path": str(manifest_path)}


def _latest_row(rows: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    valid = [
        row
        for row in rows
        if _safe_number(row.get("year")) is not None
        and _safe_number(row.get("month")) is not None
    ]
    if not valid:
        return None
    return max(
        valid,
        key=lambda row: (int(row["year"]), int(row["month"])),
    )


def build_macro_context(
    cpi_rows: Sequence[Mapping[str, Any]],
    confidence_rows: Sequence[Mapping[str, Any]],
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    national_rows = [row for row in cpi_rows if str(row.get("region_id")) == "5"]
    latest_national = _latest_row(national_rows)
    latest_confidence = _latest_row(confidence_rows)
    latest_by_region: List[Dict[str, Any]] = []
    region_ids = sorted({str(row.get("region_id")) for row in cpi_rows})
    for region_id in region_ids:
        latest = _latest_row(
            [row for row in cpi_rows if str(row.get("region_id")) == region_id]
        )
        if latest:
            latest_by_region.append(
                {
                    "region_id": latest.get("region_id"),
                    "region_name": latest.get("region_name"),
                    "year": int(latest["year"]),
                    "month": int(latest["month"]),
                    "price_index": _safe_number(latest.get("price_index")),
                    "mom": _safe_number(latest.get("mom")),
                    "yoy": _safe_number(latest.get("yoy")),
                }
            )
    return {
        "status": "observed_official_context",
        "generated_at": generated_at or _utc_now(),
        "quantitative_effect": "context_only_until_backtested",
        "national_cpi": (
            {
                "year": int(latest_national["year"]),
                "month": int(latest_national["month"]),
                "price_index": _safe_number(latest_national.get("price_index")),
                "mom": _safe_number(latest_national.get("mom")),
                "yoy": _safe_number(latest_national.get("yoy")),
                "aoa": _safe_number(latest_national.get("aoa")),
            }
            if latest_national
            else None
        ),
        "regional_cpi": latest_by_region,
        "consumer_confidence": (
            {
                "year": int(latest_confidence["year"]),
                "month": int(latest_confidence["month"]),
                "index_all": _safe_number(latest_confidence.get("index_all")),
                "index_current": _safe_number(latest_confidence.get("index_current")),
                "index_future": _safe_number(latest_confidence.get("index_future")),
            }
            if latest_confidence
            else None
        ),
        "limitations": [
            "Macro indicators are descriptive context and do not change demand "
            "coefficients until an out-of-sample backtest establishes a mapping."
        ],
    }


def load_latest_moc_context(data_catalog_root: Path) -> Dict[str, Any]:
    manifests = sorted((data_catalog_root / "raw" / "moc").glob("*/manifest.json"))
    if not manifests:
        return {
            "status": "not_available",
            "quantitative_effect": "none",
            "reason": "尚未运行泰国商务部公开数据刷新命令。",
        }
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    context = dict(manifest.get("context") or {})
    try:
        context["manifest_path"] = str(manifests[-1].relative_to(data_catalog_root))
    except ValueError:
        context["manifest_path"] = str(manifests[-1])
    context["source_count"] = len(manifest.get("sources") or [])
    return context


def write_standalone_moc_snapshot(
    result: Mapping[str, Any],
    snapshot_root: Path,
) -> Path:
    fetched_at = str(result["manifest"]["fetched_at"])
    target_dir = snapshot_root / fetched_at[:10]
    manifest = MocCollector.write_snapshot(result, target_dir)
    suffix = hashlib.sha256(_canonical_json_bytes(manifest["query"])).hexdigest()[:10]
    manifest_path = target_dir / f"{result['source'].endpoint}-{suffix}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
