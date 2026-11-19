"""Voice input: a short recording is sent to Groq's Whisper model and only the text comes back.

The audio is never written to disk or the database; it lives in memory for the length of the request.
"""
import json
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen  # patched in tests

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from . import research

MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo").strip()
MAX_BYTES = 15 * 1024 * 1024
LIMIT, WINDOW = 40, 600  # requests per user per ten minutes
AUDIO_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/aac": "m4a"}
# Whisper takes the prompt as preceding text: a natural legal sentence (not a word list) steers spelling such as "§ 536 BGB".
PROMPT = {
    "de": "Die Mandantin mindert die Miete nach § 536 BGB und setzt dem Vermieter eine Frist zur Mängelbeseitigung. Gegen den Bescheid wird Widerspruch eingelegt.",
    "en": "The client reduces the rent under section 536 BGB and sets the landlord a deadline to remedy the defect. An objection is lodged against the notice.",
}
available = lambda: bool(research.GROQ_API_KEY)
# On silence Whisper "hears" the subtitle credits it was trained on. Such lines are discarded, never inserted.
PHANTOMS = ("untertitelung des zdf", "untertitel im auftrag des zdf", "untertitel der amara", "untertitel von stephanie geiges", "vielen dank fürs zuschauen",
            "vielen dank für's zuschauen", "danke fürs zuschauen", "bis zum nächsten mal", "copyright wdr", "swr 2020", "swr 2021", "thanks for watching", "thank you for watching")


def clean(result: dict) -> str:
    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        kept = [str(item.get("text", "")) for item in segments if isinstance(item, dict) and float(item.get("no_speech_prob", 0) or 0) < 0.6]
        text = " ".join(part.strip() for part in kept if part.strip())
    else:
        text = str(result.get("text", ""))
    text = text.strip()
    folded = text.lower().strip(" .,!")
    return "" if not folded or any(phantom in folded for phantom in PHANTOMS) and len(folded) < 80 else text


def multipart(fields: dict, filename: str, content_type: str, content: bytes) -> tuple[bytes, str]:
    boundary = "----schimmelpilz" + uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode() for name, value in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode() + content + b"\r\n")
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), boundary


def transcribe(content: bytes, content_type: str, language: str) -> str:
    body, boundary = multipart({"model": MODEL, "language": language, "prompt": PROMPT[language], "response_format": "verbose_json", "temperature": "0"},
                               "speech." + AUDIO_TYPES[content_type], content_type, content)
    headers = {**research.groq_headers(), "Content-Type": "multipart/form-data; boundary=" + boundary}
    with urlopen(Request(research.GROQ_BASE_URL + "/audio/transcriptions", data=body, headers=headers, method="POST"), timeout=60) as response:
        return clean(json.loads(response.read(4 * 1024 * 1024)))


def router(db, require_user):
    routes = APIRouter()
    recent = defaultdict(deque)

    @routes.post("/api/speech/transcribe")
    async def speech_to_text(file: UploadFile = File(...), language: Literal["de", "en"] = Form("de"), user: dict = Depends(require_user)):
        if not available():
            raise HTTPException(503, "speech_unavailable")
        with db() as connection:
            if not connection.execute("SELECT ai_enabled FROM operator_settings WHERE id=1").fetchone()[0]:
                raise HTTPException(503, "ai_paused_by_operator")
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type not in AUDIO_TYPES:
            raise HTTPException(415, "unsupported_audio")
        stamps, moment = recent[user["id"]], time.monotonic()
        while stamps and moment - stamps[0] > WINDOW:
            stamps.popleft()
        if len(stamps) >= LIMIT:
            raise HTTPException(429, "speech_rate_limited")
        content = await file.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise HTTPException(413, "audio_too_large")
        if len(content) < 1000:
            raise HTTPException(422, "audio_too_short")
        stamps.append(moment)
        try:
            text = transcribe(content, content_type, language)
        except HTTPError as error:
            raise HTTPException(502, "speech_failed") from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise HTTPException(502, "speech_failed") from error
        return {"text": text}

    return routes
