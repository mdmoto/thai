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


if __name__ == "__main__":
    unittest.main()
