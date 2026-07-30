"""Regression tests for UTC API timestamp serialization."""

from datetime import datetime, timedelta, timezone
import unittest

from app.datetime_utils import utc_isoformat


class DatetimeUtilsTests(unittest.TestCase):
    def test_naive_database_datetime_is_serialized_as_utc(self):
        self.assertEqual(
            utc_isoformat(datetime(2026, 7, 30, 8, 0, 0)),
            "2026-07-30T08:00:00Z",
        )

    def test_aware_datetime_is_normalized_to_utc(self):
        bangkok = timezone(timedelta(hours=7))
        self.assertEqual(
            utc_isoformat(datetime(2026, 7, 30, 15, 0, 0, tzinfo=bangkok)),
            "2026-07-30T08:00:00Z",
        )

    def test_none_stays_none(self):
        self.assertIsNone(utc_isoformat(None))


if __name__ == "__main__":
    unittest.main()
