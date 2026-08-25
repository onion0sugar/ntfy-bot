"""Klient publikujący powiadomienia tekstowe do ntfy/ntfy.sh."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from urllib import error, request

logger = logging.getLogger("ntfy")


class NtfyError(Exception):
    """Błąd publikacji lub konfiguracji ntfy."""


def _publish_sync(cfg: SimpleNamespace, message: str) -> None:
    url = f"{(cfg.ntfy_server or 'https://ntfy.sh').rstrip('/')}/{cfg.ntfy_topic.lstrip('/')}"
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Title": cfg.ntfy_title,
        "Priority": cfg.ntfy_priority,
    }
    if cfg.ntfy_tags:
        headers["Tags"] = cfg.ntfy_tags
    if cfg.ntfy_token:
        headers["Authorization"] = f"Bearer {cfg.ntfy_token}"
    req = request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise NtfyError(f"ntfy returned HTTP {response.status}")
            response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise NtfyError(f"ntfy returned HTTP {exc.code}: {detail}") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise NtfyError(f"ntfy connection failed: {exc}") from exc


class Ntfy:
    """Asynchroniczny interfejs publikacji do jednego topicu ntfy."""

    def __init__(self, cfg: SimpleNamespace):
        if getattr(cfg, "ntfy_topic", "") and any(ch.isspace() for ch in cfg.ntfy_topic):
            raise NtfyError("NTFY_TOPIC nie może zawierać spacji")
        self._cfg = cfg

    async def publish_to(self, topic: str, message: str, title: str | None = None) -> None:
        cfg = SimpleNamespace(**vars(self._cfg))
        cfg.ntfy_topic = topic
        if title:
            cfg.ntfy_title = title
        await asyncio.to_thread(_publish_sync, cfg, message)
        logger.info("Notification sent to ntfy topic %s", topic)

    async def publish(self, message: str) -> None:
        await self.publish_to(self._cfg.ntfy_topic, message)

    async def close(self) -> None:
        """Zachowaj jednolity cykl życia adaptera z innymi kanałami."""
        return None
