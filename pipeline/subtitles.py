from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import subprocess
import json
from .logger import setup_logger
from .helpers import create_dummy_subtitles


class SubtitleGenerator:
    """Generate subtitles using Whisper and export to ASS format."""
    def __init__(self, style: str, model: str = "base", log_file: Optional[Path] = None, debug: bool = False):
        self.style = style
        self.model_name = model
        self.logger = setup_logger("subtitles", log_file, debug)

    def transcribe(self, audio_path: Path) -> List[dict]:
        """Use whisper to transcribe audio to words with timestamps."""
        self.logger.info("Transcribing audio with Whisper")
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            self.logger.error(f"Audio file not found: {audio_path}")
            return []
        try:
            import whisper
        except Exception as e:
            self.logger.error(f"Whisper not available: {e}")
            return []
        model = whisper.load_model(self.model_name)
        result = model.transcribe(str(audio_path), word_timestamps=True)
        words = result.get("segments", [])
        self.logger.info(f"Transcription complete: {len(words)} segments")
        return words

    def generate_ass(self, words: List[dict], output_path: Path):
        self.logger.info(f"Generating {self.style} subtitles")
        if not words:
            self.logger.warning("No subtitle segments provided; using dummy subtitles")
            create_dummy_subtitles(output_path)
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n\n")
            f.write(
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, BackColour, OutlineColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow, Encoding\n"
            )
            f.write(
                "Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H00000000,0,0,2,10,10,10,1,2,0,0\n"
            )
            f.write("[Events]\nFormat: Start, End, Style, Text\n")
            for w in words:
                start = self._format_time(w["start"])
                end = self._format_time(w["end"])
                text = w.get("text", "").strip()
                line = f"Dialogue: 0,{start},{end},Default,{self._style_tag(text)}\n"
                f.write(line)
        self.logger.info(f"Subtitles written to {output_path}")

    def _style_tag(self, text: str) -> str:
        if self.style == "karaoke":
            return f"{{\\k20}}{text}"
        if self.style == "progressive":
            return f"{{\\alpha&HFF&\\t(0,300,\\alpha&H00&)}}{text}"
        return text

    @staticmethod
    def _format_time(seconds: float) -> str:
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 100)
        return f"{hrs:01d}:{mins:02d}:{secs:02d}.{ms:02d}"

