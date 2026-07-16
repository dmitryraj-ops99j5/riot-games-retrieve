import unittest
from unittest.mock import patch, MagicMock
import httpx
from riot_retrieve.client import RiotClient, RiotApiError, get_regional_route


class TestRouteMapping(unittest.TestCase):
    def test_regional_route_groups(self):
        self.assertEqual(get_regional_route("na1"), "americas")
        self.assertEqual(get_regional_route("br1"), "americas")
        self.assertEqual(get_regional_route("euw1"), "europe")
        self.assertEqual(get_regional_route("eun1"), "europe")
        self.assertEqual(get_regional_route("kr"), "asia")
        self.assertEqual(get_regional_route("jp1"), "asia")
        self.assertEqual(get_regional_route("oc1"), "sea")

    def test_case_insensitivity(self):
        self.assertEqual(get_regional_route("EUW1"), "europe")
        self.assertEqual(get_regional_route("NA1"), "americas")

    def test_unknown_region_fallback(self):
        # Unknown platform strings fallback to americas route
        self.assertEqual(get_regional_route("unknown_loc"), "americas")


class TestClientRateLimit(unittest.TestCase):
    def setUp(self):
        self.client = RiotClient(api_key="RGAPI-test-123", default_region="na1", max_retries=2)

    @patch("time.sleep")
    @patch.object(httpx.Client, "get")
    def test_backoff_on_429(self, mock_get, mock_sleep):
        # Return 429 on first attempt, 200 on second
        resp_429 = MagicMock(status_code=429)
        resp_429.headers = {"Retry-After": "2"}
        resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=resp_429
        )

        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"puuid": "fake-puuid-xyz"}
        resp_200.raise_for_status.return_value = None

        mock_get.side_effect = [resp_429, resp_200]

        res = self.client.get_account_by_riot_id("Player", "NA1")

        self.assertEqual(res["puuid"], "fake-puuid-xyz")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(2.0)

    @patch("time.sleep")
    @patch.object(httpx.Client, "get")
    def test_backoff_default_when_no_retry_header(self, mock_get, mock_sleep):
        # 429 without header should fall back to base backoff interval (1.0s)
        resp_429 = MagicMock(status_code=429)
        resp_429.headers = {}
        resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=resp_429
        )

        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"puuid": "player-ok"}
        resp_200.raise_for_status.return_value = None

        mock_get.side_effect = [resp_429, resp_200]

        self.client.get_account_by_riot_id("Player", "NA1")
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch.object(httpx.Client, "get")
    def test_exceed_max_retries(self, mock_get, mock_sleep):
        resp_429 = MagicMock(status_code=429)
        resp_429.headers = {"Retry-After": "1"}
        resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limit hit", request=MagicMock(), response=resp_429
        )
        mock_get.return_value = resp_429

        with self.assertRaises(RiotApiError) as ctx:
            self.client.get_match("NA1_12345")

        self.assertIn("429", str(ctx.exception))
        self.assertEqual(mock_get.call_count, 3)  # initial + 2 retries

    @patch.object(httpx.Client, "get")
    def test_not_found_raises_immediately(self, mock_get):
        resp_404 = MagicMock(status_code=404)
        resp_404.headers = {}
        resp_404.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=resp_404
        )
        mock_get.return_value = resp_404

        with self.assertRaises(RiotApiError):
            self.client.get_account_by_riot_id("DoesNotExist", "0000")

        self.assertEqual(mock_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
