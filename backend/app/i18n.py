"""Tiny i18n helper for messages the bot publishes. Add a language by dropping a JSON file
in app/locales/ (e.g. es.json) with the same keys as en.json."""

import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"
FALLBACK = "en"


@lru_cache
def _catalog(lang: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def available_languages() -> list[str]:
    return sorted(p.stem for p in LOCALES_DIR.glob("*.json"))


def t(lang: str | None, key: str, **params: object) -> str:
    lang = (lang or FALLBACK).replace("-", "_")
    text = _catalog(lang).get(key) or _catalog(lang.split("_")[0]).get(key)
    text = text or _catalog(FALLBACK).get(key) or key
    return text.format(**params) if params else text
