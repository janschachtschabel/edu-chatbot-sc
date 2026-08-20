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

**C1-f2b6a:** ``_apply_state_auto_followup`` folgt der Widget-Sprache. Der Chip
und sein Doublette-Wächter sind dabei EIN Stück: ``"Hat das geholfen?"`` enthält
``"geholfen"`` aus der Stichwortliste. Nur den Chip zu übersetzen hätte die
Idempotenz zerstört — der Wächter hätte die englische Pass-Quality-Frage des
LLM nicht mehr erkannt und eine zweite angehängt.
"""

from __future__ import annotations

from typing import Final

from boerdi.i18n import DEFAULT, Locale, bot_text
from boerdi.services.config_loader import load_display_rules_config

# Stichwörter, an denen der Wächter eine bereits vorhandene Pass-Quality-Frage
# erkennt. Er liest die vom LLM erzeugten Quick-Replies, also UNSERE eigene
# Ausgabe — deren Sprache ist bekannt, deshalb Umschaltung je Sprache und keine
# Vereinigung (Gegenstück: ``safety/regex_gate`` über der Nutzer-Eingabe).
# Reiner Teilzeichenketten-Vergleich, ALT-verbatim: ``"richtig"`` trifft auch
# „Richtig starke Auswahl!". Die englischen Einträge sind nach demselben Muster
# kurz gehalten — sie sollen Wortformen mitnehmen („help" in „helped"/„helpful").
_PASS_QUALITY_KEYWORDS: Final[dict[Locale, tuple[str, ...]]] = {
    "de": ("geholfen", "gepasst", "passt", "passend", "richtig",
           "stimmt", "weiterhilft"),
    "en": ("help", "fit", "right", "correct", "useful", "what you needed"),
}


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


#: Marke der Kontext-Begrüßung im Debug-Label (``CTX:collection``, ``CTX:skipped``).
#: Eine Konstante statt eines Literals an beiden Enden: der Knoten SETZT sie, der
#: Anzeige-Trim LIEST sie. Driften die auseinander, fällt der Deckel wieder auf
#: gepflegte Knöpfe — lautlos, denn nichts wirft dabei.
CONTEXT_GREETING_MARKER: Final[str] = "CTX:"

#: Obergrenze für redaktionell gepflegte Pillen.
#:
#: Sie sind vom Generator-Deckel ausgenommen (:func:`has_curated_quick_replies`)
#: — aber „ausgenommen" darf nicht „unbegrenzt" heißen. Der Pfad klammerte
#: vorher hart auf 6; fiele jede Grenze weg, ergäben 20 gepflegte Einträge auch
#: 20 Knöpfe. Die Leiste bricht sie zwar um (``quick-replies.component.scss``:
#: ``flex-wrap: wrap``) — aber mehrere Umbruchzeilen unter einer Nachricht sind
#: keine Chip-Leiste mehr, sondern ein Menü. 8 lässt die längste heute gepflegte
#: Liste (5) mit Luft durch und fängt einen Pflegefehler ab.
CURATED_QR_MAX: Final[int] = 8


def has_curated_quick_replies(pattern_id: str) -> bool:
    """Sind die Quick-Replies dieser Antwort redaktionell gepflegt statt erzeugt?

    Dann gilt ``display-rules.quick_replies.max_count`` NICHT: dieser Wert ist
    die Zielzahl des QR-Generators (siehe :func:`_qr_default_count`), kein
    Anzeige-Limit. Heute trifft das genau die Kontext-Begrüßung, deren Pillen je
    Seitenart in ``01-base/context-actions`` stehen — von fünf gepflegten
    Knöpfen kamen zwei an (Live-Befund 2026-08-14, Deckel im Seed auf 2).

    Die Webseiten-Tour gehört derselben Klasse an, braucht diese Abfrage aber
    nicht: ihre Antworten tragen ein ``tour``-Feld und verlassen den
    Widget-Postprocess schon in dessen erster Zeile.
    """
    return (pattern_id or "").strip().startswith(CONTEXT_GREETING_MARKER)


def host_qr_max(gewuenscht: int | None, host_chips: list[str] | None) -> int | None:
    """O-B2 (2026-08-20): die vom Gastgeber genannte Chip-Gesamtzahl im
    Mix-Modus — oder ``None``, wenn kein Mix verlangt ist.

    Zwei Bedingungen, beide bewusst: (1) Ohne Zahl bleibt es beim harten
    Überschreiben aus O-B. (2) Ohne EIGENE Chips des Gastgebers ist die Zahl
    keine Aussage — ``max=3`` allein hieße still „kappe den Generator", und
    dafür gibt es schon die Anzeige-Regeln. Geklammert auf 1–6 aus demselben
    Grund wie ``MAX_ERZWUNGENE_CHIPS`` (graph/nodes/assemble.py): darüber
    bricht die Chip-Leiste um. Von assemble (Kaskade) UND widget_postprocess
    (Anzeige-Deckel) benutzt — EINE Semantik, eine Klammer.
    """
    if gewuenscht is None:
        return None
    if not any(isinstance(c, str) and c.strip() for c in (host_chips or [])):
        return None
    return max(1, min(6, gewuenscht))


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
    lang: Locale = DEFAULT,
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
    pass_quality_keywords = _PASS_QUALITY_KEYWORDS.get(
        lang, _PASS_QUALITY_KEYWORDS[DEFAULT])
    for q in qrs:
        q_lower = (q or "").lower()
        if any(kw in q_lower for kw in pass_quality_keywords):
            return qrs  # schon eine Pass-QR drin, nichts tun

    # Nicht überfüllen — wenn der LLM schon 4 QRs hatte, ersetze die letzte.
    auto_qr = bot_text(lang, "qr.passQuality")
    if len(qrs) >= 4:
        qrs[-1] = auto_qr
    else:
        qrs.append(auto_qr)
    return qrs
