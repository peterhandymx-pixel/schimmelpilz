import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

from server import research


class Reply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): return False


def answer(text, finish='stop'):
    return Reply(json.dumps({'choices': [{'message': {'content': text}, 'finish_reason': finish}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}).encode())


def configured():
    return patch.multiple(research, LLM_BASE_URL='https://llm.example.invalid/v1', LLM_API_KEY='test-key', LLM_MODEL='some-model', GEMINI_RETRY_DELAYS=(0, 0, 0))


def test_generic_provider_answers_and_hides_thinking():
    sent = []
    with configured(), patch.object(research, 'urlopen', side_effect=lambda request, timeout: sent.append(request) or answer('<think>intern</think>### Kurze Antwort\nJa.')):
        result = research.generate_llm_answer([{'role': 'user', 'content': 'Frage'}])
    assert result['answer'] == '### Kurze Antwort\nJa.'
    assert sent[0].full_url == 'https://llm.example.invalid/v1/chat/completions'
    assert sent[0].headers['Authorization'] == 'Bearer test-key'
    assert json.loads(sent[0].data)['model'] == 'some-model'


def test_json_mode_falls_back_when_provider_rejects_it():
    bodies = []
    def reply(request, timeout):
        bodies.append(json.loads(request.data))
        if 'response_format' in bodies[-1]:
            raise HTTPError(request.full_url, 400, 'bad request', {}, io.BytesIO(b'{}'))
        return answer('{"norms": []}')
    with configured(), patch.object(research, 'urlopen', side_effect=reply):
        assert research.generate_llm_answer([{'role': 'user', 'content': 'x'}], json_mode=True)['answer'] == '{"norms": []}'
    assert ['response_format' in body for body in bodies] == [True, False]


def test_missing_configuration_is_reported():
    with patch.multiple(research, LLM_BASE_URL='', LLM_API_KEY='', LLM_MODEL=''):
        assert research.llm_status()['ready'] is False
        try:
            research.generate_llm_answer([{'role': 'user', 'content': 'x'}])
        except ValueError as error:
            assert 'LLM_BASE_URL' in str(error)
