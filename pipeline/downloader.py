from __future__ import annotations

from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List

from yt_dlp import YoutubeDL

from .logger import setup_logger
from .helpers import sanitize_name


class Downloader:
    def __init__(self, output_dir: Path, log_file: Path | None = None, debug: bool = False) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logger("downloader", log_file, debug)
        self.executor = ThreadPoolExecutor(max_workers=3)

    def _download(self, url: str, quality: str, audio_only: bool) -> None:
        fname = sanitize_name(url)[:20]
        opts = {
            "outtmpl": str(self.output_dir / f"{fname}.%(ext)s"),
            "quiet": True,
        }
        if audio_only:
            opts["format"] = "bestaudio"
        elif quality != "best":
            opts["format"] = f"bestvideo[height<={quality.rstrip('p')}]+bestaudio/best"
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        self.logger.info(f"Downloaded {url}")

    def download_batch(self, urls: List[str], quality: str = "best", audio_only: bool = False) -> None:
        futs = [self.executor.submit(self._download, u.strip(), quality, audio_only) for u in urls if u.strip()]
        for f in futs:
            f.result()
