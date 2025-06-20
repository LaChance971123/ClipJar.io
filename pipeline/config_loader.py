from __future__ import annotations

import json
import logging
import os
from pathlib import Path


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to load config {path}: {e}")
        return {}


def validate_elevenlabs(config: dict, logger: logging.Logger) -> bool:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = config.get("default_voice_id") or os.getenv("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        logger.error("ElevenLabs configuration missing api_key or voice_id")
        return False
    return True


def validate_whisper(config: dict, logger: logging.Logger) -> bool:
    model = config.get("whisper_model")
    if not model:
        logger.error("Whisper configuration missing 'model'")
        return False
    return True
