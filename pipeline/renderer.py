from __future__ import annotations

import random
import subprocess
from pathlib import Path
from typing import Optional
import shutil
import tempfile

from .logger import setup_logger


class VideoRenderer:
    """Render the final video using FFmpeg."""
    def __init__(
        self,
        bg_folder: Path,
        watermark: Path | None = None,
        opacity: float = 1.0,
        resolution: str = "1080x1920",
        ffmpeg_path: str = "ffmpeg",
        log_file: Optional[Path] = None,
        debug: bool = False,
    ):
        self.logger = setup_logger("renderer", log_file, debug)
        self.bg_root = bg_folder.parent
        self.bg_folder = self._resolve_folder(bg_folder)
        self.watermark = watermark if watermark and watermark.exists() else None
        self.opacity = opacity
        self.resolution = resolution
        self.ffmpeg = ffmpeg_path
        if not shutil.which(self.ffmpeg):
            self.logger.warning(f"ffmpeg executable '{self.ffmpeg}' not found")

    def _list_videos(self, folder: Path) -> list[Path]:
        return [p for p in folder.glob("*") if p.suffix.lower() in {".mp4", ".webm"}]

    def _resolve_folder(self, folder: Path) -> Path:
        folder = folder.resolve()
        if folder.exists():
            videos = self._list_videos(folder)
            if videos:
                return folder
            # if folder is a root containing subfolders, try them
            subdirs = [p for p in folder.iterdir() if p.is_dir()]
            for sub in subdirs:
                vids = self._list_videos(sub)
                if vids:
                    self.logger.warning(
                        f"Falling back to {sub} due to missing videos in {folder}"
                    )
                    return sub
            self.logger.warning(
                f"No background videos found in '{folder}'. Please add videos or pick another style."
            )
        # try case-insensitive search in root
        root = folder.parent
        if not root.exists():
            raise FileNotFoundError(f"Background root {root} does not exist")
        target = folder.name.lower()
        for cand in root.iterdir():
            if cand.is_dir() and cand.name.lower() == target:
                videos = self._list_videos(cand)
                if videos:
                    self.logger.info(f"Resolved background folder to {cand}")
                    return cand
                self.logger.error(f"No background videos found in {cand}")
                break
        # fallback to default 'Rain' folder if available
        for cand in root.iterdir():
            if cand.is_dir() and cand.name.lower() == "rain" and self._list_videos(cand):
                self.logger.warning(
                    f"Falling back to {cand} due to missing {folder.name} videos"
                )
                return cand
        # fallback to any folder with videos
        for cand in root.iterdir():
            if cand.is_dir() and self._list_videos(cand):
                self.logger.warning(
                    f"Falling back to {cand} due to missing {folder.name} videos"
                )
                return cand
        raise FileNotFoundError(f"No background videos found in {root}")

    def pick_background(self) -> Path:
        videos = self._list_videos(self.bg_folder)
        if not videos:
            self.logger.error(f"No background videos found in {self.bg_folder}")
            raise FileNotFoundError("No background videos found")
        choice = random.choice(videos)
        self.logger.info(f"Selected background video {choice}")
        return choice

    def render(
        self,
        audio_path: Path,
        subtitles: Path | None,
        output_path: Path,
        intro: Path | None = None,
        outro: Path | None = None,
        crop_safe: bool = False,
        overlay_text: str | None = None,
    ):
        """Render the final video using *audio_path* and optional *subtitles*.

        Automatically switches to ``-filter_complex`` when a watermark and
        subtitles are both present. All paths are converted to POSIX style to
        avoid Windows escaping issues.
        """
        self.logger.info("Starting FFmpeg render")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if subtitles and not subtitles.exists():
            self.logger.warning(f"Subtitle file not found: {subtitles}")
            subtitles = None
        if intro and not intro.exists():
            raise FileNotFoundError(f"Intro clip not found: {intro}")
        if outro and not outro.exists():
            raise FileNotFoundError(f"Outro clip not found: {outro}")

        if output_path.suffix.lower() != ".mp4":
            raise ValueError("Output path must end with .mp4")

        bg_video = self.pick_background()

        # simple wav validation
        try:
            import wave

            with wave.open(str(audio_path), "rb") as _:
                pass
        except Exception as e:
            self.logger.error(f"Invalid audio file {audio_path}: {e}")
            raise

        self.logger.info(f"Using background video {bg_video}")

        bg = bg_video.as_posix()
        audio = audio_path.as_posix()
        subs = subtitles.as_posix() if subtitles and subtitles.exists() else None
        wm = self.watermark.as_posix() if self.watermark else None

        base_cmd = [self.ffmpeg, "-y", "-i", bg, "-i", audio]

        # Determine filters
        if subs and wm:
            fc = [f"[0:v]subtitles='{subs}'[vsubs]"]
            fc.append(f"movie={wm}[wm]")
            chain = "[vsubs][wm]overlay=W-w-10:H-h-10"
            if crop_safe:
                chain += ",crop=iw*0.9:ih*0.9:(iw-iw*0.9)/2:(ih-ih*0.9)/2"
            if overlay_text:
                text = overlay_text.replace("'", r"\'")
                chain += (
                    f",drawtext=text='{text}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=10:enable='lt(t,3)'"
                )
            chain += ",format=yuv420p[v]"
            fc.append(chain)
            filter_complex = ";".join(fc)
            cmd = base_cmd + [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a",
            ]
        else:
            vf_parts = []
            if subs:
                vf_parts.append(f"subtitles='{subs}'")
            if wm:
                vf_parts.append(
                    "movie="
                    + wm
                    + "[wm];[in][wm]overlay=W-w-10:H-h-10:format=auto"
                )
            if crop_safe:
                vf_parts.append("crop=iw*0.9:ih*0.9:(iw-iw*0.9)/2:(ih-ih*0.9)/2")
            if overlay_text:
                draw = (
                    "drawtext=text='"
                    + overlay_text.replace("'", r"\'")
                    + "':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=10:enable='lt(t,3)'"
                )
                vf_parts.append(draw)
            vf_parts.append("format=yuv420p")
            vf = ";".join(vf_parts) if wm and not subs else ",".join(vf_parts)
            cmd = base_cmd + ["-vf", vf]

        temp_dir = None
        main_output = output_path
        if intro or outro:
            temp_dir = tempfile.TemporaryDirectory()
            main_output = Path(temp_dir.name) / "main.mp4"

        cmd += ["-s", self.resolution, main_output.as_posix()]

        self.logger.debug("FFmpeg command: " + " ".join(cmd))

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stdout:
                self.logger.debug(result.stdout)
            if result.stderr:
                self.logger.debug(result.stderr)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg failed: {e.stderr}")
            raise

        if not main_output.exists() or main_output.stat().st_size == 0:
            raise RuntimeError("Render produced no output")

        if intro or outro:
            concat = Path(temp_dir.name) / "concat.txt"
            with open(concat, "w") as f:
                if intro:
                    f.write(f"file '{intro.as_posix()}'\n")
                f.write(f"file '{main_output.as_posix()}'\n")
                if outro:
                    f.write(f"file '{outro.as_posix()}'\n")
            cmd2 = [
                self.ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat.as_posix(),
                "-c",
                "copy",
                output_path.as_posix(),
            ]
            try:
                subprocess.run(cmd2, check=True)
            finally:
                main_output.unlink(missing_ok=True)
                concat.unlink(missing_ok=True)
                temp_dir.cleanup()

        self.logger.info(f"Render complete: {output_path}")

