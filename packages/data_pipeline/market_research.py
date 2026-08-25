"""Auditable public-market research for deep decision studies.

The collector deliberately avoids login cookies, private endpoints, and claims
that public engagement equals sales. It gathers customer-supplied public pages,
public YouTube metadata, and bounded consumer-style public search results,
records provenance and hashes, and fails open so a blocked source never
corrupts the quantitative simulation.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional

import httpx


RESEARCH_VERSION = "SEA-MARKET-RESEARCH-2026.08.1"
PROFESSIONAL_RESEARCH_VERSION = "SEA-MARKET-RESEARCH-2026.08.1"
USER_AGENT = "SoutheastAsiaMarketTwin/2.2 (+public-market-research)"
PLATFORM_HOSTS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "lazada.co.th": "Lazada",
    "shopee.co.th": "Shopee",
    "lazada.com.my": "Lazada",
    "shopee.com.my": "Shopee",
}
SOURCE_STRATEGY = [
    {
        "priority": 1,
        "sources": ["Shopee", "Lazada", "TikTok Shop"],
        "role": "价格、销量提示、评价与竞品证据",
    },
    {
        "priority": 2,
        "sources": ["Facebook", "TikTok", "Instagram"],
        "role": "泰国本地讨论、社群情绪、短视频与直播反馈",
    },
    {
        "priority": 3,
        "sources": ["Google 搜索", "泰国媒体", "论坛", "公开评测页"],
        "role": "需求场景、问题词、趋势与第三方验证",
    },
    {
        "priority": 4,
        "sources": ["YouTube"],
        "role": "长测评、安装体验与耐用性补充证据",
    },
    {
        "priority": 5,
        "sources": ["品牌官网"],
        "role": "产品规格与官方主张基线",
    },
]
OFFLINE_STUDY_TYPES = {
    "VENUE_STUDY",
    "SITE_COMPARISON",
    "OPERATING_SCENARIO",
    "RESTAURANT",
    "CAFE",
    "BAR",
    "RETAIL",
}
OFFLINE_SOURCE_STRATEGY = [
    {
        "priority": 1,
        "sources": ["Google Maps", "公开地点资料", "顾客公开评价"],
        "role": "地点、周边设施、营业信息与真实到店体验线索",
    },
    {
        "priority": 2,
        "sources": ["Facebook", "LINE", "TikTok", "Instagram"],
        "role": "本地社群、探店内容与到店发现路径",
    },
    {
        "priority": 3,
        "sources": ["泰国媒体", "Pantip", "公开评测页", "交通与旅游公开资料"],
        "role": "商圈需求、出行便利、口碑主题与第三方验证",
    },
    {
        "priority": 4,
        "sources": ["品牌官网", "物业或商圈公开页"],
        "role": "门店主张、场地与商圈公开基线",
    },
    {
        "priority": 5,
        "sources": ["YouTube"],
        "role": "长视频探店或行业背景补充，不作为优先采集来源",
    },
]
PLATFORM_PRIORITY = {
    "Shopee": (1, "电商购买证据"),
    "Lazada": (1, "电商购买证据"),
    "Facebook": (2, "泰国社交讨论"),
    "TikTok": (2, "泰国社交讨论"),
    "Instagram": (2, "泰国社交讨论"),
    "YouTube": (4, "长测评补充证据"),
    "公开网页": (3, "公开搜索与评测证据"),
}
MARKETPLACE_PLATFORMS = {"Shopee", "Lazada"}
MAX_RESEARCH_URLS_PER_DOMAIN = 3
MAX_MARKETPLACE_URLS_PER_DOMAIN = 10
MARKETPLACE_SOURCE_DOMAINS = (
    "shopee.co.th",
    "lazada.co.th",
    "shopee.com.my",
    "lazada.com.my",
    "shop.tiktok.com",
    "tiktokshop.com",
)
ANTI_BOT_MARKERS = (
    "x5secdata",
    "captcha",
    "verify you are human",
    "detected unusual traffic",
    "unusual traffic from your network",
    "access denied",
    "error 403",
    "403 forbidden",
    "do not have access to this page",
    "security verification",
    "robot verification",
    "too many requests",
)
LOGIN_WALL_MARKERS = (
    "login required",
    "not logged in",
    "log in to continue",
    "please log in",
    "sign in to continue",
    "เข้าสู่ระบบเพื่อดำเนินการต่อ",
)
SEARCH_TERM_STOPWORDS = {
    "and",
    "review",
    "reviews",
    "thailand",
    "lazada",
    "shopee",
    "tiktok",
    "ราคา",
    "รีวิว",
    "ขายแล้ว",
}
CONSUMER_SIGNAL_TERMS = (
    "รีวิว",
    "ราคา",
    "ข้อดี",
    "ข้อเสีย",
    "ใช้จริง",
    "ซื้อ",
    "เปรียบเทียบ",
    "review",
    "price",
    "pros",
    "cons",
    "unboxing",
)
SOURCE_ADAPTER_REGISTRY = {
    "Crawl4AI public page reader": {
        "adapter_id": "public_page_reader",
        "channel": "customer_supplied_public_web",
        "access_policy": "robots_aware_public_http_only",
        "credential_policy": "no_personal_cookie",
        "cost_model": "local_compute",
        "fallback": "public_search_discovery",
    },
    "Firecrawl multi-query consumer research": {
        "adapter_id": "firecrawl_consumer_search",
        "channel": "public_web_search",
        "access_policy": "configured_api_or_self_hosted_only",
        "credential_policy": "service_api_key_only",
        "cost_model": "provider_credits",
        "fallback": "public_pages_and_official_public_apis",
    },
    "Gemini Grounding with Google Search": {
        "adapter_id": "google_grounded_search",
        "channel": "cited_public_search",
        "access_policy": "configured_google_provider_only",
        "credential_policy": "service_credential_only",
        "cost_model": "provider_requests",
        "fallback": "customer_urls_and_public_page_reader",
    },
    "YouTube public metadata": {
        "adapter_id": "youtube_public_metadata",
        "channel": "public_video_metadata",
        "access_policy": "public_metadata_only",
        "credential_policy": "no_personal_cookie",
        "cost_model": "local_compute_or_official_quota",
        "fallback": "official_api_key_or_public_url",
    },
    "Meta / TikTok public discovery": {
        "adapter_id": "social_public_discovery",
        "channel": "public_social_discovery",
        "access_policy": "search_index_and_official_embed_only",
        "credential_policy": "no_personal_cookie",
        "cost_model": "included_in_search",
        "fallback": "customer_authorized_export_or_official_api",
    },
    "Lazada / Shopee public commerce evidence": {
        "adapter_id": "marketplace_public_evidence",
        "channel": "public_commerce_pages",
        "access_policy": "public_product_metadata_only",
        "credential_policy": "no_personal_cookie",
        "cost_model": "included_in_page_collection",
        "fallback": "customer_export_or_authorized_provider",
    },
}


def _is_offline_study(study: Mapping[str, Any]) -> bool:
    return str(study.get("study_type") or "").upper() in OFFLINE_STUDY_TYPES


def _country_code(study: Mapping[str, Any]) -> str:
    facts = study.get("facts") or {}
    inputs = study.get("inputs") or {}
    return str(
        facts.get("country_code")
        or inputs.get("country_code")
        or study.get("country_code")
        or "TH"
    ).strip().upper()


def _is_marketplace_evidence(item: Mapping[str, Any]) -> bool:
    """Avoid letting a redirect or title hide an e-commerce result as TikTok."""
    platform = str(item.get("platform") or "").casefold()
    if platform in {"shopee", "lazada", "tiktok shop"}:
        return True
    text = " ".join(
        str(item.get(field) or "")
        for field in ("url", "title", "excerpt", "description")
    ).casefold()
    return any(marker in text for marker in ("shopee", "lazada", "tiktok shop"))


URL_TOKEN_STOPWORDS = {
    "collection",
    "collections",
    "global",
    "html",
    "official",
    "product",
    "products",
    "shop",
    "thailand",
    "version",
    "white",
}

PageReader = Callable[[List[str]], Awaitable[List[Dict[str, Any]]]]
VideoSearcher = Callable[[str, int], Awaitable[List[Dict[str, Any]]]]
ConsumerSearcher = Callable[[str, int], Awaitable[List[Dict[str, Any]]]]
GroundedSearcher = Callable[
    [List[str], int],
    Awaitable[Dict[str, Any]],
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any, limit: int = 12_000) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _hostname_platform(hostname: str) -> str:
    normalized = hostname.lower().removeprefix("www.")
    for suffix, platform in PLATFORM_HOSTS.items():
        if normalized == suffix or normalized.endswith(f".{suffix}"):
            return platform
    return "公开网页"


def _research_url_domain_cap(hostname: str) -> int:
    """Allow a useful SKU panel without letting other sources dominate."""
    normalized = hostname.lower().removeprefix("www.").rstrip(".")
    if any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in MARKETPLACE_SOURCE_DOMAINS
    ):
        return MAX_MARKETPLACE_URLS_PER_DOMAIN
    return MAX_RESEARCH_URLS_PER_DOMAIN


def _grounded_platform(title: str, url: str) -> str:
    """Recover the source platform when Google returns a redirect URL."""
    parsed = urllib.parse.urlsplit(url)
    platform = _hostname_platform(parsed.hostname or "")
    if platform != "公开网页":
        return platform
    title_host = _clean_text(title, 200).lower()
    for hostname, label in PLATFORM_HOSTS.items():
        if hostname in title_host:
            return label
    return "公开网页"


def _is_public_http_url(value: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "metadata.google.internal"} or hostname.endswith(
        (".local", ".internal")
    ):
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        return True


def _resolved_to_public_ip(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    if not addresses:
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return False
    return True


def _source_id(source_type: str, url: str, content_hash: str) -> str:
    raw = f"{source_type}|{url}|{content_hash}".encode("utf-8")
    return f"src_{hashlib.sha256(raw).hexdigest()[:16]}"


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _canonical_url(value: str) -> str:
    """Normalize public result URLs so tracking parameters do not create duplicates."""
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return value
    filtered_query = urllib.parse.urlencode(
        [
            (key, item)
            for key, item in urllib.parse.parse_qsl(
                parsed.query,
                keep_blank_values=False,
            )
            if not key.lower().startswith("utm_")
            and key.lower()
            not in {
                "fbclid",
                "gclid",
                "ref",
                "referrer",
                "source",
                "spm",
            }
        ]
    )
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            filtered_query,
            "",
        )
    )


def _evidence_data_status(item: Mapping[str, Any]) -> str:
    """Keep public observations distinct from assumptions and weak labels."""
    source_type = str(item.get("source_type") or "").casefold()
    if item.get("observed") is False or any(
        marker in source_type
        for marker in ("assumption", "inferred", "weak_label", "synthetic")
    ):
        return "inferred_or_assumed"
    return "observed_public_evidence"


def _source_health_snapshot(
    collectors: List[Dict[str, Any]],
    checked_at: str,
) -> Dict[str, Any]:
    """Normalize collector outcomes into one operational health contract."""
    adapters: List[Dict[str, Any]] = []
    health_counts: Dict[str, int] = {}
    for collector in collectors:
        name = str(collector.get("collector") or "unknown")
        status = str(collector.get("status") or "unknown")
        failure_reason = collector.get("failure_reason")
        if status == "succeeded" and not failure_reason:
            health = "healthy"
        elif status in {"succeeded", "partial", "public_only"}:
            health = "degraded"
        elif status == "unavailable":
            health = "unavailable"
        else:
            health = "inactive"
        health_counts[health] = health_counts.get(health, 0) + 1
        requested = int(collector.get("requested") or 0)
        result_count = int(collector.get("result_count") or 0)
        registry = SOURCE_ADAPTER_REGISTRY.get(name, {})
        adapters.append(
            {
                "collector": name,
                **registry,
                "health": health,
                "collector_status": status,
                "requested": requested,
                "result_count": result_count,
                "success_rate": (
                    round(min(1.0, result_count / requested), 4)
                    if requested > 0
                    else None
                ),
                "failure_reason": failure_reason,
                "fallback_result": collector.get("fallback_result"),
                "estimated_credits": int(
                    collector.get("estimated_credits") or 0
                ),
            }
        )
    active = [
        item for item in adapters if item["health"] != "inactive"
    ]
    if not active:
        overall_status = "inactive"
    elif all(item["health"] == "healthy" for item in active):
        overall_status = "healthy"
    elif any(item["health"] == "healthy" for item in active):
        overall_status = "degraded"
    else:
        overall_status = "unavailable"
    return {
        "version": "SOURCE-HEALTH-2026.08.1",
        "checked_at": checked_at,
        "overall_status": overall_status,
        "health_counts": health_counts,
        "adapters": adapters,
    }


def _parse_publication_time(item: Mapping[str, Any]) -> Optional[datetime]:
    for key in ("published_at", "published_date", "publication_date"):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _evidence_audit(
    evidence: List[Dict[str, Any]],
    *,
    candidate_count: int,
    duplicate_url_count: int,
    duplicate_content_count: int,
    scope_excluded_count: int,
    completed_at: str,
) -> Dict[str, Any]:
    """Audit evidence quality without converting public signals into sales truth."""
    domains: Dict[str, int] = {}
    grade_counts: Dict[str, int] = {}
    data_status_counts: Dict[str, int] = {}
    publication_times: List[datetime] = []
    provenance_count = 0
    hash_count = 0
    for item in evidence:
        hostname = (
            urllib.parse.urlsplit(str(item.get("url") or "")).hostname or ""
        ).lower().removeprefix("www.")
        if hostname:
            domains[hostname] = domains.get(hostname, 0) + 1
        grade = str(item.get("evidence_grade") or "ungraded")
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
        data_status = str(
            item.get("data_status") or _evidence_data_status(item)
        )
        data_status_counts[data_status] = (
            data_status_counts.get(data_status, 0) + 1
        )
        if item.get("source_id") and item.get("url"):
            provenance_count += 1
        if item.get("content_sha256"):
            hash_count += 1
        published_at = _parse_publication_time(item)
        if published_at:
            publication_times.append(published_at)

    accepted_count = len(evidence)
    top_domain = max(domains, key=domains.get) if domains else None
    top_domain_count = domains.get(top_domain, 0) if top_domain else 0
    top_domain_share = (
        round(top_domain_count / accepted_count, 4)
        if accepted_count
        else 0.0
    )
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    stale_publication_count = sum(
        1
        for published_at in publication_times
        if (completed - published_at).days > 365
    )
    flags: List[str] = []
    if accepted_count >= 5 and top_domain_share > 0.6:
        flags.append("single_domain_concentration")
    if provenance_count != accepted_count:
        flags.append("missing_provenance")
    if hash_count != accepted_count:
        flags.append("missing_content_hash")
    if data_status_counts.get("inferred_or_assumed", 0):
        flags.append("inferred_evidence_requires_separation")
    if stale_publication_count:
        flags.append("stale_published_evidence_present")

    return {
        "version": "EVIDENCE-AUDIT-2026.08.1",
        "status": "attention_required" if flags else "passed",
        "audited_at": completed_at,
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "duplicate_url_count": duplicate_url_count,
        "duplicate_content_count": duplicate_content_count,
        "scope_excluded_count": scope_excluded_count,
        "provenance_coverage": (
            round(provenance_count / accepted_count, 4)
            if accepted_count
            else 0.0
        ),
        "content_hash_coverage": (
            round(hash_count / accepted_count, 4)
            if accepted_count
            else 0.0
        ),
        "publication_time_coverage": (
            round(len(publication_times) / accepted_count, 4)
            if accepted_count
            else 0.0
        ),
        "stale_publication_count": stale_publication_count,
        "domain_counts": dict(sorted(domains.items())),
        "top_domain": top_domain,
        "top_domain_share": top_domain_share,
        "grade_counts": dict(sorted(grade_counts.items())),
        "data_status_counts": dict(sorted(data_status_counts.items())),
        "flags": flags,
        "quantitative_policy": (
            "public evidence may enrich choice-set attributes but may not "
            "directly calibrate choice coefficients or be presented as sales"
        ),
    }


def _market_signals(content: str) -> Dict[str, List[str]]:
    patterns = {
        "prices": (
            r"(?:฿\s?[\d][\d,]*(?:\.\d{1,2})?"
            r"|(?:THB|บาท)\s?[\d][\d,]*(?:\.\d{1,2})?"
            r"|[\d][\d,]*(?:\.\d{1,2})?\s?บาท"
            r"|(?:RM|MYR)\s?[\d][\d,]*(?:\.\d{1,2})?)"
        ),
        "ratings": (
            r"\b[0-5](?:\.\d{1,2})?\s*"
            r"(?:/\s?5|ดาว|คะแนน|rating)"
        ),
        "sales_mentions": (
            r"(?:ขายแล้ว|ขายได้|sold)\s*"
            r"[\d,.]+\s*(?:k|พัน|หมื่น|ชิ้น)?"
        ),
        "review_mentions": (
            r"(?:[\d,.]+\s*)?"
            r"(?:รีวิว|reviews?|ratings?|ความคิดเห็น)"
        ),
    }
    return {
        field: _unique(
            _clean_text(match, 120)
            for match in re.findall(pattern, content, flags=re.IGNORECASE)
        )[:10]
        for field, pattern in patterns.items()
    }


def _url_identity_terms(url: str) -> List[str]:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).lower()
    return [
        token
        for token in _unique(re.split(r"[^a-z0-9ก-๙]+", path))
        if len(token) >= 4 and token not in URL_TOKEN_STOPWORDS
    ][:20]


class PublicMarketResearch:
    """Collect public evidence for PROFESSIONAL runs with bounded, clear usage."""

    def __init__(
        self,
        enabled: Optional[bool] = None,
        page_reader: Optional[PageReader] = None,
        video_searcher: Optional[VideoSearcher] = None,
        max_pages: Optional[int] = None,
        max_videos: Optional[int] = None,
        consumer_searcher: Optional[ConsumerSearcher] = None,
        firecrawl_enabled: Optional[bool] = None,
        max_search_results: Optional[int] = None,
        max_search_queries: Optional[int] = None,
        max_evidence: Optional[int] = None,
        grounded_searcher: Optional[GroundedSearcher] = None,
        google_grounded_search_enabled: Optional[bool] = None,
    ):
        configured = os.environ.get("MARKET_RESEARCH_ENABLED", "").lower()
        self.enabled = (
            enabled
            if enabled is not None
            else configured in {"1", "true", "yes", "on"}
        )
        self.page_reader = page_reader or self._crawl_public_pages
        self.video_searcher = video_searcher or self._search_youtube
        firecrawl_configured = os.environ.get(
            "FIRECRAWL_ENABLED",
            "",
        ).lower()
        firecrawl_requested = (
            firecrawl_enabled
            if firecrawl_enabled is not None
            else bool(consumer_searcher)
            or firecrawl_configured in {"1", "true", "yes", "on"}
        )
        firecrawl_url = os.environ.get(
            "FIRECRAWL_API_URL",
            "https://api.firecrawl.dev/v2",
        ).rstrip("/")
        firecrawl_has_access = bool(consumer_searcher) or bool(
            os.environ.get("FIRECRAWL_API_KEY", "").strip()
        )
        if firecrawl_url != "https://api.firecrawl.dev/v2":
            firecrawl_has_access = True
        if os.environ.get("FIRECRAWL_ALLOW_KEYLESS", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            firecrawl_has_access = True
        # Firecrawl Cloud's keyless endpoint is not a dependable production
        # data source.  It may briefly answer before returning a wall of 429s.
        self.firecrawl_enabled = bool(
            firecrawl_requested and firecrawl_has_access
        )
        self.firecrawl_requested = bool(firecrawl_requested)
        self.consumer_searcher = consumer_searcher or self._search_firecrawl
        grounded_configured = os.environ.get(
            "GOOGLE_GROUNDED_SEARCH_ENABLED",
            "",
        ).lower()
        self.google_grounded_search_enabled = (
            google_grounded_search_enabled
            if google_grounded_search_enabled is not None
            else bool(grounded_searcher)
            or grounded_configured in {"1", "true", "yes", "on"}
        )
        self._uses_default_grounded_search = grounded_searcher is None
        self.grounded_searcher = grounded_searcher or self._search_google_grounded
        configured_page_limit = max_pages or os.environ.get(
            "MARKET_RESEARCH_MAX_PAGES",
            "20",
        )
        configured_video_limit = max_videos or os.environ.get(
            "MARKET_RESEARCH_MAX_VIDEOS",
            "8",
        )
        self.max_pages = max(1, min(int(configured_page_limit), 30))
        self.max_videos = max(1, min(int(configured_video_limit), 30))
        configured_search_limit = max_search_results or os.environ.get(
            "FIRECRAWL_SEARCH_LIMIT",
            "10",
        )
        self.max_search_results = max(
            1,
            min(int(configured_search_limit), 10),
        )
        configured_query_limit = max_search_queries or os.environ.get(
            "MARKET_RESEARCH_QUERY_COUNT",
            "12",
        )
        self.max_search_queries = max(
            1,
            min(int(configured_query_limit), 20),
        )
        configured_evidence_limit = max_evidence or os.environ.get(
            "MARKET_RESEARCH_EVIDENCE_LIMIT",
            "150",
        )
        self.max_evidence = max(
            20,
            min(int(configured_evidence_limit), 200),
        )
        self.search_concurrency = max(
            1,
            min(
                int(os.environ.get("MARKET_RESEARCH_SEARCH_CONCURRENCY", "3")),
                6,
            ),
        )
        self.retry_attempts = max(
            1,
            min(
                int(os.environ.get("MARKET_RESEARCH_RETRY_ATTEMPTS", "3")),
                4,
            ),
        )

    @staticmethod
    def _research_urls(study: Mapping[str, Any]) -> List[str]:
        inputs = study.get("inputs") or {}
        facts = study.get("facts") or {}
        candidates: List[str] = []
        for value in (
            facts.get("url"),
            inputs.get("url"),
            *(inputs.get("research_urls") or []),
            *(inputs.get("competitors") or []),
        ):
            if isinstance(value, str) and _is_public_http_url(value):
                candidates.append(value.strip())
        for item in (
            list(inputs.get("competitor_data") or [])
            + list(facts.get("competitor_data") or [])
        ):
            if not isinstance(item, Mapping):
                continue
            for key in ("source_url", "url", "product_url"):
                value = item.get(key)
                if isinstance(value, str) and _is_public_http_url(value):
                    candidates.append(value.strip())
        # A customer may paste multiple product variants or tracking links from
        # the same marketplace. Canonicalise before deduplication and bound a
        # single host so one unstable source cannot dominate the evidence set.
        accepted: List[str] = []
        domain_counts: Dict[str, int] = {}
        for candidate in candidates:
            canonical = _canonical_url(candidate)
            if canonical in accepted:
                continue
            hostname = (
                urllib.parse.urlsplit(canonical).hostname or ""
            ).lower().removeprefix("www.")
            if domain_counts.get(hostname, 0) >= _research_url_domain_cap(
                hostname
            ):
                continue
            domain_counts[hostname] = domain_counts.get(hostname, 0) + 1
            accepted.append(canonical)
        return accepted

    @staticmethod
    def _search_query(study: Mapping[str, Any]) -> str:
        inputs = study.get("inputs") or {}
        facts = study.get("facts") or {}
        pieces = _unique(
            [
                facts.get("product_name") or study.get("name") or "",
                facts.get("category") or inputs.get("category") or "",
                *(inputs.get("competitors") or [])[:2],
            ]
        )
        plain = [value for value in pieces if not _is_public_http_url(value)]
        suffix = (
            " Malaysia ulasan review"
            if _country_code(study) == "MY"
            else " Thailand รีวิว review"
        )
        return _clean_text(" ".join(plain) + suffix, 240)

    @staticmethod
    def _offline_location_labels(study: Mapping[str, Any]) -> List[str]:
        facts = study.get("facts") or {}
        inputs = study.get("inputs") or {}
        candidates = (
            facts.get("candidate_locations")
            or inputs.get("candidate_locations")
            or []
        )
        values: List[Any] = []
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                values.extend(
                    candidate.get(key)
                    for key in (
                        "label",
                        "name",
                        "address",
                        "formatted_address",
                    )
                )
        location = facts.get("location") or inputs.get("location")
        if isinstance(location, Mapping):
            values.extend(
                location.get(key)
                for key in ("label", "name", "address", "formatted_address")
            )
        return [
            _clean_text(value, 140)
            for value in _unique(values)
            if _clean_text(value, 140)
        ][:5]

    @staticmethod
    def _consumer_search_query(study: Mapping[str, Any]) -> str:
        base = PublicMarketResearch._search_query(study)
        if _country_code(study) == "MY":
            if _is_offline_study(study):
                locations = PublicMarketResearch._offline_location_labels(study)
                location_context = " ".join(locations) or "Malaysia"
                return _clean_text(
                    f"{base} {location_context} ulasan kedai suasana harga "
                    "Google Maps Facebook TikTok akses pengangkutan parkir",
                    320,
                )
            return _clean_text(
                f"{base} harga kelebihan kekurangan pengalaman sebenar "
                "beli Shopee Malaysia Lazada Malaysia TikTok",
                320,
            )
        if _is_offline_study(study):
            locations = PublicMarketResearch._offline_location_labels(study)
            location_context = " ".join(locations) or "Thailand"
            return _clean_text(
                f"{base} {location_context} รีวิวร้าน บรรยากาศ ราคา "
                "Google Maps Facebook TikTok การเดินทาง ที่จอดรถ",
                320,
            )
        return _clean_text(
            f"{base} ราคา ข้อดี ข้อเสีย ใช้จริง ซื้อที่ไหน "
            "Shopee Lazada TikTok Thailand",
            320,
        )

    @staticmethod
    def _consumer_search_queries(study: Mapping[str, Any]) -> List[str]:
        """Build local consumer-intent query clusters instead of one broad query."""
        inputs = study.get("inputs") or {}
        facts = study.get("facts") or {}
        product = _clean_text(
            facts.get("product_name") or study.get("name") or "",
            120,
        )
        category = _clean_text(
            facts.get("category") or inputs.get("category") or product,
            100,
        )
        subject = _clean_text(" ".join(_unique([product, category])), 180)
        is_malaysia = _country_code(study) == "MY"
        if _is_offline_study(study):
            venue_type = _clean_text(
                facts.get("venue_type") or inputs.get("venue_type") or category,
                100,
            )
            locations = PublicMarketResearch._offline_location_labels(study)
            location_context = " ".join(locations) or (
                "Malaysia" if is_malaysia else "Thailand"
            )
            if is_malaysia:
                query_templates = [
                    f"{subject} {location_context} ulasan kedai suasana harga",
                    f"{venue_type} {location_context} Google Maps ulasan akses parkir",
                    f"{location_context} tempat popular penduduk tempatan pelancong waktu sibuk",
                    f"site:facebook.com {subject} {location_context} ulasan Malaysia",
                    f"site:tiktok.com {subject} {location_context} review Malaysia",
                    f"site:instagram.com {subject} {location_context} Malaysia review",
                    f"{location_context} pengangkutan awam parkir pedestrian access",
                    f"{location_context} cafe restaurant competitor price review Malaysia",
                    f"{location_context} tourism local demand cafe restaurant Malaysia",
                    f"{venue_type} Malaysia forum ulasan cadangan masalah",
                    f"{venue_type} Malaysia operating hours queue service review",
                    f"{subject} {location_context} local community event demand",
                ]
                return _unique(
                    _clean_text(query, 320) for query in query_templates
                )
            query_templates = [
                f"{subject} {location_context} รีวิวร้าน บรรยากาศ ราคา",
                f"{venue_type} {location_context} Google Maps รีวิว การเดินทาง ที่จอดรถ",
                f"{location_context} ร้านน่าไป คนท้องถิ่น นักท่องเที่ยว ช่วงเวลา",
                f"site:facebook.com {subject} {location_context} รีวิว ความคิดเห็น ไทย",
                f"site:tiktok.com {subject} {location_context} รีวิวร้าน ไทย",
                f"site:instagram.com {subject} {location_context} Thailand review",
                f"{location_context} การเดินทาง รถสาธารณะ ที่จอดรถ คนเดิน",
                f"{location_context} คาเฟ่ ร้านอาหาร คู่แข่ง ราคา รีวิว Thailand",
                f"{location_context} tourism local demand cafe restaurant Thailand",
                f"{venue_type} Thailand Pantip รีวิว ร้านแนะนำ ปัญหา",
                f"{venue_type} Thailand operating hours queue service review",
                f"{subject} {location_context} local community event demand",
            ]
            return _unique(
                _clean_text(query, 320) for query in query_templates
            )
        competitors = [
            value
            for value in _unique(
                [
                    *(inputs.get("competitors") or []),
                    *(
                        item.get("name")
                        for item in (inputs.get("competitor_data") or [])
                        if isinstance(item, Mapping)
                    ),
                ]
            )
            if value and not _is_public_http_url(value)
        ][:3]
        if is_malaysia:
            query_templates = [
                f"{subject} ulasan pengalaman sebenar kelebihan kekurangan Malaysia",
                f"{subject} masalah rosak bising pulangan ulasan negatif",
                f"{subject} harga berbaloi perbandingan model terbaik",
                f"{subject} beli Shopee Malaysia Lazada Malaysia ulasan pembeli",
                f"site:tiktok.com {subject} ulasan Malaysia pengalaman sebenar",
                f"site:facebook.com {subject} ulasan pendapat Malaysia",
                f"site:instagram.com {subject} Malaysia review",
                f"site:youtube.com {subject} Malaysia review test unboxing",
                f"{category} Malaysia consumer demand buying behaviour",
                f"{category} Malaysia forum review problem recommendation",
                f"{category} warranty delivery after sales Malaysia",
                f"{category} alternatives competitors popular brands Malaysia",
                *(
                    f"{subject} vs {competitor} price review Malaysia"
                    for competitor in competitors
                ),
            ]
            return _unique(
                _clean_text(query, 320) for query in query_templates
            )
        query_templates = [
            f"{subject} รีวิว ใช้จริง ข้อดี ข้อเสีย ประเทศไทย",
            f"{subject} ปัญหา เสีย พัง เสียงดัง คืนสินค้า รีวิวลบ",
            f"{subject} ราคา คุ้มไหม เปรียบเทียบ รุ่นไหนดี",
            f"{subject} ซื้อที่ไหน Shopee Lazada Thailand รีวิวผู้ซื้อ",
            f"site:tiktok.com {subject} รีวิว ไทย ใช้จริง",
            f"site:facebook.com {subject} รีวิว ความคิดเห็น ไทย",
            f"site:instagram.com {subject} Thailand review",
            f"site:youtube.com {subject} รีวิว ทดสอบ แกะกล่อง",
            f"{category} ความต้องการ ผู้บริโภคไทย พฤติกรรมการซื้อ",
            f"{category} pantip รีวิว ปัญหา แนะนำ",
            f"{category} รับประกัน จัดส่ง บริการหลังการขาย ประเทศไทย",
            f"{category} ทางเลือก คู่แข่ง แบรนด์ยอดนิยม Thailand",
            *(
                f"{subject} เทียบ {competitor} ราคา รีวิว Thailand"
                for competitor in competitors
            ),
        ]
        return _unique(_clean_text(query, 320) for query in query_templates)

    async def _search_consumer_queries(
        self,
        queries: List[str],
    ) -> Dict[str, Any]:
        semaphore = asyncio.Semaphore(self.search_concurrency)

        async def search_one(query: str) -> Dict[str, Any]:
            async with semaphore:
                last_error: Optional[Exception] = None
                for attempt in range(self.retry_attempts):
                    try:
                        items = await self.consumer_searcher(
                            query,
                            self.max_search_results,
                        )
                        for item in items:
                            item.setdefault("query_cluster", query)
                        return {
                            "query": query,
                            "items": items,
                            "error": None,
                            "attempts": attempt + 1,
                        }
                    except Exception as error:
                        last_error = error
                        if attempt + 1 < self.retry_attempts:
                            await asyncio.sleep(min(4.0, 0.75 * 2**attempt))
                return {
                    "query": query,
                    "items": [],
                    "error": type(last_error).__name__,
                    "attempts": self.retry_attempts,
                }

        results = await asyncio.gather(
            *(search_one(query) for query in queries),
        )
        return {
            "items": [
                item
                for result in results
                for item in result["items"]
            ],
            "completed_queries": sum(
                1 for result in results if not result["error"]
            ),
            "failed_queries": [
                {
                    "query": result["query"],
                    "error": result["error"],
                }
                for result in results
                if result["error"]
            ],
        }

    async def _run_grounded_search(
        self,
        queries: List[str],
        study: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Keep injected test/search adapters compatible with the two-arg API."""
        if self._uses_default_grounded_search:
            return await self._search_google_grounded(
                queries,
                self.max_search_results,
                offline_venue=_is_offline_study(study),
                country_code=_country_code(study),
            )
        return await self.grounded_searcher(
            queries,
            self.max_search_results,
        )

    async def collect(
        self,
        study: Mapping[str, Any],
        plan_code: str,
    ) -> Dict[str, Any]:
        started_at = _utc_now()
        is_offline = _is_offline_study(study)
        source_strategy = (
            OFFLINE_SOURCE_STRATEGY if is_offline else SOURCE_STRATEGY
        )
        base = {
            "version": RESEARCH_VERSION,
            "status": "not_applicable",
            "started_at": started_at,
            "completed_at": started_at,
            "query": self._search_query(study),
            "consumer_search_query": self._consumer_search_query(study),
            "consumer_search_queries": [],
            "source_count": 0,
            "candidate_count": 0,
            "platform_counts": {},
            "evidence": [],
            "collectors": [],
            "source_health": {
                "version": "SOURCE-HEALTH-2026.08.1",
                "checked_at": started_at,
                "overall_status": "not_run",
                "health_counts": {},
                "adapters": [],
            },
            "evidence_audit": {
                "version": "EVIDENCE-AUDIT-2026.08.1",
                "status": "not_run",
                "audited_at": started_at,
                "flags": [],
            },
            "warnings": [],
            "source_strategy": {
                "ranking_basis": (
                    "到店与选址决策价值，不按采集便利度或单纯访问量排序"
                    if is_offline
                    else "购买决策价值，不按采集便利度或单纯访问量排序"
                ),
                "scope": (
                    "offline_venue_acquisition"
                    if is_offline
                    else "product_purchase_acquisition"
                ),
                "priority_order": source_strategy,
                "discovery_channel": (
                    "Firecrawl 消费者公开检索；只作为公开线索，不代表平台后台数据"
                ),
            },
            "usage_policy": {
                "quantitative_effect": (
                    "verified_public_price_rating_fields_may_update_choice_"
                    "set_attributes_but_never_choice_coefficients"
                ),
                "allowed": [
                    "竞品与价格证据",
                    "公开评价主题",
                    "可验证公开价格与评分用于补充产品和竞品属性",
                    "传播素材与市场风险",
                    "后续调研问题",
                ],
                "not_allowed": [
                    "把点赞、播放或页面销量文案直接当成成交量",
                    "绕过登录、验证码或平台访问限制",
                    "使用个人浏览器 Cookie 进行商业批量采集",
                ],
            },
            "source_adapter_policy": {
                "version": "SOURCE-ADAPTER-REGISTRY-2026.08.1",
                "adapter_ids": [
                    item["adapter_id"]
                    for item in SOURCE_ADAPTER_REGISTRY.values()
                ],
                "credential_rule": (
                    "service credentials, official APIs, customer-authorized "
                    "exports, or public no-login access only"
                ),
                "prohibited": [
                    "personal browser cookies",
                    "login or captcha bypass",
                    "private endpoints",
                ],
            },
        }
        if str(plan_code).upper() != "PROFESSIONAL":
            base["warnings"] = ["公开市场深度扫描仅在深度决策中执行。"]
            return base
        base["version"] = PROFESSIONAL_RESEARCH_VERSION
        base["source_strategy"]["discovery_channel"] = (
            (
                "Gemini Google Search Grounding 与已配置的 Firecrawl，"
                "仅检索线下地点、商圈与到店发现公开线索；"
                "不把电商平台当作线下渠道证据"
            )
            if is_offline
            else (
                "Gemini Google Search Grounding 与已配置的 Firecrawl；"
                "只作为公开线索，不代表平台后台数据"
            )
        )
        if not self.enabled:
            base["status"] = "disabled"
            base["warnings"] = ["公开市场采集在当前环境未启用。"]
            return base

        urls = self._research_urls(study)[: self.max_pages]
        source_domains = sorted(
            {
                (urllib.parse.urlsplit(url).hostname or "")
                .lower()
                .removeprefix("www.")
                for url in urls
            }
        )
        base["customer_source_scope"] = {
            "requested_public_urls": len(urls),
            "unique_domains": len(source_domains),
            "domains": source_domains,
            "per_domain_cap": MAX_RESEARCH_URLS_PER_DOMAIN,
            "marketplace_per_domain_cap": MAX_MARKETPLACE_URLS_PER_DOMAIN,
            "marketplace_domains": list(MARKETPLACE_SOURCE_DOMAINS),
            "purpose": (
                "Capture attributable public product, competitor, price, "
                "promotion, rating and product-claim evidence."
            ),
        }
        scope_warnings: List[str] = []
        if is_offline:
            marketplace_urls = [
                url
                for url in urls
                if _hostname_platform(
                    urllib.parse.urlsplit(url).hostname or ""
                )
                in MARKETPLACE_PLATFORMS
            ]
            urls = [url for url in urls if url not in marketplace_urls]
            if marketplace_urls:
                scope_warnings.append(
                    "线下研究已忽略电商商品页；请提供地点、商圈或公开社群页面作为补充来源。"
                )
        query = base["query"]
        consumer_queries = self._consumer_search_queries(study)[
            : self.max_search_queries
        ]
        base["consumer_search_queries"] = consumer_queries
        page_task = asyncio.create_task(self.page_reader(urls))
        video_task = asyncio.create_task(
            self.video_searcher(query, self.max_videos)
        )
        if self.firecrawl_enabled:
            search_task = asyncio.create_task(
                self._search_consumer_queries(consumer_queries)
            )
        else:
            search_task = asyncio.create_task(
                asyncio.sleep(
                    0,
                    result={
                        "items": [],
                        "completed_queries": 0,
                        "failed_queries": [],
                    },
                )
            )
        if self.google_grounded_search_enabled:
            grounded_task = asyncio.create_task(
                self._run_grounded_search(consumer_queries, study)
            )
        else:
            grounded_task = asyncio.create_task(
                asyncio.sleep(
                    0,
                    result={
                        "items": [],
                        "completed_queries": 0,
                        "failed_queries": [],
                        "request_count": 0,
                        "providers_used": [],
                    },
                )
            )
        (
            page_results,
            video_results,
            search_results,
            grounded_results,
        ) = await asyncio.gather(
            page_task,
            video_task,
            search_task,
            grounded_task,
            return_exceptions=True,
        )

        evidence: List[Dict[str, Any]] = []
        collectors: List[Dict[str, Any]] = []
        warnings: List[str] = list(scope_warnings)
        if isinstance(page_results, Exception):
            page_failure_reason = type(page_results).__name__
            warnings.append(f"公开网页采集失败：{page_failure_reason}")
            page_items: List[Dict[str, Any]] = []
            page_status = "unavailable"
        else:
            page_failure_reason = None
            page_items = page_results
            page_status = "succeeded" if page_items else (
                "not_applicable" if not urls else "partial"
            )
            evidence.extend(page_items)
        collectors.append(
            {
                "collector": "Crawl4AI public page reader",
                "status": page_status,
                "requested": len(urls),
                "result_count": len(page_items),
                "failure_reason": page_failure_reason,
                "fallback_result": (
                    None if page_items else "public_search_discovery"
                ),
            }
        )

        if not self.firecrawl_enabled:
            search_items: List[Dict[str, Any]] = []
            search_status = "disabled"
            search_failure_reason = None
        elif isinstance(search_results, Exception):
            search_failure_reason = type(search_results).__name__
            warnings.append(
                f"消费者公开检索失败：{search_failure_reason}"
            )
            search_items = []
            search_status = "unavailable"
        else:
            search_failure_reason = None
            search_items = search_results["items"]
            search_status = "succeeded" if search_items else "partial"
            evidence.extend(search_items)
            failed_searches = search_results["failed_queries"]
            if failed_searches:
                search_failure_reason = (
                    f"{len(failed_searches)}_query_failures"
                )
                warnings.append(
                    f"Firecrawl 有 {len(failed_searches)} 个检索主题失败；"
                    "系统已保留其他成功来源。"
                )
        collectors.append(
            {
                "collector": "Firecrawl multi-query consumer research",
                "status": search_status,
                "requested": (
                    len(consumer_queries) * self.max_search_results
                    if self.firecrawl_enabled
                    else 0
                ),
                "result_count": len(search_items),
                "failure_reason": search_failure_reason,
                "query_count": len(consumer_queries),
                "completed_queries": (
                    int(search_results.get("completed_queries", 0))
                    if isinstance(search_results, Mapping)
                    else 0
                ),
                "estimated_credits": (
                    2 * len(consumer_queries)
                    if self.firecrawl_enabled
                    else 0
                ),
                "access_mode": (
                    "api_key"
                    if os.environ.get("FIRECRAWL_API_KEY")
                    else "self_hosted_or_injected"
                    if self.firecrawl_enabled
                    else "not_configured"
                ),
                "fallback_result": (
                    None
                    if search_items
                    else "public_pages_and_official_public_apis"
                ),
            }
        )

        if not self.google_grounded_search_enabled:
            grounded_items: List[Dict[str, Any]] = []
            grounded_status = "disabled"
            grounded_failure_reason = None
        elif isinstance(grounded_results, Exception):
            grounded_items = []
            grounded_status = "unavailable"
            grounded_failure_reason = type(grounded_results).__name__
            warnings.append(
                "Google 公开检索失败："
                f"{grounded_failure_reason}"
            )
        else:
            grounded_failure_reason = None
            grounded_items = list(grounded_results.get("items") or [])
            grounded_status = "succeeded" if grounded_items else "partial"
            evidence.extend(grounded_items)
            failed_grounded = list(
                grounded_results.get("failed_queries") or []
            )
            if failed_grounded:
                grounded_failure_reason = (
                    f"{len(failed_grounded)}_query_failures"
                )
                warnings.append(
                    f"Google 公开检索有 {len(failed_grounded)} 个主题失败；"
                    "系统已保留带引用的成功结果。"
                )
        collectors.append(
            {
                "collector": "Gemini Grounding with Google Search",
                "status": grounded_status,
                "requested": len(consumer_queries),
                "result_count": len(grounded_items),
                "failure_reason": grounded_failure_reason,
                "query_count": len(consumer_queries),
                "completed_queries": (
                    int(grounded_results.get("completed_queries", 0))
                    if isinstance(grounded_results, Mapping)
                    else 0
                ),
                "request_count": (
                    int(grounded_results.get("request_count", 0))
                    if isinstance(grounded_results, Mapping)
                    else 0
                ),
                "providers_used": (
                    list(grounded_results.get("providers_used") or [])
                    if isinstance(grounded_results, Mapping)
                    else []
                ),
                "access_mode": "google_search_grounding",
                "fallback_result": (
                    None
                    if grounded_items
                    else "customer_urls_and_public_page_reader"
                ),
            }
        )

        if isinstance(video_results, Exception):
            video_failure_reason = type(video_results).__name__
            warnings.append(
                f"YouTube 公开资料采集失败：{video_failure_reason}"
            )
            video_items: List[Dict[str, Any]] = []
            video_status = "unavailable"
        else:
            video_failure_reason = None
            video_items = video_results
            video_status = "succeeded" if video_items else "partial"
            evidence.extend(video_items)
        collectors.append(
            {
                "collector": "YouTube public metadata",
                "status": video_status,
                "requested": self.max_videos,
                "result_count": len(video_items),
                "failure_reason": video_failure_reason,
                "fallback_result": (
                    None if video_items else "official_api_key_or_public_url"
                ),
            }
        )
        collectors.append(
            {
                "collector": "Meta / TikTok public discovery",
                "status": "public_only",
                "requested": 0,
                "result_count": 0,
                "fallback_result": "search_index_and_official_embed_only",
            }
        )
        if not is_offline:
            collectors.append(
                {
                    "collector": "Lazada / Shopee public commerce evidence",
                    "status": "public_only",
                    "requested": 0,
                    "result_count": 0,
                    "fallback_result": "public_product_metadata_only",
                }
            )

        unique_evidence: List[Dict[str, Any]] = []
        seen_urls = set()
        seen_content_hashes = set()
        duplicate_url_count = 0
        duplicate_content_count = 0
        skipped_marketplace_evidence = 0
        for item in evidence:
            url = item.get("url")
            canonical_url = _canonical_url(str(url or ""))
            if not canonical_url:
                continue
            if canonical_url in seen_urls:
                duplicate_url_count += 1
                continue
            seen_urls.add(canonical_url)
            item["url"] = canonical_url
            content_hash = str(item.get("content_sha256") or "").strip()
            if content_hash and content_hash in seen_content_hashes:
                duplicate_content_count += 1
                continue
            if content_hash:
                seen_content_hashes.add(content_hash)
            platform = str(item.get("platform") or "公开网页")
            if is_offline and _is_marketplace_evidence(item):
                skipped_marketplace_evidence += 1
                continue
            priority, role = PLATFORM_PRIORITY.get(
                platform,
                PLATFORM_PRIORITY["公开网页"],
            )
            item["decision_priority"] = priority
            item.setdefault("evidence_role", role)
            item["data_status"] = _evidence_data_status(item)
            grade_score = {
                "A": 40,
                "B": 32,
                "C": 24,
                "D": 12,
            }.get(str(item.get("evidence_grade") or "D"), 8)
            observed_score = min(
                20,
                3 * len(item.get("observed_fields") or []),
            )
            signal_score = min(
                20,
                2
                * sum(
                    len(values)
                    for values in (item.get("market_signals") or {}).values()
                ),
            )
            excerpt_score = min(
                20,
                len(str(item.get("excerpt") or "")) // 80,
            )
            item["evidence_quality_score"] = min(
                100,
                grade_score + observed_score + signal_score + excerpt_score,
            )
            unique_evidence.append(item)
        if skipped_marketplace_evidence:
            warnings.append(
                "线下研究已排除 "
                f"{skipped_marketplace_evidence} 条电商平台证据，"
                "避免把线上购买路径混入到店判断。"
            )
        unique_evidence.sort(
            key=lambda item: (
                int(item.get("decision_priority") or 99),
                -int(item.get("evidence_quality_score") or 0),
            )
        )
        unique_evidence = unique_evidence[: self.max_evidence]
        platform_counts: Dict[str, int] = {}
        for item in unique_evidence:
            platform = str(item.get("platform") or "公开网页")
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

        completed_at = _utc_now()
        evidence_audit = _evidence_audit(
            unique_evidence,
            candidate_count=len(evidence),
            duplicate_url_count=duplicate_url_count,
            duplicate_content_count=duplicate_content_count,
            scope_excluded_count=skipped_marketplace_evidence,
            completed_at=completed_at,
        )
        if "single_domain_concentration" in evidence_audit["flags"]:
            warnings.append(
                "证据审计发现单一域名占比超过 60%；"
                "报告保留该证据，但应结合其他独立来源解释。"
            )
        if "inferred_evidence_requires_separation" in evidence_audit["flags"]:
            warnings.append(
                "证据审计发现推断或假设项；"
                "系统已标记并禁止其直接校准选择系数。"
            )
        source_health = _source_health_snapshot(collectors, completed_at)
        base.update(
            {
                "status": (
                    "succeeded"
                    if unique_evidence and not warnings
                    else "partial"
                    if unique_evidence
                    else "unavailable"
                ),
                "completed_at": completed_at,
                "source_count": len(unique_evidence),
                "candidate_count": len(evidence),
                "evidence_target": {
                    "minimum": min(80, self.max_evidence),
                    "target": min(120, self.max_evidence),
                    "maximum": self.max_evidence,
                    "target_met": len(unique_evidence)
                    >= min(80, self.max_evidence),
                },
                "platform_counts": platform_counts,
                "evidence": unique_evidence,
                "collectors": collectors,
                "source_health": source_health,
                "evidence_audit": evidence_audit,
                "warnings": warnings,
            }
        )
        return base

    async def _robots_allows(self, url: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.hostname or not await asyncio.to_thread(
            _resolved_to_public_ip,
            parsed.hostname,
        ):
            return False
        robots_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "/robots.txt", "", "")
        )
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=12.0,
                follow_redirects=False,
            ) as client:
                response = await client.get(robots_url)
            if response.status_code >= 400:
                return False
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(response.text.splitlines())
            return parser.can_fetch(USER_AGENT, url)
        except httpx.HTTPError:
            return False

    async def _crawl_public_pages(
        self,
        urls: List[str],
    ) -> List[Dict[str, Any]]:
        if not urls:
            return []
        allowed: List[str] = []
        for url in urls:
            if await self._robots_allows(url):
                allowed.append(url)
        if not allowed:
            return []

        runtime_directory = Path(
            os.environ.get(
                "CRAWL4AI_RUNTIME_DIR",
                "/tmp/market-twin-crawl4ai",
            )
        )
        runtime_directory.mkdir(parents=True, exist_ok=True)
        # Crawl4AI initializes its SQLite database while being imported. Its
        # environment variable includes an underscore between "4" and "AI".
        # Set it explicitly so container runtimes cannot redirect writes to an
        # unwritable HOME directory.
        os.environ["CRAWL4_AI_BASE_DIRECTORY"] = str(runtime_directory)
        try:
            from crawl4ai import (
                AsyncWebCrawler,
                BrowserConfig,
                CacheMode,
                CrawlerRunConfig,
            )
        except ImportError:
            return await self._read_with_jina(allowed)

        browser = BrowserConfig(
            headless=True,
            java_script_enabled=True,
            user_agent=USER_AGENT,
        )
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=45_000,
            word_count_threshold=20,
        )
        items: List[Dict[str, Any]] = []
        try:
            async with AsyncWebCrawler(
                config=browser,
                base_directory=str(runtime_directory),
            ) as crawler:
                results = await crawler.arun_many(allowed, config=run_config)
                for result in results:
                    if not result.success:
                        continue
                    markdown = result.markdown
                    if not isinstance(markdown, str):
                        markdown = (
                            getattr(markdown, "fit_markdown", None)
                            or getattr(markdown, "raw_markdown", None)
                            or str(markdown)
                        )
                    item = self._page_evidence(result.url, markdown)
                    if item:
                        items.append(item)
        except Exception:
            return await self._read_with_jina(allowed)
        accepted_urls = {str(item.get("url")) for item in items}
        fallback_urls = [url for url in allowed if url not in accepted_urls]
        if fallback_urls:
            fallback_items = await self._read_with_jina(fallback_urls)
            for item in fallback_items:
                if item.get("url") not in accepted_urls:
                    items.append(item)
                    accepted_urls.add(str(item.get("url")))
        return items

    @staticmethod
    def _grounded_providers() -> List[Dict[str, Any]]:
        providers: List[Dict[str, Any]] = []
        keys: List[str] = []
        for name in (
            "GEMINI_API_KEY_PRIMARY",
            "GEMINI_API_KEY_SECONDARY",
            "GEMINI_API_KEY",
        ):
            value = os.environ.get(name, "").strip()
            if value and value not in keys:
                keys.append(value)
        for index, key in enumerate(keys, start=1):
            providers.append(
                {
                    "id": f"api_key_{index}",
                    "mode": (
                        "vertex_express"
                        if key.startswith("AQ.")
                        else "gemini_developer"
                    ),
                    "api_key": key,
                }
            )
        vertex_enabled = os.environ.get(
            "GEMINI_VERTEX_FALLBACK",
            "",
        ).lower() in {"1", "true", "yes", "on"}
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if vertex_enabled and project:
            providers.append(
                {
                    "id": "vertex_service_account",
                    "mode": "vertex_adc",
                    "project": project,
                    "location": os.environ.get(
                        "GOOGLE_CLOUD_LOCATION",
                        "global",
                    ).strip(),
                }
            )
        return providers

    @staticmethod
    async def _call_grounded_provider(
        provider: Mapping[str, Any],
        model: str,
        prompt: str,
    ) -> Any:
        from google import genai
        from google.genai import types

        mode = str(provider["mode"])
        http_options = types.HttpOptions(api_version="v1")
        if mode == "vertex_express":
            client = genai.Client(
                vertexai=True,
                api_key=str(provider["api_key"]),
                http_options=http_options,
            )
        elif mode == "gemini_developer":
            client = genai.Client(api_key=str(provider["api_key"]))
        elif mode == "vertex_adc":
            client = genai.Client(
                vertexai=True,
                project=str(provider["project"]),
                location=str(provider["location"]),
                http_options=http_options,
            )
        else:
            raise ValueError("Unsupported grounded-search provider")
        async with client.aio as async_client:
            return await async_client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.0,
                    max_output_tokens=4_096,
                ),
            )

    @staticmethod
    def _grounded_items(
        response: Any,
        queries: List[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        candidates = list(getattr(response, "candidates", None) or [])
        if not candidates:
            return []
        candidate = candidates[0]
        metadata = getattr(candidate, "grounding_metadata", None)
        if not metadata:
            return []
        chunks = list(getattr(metadata, "grounding_chunks", None) or [])
        supports = list(getattr(metadata, "grounding_supports", None) or [])
        supported_text: Dict[int, List[str]] = {}
        for support in supports:
            segment = getattr(support, "segment", None)
            text = _clean_text(getattr(segment, "text", ""), 1_200)
            if not text:
                continue
            for index in (
                getattr(support, "grounding_chunk_indices", None) or []
            ):
                supported_text.setdefault(int(index), []).append(text)

        items: List[Dict[str, Any]] = []
        seen = set()
        for index, chunk in enumerate(chunks):
            web = getattr(chunk, "web", None)
            if not web:
                continue
            url = str(getattr(web, "uri", "") or "").strip()
            title = _clean_text(getattr(web, "title", ""), 220)
            if not _is_public_http_url(url):
                continue
            excerpts = _unique(supported_text.get(index, []))
            excerpt = _clean_text(" ".join(excerpts), 1_500)
            identity = (title.lower(), excerpt.lower())
            if identity in seen:
                continue
            seen.add(identity)
            digest_payload = json.dumps(
                {
                    "title": title,
                    "url": url,
                    "excerpt": excerpt,
                    "queries": queries,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            digest = _content_hash(digest_payload)
            items.append(
                {
                    "source_id": _source_id(
                        "google_search_grounded_public",
                        url,
                        digest,
                    ),
                    "source_type": "google_search_grounded_public",
                    "collector": "Gemini Google Search Grounding",
                    "platform": _grounded_platform(title, url),
                    "title": title or "Google Search 公开引用来源",
                    "url": url,
                    "collected_at": _utc_now(),
                    "evidence_grade": "D",
                    "content_sha256": digest,
                    "excerpt": excerpt,
                    "observed_fields": [
                        "citation_title",
                        *( ["grounded_summary_segment"] if excerpt else [] ),
                    ],
                    "market_signals": _market_signals(excerpt),
                    "quality_checks": {
                        "grounded_citation": True,
                        "direct_page_retrieved": False,
                        "query_clusters": queries,
                    },
                    "evidence_role": "Google 检索引用与消费者公开线索",
                    "limitation": (
                        "来自 Gemini Grounding with Google Search 返回的"
                        "可点击引用与受支持文本片段；不是平台后台数据，"
                        "也不等同于已独立抓取并核验的页面全文或成交数据。"
                    ),
                }
            )
            if len(items) >= limit:
                break
        return items

    async def _search_google_grounded(
        self,
        queries: List[str],
        limit: int,
        offline_venue: bool = False,
        country_code: str = "TH",
    ) -> Dict[str, Any]:
        providers = self._grounded_providers()
        if not providers:
            return {
                "items": [],
                "completed_queries": 0,
                "failed_queries": [
                    {"query": "all", "error": "ProviderNotConfigured"}
                ],
                "request_count": 0,
                "providers_used": [],
            }
        group_size = max(
            1,
            min(
                int(os.environ.get("GOOGLE_GROUNDED_QUERY_GROUP_SIZE", "4")),
                8,
            ),
        )
        model = os.environ.get(
            "GEMINI_GROUNDED_SEARCH_MODEL",
            "gemini-2.5-flash",
        ).strip()
        provider_index = 0
        request_count = 0
        completed_queries = 0
        items: List[Dict[str, Any]] = []
        failures: List[Dict[str, str]] = []
        providers_used: List[Dict[str, str]] = []
        for start in range(0, len(queries), group_size):
            group = queries[start : start + group_size]
            is_malaysia = country_code == "MY"
            if offline_venue and is_malaysia:
                prompt = (
                    "Search the public web for current, decision-useful "
                    "Malaysia physical-venue and location evidence for the "
                    "query clusters below. Prioritize Malay-, English-, and "
                    "Chinese-language Google Maps or public place listings, "
                    "customer reviews, Facebook local communities, TikTok or "
                    "Instagram venue-discovery content, Malaysian local media, "
                    "transport, tourism, and official district or venue pages. "
                    "Look for accessibility, parking, opening context, nearby "
                    "competition, local versus tourist demand, and recurring "
                    "experience themes. Cite every factual claim. Do not treat "
                    "likes, views, reviews, or marketplace counters as actual "
                    "footfall, sales, or conversion. Return a concise Chinese "
                    "evidence summary.\n\n"
                    + "\n".join(f"- {query}" for query in group)
                )
            elif is_malaysia:
                prompt = (
                    "Search the public web for current, decision-useful Malaysia "
                    "market evidence for the query clusters below. Prioritize "
                    "Malay-, English-, and Chinese-language sources, Shopee "
                    "Malaysia, Lazada Malaysia, TikTok, Facebook, Instagram, "
                    "Malaysian forums and local media, review sites, and official "
                    "brand pages. Look for prices in MYR, ratings, recurring "
                    "complaints, warranty, delivery, product comparisons, and "
                    "real usage contexts. Cite every factual claim. Do not claim "
                    "that public engagement or displayed sold counts equal "
                    "verified sales or conversion. Return a concise Chinese "
                    "evidence summary.\n\n"
                    + "\n".join(f"- {query}" for query in group)
                )
            elif offline_venue:
                prompt = (
                    "Search the public web for current, decision-useful "
                    "Thailand physical-venue and location evidence for the "
                    "query clusters below. Prioritize Thai-language Google Maps "
                    "or public place listings, customer reviews, Facebook/LINE "
                    "local communities, TikTok or Instagram venue-discovery "
                    "content, Pantip, Thai local media, transport, tourism and "
                    "official venue or district pages. Look for accessibility, "
                    "parking, opening context, nearby competition, local versus "
                    "tourist demand, recurring experience themes and public "
                    "location facts. Cite every factual claim. Do not use Shopee, "
                    "Lazada, TikTok Shop, delivery marketplaces, displayed sales, "
                    "likes, views or reviews as a measure of actual footfall, "
                    "sales or conversion. Return a concise Thai evidence summary.\n\n"
                    + "\n".join(f"- {query}" for query in group)
                )
            else:
                prompt = (
                    "Search the public web for current, decision-useful Thailand "
                    "market evidence for the query clusters below. Prioritize "
                    "Thai-language sources, Shopee, Lazada, TikTok, Facebook, "
                    "Instagram, Pantip, Thai review sites, and official brand "
                    "pages. Look for prices, ratings, recurring complaints, "
                    "warranty, delivery, product comparisons, and real usage "
                    "contexts. Cite every factual claim. Do not claim that public "
                    "likes, views, reviews, or displayed sold counts equal verified "
                    "sales or conversion. Return a concise Thai evidence summary.\n\n"
                    + "\n".join(f"- {query}" for query in group)
                )
            response: Any = None
            last_error = "ProviderUnavailable"
            for candidate_index in range(provider_index, len(providers)):
                provider = providers[candidate_index]
                request_count += 1
                try:
                    response = await self._call_grounded_provider(
                        provider,
                        model,
                        prompt,
                    )
                    provider_index = candidate_index
                    public_provider = {
                        "id": str(provider["id"]),
                        "mode": str(provider["mode"]),
                    }
                    if public_provider not in providers_used:
                        providers_used.append(public_provider)
                    break
                except Exception as error:
                    last_error = type(error).__name__
                    continue
            if response is None:
                failures.extend(
                    {"query": query, "error": last_error}
                    for query in group
                )
                continue
            completed_queries += len(group)
            items.extend(
                self._grounded_items(
                    response,
                    group,
                    max(10, min(30, limit * 2)),
                )
            )
        return {
            "items": items,
            "completed_queries": completed_queries,
            "failed_queries": failures,
            "request_count": request_count,
            "providers_used": providers_used,
        }

    async def _search_firecrawl(
        self,
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not query:
            return []
        base_url = os.environ.get(
            "FIRECRAWL_API_URL",
            "https://api.firecrawl.dev/v2",
        ).rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "query": query,
            "limit": limit,
            "sources": ["web"],
            "scrapeOptions": {
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
        }
        async with httpx.AsyncClient(
            headers=headers,
            timeout=90.0,
            follow_redirects=False,
        ) as client:
            response = await client.post(f"{base_url}/search", json=payload)
            response.raise_for_status()
        body = response.json()
        data = body.get("data") or {}
        results = data.get("web") if isinstance(data, Mapping) else data
        if not isinstance(results, list):
            return []
        items: List[Dict[str, Any]] = []
        for rank, result in enumerate(results[:limit], start=1):
            if not isinstance(result, Mapping):
                continue
            item = self._consumer_search_evidence(result, query, rank)
            if item:
                items.append(item)
        return items

    @staticmethod
    def _consumer_search_evidence(
        result: Mapping[str, Any],
        query: str,
        rank: int,
    ) -> Optional[Dict[str, Any]]:
        url = str(result.get("url") or "").strip()
        if not _is_public_http_url(url):
            return None
        parsed = urllib.parse.urlsplit(url)
        platform = _hostname_platform(parsed.hostname or "")
        if platform != "公开网页" and parsed.path in {"", "/"}:
            return None
        title = _clean_text(result.get("title"), 220)
        description = _clean_text(result.get("description"), 1_200)
        markdown = _clean_text(result.get("markdown"), 4_000)
        lowered_markdown = markdown.lower()
        if any(
            marker in lowered_markdown
            for marker in (*ANTI_BOT_MARKERS, *LOGIN_WALL_MARKERS)
        ):
            markdown = ""
        combined = _clean_text(
            " ".join(value for value in (title, description, markdown) if value),
            5_000,
        )
        lowered = combined.lower()
        if len(combined) < 24 or any(
            marker in lowered
            for marker in (*ANTI_BOT_MARKERS, *LOGIN_WALL_MARKERS)
        ):
            return None
        query_terms = [
            token
            for token in _unique(
                re.findall(r"[a-z0-9ก-๙\u3400-\u9fff]+", query.lower())
            )
            if len(token) >= 4 and token not in SEARCH_TERM_STOPWORDS
        ]
        matched_terms = [term for term in query_terms if term in lowered][:12]
        consumer_signal_hits = [
            term for term in CONSUMER_SIGNAL_TERMS if term in lowered
        ]
        if not matched_terms and not consumer_signal_hits:
            return None

        metadata = result.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}
        published_at = (
            metadata.get("datePublished")
            or metadata.get("uploadDate")
            or metadata.get("publishedTime")
        )
        market_signals = _market_signals(combined)
        digest_payload = json.dumps(
            {
                "url": url,
                "title": title,
                "description": description,
                "markdown": markdown,
                "rank": rank,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = _content_hash(digest_payload)
        has_scraped_content = len(markdown) >= 80
        observed_fields = [
            field
            for field, value in (
                ("title", title),
                ("description", description),
                ("page_text", markdown),
                ("published_at", published_at),
            )
            if value
        ]
        return {
            "source_id": _source_id(
                "consumer_public_search",
                url,
                digest,
            ),
            "source_type": "consumer_public_search",
            "collector": "Firecrawl",
            "platform": platform,
            "title": title or parsed.hostname or "消费者公开检索结果",
            "url": url,
            "published_at": published_at,
            "collected_at": _utc_now(),
            "evidence_grade": "C" if has_scraped_content else "D",
            "content_sha256": digest,
            "excerpt": (markdown or description or title)[:900],
            "observed_fields": observed_fields,
            "market_signals": market_signals,
            "quality_checks": {
                "search_rank": rank,
                "matched_query_terms": matched_terms,
                "consumer_signal_terms": consumer_signal_hits,
                "login_or_challenge_content_removed": bool(
                    lowered_markdown
                    and not markdown
                ),
                "content_length": len(combined),
            },
            "evidence_role": "消费者公开检索线索",
            "limitation": (
                "来自公开搜索索引或页面摘要，不代表平台后台、真实身份、"
                "成交量或整体市场；排名和内容会随时间变化。"
            ),
        }

    async def _read_with_jina(
        self,
        urls: List[str],
    ) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=40.0,
            follow_redirects=False,
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.get(
                        "https://r.jina.ai/"
                        + urllib.parse.quote(url, safe=":/?=&%")
                    )
                    for url in urls
                ],
                return_exceptions=True,
            )
        items: List[Dict[str, Any]] = []
        for url, response in zip(urls, responses):
            if isinstance(response, Exception) or response.status_code != 200:
                continue
            item = self._page_evidence(url, response.text)
            if item:
                item["collector"] = "Jina Reader fallback"
                items.append(item)
        return items

    @staticmethod
    def _page_evidence(url: str, content: str) -> Optional[Dict[str, Any]]:
        cleaned = _clean_text(content)
        if len(cleaned) < 80:
            return None
        lowered = cleaned.lower()
        challenge_hits = [
            marker for marker in ANTI_BOT_MARKERS if marker in lowered
        ]
        if challenge_hits:
            return None
        parsed = urllib.parse.urlsplit(url)
        platform = _hostname_platform(parsed.hostname or "")
        market_signals = _market_signals(cleaned)
        identity_terms = [
            term for term in _url_identity_terms(url) if term in lowered
        ]
        signal_groups = [
            *(
                ["product_identity"]
                if identity_terms
                else []
            ),
            *(
                ["price"]
                if market_signals["prices"]
                else []
            ),
            *(
                ["rating"]
                if market_signals["ratings"]
                else []
            ),
            *(
                ["sales"]
                if market_signals["sales_mentions"]
                else []
            ),
            *(
                ["reviews"]
                if market_signals["review_mentions"]
                else []
            ),
        ]
        if platform in MARKETPLACE_PLATFORMS and not (
            market_signals["prices"] and len(signal_groups) >= 2
        ):
            return None
        title_match = re.search(r"(?:^|\s)Title:\s*(.{3,200}?)(?:\sURL Source:|$)", content)
        title = (
            _clean_text(title_match.group(1), 180)
            if title_match
            else parsed.hostname or "公开网页"
        )
        digest = _content_hash(cleaned)
        return {
            "source_id": _source_id("public_page", url, digest),
            "source_type": "public_page",
            "collector": "Crawl4AI",
            "platform": platform,
            "title": title,
            "url": url,
            "published_at": None,
            "collected_at": _utc_now(),
            "evidence_grade": "C",
            "content_sha256": digest,
            "excerpt": cleaned[:900],
            "observed_fields": [
                "page_text",
                "page_title",
                *(
                    ["prices"]
                    if market_signals["prices"]
                    else []
                ),
                *(
                    ["ratings"]
                    if market_signals["ratings"]
                    else []
                ),
                *(
                    ["sales_mentions"]
                    if market_signals["sales_mentions"]
                    else []
                ),
                *(
                    ["review_mentions"]
                    if market_signals["review_mentions"]
                    else []
                ),
            ],
            "market_signals": market_signals,
            "quality_checks": {
                "challenge_detected": False,
                "matched_signal_groups": signal_groups,
                "matched_product_terms": identity_terms,
                "content_length": len(cleaned),
                "marketplace_minimum_passed": (
                    platform not in MARKETPLACE_PLATFORMS
                    or bool(
                        market_signals["prices"]
                        and len(signal_groups) >= 2
                    )
                ),
            },
            "limitation": "公开页面内容可变；未验证成交量、转化率或用户身份。",
        }

    async def _search_youtube(
        self,
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not query:
            return []
        return await asyncio.wait_for(
            asyncio.to_thread(self._search_youtube_sync, query, limit),
            timeout=90.0,
        )

    @staticmethod
    def _search_youtube_sync(
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        try:
            import yt_dlp
        except ImportError:
            return []
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "playlistend": limit,
            "socket_timeout": 20,
            "retries": 1,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            result = downloader.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
            )
        entries = (result or {}).get("entries") or []
        items: List[Dict[str, Any]] = []
        for entry in entries[:limit]:
            if not isinstance(entry, Mapping):
                continue
            video_id = str(entry.get("id") or "").strip()
            url = entry.get("webpage_url") or entry.get("url")
            if video_id and (not url or not str(url).startswith("http")):
                url = f"https://www.youtube.com/watch?v={video_id}"
            if not url:
                continue
            title = _clean_text(entry.get("title") or "YouTube 公开视频", 180)
            description = _clean_text(entry.get("description"), 900)
            payload = json.dumps(
                {
                    "title": title,
                    "description": description,
                    "channel": entry.get("channel") or entry.get("uploader"),
                    "duration": entry.get("duration"),
                    "view_count": entry.get("view_count"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            digest = _content_hash(payload)
            items.append(
                {
                    "source_id": _source_id(
                        "youtube_public_metadata",
                        str(url),
                        digest,
                    ),
                    "source_type": "youtube_public_metadata",
                    "collector": "yt-dlp",
                    "platform": "YouTube",
                    "title": title,
                    "url": str(url),
                    "published_at": entry.get("upload_date"),
                    "collected_at": _utc_now(),
                    "evidence_grade": "C",
                    "content_sha256": digest,
                    "excerpt": description,
                    "observed_fields": [
                        key
                        for key in (
                            "title",
                            "description",
                            "channel",
                            "duration",
                            "view_count",
                        )
                        if entry.get(key) is not None
                    ],
                    "metrics": {
                        "channel": entry.get("channel") or entry.get("uploader"),
                        "duration_seconds": entry.get("duration"),
                        "view_count": entry.get("view_count"),
                    },
                    "limitation": "播放量是公开互动指标，不等于购买或成交。",
                }
            )
        return items
