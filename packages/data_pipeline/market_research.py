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


RESEARCH_VERSION = "TH-MARKET-RESEARCH-2026.07.6"
PROFESSIONAL_RESEARCH_VERSION = "TH-MARKET-RESEARCH-2026.08.1"
USER_AGENT = "ThailandMarketTwin/2.1 (+public-market-research)"
PLATFORM_HOSTS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "lazada.co.th": "Lazada",
    "shopee.co.th": "Shopee",
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


def _is_offline_study(study: Mapping[str, Any]) -> bool:
    return str(study.get("study_type") or "").upper() in OFFLINE_STUDY_TYPES
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


def _market_signals(content: str) -> Dict[str, List[str]]:
    patterns = {
        "prices": (
            r"(?:฿\s?[\d][\d,]*(?:\.\d{1,2})?"
            r"|(?:THB|บาท)\s?[\d][\d,]*(?:\.\d{1,2})?"
            r"|[\d][\d,]*(?:\.\d{1,2})?\s?บาท)"
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
        return _unique(candidates)

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
        return _clean_text(" ".join(plain) + " Thailand รีวิว review", 240)

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
        """Build Thai consumer-intent query clusters instead of one broad query."""
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
        if _is_offline_study(study):
            venue_type = _clean_text(
                facts.get("venue_type") or inputs.get("venue_type") or category,
                100,
            )
            locations = PublicMarketResearch._offline_location_labels(study)
            location_context = " ".join(locations) or "Thailand"
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
            warnings.append(f"公开网页采集失败：{type(page_results).__name__}")
            page_items: List[Dict[str, Any]] = []
            page_status = "unavailable"
        else:
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
                "fallback_result": (
                    None if page_items else "public_search_discovery"
                ),
            }
        )

        if not self.firecrawl_enabled:
            search_items: List[Dict[str, Any]] = []
            search_status = "disabled"
        elif isinstance(search_results, Exception):
            warnings.append(
                f"消费者公开检索失败：{type(search_results).__name__}"
            )
            search_items = []
            search_status = "unavailable"
        else:
            search_items = search_results["items"]
            search_status = "succeeded" if search_items else "partial"
            evidence.extend(search_items)
            failed_searches = search_results["failed_queries"]
            if failed_searches:
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
        elif isinstance(grounded_results, Exception):
            grounded_items = []
            grounded_status = "unavailable"
            warnings.append(
                "Google 公开检索失败："
                f"{type(grounded_results).__name__}"
            )
        else:
            grounded_items = list(grounded_results.get("items") or [])
            grounded_status = "succeeded" if grounded_items else "partial"
            evidence.extend(grounded_items)
            failed_grounded = list(
                grounded_results.get("failed_queries") or []
            )
            if failed_grounded:
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
            warnings.append(
                f"YouTube 公开资料采集失败：{type(video_results).__name__}"
            )
            video_items: List[Dict[str, Any]] = []
            video_status = "unavailable"
        else:
            video_items = video_results
            video_status = "succeeded" if video_items else "partial"
            evidence.extend(video_items)
        collectors.append(
            {
                "collector": "YouTube public metadata",
                "status": video_status,
                "requested": self.max_videos,
                "result_count": len(video_items),
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
        skipped_marketplace_evidence = 0
        for item in evidence:
            url = item.get("url")
            canonical_url = _canonical_url(str(url or ""))
            if not canonical_url or canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            item["url"] = canonical_url
            platform = str(item.get("platform") or "公开网页")
            if is_offline and platform in MARKETPLACE_PLATFORMS:
                skipped_marketplace_evidence += 1
                continue
            priority, role = PLATFORM_PRIORITY.get(
                platform,
                PLATFORM_PRIORITY["公开网页"],
            )
            item["decision_priority"] = priority
            item.setdefault("evidence_role", role)
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
            if offline_venue:
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
