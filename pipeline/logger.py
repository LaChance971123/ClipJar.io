import logging
from pathlib import Path


def setup_logger(name: str, log_file: Path | None = None, debug: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    else:
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            logger.addHandler(ch)

    if log_file:
        log_file = Path(log_file)
        if not any(isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file for h in logger.handlers):
            fh = logging.FileHandler(log_file)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    return logger
