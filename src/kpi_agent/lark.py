from __future__ import annotations

import requests


def send_text(webhook: str, text: str, timeout: int = 10) -> tuple[bool, str]:
    payload = {"msg_type": "text", "content": {"text": text}}
    try:
        res = requests.post(webhook, json=payload, timeout=timeout)
        ok = 200 <= res.status_code < 300
        return ok, f"status={res.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
