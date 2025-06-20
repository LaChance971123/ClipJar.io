from __future__ import annotations

import argparse
import random
from pathlib import Path

from pipeline import __version__
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - missing dependency
    def load_dotenv():
        pass


class CLI:
    """Command-line interface for the ClipJar pipeline."""
    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        """Return the argument parser for the CLI."""
        parser = argparse.ArgumentParser(description="Video generation pipeline")
        parser.add_argument(
            "--version",
            action="version",
            version=f"AutoContent {__version__}",
            help="Show program version and exit",
        )
        parser.add_argument("--script-file", help="Path to script text file")
        parser.add_argument("--script-text", help="Inline script text")
        parser.add_argument(
            "--style",
            choices=["karaoke", "progressive", "simple"],
            default=None,
            help="Subtitle style",
        )
        parser.add_argument("--resolution", help="Video resolution e.g. 1080x1920")
        parser.add_argument("--background-style", help="Background style to use")
        parser.add_argument("--background", help=argparse.SUPPRESS)
        parser.add_argument("--output", help="Output video path")
        parser.add_argument("--preset", help="Name of preset to use")
        parser.add_argument("--preview-voice", help="Preview voice ID then exit")
        parser.add_argument("--batch", help="Folder of scripts for batch mode")
        parser.add_argument("--randomize", action="store_true", help="Randomize voice/background in batch mode")
        parser.add_argument("--watermark-path", help="Override watermark image path")
        parser.add_argument("--generate", action="store_true", help="Generate story with Mistral AI")
        parser.add_argument("--genre", help="Story genre")
        parser.add_argument("--tone", help="Story tone")
        parser.add_argument("--prompt", help="Prompt seed for story generation")
        parser.add_argument("--no-subtitles", action="store_true", help="Do not create subtitles")
        parser.add_argument("--audio-only", action="store_true", help="Export only audio")
        parser.add_argument("--force-coqui", action="store_true", help="Use Coqui TTS instead of ElevenLabs")
        parser.add_argument("--whisper-disable", action="store_true", help="Skip Whisper transcription")
        parser.add_argument("--no-watermark", action="store_true", help="Disable watermark")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--verbose", action="store_true", help="Verbose logging")
        parser.add_argument("--log-to-file", action="store_true")
        return parser

    @staticmethod
    def parse(args=None) -> argparse.Namespace:
        """Parse command line *args* or ``sys.argv`` when ``None``."""
        parser = CLI.build_parser()
        return parser.parse_args(args)


def _load_config() -> "Config":
    from pipeline.config import Config
    cfg_path = Path("config/config.json")
    config = Config.load(cfg_path)
    return config


def _read_script(args: argparse.Namespace) -> tuple[str, str]:
    if args.script_text:
        return args.script_text, "cli"
    if args.script_file:
        path = Path(args.script_file)
        if not path.exists():
            raise FileNotFoundError(f"Script file {path} does not exist")
        return path.read_text(), path.stem
    text = "".join(iter(input, ""))  # stdin
    return text, "stdin"


def main(argv=None) -> None:
    """Entry point for the ClipJar CLI."""
    from pipeline.pipeline import VideoPipeline
    from pipeline.logger import setup_logger
    from pipeline.helpers import color_print, log_trace, validate_files

    color_print("INFO", "Starting AutoContent CLI pipeline...")
    load_dotenv()
    args = CLI.parse(argv)
    if args.verbose:
        args.debug = True

    config = _load_config()
    logger = setup_logger("cli", None, args.debug)
    config.validate(logger)

    if args.preview_voice:
        from pipeline.helpers import preview_voice

        preview = preview_voice(config.voice_engine, args.preview_voice, config.coqui_model_name)
        color_print("INFO", f"Preview saved to {preview}")
        return

    if args.generate:
        from pipeline import generator

        try:
            script_text = generator.generate_story(args.genre, args.tone, args.prompt)
            name = "generated"
            color_print("INFO", "Story generated with Mistral")
        except Exception as e:
            color_print("ERROR", f"Generation failed: {e}")
            log_trace(e)
            script_text, name = "Generation failed", "generated"
    else:
        try:
            script_text, name = _read_script(args)
            color_print("INFO", f"Loaded script from {name}")
        except Exception as e:
            color_print("ERROR", f"Failed to read script: {e}")
            log_trace(e)
            return

    preset_name = args.preset or config.default_preset
    try:
        p_bg, p_subs = config.apply_preset(preset_name)
    except KeyError:
        color_print("ERROR", f"Preset '{preset_name}' not found")
        return
    background = args.background_style or args.background
    if not background:
        background = p_bg
    if p_subs is False:
        args.no_subtitles = True

    if args.watermark_path:
        config.watermark_path = args.watermark_path
        config.watermark_enabled = True
    color_print("INFO", f"Using voice engine: {config.voice_engine}")
    if args.force_coqui:
        color_print("INFO", "Force Coqui flag enabled")
    color_print("INFO", f"Whisper model: {config.whisper_model}")

    if args.style:
        config.subtitle_style = args.style
    if args.resolution:
        config.resolution = args.resolution
    if args.no_watermark:
        config.watermark_enabled = False
    output_path = Path(args.output) if args.output else None

    log_file = None
    if args.log_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "pipeline.log"

    pipeline = VideoPipeline(config, debug=args.debug, log_file=log_file)

    if args.batch:
        folder = Path(args.batch)
        scripts = sorted(folder.glob("*.txt"))
        if not scripts:
            color_print("ERROR", f"No .txt files found in {folder}")
            return
        results = []
        for idx, sp in enumerate(scripts, 1):
            color_print("INFO", f"[{idx}/{len(scripts)}] Processing {sp.name}")
            text = sp.read_text()
            bkg = background
            if args.randomize:
                if config.background_styles:
                    bkg = random.choice(list(config.background_styles.keys()))
                if config.voices:
                    config.default_voice_id = random.choice(list(config.voices.values()))
            try:
                ctx = pipeline.run(
                    text,
                    sp.stem,
                    background=bkg,
                    force_coqui=args.force_coqui,
                    whisper_disable=args.whisper_disable,
                    no_subtitles=args.no_subtitles,
                )
                results.append(f"{sp.name}: success -> {ctx.final_video_path}")
            except Exception as e:
                color_print("ERROR", f"Failed {sp.name}: {e}")
                log_trace(e)
                results.append(f"{sp.name}: failed - {e}")
        (folder / "batch_summary.txt").write_text("\n".join(results))
        color_print("SUCCESS", "Batch processing complete")
        return
    try:
        ctx = pipeline.run(
            script_text,
            name,
            background=background,
            output=output_path,
            force_coqui=args.force_coqui,
            whisper_disable=args.whisper_disable,
            no_subtitles=args.no_subtitles,
        )
    except Exception as exc:
        color_print("ERROR", f"Pipeline failed: {exc}")
        log_trace(exc)
        return

    paths = [ctx.voiceover_path, ctx.final_video_path]
    if not args.no_subtitles:
        paths.append(ctx.subtitles_path)
    missing = validate_files(*paths)
    for m in missing:
        color_print("ERROR", f"Output missing or empty: {m}")

    color_print("SUCCESS", "Pipeline completed successfully")
    color_print("INFO", f"Output folder: {ctx.output_dir}")
    color_print("INFO", f"Final video: {ctx.final_video_path}")
    color_print("INFO", f"Voice engine: {ctx.voice_engine}")
    color_print("INFO", f"Whisper model: {config.whisper_model}")


if __name__ == "__main__":
    main()

