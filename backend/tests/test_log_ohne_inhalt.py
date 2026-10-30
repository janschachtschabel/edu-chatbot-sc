"""Paket 18C/D (2.10): Wächter — Logaufrufe tragen keine Inhalte.

Der Kanarienvogel (``test_kanarienvogel_logs.py``) prüft zur Laufzeit, was durch die getesteten
Zugwege läuft; dieser Wächter prüft den ganzen Quelltext, auch Zweige, die kein Test durchläuft.

Geprüft wird jedes Argument eines Logaufrufs (auch ``ereignis(...)``) — ab INFO immer, DEBUG
außerhalb eines ``if … log_content``: Kein Name, dessen letzter Teil nach Inhalt oder Sitzung
klingt (``_user_msg``, ``extra_args``, ``query_tokens``, ``ctx.req.message``, ``_m16_thema`` …),
und kein Inhaltsschlüssel (``x.get("thema")``, ``s["query"]``) darf darin stehen — außer in
einem Helfer, der ihn unkenntlich macht (``inhalt``, ``kennung``, ``len``, ``filterwerte``,
``fehlerorte``). Bis zum Review von Phase 2 verglich der Wächter ganze Ausdrücke; Aliasnamen
und Attributketten liefen durch.

Bewusste Ausnahmen — öffentliche Katalogdaten wie Titel von Materialien und Sammlungen, der Text
einer Ausnahme (Grundlage §1: Fehlermeldungen bleiben), Konfigurationswerte — tragen im Aufruf
den Kommentar ``# log-ok: <Grund>``.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "boerdi"
_STUFEN = {"info", "warning", "warn", "error", "exception", "critical"}
_LOGGER = {"logger", "log", "_logger", "_log", "logging"}
#: Wortstämme, mit denen ein Namensteil beginnt, der Inhalt oder eine Sitzung hält.
STAEMME = (
    "message", "msg", "nachricht", "thema", "topic", "query", "term", "suchbegriff", "slot",
    "entit", "args", "argument", "signatur", "reasoning", "text", "antwort", "response", "prompt",
    "qrs", "quick_repl", "title", "titel", "sitzung",
)
#: Ganze Namensteile (zu kurz für einen Stamm).
GANZE = frozenset({"q", "sig", "sid", "session_id", "search_url"})
#: Schlüssel (``x.get("…")``, ``x["…"]``), die Inhalt halten — genau, nicht als Stamm
#: (``queryType`` ist eine Art, ``missing_slots`` sind Slot-Namen).
SCHLUESSEL = frozenset({
    "thema", "topic", "query", "q", "message", "text", "title", "search_term", "suchbegriff",
    "content", "entities", "reasoning", "tool_reasoning", "session_id",
})
_HELFER = {"inhalt", "kennung", "len", "filterwerte", "fehlerorte"}
_AUSNAHME = "# log-ok:"


def _klingt_nach_inhalt(name: str) -> bool:
    teil = name.lower().strip("_")
    if teil in GANZE or "session_id" in teil:
        return True
    if teil.endswith(("_id", "_ids")):  # ``message_id`` ist eine Kennung
        return False
    return any(t in GANZE or t.startswith(STAEMME) for t in teil.split("_") if t)


def _schluessel(knoten: ast.AST) -> bool:
    return isinstance(knoten, ast.Constant) and knoten.value in SCHLUESSEL


def _verboten(knoten: ast.AST) -> list[str]:
    if isinstance(knoten, ast.Call):
        f = knoten.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name in _HELFER:
            return []
        if name == "get" and knoten.args and _schluessel(knoten.args[0]):
            return [ast.unparse(knoten)]
    if isinstance(knoten, ast.Subscript) and _schluessel(knoten.slice):
        return [ast.unparse(knoten)]
    if isinstance(knoten, ast.Name) and _klingt_nach_inhalt(knoten.id):
        return [knoten.id]
    if isinstance(knoten, ast.Attribute) and _klingt_nach_inhalt(knoten.attr):
        return [ast.unparse(knoten)]
    funde: list[str] = []
    for kind in ast.iter_child_nodes(knoten):
        funde += _verboten(kind)
    return funde


def _ist_debug(stufe: ast.AST) -> bool:
    if isinstance(stufe, ast.IfExp):
        return _ist_debug(stufe.body) and _ist_debug(stufe.orelse)
    return ast.unparse(stufe).endswith("DEBUG")


class _Sammler(ast.NodeVisitor):
    """Logaufrufe mit ihren zu prüfenden Argumenten; DEBUG nur außerhalb ``if … log_content``."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[ast.Call, list[ast.AST]]] = []
        self._geschuetzt = 0

    def visit_If(self, knoten: ast.If) -> None:
        schutz = "log_content" in ast.unparse(knoten.test)
        self._geschuetzt += schutz
        for kind in knoten.body:
            self.visit(kind)
        self._geschuetzt -= schutz
        for kind in knoten.orelse:
            self.visit(kind)

    def visit_Call(self, knoten: ast.Call) -> None:
        f = knoten.func
        werte = [k.value for k in knoten.keywords if k.arg not in ("exc_info", "stack_info")]
        if isinstance(f, ast.Name) and f.id == "ereignis":
            stufe = next((k.value for k in knoten.keywords if k.arg == "stufe"), None)
            if not (stufe is not None and _ist_debug(stufe) and self._geschuetzt):
                self.aufrufe.append((knoten, [*knoten.args[2:], *werte]))
        elif isinstance(f, ast.Name) and f.id == "gedrosselt":
            # Paket 18E: ``gedrosselt(logger, stufe, schluessel, abstand_s, text, *args)`` —
            # geprüft wird, was ins Log geht (Vorlage und Werte), an jedem Aufruf.
            self.aufrufe.append((knoten, [*knoten.args[4:], *werte]))
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                and f.value.id in _LOGGER:
            if f.attr in _STUFEN:
                self.aufrufe.append((knoten, [*knoten.args, *werte]))
            elif f.attr == "debug" and not self._geschuetzt:
                self.aufrufe.append((knoten, [*knoten.args, *werte]))
            elif f.attr == "log" and knoten.args and not (
                    _ist_debug(knoten.args[0]) and self._geschuetzt):
                self.aufrufe.append((knoten, [*knoten.args[1:], *werte]))
        self.generic_visit(knoten)


def _logaufrufe(baum: ast.AST) -> list[tuple[ast.Call, list[ast.AST]]]:
    sammler = _Sammler()
    sammler.visit(baum)
    return sammler.aufrufe


def _funde() -> list[str]:
    funde = []
    for datei in sorted(_SRC.rglob("*.py")):
        quelle = datei.read_text(encoding="utf-8")
        zeilen = quelle.splitlines()
        for aufruf, argumente in _logaufrufe(ast.parse(quelle)):
            namen = [n for a in argumente for n in _verboten(a)]
            if not namen:
                continue
            bereich = zeilen[aufruf.lineno - 1:(aufruf.end_lineno or aufruf.lineno)]
            if any(_AUSNAHME in z for z in bereich):
                continue
            rel = datei.relative_to(_SRC).as_posix()
            funde.append(f"{rel}:{aufruf.lineno} {sorted(set(namen))}")
    return funde


def test_logaufrufe_tragen_keine_inhalte():
    funde = _funde()
    assert not funde, f"{len(funde)} Logaufrufe mit Inhalt:\n" + "\n".join(funde)


def test_der_waechter_erkennt_aliase_ketten_und_schluessel():
    baum = ast.parse(
        "logger.info('a %s', ctx.req.message[:80])\n"
        "logger.info('b %s', _user_msg)\n"
        "logger.info('c %s', extra_args)\n"
        "logger.info('d %s', state.get('thema'))\n"
        "logger.info('e %s', s['query'])\n"
        "log.log(logging.INFO if x else logging.DEBUG, 'f %s', query_tokens)\n"
        "ereignis(log, 'g', wert=signature)\n"
        "logger.debug('h %s', req.session_id)\n"
        "gedrosselt(logger, logging.WARNING, 'k', 60, 'i %s', response_text)\n"
    )
    gefunden = [n for aufruf, args in _logaufrufe(baum) for a in args for n in _verboten(a)]
    assert gefunden == ["ctx.req.message", "_user_msg", "extra_args", "state.get('thema')",
                        "s['query']", "query_tokens", "signature", "req.session_id",
                        "response_text"]


def test_der_waechter_laesst_helfer_kennungen_und_geschuetztes_debug_durch():
    baum = ast.parse(
        "logger.info('x %s %s %d', inhalt(req.message), kennung(session_id), len(args))\n"
        "if get_settings().log_content:\n"
        "    logger.debug('y %s', arguments)\n"
        "logger.info('z %s %s %s', tool_name, type(err).__name__, message_id)\n"
        "logger.info('w %s', meta.get('queryType'))\n"
    )
    assert [n for aufruf, args in _logaufrufe(baum) for a in args for n in _verboten(a)] == []
