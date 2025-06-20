from __future__ import annotations

"""Simple story generator placeholder."""

from typing import Optional
import json
try:
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None


def generate_story(
    genre: Optional[str] = None,
    tone: Optional[str] = None,
    prompt: Optional[str] = None,
) -> str:
    """Return a short story using a local Mistral/LLM instance."""

    base_prompt = prompt or "Tell a short story."
    if genre:
        base_prompt += f"\nGenre: {genre}"
    if tone:
        base_prompt += f"\nTone: {tone}"

    if requests is not None:
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "mistral", "prompt": base_prompt},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("response") or data.get("message", "")
                if text:
                    return text.strip()
        except Exception:
            pass

    # Fallback simple story
    base = prompt or "Once upon a time there was a short story."
    if genre:
        base = f"A {genre} story: {base}"
    if tone:
        base = f"({tone} tone) " + base
    return base
