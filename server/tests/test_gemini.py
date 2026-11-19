import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from server import research


class FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.raw[:limit]


MESSAGES = [
    {"role": "system", "content": "Rules"},
    {"role": "user", "content": "Earlier question"},
    {"role": "assistant", "content": "Earlier answer"},
    {"role": "user", "content": "Current question"},
]


def gemini_reply(text="Answer", finish="STOP", thought=False):
    parts = [{"text": "hidden reasoning", "thought": True}] if thought else []
    parts.append({"text": text})
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}], "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4}}


@patch.object(research, "AI_PROVIDER", "gemini")
@patch.object(research, "GEMINI_API_KEY", "test-key")
@patch.object(research, "GEMINI_MODEL", "gemini-test")
class GeminiTransportTests(unittest.TestCase):
    def test_request_maps_roles_and_keeps_key_out_of_url(self):
        with patch.object(research, "urlopen", return_value=FakeResponse(gemini_reply())) as opened:
            result = research.generate_answer(MESSAGES)
        request = opened.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/models/gemini-test:generateContent"))
        self.assertNotIn("test-key", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        body = json.loads(request.data)
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "Rules")
        self.assertEqual([item["role"] for item in body["contents"]], ["user", "model", "user"])
        self.assertEqual(result, {"answer": "Answer", "input_tokens": 12, "output_tokens": 4, "truncated": False})

    def test_thought_parts_are_not_returned(self):
        with patch.object(research, "urlopen", return_value=FakeResponse(gemini_reply(thought=True))):
            self.assertEqual(research.generate_answer(MESSAGES)["answer"], "Answer")

    def test_max_tokens_is_reported_as_truncated(self):
        with patch.object(research, "urlopen", return_value=FakeResponse(gemini_reply(finish="MAX_TOKENS"))):
            self.assertTrue(research.generate_answer(MESSAGES)["truncated"])

    def test_blocked_or_unfinished_responses_are_rejected(self):
        for payload in ({"promptFeedback": {"blockReason": "SAFETY"}}, gemini_reply(finish="SAFETY"), gemini_reply(text="  ")):
            with patch.object(research, "urlopen", return_value=FakeResponse(payload)):
                with self.assertRaises(ValueError):
                    research.generate_answer(MESSAGES)

    def test_high_demand_is_retried_but_other_errors_are_not(self):
        busy = HTTPError("https://example.invalid", 503, "Service Unavailable", {}, None)
        with patch.object(research, "GEMINI_RETRY_DELAYS", (0, 0)), patch.object(research, "urlopen", side_effect=[busy, busy, FakeResponse(gemini_reply())]) as opened:
            self.assertEqual(research.generate_answer(MESSAGES)["answer"], "Answer")
        self.assertEqual(opened.call_count, 3)
        with patch.object(research, "GEMINI_RETRY_DELAYS", (0, 0)), patch.object(research, "urlopen", side_effect=[busy, busy, busy]):
            with self.assertRaises(HTTPError):
                research.generate_answer(MESSAGES)
        denied = HTTPError("https://example.invalid", 403, "Forbidden", {}, None)
        with patch.object(research, "urlopen", side_effect=[denied]) as opened:
            with self.assertRaises(HTTPError):
                research.generate_answer(MESSAGES)
        self.assertEqual(opened.call_count, 1)

    def test_missing_key_is_unavailable_without_network(self):
        with patch.object(research, "GEMINI_API_KEY", ""), patch.object(research, "urlopen", side_effect=AssertionError("No request without a key")):
            self.assertEqual(research.ai_status(), {"ready": False, "model": "gemini-test", "reason": "unavailable", "provider": "gemini"})
            with self.assertRaises(ValueError):
                research.generate_answer(MESSAGES)


if __name__ == "__main__":
    unittest.main()


def test_daily_quota_is_not_retried():
    import io
    from unittest.mock import patch
    from urllib.error import HTTPError
    from server import research
    body = b'{"error":{"code":429,"details":[{"violations":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}'
    daily = HTTPError('https://example.invalid', 429, 'Too Many Requests', {}, io.BytesIO(body))
    with patch.object(research, 'GEMINI_API_KEY', 'test'), patch.object(research, 'GEMINI_RETRY_DELAYS', (5, 5, 5)), \
            patch.object(research.time, 'sleep', side_effect=AssertionError('must not wait')), patch.object(research, 'urlopen', side_effect=[daily]) as opened:
        try:
            research.generate_gemini_answer([{'role': 'user', 'content': 'x'}])
        except HTTPError as error:
            assert error.code == 429
        assert opened.call_count == 1
