from __future__ import annotations

from pathlib import Path

from agents.paths import PROMPTS_DIR


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **values: str) -> str:
    template = load_prompt(name)
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template
