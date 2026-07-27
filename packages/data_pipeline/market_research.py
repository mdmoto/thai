"""Auditable public-market research for deep decision studies.

The collector deliberately avoids login cookies, private endpoints, and claims
that public engagement equals sales. It gathers only public pages supplied by
the customer plus public YouTube metadata, records provenance and hashes, and
fails open so a blocked source never corrupts the quantitative simulation.
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


RESEARCH_VERSION = "TH-MARKET-RESEARCH-2026.07.3"
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
    "security verification",
    "robot verification",
    "too many requests",
)
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
        max_pages: int = 12,
        max_videos: int = 12,
    ):
        configured = os.environ.get("MARKET_RESEARCH_ENABLED", "").lower()
        self.enabled = (
            enabled
            if enabled is not None
            else configured in {"1", "true", "yes", "on"}
        )
        self.page_reader = page_reader or self._crawl_public_pages
        self.video_searcher = video_searcher or self._search_youtube
        self.max_pages = max(1, min(int(max_pages), 30))
        self.max_videos = max(1, min(int(max_videos), 30))

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

    async def collect(
        self,
        study: Mapping[str, Any],
        plan_code: str,
    ) -> Dict[str, Any]:
        started_at = _utc_now()
        base = {
            "version": RESEARCH_VERSION,
            "status": "not_applicable",
            "started_at": started_at,
            "completed_at": started_at,
            "query": self._search_query(study),
            "source_count": 0,
            "platform_counts": {},
            "evidence": [],
            "collectors": [],
            "warnings": [],
            "source_strategy": {
                "ranking_basis": "购买决策价值，不按采集便利度或单纯访问量排序",
                "priority_order": SOURCE_STRATEGY,
            },
            "usage_policy": {
                "quantitative_effect": "none_until_customer_calibration",
                "allowed": [
                    "竞品与价格证据",
                    "公开评价主题",
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
        if not self.enabled:
            base["status"] = "disabled"
            base["warnings"] = ["公开市场采集在当前环境未启用。"]
            return base

        urls = self._research_urls(study)[: self.max_pages]
        query = base["query"]
        page_task = asyncio.create_task(self.page_reader(urls))
        video_task = asyncio.create_task(
            self.video_searcher(query, self.max_videos)
        )
        page_results, video_results = await asyncio.gather(
            page_task,
            video_task,
            return_exceptions=True,
        )

        evidence: List[Dict[str, Any]] = []
        collectors: List[Dict[str, Any]] = []
        warnings: List[str] = []
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
                    None if page_items else "customer_authorized_url_required"
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
        collectors.extend(
            [
                {
                    "collector": "Meta / TikTok authorized business data",
                    "status": "authorization_required",
                    "requested": 0,
                    "result_count": 0,
                    "fallback_result": "public_url_evidence_only",
                },
                {
                    "collector": "Lazada / Shopee merchant data",
                    "status": "authorization_required",
                    "requested": 0,
                    "result_count": 0,
                    "fallback_result": "public_product_metadata_only",
                },
            ]
        )

        unique_evidence: List[Dict[str, Any]] = []
        seen_urls = set()
        for item in evidence:
            url = item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            platform = str(item.get("platform") or "公开网页")
            priority, role = PLATFORM_PRIORITY.get(
                platform,
                PLATFORM_PRIORITY["公开网页"],
            )
            item["decision_priority"] = priority
            item["evidence_role"] = role
            unique_evidence.append(item)
        unique_evidence.sort(
            key=lambda item: int(item.get("decision_priority") or 99)
        )
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
                "platform_counts": platform_counts,
                "evidence": unique_evidence[: self.max_pages + self.max_videos],
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
