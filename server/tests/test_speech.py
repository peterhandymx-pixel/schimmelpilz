import io
import json
from unittest import mock

from fastapi.testclient import TestClient

from server import app as api, research, speech
from server.tests import test_inbox


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SpeechTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def post(self, client, content=b'x' * 4000, content_type='audio/webm', language='de'):
        return client.post('/api/speech/transcribe', data={'language': language}, files={'file': ('speech', content, content_type)})

    def test_transcribes_without_storing_audio(self):
        sent = {}

        def fake(request, timeout):
            sent['url'], sent['body'], sent['type'] = request.full_url, request.data, request.headers['Content-type']
            return FakeResponse(json.dumps({'text': ' Muss die Mandantin eine Frist setzen? '}).encode())

        with mock.patch.object(research, 'GROQ_API_KEY', 'test-key'), mock.patch.object(speech, 'urlopen', fake), TestClient(api.app) as client:
            self.assertIn(client.post('/api/speech/transcribe', files={'file': ('s', b'x' * 4000, 'audio/webm')}).status_code, (401, 403))
            self.login(client, 'speech@example.invalid')
            self.assertTrue(client.get('/api/research/status').json()['speech'])
            result = self.post(client)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json(), {'text': 'Muss die Mandantin eine Frist setzen?'})
            self.assertTrue(sent['url'].endswith('/audio/transcriptions'))
            self.assertIn('multipart/form-data; boundary=', sent['type'])
            self.assertIn(b'whisper-large-v3-turbo', sent['body'])
            self.assertIn(b'name="language"\r\n\r\nde', sent['body'])
            self.assertIn('filename="speech.webm"'.encode(), sent['body'])
            # Wrong type, too short and too large are refused before anything leaves the server.
            self.assertEqual(self.post(client, content_type='video/mp4').status_code, 415)
            self.assertEqual(self.post(client, content=b'x' * 10).status_code, 422)
            with mock.patch.object(speech, 'MAX_BYTES', 5000):
                self.assertEqual(self.post(client, content=b'x' * 6000).status_code, 413)

    def test_unavailable_without_key_and_rate_limited(self):
        with mock.patch.object(research, 'GROQ_API_KEY', ''), TestClient(api.app) as client:
            self.login(client, 'speech-off@example.invalid')
            self.assertFalse(client.get('/api/research/status').json()['speech'])
            self.assertEqual(self.post(client).status_code, 503)
        reply = lambda request, timeout: FakeResponse(b'{"text": "ok"}')
        with mock.patch.object(research, 'GROQ_API_KEY', 'test-key'), mock.patch.object(speech, 'urlopen', reply), mock.patch.object(speech, 'LIMIT', 2), TestClient(api.app) as client:
            self.login(client, 'speech-limit@example.invalid')
            self.assertEqual([self.post(client).status_code for _ in range(3)], [200, 200, 429])
