"""UI-Module im Gold-Runner (Paket U1-g) — aus ``run_golden.py`` ausgelagert (Review U1 gesamt,
Befund 8).

Was der Lauf an den UI-Blöcken einer Antwort abliest: die Dokument-Boxen, die gezeigten Module,
die offene Frage (und ob eine abfragende Anzeige offen ist), die Antwort im Auswahlfeld und die
Textfassungen für den Bericht. Framework-frei wie ``run_golden.py`` (nur Standardbibliothek):
``run_golden.py`` lädt diese Datei über ihren Pfad, wie ``compare_golden.py`` den Runner lädt —
beide liegen nebeneinander, im Image unter ``/app/evals/``.

Zwilling im Backend: ``services/eval/runner.py`` trägt ``_dokument_boxen``, ``_gezeigte_module``
und die Textfassungs-Regel selbst — ein normales Paket-Modul, das keine Datei außerhalb des
Pakets braucht (``services/eval/golden_run._runner_path``). Der Wächter
``tests/test_eval_ui_module.py`` vergleicht beide an denselben Antworten.
"""

from __future__ import annotations

import re
from typing import Any

#: Module, deren Inhalt ``augment_bot_text`` schon zeigt (Dokument-Box, Karten) — ihre
#: Textfassung käme doppelt (U1-g, G-5).
SCHON_GEZEIGT = frozenset({"ui_inhaltsrahmen", "ui_trefferliste"})
#: ``ui_module/namen.ENTSCHEIDUNG`` — hier als Text, die Datei bleibt ohne ``boerdi.*``; ein
#: Wächter hält beide gleich.
ENTSCHEIDUNG = "ui_entscheidung"
#: Paket U2: der Strukturentwurf — ``ui_antwort: {uebernehmen: true}`` übernimmt ihn.
STRUKTURENTWURF = "ui_strukturentwurf"
TEXTFASSUNG_MAX = 1500
#: ``maxLength`` des Freitexts im Antwort-Schema von ``ui_entscheidung`` — das Widget kürzt
#: darauf (``FREITEXT_MAX`` im Modul), der Runner auch; ein Test hält beide am Manifest.
FREITEXT_MAX = 1000


def normalisiert(text: str) -> str:
    """Case- and whitespace-blind: models put no-break spaces into phone numbers."""
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def dokument_boxen(bot_resp: dict[str, Any]) -> list[dict[str, str]]:
    """Every document box the person saw, as ``{kind, title, content}``.

    Since U1-b2 boxes arrive as ``ui_inhaltsrahmen`` blocks in ``ui.ui_bloecke``; the old
    ``inline_documents`` field is still read so a run against an older backend counts too.
    """
    boxen: list[dict[str, str]] = []
    for doc in bot_resp.get("inline_documents") or []:
        if isinstance(doc, dict):
            boxen.append({"kind": str(doc.get("kind") or ""), "title": str(doc.get("title") or ""),
                          "content": str(doc.get("content") or "")})
    for block in (bot_resp.get("ui") or {}).get("ui_bloecke") or []:
        if isinstance(block, dict) and block.get("modul") == "ui_inhaltsrahmen":
            daten = block.get("daten") or {}
            boxen.append({"kind": str(daten.get("art") or ""),
                          "title": str(daten.get("titel") or ""),
                          "content": str(daten.get("markdown") or "")})
    return boxen


def ui_bloecke(bot_resp: dict[str, Any]) -> list[dict[str, Any]]:
    """The UI blocks of an answer (``ui.ui_bloecke``), dicts only."""
    return [b for b in (bot_resp.get("ui") or {}).get("ui_bloecke") or [] if isinstance(b, dict)]


def gezeigte_module(bot_resp: dict[str, Any]) -> list[str]:
    """The modules the person saw in this answer, once each, in display order (U1-g, G-3/G-6)."""
    return list(dict.fromkeys(str(b.get("modul") or "") for b in ui_bloecke(bot_resp)
                              if b.get("modul")))


def offene_frage(bot_resp: dict[str, Any]) -> dict[str, Any] | None:
    """The open ``ui_entscheidung`` block of an answer — the question the next turn may answer
    in its choice box (U1-g, G-4). A stored block without status counts as open, like
    ``UiBlock``'s default for an asking module."""
    for block in reversed(ui_bloecke(bot_resp)):
        if (block.get("modul") == ENTSCHEIDUNG and block.get("art") == "abfragen"
                and block.get("status") in (None, "offen")):
            return block
    return None


def offener_entwurf(bot_resp: dict[str, Any]) -> dict[str, Any] | None:
    """The open ``ui_strukturentwurf`` block of an answer (U2) — like :func:`offene_frage`."""
    for block in reversed(ui_bloecke(bot_resp)):
        if (block.get("modul") == STRUKTURENTWURF and block.get("art") == "abfragen"
                and block.get("status") in (None, "offen")):
            return block
    return None


def _punkte(knoten: Any) -> int:
    return sum(1 + _punkte(k.get("kinder")) for k in knoten or [] if isinstance(k, dict))


def baue_entwurf_antwort(
    entwurf: dict[str, Any] | None, getippt: str,
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """``(ui_antwort, message, observed)`` for a turn that accepts the open draft unchanged —
    the widget's "Übernehmen" (U2): ``uebernommen: true``, ``bearbeitet: false`` and the
    widget's German sentence. No open draft → ``getippt`` goes as typed text."""
    if entwurf is None:
        return None, getippt, {"status": "kein_entwurf"}
    daten = dict(entwurf.get("daten") or {})
    text = (f"Entwurf „{daten.get('titel') or ''}“ übernommen "
            f"({_punkte(daten.get('knoten'))} Punkte).")
    return ({"block_id": str(entwurf.get("block_id") or ""),
             "daten": {**daten, "uebernommen": True, "bearbeitet": False}}, text,
            {"status": "gesendet", "uebernommen": True})


def baue_ui_antwort(
    spec: dict[str, Any], frage: dict[str, Any] | None, getippt: str,
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """``(ui_antwort, message, observed)`` for a turn that answers in the choice box (G-4).

    Options are chosen by label, not by id — the model picks the ids during the run. Each
    phrase of ``waehle`` hits an option in three tiers (:func:`_trefferstufe`): the exact label
    (case-blind) or id, then the phrase as whole words of the label, then — last resort — as
    part of a word. Only a phrase's best tier counts: "Physik" takes "Physik", not
    "Astrophysik" (review U1-g #1). Single choice: the best tier any phrase reaches; among
    phrases on it the first (the author's preference), its first option in block order.
    Multiple choice: per phrase its best-tier options, in block order. ``freitext`` only if the
    block offers it, cut to ``FREITEXT_MAX`` like the widget (``observed.freitext_gekuerzt``
    holds the original length).
    ``message`` is the readable form the widget sends (labels joined by ", ", the addition on
    its own line). No open question or no matching option → ``getippt`` goes as typed text, as
    a person would answer; the server frames the closed question for the model.
    ``observed.status`` ``gesendet`` says the answer went out — whether the server took it, the
    response does not show (a mismatching one is dropped with a log line only, review U1-g #3).
    """
    if frage is None:
        return None, getippt, {"status": "keine_frage", "gewaehlt": []}
    daten = frage.get("daten") or {}
    optionen = [o for o in daten.get("optionen") or [] if isinstance(o, dict)]

    # Je Wendung ihre beste Stufe und die Möglichkeiten darauf (Block-Reihenfolge).
    beste: list[tuple[int, list[int]]] = []
    for wendung in spec.get("waehle") or []:
        stufen = [_trefferstufe(o, wendung) for o in optionen]
        if treffer := [s for s in stufen if s is not None]:
            stufe = min(treffer)
            beste.append((stufe, [i for i, s in enumerate(stufen) if s == stufe]))
    if not beste:
        return None, getippt, {"status": "keine_passende_option", "gewaehlt": []}
    if daten.get("mehrfach") is True:
        gewaehlt = [optionen[i] for i in sorted({i for _, liste in beste for i in liste})]
    else:  # Einzelwahl: beste Stufe, dann die Reihenfolge des Autors (``min`` ist stabil)
        gewaehlt = [optionen[min(beste, key=lambda b: b[0])[1][0]]]
    antwort_daten: dict[str, Any] = {"gewaehlt": [str(o["id"]) for o in gewaehlt]}
    labels = [str(o.get("label") or "") for o in gewaehlt]
    beobachtet: dict[str, Any] = {"status": "gesendet", "gewaehlt": labels}
    zusatz = str(spec.get("freitext") or "").strip() if daten.get("freitext") is True else ""
    if len(zusatz) > FREITEXT_MAX:
        beobachtet["freitext_gekuerzt"] = len(zusatz)
        zusatz = zusatz[:FREITEXT_MAX]
    if zusatz:
        antwort_daten["freitext"] = zusatz
    text = "\n".join(t for t in (", ".join(labels), zusatz) if t)
    return ({"block_id": str(frage.get("block_id") or ""), "daten": antwort_daten}, text,
            beobachtet)


def _trefferstufe(option: dict[str, Any], wendung: str) -> int | None:
    """0 = exact label or id, 1 = whole words of the label, 2 = part of a word, ``None`` = no
    hit. Case- and whitespace-blind like the text checks (:func:`normalisiert`)."""
    w = normalisiert(wendung)
    if not w:
        return None
    label = normalisiert(str(option.get("label") or ""))
    if label == w or w == str(option.get("id")):
        return 0
    if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", label):
        return 1
    return 2 if w in label else None


def zeigt_offene_abfrage(bot_resp: dict[str, Any]) -> bool:
    """Steht in der Antwort ein offener abfragender Block (eine Frage mit Auswahlfeld)? Darunter
    gibt es absichtlich keine Schnellantworten — ein Klick darauf machte die Frage veraltet
    (Review U1 gesamt, Befund 12)."""
    return any(b.get("art") == "abfragen" and b.get("status") in (None, "offen")
               for b in ui_bloecke(bot_resp))


def mit_textfassungen(bot_text: str, bot_resp: dict[str, Any]) -> str:
    """Hängt die Textfassung jedes Blocks an, den der Leser sonst nicht sähe — die Frage samt
    Möglichkeiten, den Themenbaum (U1-g, G-5); Dokument-Box und Trefferliste zeigt
    ``augment_bot_text`` schon."""
    for block in ui_bloecke(bot_resp):
        text = str(block.get("text") or "").strip()
        if text and block.get("modul") not in SCHON_GEZEIGT:
            bot_text = ((bot_text or "").rstrip() + f"\n\n---\n[UI-Modul {block.get('modul')}"
                        " — vom Nutzer sichtbar]\n\n" + text[:TEXTFASSUNG_MAX])
    return bot_text
