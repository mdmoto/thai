import unittest

from app.schemas.study import CreateStudyRequest


class StudySchemaTests(unittest.TestCase):
    def test_all_self_service_study_types_are_accepted(self):
        for study_type in (
            "PRODUCT_VALIDATION",
            "PRICING_STUDY",
            "VENUE_STUDY",
            "SITE_COMPARISON",
            "CREATIVE_TEST",
            "OPERATING_SCENARIO",
        ):
            with self.subTest(study_type=study_type):
                request = CreateStudyRequest(
                    name="测试项目",
                    study_type=study_type,
                )
                self.assertEqual(request.study_type, study_type)

    def test_venue_and_creative_fields_are_preserved(self):
        request = CreateStudyRequest(
            name="Nimman 咖啡馆",
            study_type="VENUE_STUDY",
            venue_type="CAFE",
            average_check=220,
            capacity=48,
            opening_hours="08:00–20:00",
            location={"label": "Chiang Mai, Nimman"},
        )
        self.assertEqual(request.venue_type, "CAFE")
        self.assertEqual(request.capacity, 48)
        self.assertEqual(request.location["label"], "Chiang Mai, Nimman")

    def test_ecommerce_context_is_preserved(self):
        request = CreateStudyRequest(
            name="电商测试",
            study_type="PRODUCT_VALIDATION",
            template_key="ECOMMERCE",
            marketplaces=["Shopee", "Lazada"],
            shipping_fee=45,
            delivery_days=3,
            cod_available=True,
            official_store=False,
        )
        self.assertEqual(request.template_key, "ECOMMERCE")
        self.assertEqual(request.marketplaces, ["Shopee", "Lazada"])
        self.assertTrue(request.cod_available)

    def test_observed_choice_rows_remove_customer_identifiers(self):
        request = CreateStudyRequest(
            name="真实购买校准",
            study_type="PRODUCT_VALIDATION",
            observed_choice_data=[
                {
                    "choice_set_id": "customer-email@example.com-order-009",
                    "alternative": "Internal SKU 481",
                    "chosen": 1,
                    "price_log_ratio": 0.92,
                    "quality_fit": 0.8,
                    "customer_email": "customer-email@example.com",
                    "order_id": "order-009",
                },
                {
                    "choice_set_id": "customer-email@example.com-order-009",
                    "alternative": "Competitor secret SKU",
                    "chosen": 0,
                    "price_log_ratio": 1.1,
                    "quality_fit": 0.6,
                },
            ],
        )
        rows = request.observed_choice_data
        self.assertEqual(rows[0]["choice_set_id"], "set-00001")
        self.assertEqual(rows[1]["choice_set_id"], "set-00001")
        self.assertEqual(rows[0]["alternative"], "option-1")
        self.assertEqual(rows[1]["alternative"], "option-2")
        self.assertNotIn("customer_email", rows[0])
        self.assertNotIn("order_id", rows[0])


if __name__ == "__main__":
    unittest.main()
