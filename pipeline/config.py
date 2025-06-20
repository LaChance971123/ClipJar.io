from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import logging
import os


@dataclass
class Config:
    subtitle_style: str = "simple"
    watermark_path: str | None = None
    watermark_opacity: float = 1.0
    watermark_enabled: bool = True
    voice_engine: str = "elevenlabs"
    default_voice_id: str | None = None
    coqui_model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    whisper_model: str | None = "base"
    background_videos_path: str = "assets/backgrounds"
    resolution: str = "1080x1920"
    ffmpeg_path: str = "ffmpeg"
    step_timeout: int = 120
    safe_mode: bool = False
    developer_mode: bool = False
    voices: dict[str, str] | None = None
    background_styles: dict[str, str] | None = None
    resolutions: list[str] | None = None
    presets: dict[str, dict] | None = None
    default_preset: str = "default"
    auto_trim_silence: bool = False
    crop_safe_zone: bool = False
    summary_overlay: bool = False
    theme: str = "dark"
    always_on_top: bool = False
    first_launch: bool = True

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(**data)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.__dict__, f, indent=2)

    def validate(self, logger: logging.Logger | None = None) -> None:
        logger = logger or logging.getLogger(__name__)
        if self.watermark_path and not Path(self.watermark_path).exists():
            logger.warning(f"Watermark {self.watermark_path} not found; disabling")
            self.watermark_path = None
            self.watermark_enabled = False
        if shutil.which(self.ffmpeg_path) is None:
            logger.warning(f"ffmpeg not found at {self.ffmpeg_path}; using 'ffmpeg'")
            self.ffmpeg_path = "ffmpeg"
        bg_root = Path(self.background_videos_path)
        if not bg_root.exists():
            logger.warning(f"Background path {bg_root} does not exist")
        self.resolution = self.resolution.lower().replace(" ", "")
        if self.step_timeout <= 0:
            logger.warning("step_timeout must be > 0; using 120")
            self.step_timeout = 120

        if not self.whisper_model:
            logger.error("Whisper configuration missing 'model'")

        if self.voice_engine == "elevenlabs":
            api = os.getenv("ELEVENLABS_API_KEY")
            vid = self.default_voice_id or os.getenv("ELEVENLABS_VOICE_ID")
            if not api or not vid:
                logger.error("ElevenLabs configuration missing api_key or voice_id")

        if self.theme not in {"dark", "light"}:
            logger.warning("Invalid theme; defaulting to 'dark'")
            self.theme = "dark"

    def apply_preset(self, name: str) -> tuple[str | None, bool]:
        """Apply *name* preset. Returns (background_style, subtitles_enabled)."""
        if not self.presets or name not in self.presets:
            raise KeyError(name)
        p = self.presets[name]
        self.default_voice_id = p.get("voice", self.default_voice_id)
        self.resolution = p.get("resolution", self.resolution)
        if "watermark" in p:
            self.watermark_enabled = bool(p["watermark"])
        bg = p.get("background_style")
        subtitles = bool(p.get("subtitles", True))
        return bg, subtitles

