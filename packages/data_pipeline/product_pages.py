"""Conservative extraction of public product-page structured metadata.

This collector is intentionally not a marketplace bypass. It checks robots.txt,
uses a descriptive user agent, rate-limits requests, stores only extracted
facts plus a content hash, and never treats review counts as sales.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Mapping, Optional

import httpx


USER_AGENT = "ThailandMarketTwin/2.0 (+public-product-metadata)"


class ProductPageError(RuntimeError):
    """Raised when a public product page cannot be collected safely."""


class _StructuredMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: Dict[str, str] = {}
        self._in_json_ld = False
        self._json_ld_parts: List[str] = []
        self.json_ld: List[Any] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "meta":
            key = values.get("property") or values.get("name")
            if key and values.get("content"):
                self.meta[key.lower()] = values["content"].strip()
        if (
            tag.lower() == "script"
            and values.get("type", "").lower() == "application/ld+json"
        ):
            self._in_json_ld = True
            self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self._in_json_ld:
            return
        self._in_json_ld = False
        payload = "".join(self._json_ld_parts).strip()
        if not payload:
            return
        try:
            self.json_ld.append(json.loads(payload))
        except json.JSONDecodeError:
            return


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def _iter_nodes(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _is_product(node: Mapping[str, Any]) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, list):
        return any(str(value).lower() == "product" for value in node_type)
    return str(node_type).lower() == "product"


def _float_or_none(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _first_number(text: str, patterns: Iterable[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _float_or_none(match.group(1))
    return None


def _extract_page_claims(
    text: str,
    attribute_source: str = "seller_or_brand_product_description_claim",
) -> Dict[str, Any]:
    lowered = text.lower()
    capacity = _first_number(
        text,
        (
            r"(?:ความจุ(?:ถัง|น้ำ)?|ขนาดความจุ|capacity)[^0-9]{0,35}"
            r"(\d+(?:\.\d+)?)\s*(?:ลิตร|litres?|liters?|l\b)",
            r"(\d+(?:\.\d+)?)\s*(?:ลิตร|litres?|liters?)",
        ),
    )
    filter_stages = _first_number(
        text,
        (
            r"(?:ระบบ|แผ่น|ไส้)?กรอง[^0-9]{0,24}(\d+)\s*(?:ชั้น|ขั้นตอน)",
            r"(\d+)[-\s]*(?:stage|layer)[-\s]+(?:filter|filtration)",
        ),
    )
    noise = _first_number(
        text,
        (
            r"(\d+(?:\.\d+)?)\s*(?:เดซิเบล|db)\b",
        ),
    )
    warranty = _first_number(
        text,
        (
            r"รับประกัน(?:สินค้า|โดยศูนย์ไทย)?[^0-9]{0,40}(\d+(?:\.\d+)?)\s*ปี",
            r"(\d+(?:\.\d+)?)\s*(?:year|yr)[-\s]+warranty",
        ),
    )
    return {
        "capacity_liters": capacity,
        "filtration_stages": int(filter_stages) if filter_stages else None,
        "noise_db": noise,
        "warranty_years": warranty,
        "app_connected": any(
            token in lowered
            for token in ("แอป", "app ", "application", "mi home", "smart life")
        ),
        "wifi_connected": any(
            token in lowered for token in ("wi-fi", "wifi", "2.4 ghz", "2.4g")
        ),
        "battery_powered": any(
            token in lowered
            for token in ("แบตเตอรี่", "battery", "cordless", "ไร้สาย 100%")
        ),
        "wireless_pump": any(
            token in lowered
            for token in ("ปั๊มน้ำไร้สาย", "ปั๊มไร้สาย", "wireless pump")
        ),
        "uv_sterilization": any(
            token in lowered
            for token in (
                "uv-c",
                "uvc",
                "uva",
                "uv sterilizer",
                "uv sterilisation",
                "uv sterilization",
                "แสง uv",
                "ฆ่าเชื้อ",
            )
        ),
        "stainless_surface": any(
            token in lowered for token in ("สแตนเลส", "stainless")
        ),
        "low_water_protection": any(
            token in lowered
            for token in (
                "ระดับน้ำต่ำ",
                "น้ำเหลือน้อย",
                "น้ำหมด",
                "low water",
                "dry-run",
            )
        ),
        "sensor": any(
            token in lowered
            for token in ("เซนเซอร์", "sensor", "infrared", "อินฟราเรด")
        ),
        "food_grade": any(
            token in lowered
            for token in ("food grade", "food-grade", "วัสดุสัมผัสอาหาร")
        ),
        "attribute_source": attribute_source,
    }


class PublicProductPageCollector:
    def __init__(
        self,
        timeout_seconds: float = 30.0,
        minimum_interval_seconds: float = 1.0,
        client: Optional[httpx.Client] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.minimum_interval_seconds = max(0.0, minimum_interval_seconds)
        self._client = client
        self._last_request_at = 0.0

    def _client_or_new(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return (
            httpx.Client(
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ),
            True,
        )

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.minimum_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _robots_allows(self, client: httpx.Client, url: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        robots_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "/robots.txt", "", "")
        )
        try:
            response = client.get(robots_url)
        except httpx.HTTPError as error:
            raise ProductPageError(
                f"Could not verify robots policy for {parsed.netloc}"
            ) from error
        if response.status_code == 404:
            return True
        try:
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ProductPageError(
                f"Could not verify robots policy for {parsed.netloc}"
            ) from error
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        return parser.can_fetch(USER_AGENT, url)

    def collect(self, url: str) -> Dict[str, Any]:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProductPageError("Product URL must be an absolute HTTPS URL")

        client, should_close = self._client_or_new()
        try:
            if not self._robots_allows(client, url):
                raise ProductPageError(
                    f"robots.txt does not allow collection from {parsed.netloc}"
                )
            self._respect_rate_limit()
            response = client.get(url)
            self._last_request_at = time.monotonic()
            response.raise_for_status()
        finally:
            if should_close:
                client.close()

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            raise ProductPageError(f"Unsupported content type: {content_type}")
        if len(response.content) > 5_000_000:
            raise ProductPageError("Product page exceeded the 5 MB safety limit")

        parser = _StructuredMetadataParser()
        parser.feed(response.text)
        product: Mapping[str, Any] = {}
        for payload in parser.json_ld:
            for node in _iter_nodes(payload):
                if _is_product(node):
                    product = node
                    break
            if product:
                break

        offers = product.get("offers") if isinstance(product, Mapping) else {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, Mapping):
            offers = {}
        rating = (
            product.get("aggregateRating") if isinstance(product, Mapping) else {}
        )
        if not isinstance(rating, Mapping):
            rating = {}
        review_count = _float_or_none(rating.get("reviewCount"))
        brand = product.get("brand") if isinstance(product, Mapping) else None
        if isinstance(brand, Mapping):
            brand = brand.get("name")

        title = (
            product.get("name")
            or parser.meta.get("og:title")
            or parser.meta.get("twitter:title")
        )
        price = _float_or_none(
            offers.get("price")
            or offers.get("lowPrice")
            or parser.meta.get("product:price:amount")
        )
        currency = (
            offers.get("priceCurrency")
            or parser.meta.get("product:price:currency")
        )
        product_claim_fragments = [
            str(product.get("name") or ""),
            str(product.get("description") or ""),
            parser.meta.get("og:description", ""),
            parser.meta.get("twitter:description", ""),
        ]
        product_claim_text = " ".join(
            fragment for fragment in product_claim_fragments if fragment
        )
        claim_source = "structured_product_description"
        if not product_claim_text.strip():
            text_parser = _VisibleTextParser()
            text_parser.feed(response.text)
            product_claim_text = text_parser.text
            claim_source = "visible_page_text_fallback"
        result = {
            "schema_version": "1",
            "name": str(title).strip() if title else None,
            "brand": str(brand).strip() if brand else None,
            "sku": product.get("sku") if isinstance(product, Mapping) else None,
            "price": price,
            "currency": str(currency).upper() if currency else None,
            "price_valid_until": offers.get("priceValidUntil"),
            "rating": _float_or_none(rating.get("ratingValue")),
            "review_count": int(review_count) if review_count is not None else None,
            "availability": offers.get("availability"),
            "source_url": str(response.url),
            "source_domain": parsed.netloc.lower(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "page_sha256": hashlib.sha256(response.content).hexdigest(),
            "retrieval_method": "public_page_structured_metadata",
            "data_quality": "public_page_metadata_not_transactions",
            "observed": True,
            "transaction_data": False,
            "page_claims": _extract_page_claims(
                product_claim_text,
                attribute_source=(
                    f"seller_or_brand_{claim_source}_claim_"
                    "not_independently_verified"
                ),
            ),
            "terms_note": "Page terms and attribution requirements continue to apply.",
        }
        if not result["name"] and result["price"] is None:
            raise ProductPageError(
                "No Product JSON-LD or supported product metadata was found"
            )
        return result

    @staticmethod
    def to_competitor_data(record: Mapping[str, Any]) -> Dict[str, Any]:
        rating = _float_or_none(record.get("rating"))
        result: Dict[str, Any] = {
            "name": record.get("name") or record.get("brand") or "Competitor",
            "data_quality": record.get(
                "data_quality",
                "public_page_metadata_not_transactions",
            ),
            "evidence": {
                "source_url": record.get("source_url"),
                "fetched_at": record.get("fetched_at"),
                "page_sha256": record.get("page_sha256"),
                "review_count": record.get("review_count"),
                "transaction_data": False,
            },
        }
        if record.get("price") is not None:
            result["price"] = float(record["price"])
        if rating is not None:
            result["review_score"] = max(0.0, min(1.0, rating / 5.0))
            result["quality_score"] = result["review_score"]
        return result
