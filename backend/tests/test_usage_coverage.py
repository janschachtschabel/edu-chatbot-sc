"""K1f — Wächter: jede ``chat_completion``-Aufrufstelle bucht ihre Token.

Warum ein Wächter und kein einmaliges Aufräumen: die Kostenmessung dieses
Plans hat **vier Mal hintereinander** zu niedrig gezählt (siehe
``docs/plans/2026-08-11-kostenueberwachung.md``, §2.3 und die K1b–K1e-Belege).
Prosa-Listen und ``grep``-Zählungen sind untere Schranken; eine AST-Aufzählung
ist es nicht. Ohne diesen Test fällt das nächste neue Modul wieder still aus
der Erfassung — und eine Kostenzahl, der etwas fehlt, sieht genauso richtig aus
wie eine vollständige.

**Der Wächter hat sich sofort bezahlt gemacht:** beim ersten Lauf fand er
``_max_iterations_fallback`` (``services/tool_loop.py``) — ein echter
LLM-Aufruf im Antwortpfad, der die GANZE Nachrichtenkette anhängt und in
keiner der fünf geplanten Stellen stand. Er bucht seither unter
``fallback_summary``.

Vorbild für die Ausnahmeliste: ``BEWUSST_EINSPRACHIG`` in
``tests/test_i18n_messages.py`` — eine Ausnahme ist erlaubt, aber sie muss
**benannt und begründet** sein, und sie darf nicht verrotten: der Test prüft
beide Richtungen, also auch, dass jeder Eintrag noch gebraucht wird.

Nicht abgedeckt und bewusst so: ``llm.embedding`` (Nutzer-Entscheid, außerhalb
dieses Plans, siehe M5) und der rohe Transport ``llm._acompletion``. Letzterer
hat außerhalb von ``llm.py`` genau **einen** Aufrufer — ``_stream_completion``
(``services/llm_streaming.py``), und dessen einziger Nutzer ist der Tool-Loop,
der beide Zweige mit derselben Hand bucht (``tool_loop.py``, direkt hinter dem
Aufruf). Der Streaming-Zweig ist also erfasst, ohne dass dieser Wächter ihn
sieht.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "boerdi"

# Aufrufstellen, die bewusst KEIN ``usage_acc`` führen. Schlüssel ist
# ``<pfad>::<funktion>``, Wert die Begründung. Neue Einträge brauchen einen
# Grund, der erklärt, warum die Token hier nicht in die Kostenschau gehören
# ODER auf anderem Weg dorthin kommen.
OHNE_BUCHUNG: dict[str, str] = {
    "services/eval/judge.py::judge_turn":
        "Evals sind laut Plan §4 nicht im Erfassungsumfang — sie laufen auf "
        "Knopfdruck der Redaktion, nicht im Zug einer Person, und haben mit "
        "'Token je Sitzung' nichts zu tun.",
    "services/eval/runner.py::simulate_conversation":
        "Eval-Lauf (beide Aufrufe dieser Funktion), siehe judge.py — außerhalb "
        "des Umfangs (Plan §4).",
    "services/eval/scenario_gen.py::generate_scenarios":
        "Eval-Szenariengenerator, außerhalb des Umfangs (Plan §4).",
    "services/tool_loop.py::_run_tool_loop":
        "Bucht SELBST, direkt hinter dem Aufruf — und muss das auch: das "
        "Phasen-Etikett ('tool_loop' vs. 'response') folgt erst aus "
        "``finish_reason``/``tool_calls`` der Antwort, ist vor dem Aufruf also "
        "unbekannt. Derselbe Block bucht auch den Streaming-Zweig.",
}


def _find_call_sites(source: str, rel_path: str) -> list[tuple[str, bool, int]]:
    """Alle ``chat_completion``-Aufrufe einer Quelldatei aufzählen.

    Liefert ``(schlüssel, führt_usage_acc, zeile)``. Der Schlüssel ist
    ``<pfad>::<umschließende funktion>`` — stabil gegen Zeilenverschiebungen,
    anders als eine Zeilennummer. Auf Modulebene steht ``<module>``.
    """
    out: list[tuple[str, bool, int]] = []
    stack: list[str] = []

    class _Visitor(ast.NodeVisitor):
        def _funktion(self, node) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_FunctionDef = _funktion
        visit_AsyncFunctionDef = _funktion

        def visit_Call(self, node: ast.Call) -> None:
            f = node.func
            name = (
                f.attr if isinstance(f, ast.Attribute)
                else f.id if isinstance(f, ast.Name)
                else ""
            )
            if name == "chat_completion":
                key = f"{rel_path}::{stack[-1] if stack else '<module>'}"
                hat = any(k.arg == "usage_acc" for k in node.keywords if k.arg)
                out.append((key, hat, node.lineno))
            self.generic_visit(node)

    _Visitor().visit(ast.parse(source))
    return out


def _alle_aufrufstellen() -> list[tuple[str, bool, int]]:
    treffer: list[tuple[str, bool, int]] = []
    for pfad in sorted(_SRC.rglob("*.py")):
        rel = pfad.relative_to(_SRC).as_posix()
        treffer.extend(_find_call_sites(pfad.read_text(encoding="utf-8"), rel))
    return treffer


# ── Der Wächter ─────────────────────────────────────────────────────────

def test_jede_chat_completion_bucht_oder_steht_begruendet_in_der_liste() -> None:
    ungebucht = {key for key, hat, _ in _alle_aufrufstellen() if not hat}
    neu = ungebucht - set(OHNE_BUCHUNG)
    assert not neu, (
        "Neue chat_completion-Aufrufstelle ohne usage_acc — ihre Token fehlen "
        f"still in jeder Kostenzahl: {sorted(neu)}. Entweder ``usage_acc`` "
        "durchreichen oder mit Begründung in OHNE_BUCHUNG aufnehmen."
    )


def test_ausnahmeliste_verrottet_nicht() -> None:
    # Die Gegenrichtung: ein Eintrag, der nicht mehr gebraucht wird, macht die
    # Liste unglaubwürdig — dann glaubt man beim nächsten Mal auch den anderen
    # nicht mehr.
    ungebucht = {key for key, hat, _ in _alle_aufrufstellen() if not hat}
    tot = set(OHNE_BUCHUNG) - ungebucht
    assert not tot, (
        f"Ausnahme steht in OHNE_BUCHUNG, wird aber nicht mehr gebraucht: "
        f"{sorted(tot)} — Eintrag entfernen."
    )


def test_jede_ausnahme_hat_eine_begruendung() -> None:
    duenn = {k: v for k, v in OHNE_BUCHUNG.items() if len(v.strip()) < 30}
    assert not duenn, f"Ausnahme ohne tragfähige Begründung: {sorted(duenn)}"


# ── Der Wächter selbst, gegen Fälschung geprüft ─────────────────────────
# Ein Wächter, der nie anschlägt, ist keiner. Diese drei Tests fahren den
# Aufzähler gegen erfundene Quelltexte, damit belegt ist, dass er den
# Unterschied überhaupt sehen kann.

def test_aufzaehler_erkennt_fehlendes_usage_acc() -> None:
    quelle = (
        "async def f():\n"
        "    return await llm.chat_completion(messages=[], temperature=0)\n"
    )
    assert _find_call_sites(quelle, "x.py") == [("x.py::f", False, 2)]


def test_aufzaehler_erkennt_vorhandenes_usage_acc() -> None:
    quelle = (
        "async def f():\n"
        "    return await chat_completion(messages=[], usage_acc=acc, phase='p')\n"
    )
    assert _find_call_sites(quelle, "x.py") == [("x.py::f", True, 2)]


def test_aufzaehler_nimmt_die_innerste_funktion_und_ignoriert_fremde_aufrufe() -> None:
    quelle = (
        "async def aussen():\n"
        "    async def innen():\n"
        "        await llm.chat_completion(messages=[])\n"
        "    await llm.embedding('x')\n"
        "    await other.chat_completion_lookalike(messages=[])\n"
    )
    assert _find_call_sites(quelle, "y.py") == [("y.py::innen", False, 3)]


def test_es_gibt_ueberhaupt_aufrufstellen() -> None:
    # Schutz gegen den stillen Totalausfall: ein kaputter Pfad oder ein
    # umbenanntes Paket würde sonst eine leere Menge liefern, und der Wächter
    # wäre grün, ohne irgendetwas geprüft zu haben.
    alle = _alle_aufrufstellen()
    assert len(alle) >= 10, f"Nur {len(alle)} Aufrufstellen gefunden — Pfad kaputt?"
    assert any(hat for _, hat, _ in alle)
