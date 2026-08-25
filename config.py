"""Konfiguracja aplikacji ładowana z .env / zmiennych środowiskowych."""

from __future__ import annotations

import os
from types import SimpleNamespace

from dotenv import load_dotenv


class ConfigError(Exception):
    """Brakująca lub błędna zmienna konfiguracyjna."""


def _env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not (value and value.strip()):
        raise ConfigError(
            f"Brak wymaganej zmiennej środowiskowej: {name} "
            f"(skopiuj .env.example do .env)"
        )
    return value.strip() if value else value


def _flag(name: str, default: str = "true") -> bool:
    return (_env(name, default) or "").lower() in {"1", "true", "yes", "on"}


def load_config(env_file: str | None = None) -> SimpleNamespace:
    """Wczytaj konfigurację (nie nadpisuje istniejących zmiennych środowiska)."""
    load_dotenv(env_file)
    return SimpleNamespace(
        # MSSQL
        mssql_server=_env("MSSQL_SERVER", required=True),
        mssql_port=int(_env("MSSQL_PORT", "1433") or "1433"),
        mssql_database=_env("MSSQL_DATABASE", required=True),
        mssql_username=_env("MSSQL_USERNAME", required=True),
        mssql_password=_env("MSSQL_PASSWORD", required=True),
        mssql_encrypt=_env("MSSQL_ENCRYPT", "yes"),
        mssql_trust_server_certificate=_env("MSSQL_TRUST_SERVER_CERTIFICATE", "yes"),
        # ntfy.sh albo własny serwer ntfy
        ntfy_server=_env("NTFY_SERVER", "https://ntfy.sh"),
        ntfy_topic=_env("NTFY_TOPIC", ""),
        ntfy_token=_env("NTFY_TOKEN", ""),
        ntfy_title=_env("NTFY_TITLE", "Nowe zamówienie"),
        ntfy_priority=_env("NTFY_PRIORITY", "default"),
        ntfy_tags=_env("NTFY_TAGS", "package"),
        # Zachowanie
        poll_interval=max(1, int(_env("POLL_INTERVAL", "10") or "10")),
        # Co ile sekund powtarzać powiadomienie na własnym zegarze, dopóki
        # query.sql zwraca wiersz; 0 = wysyłaj raz na POLL_INTERVAL (co poll)
        announce_interval=max(0, int(_env("ANNOUNCE_INTERVAL", "30") or "30")),
        send_text=_flag("SEND_TEXT", "true"),
        mapping_file=_env("USER_MAPPING_FILE", "user_mapping.json"),
        courier_id=_env("COURIER_ID", "13"),
        max_notifications_per_batch=max(1, int(_env("MAX_NOTIFICATIONS_PER_BATCH", "3") or "3")),
    )
