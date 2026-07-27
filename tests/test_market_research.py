import asyncio
import unittest

from data_pipeline.market_research import PublicMarketResearch


class PublicMarketResearchTests(unittest.TestCase):
    def test_professional_run_combines_public_pages_and_video_metadata(self):
        async def fake_pages(urls):
            self.assertEqual(urls, ["https://example.com/product"])
            return [
                {
                    "source_id": "src_page",
                    "source_type": "public_page",
                    "collector": "Crawl4AI",
                    "platform": "公开网页",
                    "title": "产品公开页",
                    "url": urls[0],
                    "collected_at": "2026-07-27T00:00:00Z",
                    "evidence_grade": "C",
                    "content_sha256": "a" * 64,
                    "limitation": "公开页面内容可变。",
                }
            ]

        async def fake_videos(query, limit):
            self.assertIn("饮水机", query)
            self.assertEqual(limit, 12)
            return [
                {
                    "source_id": "src_video",
                    "source_type": "youtube_public_metadata",
                    "collector": "yt-dlp",
                    "platform": "YouTube",
                    "title": "泰国饮水机测评",
                    "url": "https://www.youtube.com/watch?v=example",
                    "collected_at": "2026-07-27T00:00:00Z",
                    "evidence_grade": "C",
                    "content_sha256": "b" * 64,
                    "limitation": "播放量不等于购买。",
                }
            ]

        collector = PublicMarketResearch(
            enabled=True,
            page_reader=fake_pages,
            video_searcher=fake_videos,
        )
        bundle = asyncio.run(
            collector.collect(
                {
                    "name": "泰国宠物饮水机",
                    "inputs": {
                        "url": "https://example.com/product",
                        "category": "宠物饮水机",
                    },
                    "facts": {"product_name": "智能饮水机"},
                },
                "PROFESSIONAL",
            )
        )

        self.assertEqual(bundle["status"], "succeeded")
        self.assertEqual(bundle["source_count"], 2)
        self.assertEqual(bundle["platform_counts"]["YouTube"], 1)
        self.assertEqual(bundle["evidence"][0]["decision_priority"], 3)
        self.assertEqual(bundle["evidence"][1]["decision_priority"], 4)
        self.assertEqual(
            bundle["source_strategy"]["priority_order"][0]["sources"],
            ["Shopee", "Lazada", "TikTok Shop"],
        )
        self.assertEqual(
            bundle["usage_policy"]["quantitative_effect"],
            "none_until_customer_calibration",
        )
        self.assertTrue(
            all(item["content_sha256"] for item in bundle["evidence"])
        )

    def test_standard_run_does_not_start_public_collection(self):
        collector = PublicMarketResearch(enabled=True)
        bundle = asyncio.run(
            collector.collect(
                {"name": "Standard", "inputs": {}, "facts": {}},
                "STANDARD",
            )
        )
        self.assertEqual(bundle["status"], "not_applicable")
        self.assertEqual(bundle["source_count"], 0)

    def test_private_urls_are_rejected_before_collection(self):
        captured = []

        async def fake_pages(urls):
            captured.extend(urls)
            return []

        async def fake_videos(query, limit):
            return []

        collector = PublicMarketResearch(
            enabled=True,
            page_reader=fake_pages,
            video_searcher=fake_videos,
        )
        asyncio.run(
            collector.collect(
                {
                    "name": "Private URL guard",
                    "inputs": {
                        "url": "http://127.0.0.1:8080/private",
                        "research_urls": [
                            "http://metadata.google.internal/computeMetadata/v1/",
                            "https://example.com/public",
                        ],
                    },
                    "facts": {},
                },
                "PROFESSIONAL",
            )
        )
        self.assertEqual(captured, ["https://example.com/public"])


if __name__ == "__main__":
    unittest.main()
