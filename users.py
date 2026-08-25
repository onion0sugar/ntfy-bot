"""Mapowanie loginów MSSQL na dwa topiki ntfy użytkownika."""

from __future__ import annotations

import json
import os


class MappingError(Exception):
    pass


def load_mapping(path: str = "user_mapping.json") -> dict[str, dict[str, str]]:
    if not os.path.isfile(path):
        raise MappingError(f"Brak pliku mapowania: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise MappingError(f"Błędny JSON w {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise MappingError("user_mapping.json musi być obiektem JSON")
    result: dict[str, dict[str, str]] = {}
    for login, topics in raw.items():
        if not isinstance(topics, dict):
            continue
        new_topic = str(topics.get("new_order_topic", "")).strip()
        ready_topic = str(topics.get("ready_order_topic", "")).strip()
        if login and new_topic and ready_topic:
            result[str(login).strip()] = {
                "new_order_topic": new_topic,
                "ready_order_topic": ready_topic,
            }
    if not result:
        raise MappingError("user_mapping.json nie zawiera poprawnych mapowań")
    return result

