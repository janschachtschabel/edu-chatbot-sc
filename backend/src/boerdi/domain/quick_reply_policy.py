"""Pure quick-reply policy helpers (P4-4-Tail-QR, port of ALT
chat_quick_replies.py's four framework-free functions): the per-pattern QR
policy (``_qr_policy``), the global QR target count from the Studio display
rules (``_qr_default_count``), the anticipation block for speculative QRs
(``_spec_qr_response_block``) and the deterministic S3 auto-followup
(``_apply_state_auto_followup``).

Framework-free (stdlib + config_loader read-facades) → ``domain/``. Consumed by
the route tail's QR-policy step, the LP-fast-path's M09 speculative-QR start and
the QR post-processing phase (all P4-5). Verbatim 1:1 from ALT with two surgical
deviations: ``_qr_policy``'s lazy config_loader import path, and
``_qr_default_count`` calling the ``load_display_rules_config`` read-facade
directly instead of ALT's ``chat_widget_modes._display_rules`` wrapper — that
wrapper is only ``load_display_rules_config() or {}`` plus a fallback whose
``quick_replies.max_count`` is 4, i.e. identical to this function's own
``except -> 4``. The guide-QR helpers (``_strip_guide_qrs`` / ``_attach_guide_qr``)
live elsewhere and stay deferred.
"""

from __future__ import annotations

from boerdi.services.config_loader import load_display_rules_config


def _qr_policy(pattern_id: str) -> tuple[str, int | None]:
    """QR-Policy ``(mode, max)`` eines Patterns aus den Pattern-MDs
    (Studio-steuerbar, 2026-06-10).

    mode: ``exact`` (QR-Call nach der Antwort, heutiges Verhalten) |
    ``speculative`` (parallel zum Antwort-LLM, Konsistenz-Gate +
    exact-Fallback) | ``none`` (kein Generator-Call, kein Auto-Followup —
    deterministische System-QRs wie Slot-Optionen/Tour/Lotse bleiben).
    max: 1–6 oder None (= globaler display-rules-Wert beim Anzeige-Trim).

    Akzeptiert auch Debug-Labels wie ``"M09 (Lernpfad)"`` (nimmt das
    erste Token); unbekannte IDs → Default. Loader ist mtime-gecacht.
    """
    pid = (pattern_id or "").split(" ")[0].strip()
    if pid:
        try:
            from boerdi.services.config_loader import load_pattern_definitions
            for p in load_pattern_definitions():
                if p.get("id") == pid:
                    mode = str(p.get("quick_replies_mode") or "exact").strip().lower()
                    if mode not in ("exact", "speculative", "none"):
                        mode = "exact"
                    qmax = None
                    raw_max = p.get("quick_replies_max")
                    if raw_max is not None:
                        try:
                            qmax = max(1, min(6, int(raw_max)))
                        except (TypeError, ValueError):
                            qmax = None
                    return mode, qmax
        except Exception:  # pragma: no cover — Policy darf nie einen Turn killen
            pass
    return "exact", None


def _qr_default_count() -> int:
    """Globale QR-Zielzahl aus ``display-rules.quick_replies.max_count``
    (Studio: Anzeige → Quick-Replies). Seit 2026-06-10 erzeugt der
    Generator direkt diese Anzahl, statt 4 zu generieren und auf den
    Deckel zu trimmen (Token-Ersparnis + konsistenter Prompt).
    ``0`` = global keine generierten QRs (Aufrufer überspringt den Call).
    Pattern-``quick_replies_max`` überschreibt diesen Wert.
    """
    try:
        raw = (((load_display_rules_config() or {}).get("quick_replies") or {})
               .get("max_count", 4))
        # Explizites ``max_count: null`` (oder fehlender Key) → Default 4;
        # nur ein bewusstes ``max_count: 0`` schaltet QRs global aus.
        if raw is None:
            raw = 4
        return max(0, min(6, int(raw)))
    except Exception:  # pragma: no cover
        return 4


def _spec_qr_response_block(
    pattern_id: str, short_purpose: str, titles: list[str],
) -> str:
    """Antizipations-Block für spekulative QRs (QR-Policy speculative).

    Ersetzt den ``Bot-Antwort:``-Inhalt im QR-Prompt, wenn der QR-Call
    parallel zum Antwort-LLM läuft: bekannt sind dann Pattern (mit
    ``short_purpose`` aus der Pattern-Config als Form-Beschreibung),
    Entities (via classification im Prompt-Kontext) und die bereits
    gegateten Prefetch-Treffer — nicht aber der Antworttext.
    """
    lines = [
        "(Die Bot-Antwort wird gerade parallel generiert — sie liegt noch "
        "nicht vor. Stütze die Vorschläge auf die folgenden Fakten:)",
        f"Gewähltes Antwort-Pattern: {pattern_id}"
        + (f" — {short_purpose}" if short_purpose else ""),
    ]
    clean_titles = [t for t in (titles or []) if (t or "").strip()][:5]
    if clean_titles:
        lines.append("Treffer, die unter der Antwort angezeigt werden:")
        lines.extend(f"- {t}" for t in clean_titles)
    else:
        lines.append("Es sind vorab keine Treffer-Karten bekannt.")
    return "\n".join(lines)


def _apply_state_auto_followup(
    *,
    state_id: str,
    quick_replies: list[str],
    has_cards: bool,
) -> list[str]:
    """Append phase-specific Auto-Followups deterministically (Welle C Sprint 6).

    Nur S3 (Ergebnis-Kuratierung) hat aktuell einen harten Trigger —
    nach Ergebnis-Lieferung soll der Bot proaktiv nach Pass-Quality fragen.
    Andere Phasen verlassen sich auf den LLM-Quick-Reply-Generator
    (der über die bot_directive aus states.yaml gesteuert wird).

    Idempotent: wenn die LLM-generierten QRs schon eine "Hat das geholfen?"-
    artige Frage enthalten, wird nichts dazugepackt.
    """
    if state_id != "S3" or not has_cards:
        return quick_replies

    qrs = list(quick_replies) if quick_replies else []
    # Doublette-Schutz: hat der LLM schon eine Pass-Quality-Frage?
    pass_quality_keywords = (
        "geholfen", "gepasst", "passt", "passend", "richtig",
        "stimmt", "weiterhilft",
    )
    for q in qrs:
        q_lower = (q or "").lower()
        if any(kw in q_lower for kw in pass_quality_keywords):
            return qrs  # schon eine Pass-QR drin, nichts tun

    # Nicht überfüllen — wenn der LLM schon 4 QRs hatte, ersetze die letzte.
    auto_qr = "Hat das geholfen?"
    if len(qrs) >= 4:
        qrs[-1] = auto_qr
    else:
        qrs.append(auto_qr)
    return qrs
