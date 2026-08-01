from __future__ import annotations

import sqlite3
import unittest

from simulation_core.social_backends.oasis_metrics import aggregate_oasis_sqlite


class OasisMetricAggregationTests(unittest.TestCase):
    def test_signup_traces_do_not_inflate_diffusion_participants(self):
        connection = sqlite3.connect(":memory:")
        for table in ("post", "like", "dislike", "comment"):
            connection.execute(f'CREATE TABLE "{table}" (user_id INTEGER)')
        connection.execute("CREATE TABLE rec (user_id INTEGER)")
        connection.execute("CREATE TABLE trace (user_id INTEGER)")
        connection.executemany(
            "INSERT INTO trace (user_id) VALUES (?)",
            [(index,) for index in range(8)],
        )
        connection.execute("INSERT INTO post (user_id) VALUES (0)")
        connection.execute("INSERT INTO like (user_id) VALUES (3)")
        connection.execute("INSERT INTO rec (user_id) VALUES (3)")

        aggregate = aggregate_oasis_sqlite(connection)

        self.assertEqual(aggregate["trace_records"], 8)
        self.assertEqual(aggregate["participants"], 2)
        self.assertEqual(aggregate["interactions"], 1)
        connection.close()


if __name__ == "__main__":
    unittest.main()
