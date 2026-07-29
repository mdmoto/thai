import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import CalibrationContribution
from app.services.platform_calibration import (
    platform_calibration_override,
    record_platform_contribution,
)


class PlatformCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _report(report_id: str, price: float, quality: float):
        return {
            "report_id": report_id,
            "category_key": "PET_WATER_FOUNTAIN",
            "study_type": "PRODUCT_VALIDATION",
            "model_lineage": {
                "choice_estimation": {
                    "status": "applied_unvalidated",
                    "study_type": "PRODUCT_VALIDATION",
                    "diagnostics": {
                        "converged": True,
                        "choice_sets": 200,
                        "observations": 400,
                        "coefficients": {
                            "price_log_ratio": price,
                            "quality_fit": quality,
                        },
                        "standard_errors": {
                            "price_log_ratio": 0.11,
                            "quality_fit": 0.09,
                        },
                    },
                }
            },
        }

    def test_contributions_are_deidentified_deduplicated_and_thresholded(self):
        db = self.Session()
        try:
            for index in range(5):
                record_platform_contribution(
                    db,
                    self._report(
                        f"rpt-private-{index}",
                        -1.3 + index * 0.03,
                        0.8 + index * 0.02,
                    ),
                )
            record_platform_contribution(
                db,
                self._report("rpt-private-0", -4.5, 3.0),
            )
            db.commit()

            contributions = db.query(CalibrationContribution).all()
            self.assertEqual(len(contributions), 5)
            self.assertFalse(
                {
                    "user_id",
                    "study_id",
                    "report_id",
                    "raw_rows",
                    "customer_email",
                }
                & set(CalibrationContribution.__table__.columns.keys())
            )
            self.assertTrue(
                all(
                    "rpt-private" not in item.source_digest
                    for item in contributions
                )
            )

            with patch.dict(
                os.environ,
                {
                    "PLATFORM_CALIBRATION_MIN_CONTRIBUTIONS": "5",
                    "PLATFORM_CALIBRATION_MIN_CHOICE_SETS": "500",
                },
            ):
                pooled = platform_calibration_override(
                    db,
                    "PET_WATER_FOUNTAIN",
                    "PRODUCT_VALIDATION",
                )
            self.assertIsNotNone(pooled)
            self.assertEqual(
                pooled["status"],
                "platform_category_benchmark_unvalidated",
            )
            self.assertEqual(
                pooled["platform_benchmark"]["privacy_status"],
                "deidentified_aggregate_coefficients_no_raw_customer_rows",
            )
            price = pooled["study_models"]["PRODUCT_VALIDATION"][
                "coefficients"
            ]["price_log_ratio"]
            self.assertLess(price["mean"], 0)
            self.assertGreater(price["sd"], 0)
        finally:
            db.close()

    def test_unfitted_public_evidence_never_enters_platform_pool(self):
        db = self.Session()
        try:
            report = self._report("rpt-prior", -1.2, 0.7)
            report["model_lineage"]["choice_estimation"]["status"] = (
                "prior_only"
            )
            self.assertIsNone(record_platform_contribution(db, report))
            db.commit()
            self.assertEqual(db.query(CalibrationContribution).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
