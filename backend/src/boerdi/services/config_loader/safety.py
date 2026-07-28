"""Safety/Policy/Privacy/Guide-Mode/Quality-Log loaders — port of ALT
config_loader/safety.py (defaults + normalizations 1:1).
"""

from __future__ import annotations

import re
from typing import Any

from boerdi.services.config_loader._store import area
from boerdi.services.config_loader.repo_and_cards import get_repo_base_url
from boerdi.settings import get_settings


def load_policy_config() -> dict[str, Any]:
    return area("01-base/policy")


def load_safety_config() -> dict[str, Any]:
    return area("01-base/safety-config")


def load_quality_log_config() -> dict[str, Any]:
    return area("01-base/quality-log-config")


def load_guide_mode_config() -> dict[str, Any]:
    cfg = area("01-base/guide-mode").get("guide_mode") or {}
    # 0 honoured as "unlimited" — only missing/non-int falls back to 5 (ALT)
    raw_max = cfg.get("max_guide_targets_per_turn")
    if raw_max is None:
        max_targets = 5
    else:
        try:
            max_targets = int(raw_max)
        except (TypeError, ValueError):
            max_targets = 5

    raw_qr = cfg.get("max_guide_quick_replies")
    if raw_qr is None:
        max_guide_qrs = 2
    else:
        try:
            max_guide_qrs = int(raw_qr)
        except (TypeError, ValueError):
            max_guide_qrs = 2
    max_guide_qrs = max(1, min(3, max_guide_qrs))

    # env override replaces YAML entirely (per-deployment allow-lists)
    env_td = (get_settings().guide_trusted_domains or "").strip()
    td_raw = re.split(r"[,\s]+", env_td) if env_td else list(cfg.get("trusted_domains") or [])
    trusted_domains: list[str] = []
    for d in td_raw:
        s = str(d or "").strip()
        if not s:
            continue
        s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE).strip("/").lower()
        if s and s not in trusted_domains:
            trusted_domains.append(s)

    return {
        "default_enabled": bool(cfg.get("default_enabled", True)),
        "allowed_hosts": [
            str(h).strip().lower() for h in (cfg.get("allowed_hosts") or []) if str(h).strip()
        ],
        "url_fields_priority": list(cfg.get("url_fields_priority") or [
            "topic_page_url", "wlo_url", "url", "content_url", "preview_url",
        ]),
        "max_guide_targets_per_turn": max_targets,
        "max_guide_quick_replies": max_guide_qrs,
        "trusted_domains": trusted_domains,
        "repo_base_url": get_repo_base_url(),
    }


def load_privacy_config() -> dict[str, bool]:
    section = (area("01-base/privacy-config").get("logging")) or {}
    return {
        "messages": bool(section.get("messages", True)),
        "memory": bool(section.get("memory", True)),
        "quality": bool(section.get("quality", True)),
        "safety": True,  # not user-togglable — audit trail can't be silenced
    }
