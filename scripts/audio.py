"""
audio.py — Converts podcast script to MP3 using OpenAI TTS.
Two distinct voices for ANA (nova) and CARLOS (onyx).
Handles chunking, rate limits, and retries robustly.
"""

import os
import re
import time
import logging
import io
from pathlib import Path

logger = logging.getLogger(__name__)

# Voice mapping
VOICES = {
    "ANA": "nova",
    "CARLOS": "onyx",
}

MAX_CHARS_PER_CHUNK = 2000  # Conservative limit for OpenAI TTS
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds between retries


def _parse_script(script: str) -> list[tuple[str, str]]:
    """
    Parses podcast script into list of (speaker, text) tuples.
    Handles **ANA:** and **CARLOS:** markers.
    Strips timestamp markers like [00:00].
    """
    # Remove timestamp markers
    script = re.sub(r'\[\d{2}:\d{2}\]', '', script)
    # Remove markdown headers
    script = re.sub(r'#{1,6}\s*.+\n', '', script)

    pattern = r'\*\*(ANA|CARLOS)\:\*\*\s*'
    parts = re.split(pattern, script)

    turns = []
    i = 1
    while i < len(parts) - 1:
        speaker = parts[i].strip()
        text = parts[i + 1].strip()
        if speaker in ("ANA", "CARLOS") and text:
            text = re.sub(r'\*+', '', text).strip()
            if text:
                turns.append((speaker, text))
        i += 2

    return turns


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
            # If single sentence is too long, split by comma
            if len(sent) > max_chars:
                parts = sent.split(', ')
                sub = ""
                for p in parts:
                    if len(sub) + len(p) + 2 <= max_chars:
                        sub = f"{sub}, {p}".strip(', ')
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = p
                if sub:
                    chunks.append(sub)
            else:
                current = sent
    if current:
        chunks.append(current)
    return chunks


def _tts_openai(text: str, voice: str, client) -> bytes | None:
    """Single TTS call with retries."""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
            )
            return response.content
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                wait = RETRY_DELAY * (attempt + 1)
                logger.warning(f"Rate limit hit, waiting {wait}s before retry {attempt+1}/{RETRY_ATTEMPTS}")
                time.sleep(wait)
            elif "quota" in error_str.lower() or "insufficient" in error_str.lower():
                logger.error("OpenAI quota exceeded. Please add credits at platform.openai.com/account/billing")
                return None
            else:
                logger.error(f"OpenAI TTS error: {e}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return None
    return None


def generate_podcast_audio_openai(script: str, output_path: str) -> bool:
    """
    Converts full podcast script to MP3 using OpenAI TTS.
    Returns True if successful.
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set.")
        return False

    try:
        from pydub import AudioSegment
        from openai import OpenAI
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return False

    oai = OpenAI(api_key=openai_key)

    turns = _parse_script(script)
    if not turns:
        logger.error("No speaker turns parsed from script.")
        return False

    logger.info(f"Generating audio for {len(turns)} speaker turns...")

    silence = AudioSegment.silent(duration=400)
    combined = AudioSegment.silent(duration=0)
    successful_turns = 0

    for i, (speaker, text) in enumerate(turns):
        voice = VOICES.get(speaker, "alloy")
        chunks = _split_text(text)
        turn_audio = AudioSegment.silent(duration=0)
        turn_success = True

        for j, chunk in enumerate(chunks):
            logger.info(f"  Turn {i+1}/{len(turns)} [{speaker}] chunk {j+1}/{len(chunks)}: {len(chunk)} chars")
            
            # Small delay between API calls to avoid rate limiting
            if i > 0 or j > 0:
                time.sleep(0.5)

            audio_bytes = _tts_openai(chunk, voice, oai)
            if audio_bytes:
                try:
                    segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                    turn_audio += segment
                except Exception as e:
                    logger.error(f"Audio decode error: {e}")
                    turn_success = False
                    break
            else:
                logger.warning(f"  Turn {i+1} chunk {j+1} failed, skipping")
                turn_success = False
                break

        if len(turn_audio) > 0:
            combined += turn_audio + silence
            successful_turns += 1

    if len(combined) == 0:
        logger.error("No audio generated.")
        return False

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    combined.export(output_path, format="mp3", bitrate="128k")
    duration_min = len(combined) / 60000
    logger.info(f"Podcast exported: {output_path} ({duration_min:.1f} min, {successful_turns}/{len(turns)} turns)")
    return True
