import asyncio
import unittest

from data_pipeline.market_research import PublicMarketResearch


class PublicMarketResearchTests(unittest.TestCase):
    def test_anti_bot_page_is_not_accepted_as_evidence(self):
        item = PublicMarketResearch._page_evidence(
            "https://www.lazada.co.th/products/petkit-eversweet.html",
            """
            # Lazada
            Sorry, we have detected unusual traffic from your network.
            Loading /punish?x5secdata=challenge-token
            PETKIT Eversweet
            """,
        )
        self.assertIsNone(item)

    def test_marketplace_page_requires_meaningful_commerce_signals(self):
        item = PublicMarketResearch._page_evidence(
            "https://shopee.co.th/petkit-eversweet-solo-2-i.1.2",
            """
            PETKIT Eversweet Solo 2 น้ำพุแมวอัตโนมัติ
            ราคา ฿1,400 คะแนน 5.0 คะแนน ขายแล้ว 5,000 ชิ้น
            รีวิวจากผู้ซื้อในประเทศไทย รับประกันศูนย์ไทยหนึ่งปี
            รายละเอียดสินค้า ปั๊มน้ำไร้สายและระบบกรองน้ำ
            """,
        )
        self.assertIsNotNone(item)
        self.assertIn("฿1,400", item["market_signals"]["prices"])
        self.assertIn(
            "price",
            item["quality_checks"]["matched_signal_groups"],
        )
        self.assertTrue(
            item["quality_checks"]["marketplace_minimum_passed"]
        )

    def test_marketplace_navigation_text_without_price_is_rejected(self):
        item = PublicMarketResearch._page_evidence(
            "https://shopee.co.th/petkitofficialthailand",
            """
            Petkit Official Thailand ร้านค้า รายการสินค้า หมวดหมู่
            ติดตาม พูดคุย ดูร้านค้า โปรโมชั่น และสินค้าแนะนำ
            ยินดีต้อนรับสู่ร้านค้าอย่างเป็นทางการ
            """,
        )
        self.assertIsNone(item)

    def test_firecrawl_consumer_search_keeps_relevant_public_signal(self):
        item = PublicMarketResearch._consumer_search_evidence(
            {
                "url": (
                    "https://www.facebook.com/petkitthailand/posts/"
                    "public-review"
                ),
                "title": "รีวิว PETKIT Eversweet Solo 2 หลังใช้จริง",
                "description": (
                    "เปรียบเทียบข้อดี ข้อเสีย ราคา และเสียงปั๊มน้ำ "
                    "พร้อมลิงก์ร้านค้าในไทย"
                ),
                "markdown": "",
            },
            "PETKIT Eversweet Solo 2 Thailand ราคา รีวิว",
            2,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item["source_type"], "consumer_public_search")
        self.assertEqual(item["platform"], "Facebook")
        self.assertEqual(item["evidence_grade"], "D")
        self.assertEqual(item["quality_checks"]["search_rank"], 2)
        self.assertIn(
            "petkit",
            item["quality_checks"]["matched_query_terms"],
        )
        self.assertEqual(len(item["content_sha256"]), 64)

    def test_firecrawl_login_wall_is_rejected(self):
        item = PublicMarketResearch._consumer_search_evidence(
            {
                "url": "https://shopee.co.th/product/1/2",
                "title": "Shopee Thailand",
                "description": "Login Required",
                "markdown": (
                    "Looks like you're not logged in yet. "
                    "Please log in to continue."
                ),
            },
            "PETKIT Eversweet Solo 2 Thailand ราคา รีวิว",
            1,
        )
        self.assertIsNone(item)

    def test_firecrawl_irrelevant_result_is_rejected(self):
        item = PublicMarketResearch._consumer_search_evidence(
            {
                "url": "https://example.com/company",
                "title": "Company information",
                "description": "Annual governance and investor relations notice.",
                "markdown": "",
            },
            "PETKIT Eversweet Solo 2 Thailand ราคา รีวิว",
            5,
        )
        self.assertIsNone(item)

    def test_professional_run_adds_consumer_public_search(self):
        searched_queries = []

        async def fake_pages(urls):
            return []

        async def fake_videos(query, limit):
            return []

        async def fake_consumer_search(query, limit):
            searched_queries.append(query)
            self.assertEqual(limit, 10)
            return [
                {
                    "source_id": "src_search",
                    "source_type": "consumer_public_search",
                    "collector": "Firecrawl",
                    "platform": "TikTok",
                    "title": "รีวิวจากผู้ใช้ไทย",
                    "url": "https://www.tiktok.com/@petkit/video/123",
                    "collected_at": "2026-07-28T00:00:00Z",
                    "evidence_grade": "D",
                    "content_sha256": "c" * 64,
                    "limitation": "公开搜索摘要。",
                    "evidence_role": "消费者公开检索线索",
                }
            ]

        collector = PublicMarketResearch(
            enabled=True,
            page_reader=fake_pages,
            video_searcher=fake_videos,
            consumer_searcher=fake_consumer_search,
        )
        bundle = asyncio.run(
            collector.collect(
                {
                    "name": "PETKIT 饮水机",
                    "inputs": {"category": "宠物饮水机"},
                    "facts": {"product_name": "PETKIT Eversweet Solo 2"},
                },
                "PROFESSIONAL",
            )
        )

        self.assertEqual(bundle["status"], "succeeded")
        self.assertEqual(bundle["source_count"], 1)
        self.assertEqual(len(searched_queries), 12)
        self.assertTrue(any("ข้อเสีย" in query for query in searched_queries))
        self.assertTrue(any("site:tiktok.com" in query for query in searched_queries))
        self.assertEqual(bundle["platform_counts"], {"TikTok": 1})
        self.assertEqual(
            bundle["evidence"][0]["evidence_role"],
            "消费者公开检索线索",
        )
        firecrawl = next(
            item
            for item in bundle["collectors"]
            if item["collector"]
            == "Firecrawl multi-query consumer research"
        )
        self.assertEqual(firecrawl["status"], "succeeded")
        self.assertEqual(firecrawl["query_count"], 12)
        self.assertEqual(firecrawl["estimated_credits"], 24)

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
