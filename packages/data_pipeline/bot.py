"""Authenticated discovery client for Bank of Thailand statistics APIs."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import httpx

BOT_SEARCH_URL = "https://gateway.api.bot.or.th/search-series/get"
BOT_SEARCH_DOCUMENTATION = (
    "https://portal.api.bot.or.th/portal/catalogue-products/"
    "statistics-1/e581631f50164ffc72525b11050b5744/docs"
)


class BotDataSourceError(RuntimeError):
    """Raised when BOT authentication or response validation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class BotStatisticsClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: float = 45.0,
        client: Optional[httpx.Client] = None,
    ):
        self.api_key = str(api_key or os.environ.get("BOT_API_KEY") or "").strip()
        self.timeout_seconds = timeout_seconds
        self._client = client

    def search_series(self, keyword: str) -> Dict[str, Any]:
        if not self.api_key:
            raise BotDataSourceError(
                "缺少 BOT_API_KEY；泰国央行门户要求 Authorization API key。"
            )
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise BotDataSourceError("BOT series keyword cannot be empty")
        client = self._client or httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        should_close = self._client is None
        try:
            response = client.get(
                BOT_SEARCH_URL,
                params={"keyword": normalized_keyword},
                headers={
                    "Authorization": self.api_key,
                    "User-Agent": "ThailandMarketTwin/2.0 (+data-provenance)",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise BotDataSourceError(
                f"Unable to search BOT statistics: {error}"
            ) from error
        finally:
            if should_close:
                client.close()
        if not isinstance(payload, (Mapping, list)):
            raise BotDataSourceError("BOT search returned an unsupported JSON shape")
        canonical = _canonical_json_bytes(payload)
        return {
            "payload": payload,
            "manifest": {
                "source_id": "BOT_STATISTICS_SERIES_SEARCH",
                "documentation": BOT_SEARCH_DOCUMENTATION,
                "api_url": BOT_SEARCH_URL,
                "query": {"keyword": normalized_keyword},
                "retrieval_method": "official_authenticated_api",
                "observed": True,
                "fetched_at": _utc_now(),
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "quantitative_effect": "none_series_discovery_only",
            },
        }


def write_bot_search_snapshot(result: Mapping[str, Any], root: Path) -> Path:
    manifest = dict(result["manifest"])
    target_dir = root / str(manifest["fetched_at"])[:10]
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(
        str(manifest["query"]["keyword"]).encode("utf-8")
    ).hexdigest()[:10]
    data_path = target_dir / f"series-search-{suffix}.json.gz"
    data_path.write_bytes(
        gzip.compress(
            _canonical_json_bytes(result["payload"]),
            compresslevel=9,
            mtime=0,
        )
    )
    manifest["snapshot_path"] = str(data_path)
    manifest_path = target_dir / f"series-search-{suffix}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
