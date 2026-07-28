"""Collectors for public Thailand NSO datasets.

Only fixed, documented public endpoints are used. Every refresh stores a
content-addressed compressed snapshot and a manifest so a model result can be
traced back to the exact records used for calibration.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import httpx


NSO_API_URL = "https://catalogapi.nso.go.th/api/index"
DEFAULT_USER_AGENT = "ThailandMarketTwin/2.0 (+data-provenance)"


@dataclass(frozen=True)
class NsoSource:
    source_id: str
    dataset_id: str
    dataset_page: str
    table: str
    title: str
    license: str
    required_fields: tuple[str, ...]
    minimum_records: int

    @property
    def api_url(self) -> str:
        return f"{NSO_API_URL}?table={self.table}&format=json"


SOURCES: Dict[str, NsoSource] = {
    "registered_population": NsoSource(
        source_id="NSO_REGISTERED_POPULATION",
        dataset_id="0405_01_0005",
        dataset_page="https://catalog.nso.go.th/dataset/0405_01_0005",
        table="OS_0405_01_0005_01",
        title="Registered population by sex, district and province",
        license="Creative Commons Attribution",
        required_fields=("YEAR", "PROVINCE", "DISTRIC", "SEX", "VALUE"),
        minimum_records=10_000,
    ),
    "household_income_distribution": NsoSource(
        source_id="NSO_SES_HOUSEHOLD_INCOME_DISTRIBUTION",
        dataset_id="ns_08_20241",
        dataset_page="https://catalog.nso.go.th/dataset/ns_08_20241",
        table="SES_41_03",
        title="Household monthly income distribution by region",
        license="Creative Commons Attribution",
        required_fields=("YEAR", "CODE_REGION", "REGION", "INCOME_PER_HH1"),
        minimum_records=30,
    ),
    "province_income_expense": NsoSource(
        source_id="NSO_SES_PROVINCE_INCOME_EXPENSE",
        dataset_id="0705_08_0031",
        dataset_page="https://catalog.nso.go.th/dataset/0705_08_0031",
        table="SFD_SPB0801",
        title="Monthly household income, expenditure and debt by province",
        license="Creative Commons Attribution",
        required_fields=(
            "year",
            "province",
            "mthincome_mthexp_totaldebt_pctexptoincome",
            "soc_eco_class1",
            "soc_eco_class2",
            "value",
        ),
        minimum_records=3_000,
    ),
    "household_size": NsoSource(
        source_id="NSO_SES_HOUSEHOLD_SIZE",
        dataset_id="0705_08_0017",
        dataset_page="https://catalog.nso.go.th/dataset/0705_08_0017",
        table="SES_0705_08_0049_01",
        title="Average household size by province",
        license="Creative Commons Attribution",
        required_fields=("Year", "Region", "Province", "Value"),
        minimum_records=900,
    ),
}


class DataSourceError(RuntimeError):
    """Raised when a remote dataset cannot be safely accepted."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NsoCollector:
    def __init__(
        self,
        timeout_seconds: float = 60.0,
        attempts: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        client: Optional[httpx.Client] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.attempts = max(1, attempts)
        self.user_agent = user_agent
        self._client = client

    def _get(self, source: NsoSource) -> httpx.Response:
        last_error: Optional[Exception] = None
        client = self._client or httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        should_close = self._client is None
        try:
            for attempt in range(self.attempts):
                try:
                    response = client.get(
                        NSO_API_URL,
                        params={"table": source.table, "format": "json"},
                    )
                    response.raise_for_status()
                    return response
                except (httpx.HTTPError, httpx.TimeoutException) as error:
                    last_error = error
                    if attempt + 1 < self.attempts:
                        time.sleep(0.4 * (2**attempt))
        finally:
            if should_close:
                client.close()
        raise DataSourceError(
            f"Unable to fetch {source.source_id}: {last_error}"
        )

    @staticmethod
    def validate_rows(
        source: NsoSource,
        rows: Any,
    ) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            raise DataSourceError(f"{source.source_id} did not return a JSON list")
        if len(rows) < source.minimum_records:
            raise DataSourceError(
                f"{source.source_id} returned {len(rows)} records; "
                f"expected at least {source.minimum_records}"
            )
        normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
        if len(normalized) != len(rows):
            raise DataSourceError(f"{source.source_id} contains non-object rows")
        missing = [
            field
            for field in source.required_fields
            if any(field not in row for row in normalized[: min(100, len(normalized))])
        ]
        if missing:
            raise DataSourceError(
                f"{source.source_id} is missing expected fields: {missing}"
            )
        return normalized

    def fetch(self, source_name: str) -> Dict[str, Any]:
        if source_name not in SOURCES:
            raise KeyError(f"Unknown NSO source: {source_name}")
        source = SOURCES[source_name]
        response = self._get(source)
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            raise DataSourceError(
                f"{source.source_id} returned unsupported content type {content_type}"
            )
        if len(response.content) > 25_000_000:
            raise DataSourceError(f"{source.source_id} exceeded the 25 MB safety limit")
        try:
            rows = self.validate_rows(source, response.json())
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DataSourceError(
                f"{source.source_id} returned invalid JSON"
            ) from error

        canonical = _canonical_json_bytes(rows)
        return {
            "source": source,
            "rows": rows,
            "manifest": {
                "source_id": source.source_id,
                "dataset_id": source.dataset_id,
                "dataset_page": source.dataset_page,
                "api_url": source.api_url,
                "title": source.title,
                "license": source.license,
                "retrieval_method": "official_public_api",
                "observed": True,
                "fetched_at": _utc_now(),
                "record_count": len(rows),
                "sha256": hashlib.sha256(canonical).hexdigest(),
            },
        }

    @staticmethod
    def write_snapshot(
        result: Mapping[str, Any],
        snapshot_root: Path,
    ) -> Dict[str, Any]:
        source: NsoSource = result["source"]
        manifest = dict(result["manifest"])
        fetched_date = str(manifest["fetched_at"])[:10]
        target_dir = snapshot_root / fetched_date
        target_dir.mkdir(parents=True, exist_ok=True)

        canonical = _canonical_json_bytes(result["rows"])
        data_path = target_dir / f"{source.table}.json.gz"
        temporary_path = target_dir / f".{source.table}.json.gz.tmp"
        temporary_path.write_bytes(gzip.compress(canonical, compresslevel=9, mtime=0))
        temporary_path.replace(data_path)
        try:
            manifest["snapshot_path"] = str(
                data_path.resolve().relative_to(Path.cwd().resolve())
            )
        except ValueError:
            manifest["snapshot_path"] = str(data_path)
        return manifest

    def refresh_all(self, snapshot_root: Path) -> Dict[str, Any]:
        manifests: Dict[str, Any] = {}
        rows: Dict[str, List[Dict[str, Any]]] = {}
        for source_name in SOURCES:
            result = self.fetch(source_name)
            manifests[source_name] = self.write_snapshot(result, snapshot_root)
            rows[source_name] = result["rows"]

        manifest = {
            "schema_version": "1",
            "pipeline": "nso_consumer_products_macro",
            "generated_at": _utc_now(),
            "sources": manifests,
        }
        manifest_path = (
            snapshot_root
            / str(manifest["generated_at"])[:10]
            / "manifest.json"
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "manifest": manifest,
            "manifest_path": str(manifest_path),
            "rows": rows,
        }


def read_snapshot(path: Path) -> List[Dict[str, Any]]:
    with gzip.open(path, "rb") as handle:
        payload = json.loads(handle.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise DataSourceError(f"Snapshot {path} does not contain a row list")
    return [dict(row) for row in payload]


def public_source_registry() -> Dict[str, Dict[str, Any]]:
    return {
        name: {
            **asdict(source),
            "api_url": source.api_url,
        }
        for name, source in SOURCES.items()
    }
