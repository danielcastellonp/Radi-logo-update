"""
audio.py — Converts podcast script to MP3 using ElevenLabs TTS.
Two distinct voices for ANA and CARLOS.
Splits long scripts into chunks and concatenates the audio.
"""

import os
import re
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# Voice IDs — these are ElevenLabs public voice IDs
# You can change these to any voices from your ElevenLabs account
VOICES = {
    "ANA": os.getenv("VOICE_ANA", "EXAVITQu4vr4xnSDxMaL"),      # Bella — clear, professional female
    "CARLOS": os.getenv("VOICE_CARLOS", "VR6AewLTigWG4xSOukaG"),  # Arnold — confident male
}

VOICE_SETTINGS = {
    "stability": 0.55,
    "similarity_boost": 0.75,
    "style": 0.1,
    "use_speaker_boost": True,
}

MAX_CHARS_PER_CHUNK = 4500  # ElevenLabs limit per request


def _parse_script(script: str) -> list[tuple[str, str]]:
    """
    Parses podcast script into list of (speaker, text) tuples.
    Handles **ANA:** and **CARLOS:** markers.
    Strips timestamp markers like [00:00].
    """
    # Remove timestamp markers
    script = re.sub(r'\[\d{2}:\d{2}\]', '', script)

    # Split by speaker turns
    pattern = r'\*\*(ANA|CARLOS)\:\*\*\s*'
    parts = re.split(pattern, script)

    turns = []
    i = 1
    while i < len(parts) - 1:
        speaker = parts[i].strip()
        text = parts[i + 1].strip()
        if speaker in ("ANA", "CARLOS") and text:
            # Clean up any markdown
            text = re.sub(r'\*+', '', text)
            text = re.sub(r'#{1,6}\s*', '', text)
            text = text.strip()
            if text:
                turns.append((speaker, text))
        i += 2

    return turns


def _tts_chunk(text: str, voice_id: str) -> bytes | None:
    """Calls ElevenLabs TTS API for a single text chunk."""
    url = f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": VOICE_SETTINGS,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=120)
        r.raise_for_status()
        return r.content
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        return None


def _split_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Splits long text into chunks at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = f"{current} {sent}".strip()
        else:
            if current:
                chunks.append(current)
            current = sent
    if current:
        chunks.append(current)
    return chunks


def generate_podcast_audio(script: str, output_path: str) -> bool:
    """
    Main function: converts full podcast script to MP3.
    Returns True if successful.
    Requires: pydub + ffmpeg for audio concatenation.
    """
    if not ELEVENLABS_API_KEY:
        logger.error("ELEVENLABS_API_KEY not set. Skipping audio generation.")
        return False

    try:
        from pydub import AudioSegment
        import io
    except ImportError:
        logger.error("pydub not installed. Run: pip install pydub")
        return False

    turns = _parse_script(script)
    if not turns:
        logger.error("No speaker turns parsed from script.")
        return False

    logger.info(f"Generating audio for {len(turns)} speaker turns...")

    # Small silence between turns (500ms)
    silence = AudioSegment.silent(duration=500)
    combined = AudioSegment.silent(duration=0)

    for i, (speaker, text) in enumerate(turns):
        voice_id = VOICES.get(speaker)
        if not voice_id:
            continue

        chunks = _split_text(text)
        turn_audio = AudioSegment.silent(duration=0)

        for chunk in chunks:
            logger.info(f"  Turn {i+1}/{len(turns)} [{speaker}]: {len(chunk)} chars")
            audio_bytes = _tts_chunk(chunk, voice_id)
            if audio_bytes:
                segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                turn_audio += segment

        if len(turn_audio) > 0:
            combined += turn_audio + silence

    if len(combined) == 0:
        logger.error("No audio generated.")
        return False

    # Export
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    combined.export(output_path, format="mp3", bitrate="128k")
    duration_min = len(combined) / 60000
    logger.info(f"Podcast exported: {output_path} ({duration_min:.1f} min)")
    return True


def generate_podcast_audio_openai(script: str, output_path: str) -> bool:
    """
    Alternative TTS using OpenAI API (alloy + nova voices).
    Uses OPENAI_API_KEY env var.
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set.")
        return False

    try:
        from pydub import AudioSegment
        import io
        from openai import OpenAI
    except ImportError:
        logger.error("openai or pydub not installed.")
        return False

    oai = OpenAI(api_key=openai_key)
    oai_voices = {"ANA": "nova", "CARLOS": "onyx"}

    turns = _parse_script(script)
    silence = AudioSegment.silent(duration=500)
    combined = AudioSegment.silent(duration=0)

    for i, (speaker, text) in enumerate(turns):
        voice = oai_voices.get(speaker, "alloy")
        chunks = _split_text(text, max_chars=4096)

        for chunk in chunks:
            logger.info(f"  OpenAI TTS Turn {i+1}/{len(turns)} [{speaker}]")
            try:
                response = oai.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=chunk,
                )
                audio_data = response.content
                segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
                combined += segment
            except Exception as e:
                logger.error(f"OpenAI TTS error: {e}")

        combined += silence

    if len(combined) == 0:
        return False

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    combined.export(output_path, format="mp3", bitrate="128k")
    duration_min = len(combined) / 60000
    logger.info(f"OpenAI Podcast exported: {output_path} ({duration_min:.1f} min)")
    return True
