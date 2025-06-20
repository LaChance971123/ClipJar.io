from __future__ import annotations

from pathlib import Path
import time
import json
from .helpers import (
    PipelineContext,
    sanitize_name,
    now_ts_folder,
    run_with_timeout,
    create_silence,
    create_dummy_subtitles,
    log_trace,
)
from .voiceover import VoiceOverGenerator
from .subtitles import SubtitleGenerator
from .renderer import VideoRenderer
from .logger import setup_logger
from .config import Config


class VideoPipeline:
    """Orchestrates the voiceover, subtitles and rendering steps."""
    def __init__(self, config: Config, debug: bool = False, log_file: Path | None = None):
        self.config = config
        log_file = Path(log_file or config.log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logger("pipeline", log_file, debug)
        self.debug = debug
        self.log_file = log_file
        self.timeout = config.step_timeout

    def run(
        self,
        script_text: str,
        script_name: str,
        background: str | None = None,
        output: Path | None = None,
        force_coqui: bool = False,
        whisper_disable: bool = False,
        no_subtitles: bool = False,
        intro: Path | None = None,
        outro: Path | None = None,
        trim_silence: bool = False,
        crop_safe: bool = False,
        summary_overlay: bool = False,
    ) -> PipelineContext:
        """Run the pipeline and return a :class:`PipelineContext`."""
        style = self.config.subtitle_style
        engine = self.config.voice_engine
        voice_id = self.config.default_voice_id
        if force_coqui:
            engine = "coqui"

        # resolve background folder
        bg_styles = self.config.background_styles or {}
        bg_folder = Path(self.config.background_videos_path)
        if background:
            for key, val in bg_styles.items():
                if key.lower() == background.lower():
                    bg_folder = Path(val)
                    break

        title = sanitize_name(script_name if script_name not in {"cli", "stdin"} else "session")
        if output:
            final_output = Path(output)
            out_dir = final_output.parent
        else:
            out_dir = Path("output") / f"{title}_{now_ts_folder()}"
            final_output = out_dir / "final_video.mp4"
        session_log = out_dir / "pipeline.log"

        ctx = PipelineContext(
            script_text=script_text,
            script_name=title,
            output_dir=out_dir,
            subtitle_style=style,
            voice_engine=engine,
            voice_id=voice_id,
            log_file=session_log,
            debug=self.debug,
        )
        ctx.final_video_path = final_output

        # Reconfigure logger to use session log as well
        setup_logger("pipeline", session_log, self.debug)
        self.logger.info("Starting pipeline")
        status = "success"
        start = time.time()
        try:
            self.logger.info("[1/3] Voiceover generation")
            # Voiceover
            voice = VoiceOverGenerator(
                engine,
                voice_id,
                self.config.coqui_model_name,
                force_coqui=force_coqui,
                debug=self.debug,
                log_file=session_log,
            )
            try:
                run_with_timeout(
                    lambda: voice.generate(ctx.script_text, ctx.voiceover_path),
                    self.timeout,
                )
                if not ctx.voiceover_path.exists() or ctx.voiceover_path.stat().st_size == 0:
                    raise RuntimeError("voiceover file invalid")
            except Exception as e:
                self.logger.error(f"Voiceover step failed: {e}")
                if self.config.developer_mode:
                    create_silence(ctx.voiceover_path)
                    self.logger.warning("Developer mode: using silent audio")
                else:
                    raise
            if trim_silence:
                self.logger.info("Trimming silence from voiceover")
                try:
                    from .helpers import trim_silence_ffmpeg

                    trim_silence_ffmpeg(ctx.voiceover_path, self.config.ffmpeg_path)
                except Exception as e:
                    self.logger.warning(f"trim_silence failed: {e}")

            if not no_subtitles:
                self.logger.info("[2/3] Generating subtitles")
                subs = SubtitleGenerator(
                    style, model=self.config.whisper_model, log_file=session_log, debug=self.debug
                )
                try:
                    if whisper_disable:
                        self.logger.info("Whisper disabled; generating basic subtitles")
                        words = [
                            {"start": i * 0.5, "end": (i + 1) * 0.5, "text": w}
                            for i, w in enumerate(script_text.split())
                        ]
                    else:
                        words = run_with_timeout(subs.transcribe, self.timeout, ctx.voiceover_path)
                    run_with_timeout(subs.generate_ass, self.timeout, words, ctx.subtitles_path)
                except Exception as e:
                    self.logger.error(f"Subtitle step failed: {e}")
                    if self.config.developer_mode:
                        create_dummy_subtitles(ctx.subtitles_path)
                        self.logger.warning("Developer mode: using dummy subtitles")
                    else:
                        raise
            else:
                ctx.subtitles_path = ctx.output_dir / "subtitles.ass"
                ctx.subtitles_path.write_text("")
                self.logger.info("Subtitles disabled")

            self.logger.info("[3/3] Rendering video")
            # Render
            watermark_path = (
                Path(self.config.watermark_path)
                if self.config.watermark_enabled and self.config.watermark_path
                else None
            )
            renderer = VideoRenderer(
                bg_folder,
                watermark_path,
                self.config.watermark_opacity,
                resolution=self.config.resolution,
                ffmpeg_path=self.config.ffmpeg_path,
                log_file=session_log,
                debug=self.debug,
            )
            run_with_timeout(
                renderer.render,
                self.timeout,
                ctx.voiceover_path,
                None if no_subtitles else ctx.subtitles_path,
                ctx.final_video_path,
                intro,
                outro,
                crop_safe=crop_safe,
                overlay_text=script_name if summary_overlay else None,
            )
        except Exception as e:
            status = "failed"
            self.logger.error(f"Pipeline failed: {e}")
            ctx.write_error_trace(e)
            log_trace(e)
            ctx.save_metadata(status=status)
            ctx.save_config_snapshot(self.config.__dict__)
            ctx.write_summary()
            ctx.archive()
            raise

        duration = f"{int(time.time() - start)}s"
        ctx.save_metadata(status=status)
        run_summary = {
            "script": ctx.script_path.name,
            "voice": ctx.voice_engine.capitalize() if ctx.voice_engine else "",
            "style": ctx.subtitle_style,
            "duration": duration,
            "success": status == "success",
        }
        with open(ctx.output_dir / "run_summary.json", "w") as f:
            json.dump(run_summary, f, indent=2)
        ctx.save_config_snapshot(self.config.__dict__)
        ctx.write_summary()
        ctx.archive()
        self.logger.info(f"Pipeline completed. Video at {ctx.final_video_path}")
        return ctx
