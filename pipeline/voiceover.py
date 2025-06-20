from __future__ import annotations

import os
try:
    import requests
except Exception:  # pragma: no cover - missing dependency in tests
    requests = None
from pathlib import Path
from typing import Optional
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - missing dependency in tests
    def load_dotenv():
        pass
from .logger import setup_logger

load_dotenv()


class VoiceOverGenerator:
    def __init__(
        self,
        engine: str,
        voice_id: Optional[str] = None,
        coqui_model_name: str | None = None,
        force_coqui: bool = False,
        debug: bool = False,
        log_file: Optional[Path] = None,
    ):
        self.engine = engine
        self.voice_id = voice_id
        self.coqui_model_name = coqui_model_name or "tts_models/en/ljspeech/tacotron2-DDC"
        self.force_coqui = force_coqui
        self.logger = setup_logger("voiceover", log_file, debug)
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")

    def generate(self, text: str, output_path: Path) -> bool:
        """Generate speech for *text* and save it to *output_path*."""
        if not text.strip():
            self.logger.error("No script text provided for voiceover")
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)

        engine = self.engine
        if self.force_coqui:
            engine = "coqui"
            self.logger.info("Force Coqui flag enabled; skipping ElevenLabs")
        self.logger.info(f"Generating voiceover using {engine}")
        if engine == "elevenlabs":
            if not self.api_key or not self.voice_id:
                self.logger.error("ElevenLabs voice ID not found. Falling back to Coqui TTS.")
                return self._generate_coqui(text, output_path)
            if self._generate_elevenlabs(text, output_path):
                ok = output_path.exists() and output_path.stat().st_size > 0
                if ok:
                    self.logger.info(f"Voiceover saved to {output_path}")
                return ok
            self.logger.error("ElevenLabs generation failed. Falling back to Coqui TTS.")
            return self._generate_coqui(text, output_path)

        return self._generate_coqui(text, output_path)

    def _generate_elevenlabs(self, text: str, output_path: Path) -> bool:
        if requests is None:
            self.logger.error("requests library not available")
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"xi-api-key": self.api_key}
        payload = {"text": text}
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    output_path.write_bytes(response.content)
                    self.logger.info("ElevenLabs voiceover generated successfully")
                    return True
                self.logger.error(
                    f"ElevenLabs API error {response.status_code}: {response.text}"
                )
                if response.status_code == 404:
                    self.logger.error("ElevenLabs voice ID not found")
                    self._list_voices()
                if response.status_code >= 500:
                    continue
                return False
            except Exception as e:
                self.logger.error(f"ElevenLabs request failed: {e}")
                if attempt == 2:
                    return False
        return False

    def _generate_coqui(self, text: str, output_path: Path) -> bool:
        self.logger.info("Using Coqui TTS")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from TTS.api import TTS
            from TTS.utils.manage import ModelManager
        except Exception as e:  # fallback import error or runtime
            self.logger.error(f"Coqui TTS not available: {e}")
            return False

        try:
            tts = TTS(model_name=self.coqui_model_name)
        except Exception:
            self.logger.info("Downloading Coqui TTS model...")
            manager = ModelManager()
            try:
                manager.download_model(self.coqui_model_name)
                tts = TTS(model_name=self.coqui_model_name)
            except Exception as e:
                self.logger.error(f"Coqui TTS download failed: {e}")
                return False

        try:
            tts.tts_to_file(text=text, file_path=str(output_path))
            if output_path.exists() and output_path.stat().st_size > 0:
                self.logger.info(f"Coqui voiceover generated successfully at {output_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Coqui TTS generation failed: {e}")
            return False

    def _list_voices(self) -> None:
        """Fetch and log available ElevenLabs voices."""
        if requests is None or not self.api_key:
            return
        try:
            resp = requests.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": self.api_key}, timeout=30)
            if resp.status_code == 200:
                voices = [v.get("voice_id", "") for v in resp.json().get("voices", [])]
                if voices:
                    self.logger.error("Available voices: " + ", ".join(voices))
        except Exception as e:
            self.logger.error(f"Failed to fetch voice list: {e}")

