import io
import json
import unittest
from unittest.mock import patch

from server import research


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class GroqTests(unittest.TestCase):
    def test_answer_reasoning_hidden_and_key_only_in_header(self):
        sent = {}

        def fake(request, timeout=0):
            sent['url'], sent['headers'], sent['body'] = request.full_url, dict(request.header_items()), json.loads(request.data)
            return FakeResponse(json.dumps({'choices': [{'message': {'content': ' Nach § 536 BGB ist die Miete gemindert. '}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 900, 'completion_tokens': 120}}).encode())

        with patch.object(research, 'GROQ_API_KEY', 'synthetic-test-key'), patch.object(research, 'GROQ_MODEL', 'openai/gpt-oss-120b'), patch.object(research, 'urlopen', fake):
            result = research.generate_groq_answer([{'role': 'system', 'content': 'x'}, {'role': 'user', 'content': 'Schimmel?'}])
        self.assertEqual(result['answer'], 'Nach § 536 BGB ist die Miete gemindert.')
        self.assertEqual((result['input_tokens'], result['output_tokens'], result['truncated']), (900, 120, False))
        self.assertTrue(sent['url'].endswith('/chat/completions'))
        self.assertNotIn('synthetic-test-key', sent['url'])
        self.assertEqual(sent['headers']['Authorization'], 'Bearer synthetic-test-key')
        self.assertFalse(sent['body']['include_reasoning'])

    def test_missing_key_and_empty_answer_fail(self):
        with patch.object(research, 'GROQ_API_KEY', ''):
            self.assertFalse(research.groq_status()['ready'])
            with self.assertRaises(ValueError):
                research.generate_groq_answer([])
        empty = lambda request, timeout=0: FakeResponse(json.dumps({'choices': [{'message': {'content': ''}, 'finish_reason': 'stop'}]}).encode())
        with patch.object(research, 'GROQ_API_KEY', 'k'), patch.object(research, 'urlopen', empty):
            with self.assertRaises(ValueError):
                research.generate_groq_answer([{'role': 'user', 'content': 'x'}])
