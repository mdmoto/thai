"""Cloud Run Job dispatch and cancellation contracts."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.services.run_dispatcher import (
    _execution_name_from_operation,
    cancel_run_execution,
)


class RunDispatcherTests(unittest.TestCase):
    def test_execution_name_is_found_in_nested_operation_metadata(self):
        expected = (
            "projects/test-project/locations/asia-southeast1/"
            "jobs/market-twin-runner/executions/market-twin-runner-abc12"
        )
        self.assertEqual(
            _execution_name_from_operation(
                {"metadata": {"target": expected}}
            ),
            expected,
        )

    def test_operation_is_resolved_before_execution_cancel(self):
        operation_name = (
            "projects/test-project/locations/asia-southeast1/"
            "operations/operation-123"
        )
        execution_name = (
            "projects/test-project/locations/asia-southeast1/"
            "jobs/market-twin-runner/executions/market-twin-runner-abc12"
        )
        credentials = Mock(token="test-token")
        get_response = Mock()
        get_response.json.return_value = {
            "metadata": {"target": execution_name}
        }
        post_response = Mock()
        with (
            patch(
                "app.services.run_dispatcher.google.auth.default",
                return_value=(credentials, "test-project"),
            ),
            patch(
                "app.services.run_dispatcher.httpx.get",
                return_value=get_response,
            ) as getter,
            patch(
                "app.services.run_dispatcher.httpx.post",
                return_value=post_response,
            ) as poster,
        ):
            self.assertTrue(cancel_run_execution(operation_name))

        credentials.refresh.assert_called_once()
        get_response.raise_for_status.assert_called_once()
        post_response.raise_for_status.assert_called_once()
        getter.assert_called_once()
        self.assertEqual(
            poster.call_args.args[0],
            f"https://run.googleapis.com/v2/{execution_name}:cancel",
        )


if __name__ == "__main__":
    unittest.main()
