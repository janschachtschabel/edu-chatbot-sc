"""Paket 18C/D (2.10): Wächter — Logaufrufe tragen keine Inhalte.

Der Kanarienvogel (``test_kanarienvogel_logs.py``) prüft zur Laufzeit, was durch die getesteten
Zugwege läuft; dieser Wächter prüft den ganzen Quelltext, auch Zweige, die kein Test durchläuft.

Geprüft wird jedes Argument eines Logaufrufs (auch ``ereignis(...)``) — ab INFO immer, DEBUG
außerhalb eines ``if … log_content``: Kein Name, dessen letzter Teil nach Inhalt oder Sitzung
klingt (``_user_msg``, ``extra_args``, ``query_tokens``, ``ctx.req.message``, ``_m16_thema`` …),
und kein Inhaltsschlüssel (``x.get("thema")``, ``s["query"]``) darf darin stehen — außer in
einem Helfer, der ihn unkenntlich macht (``inhalt``, ``kennung``, ``len``, ``filterwerte``,
``fehlerorte``). Bis zum Review von Phase 2 verglich der Wächter ganze Ausdrücke; Aliasnamen
und Attributketten liefen durch. Seit dem Review vom 2026-10-30 zählt ``if not … log_content``
nicht als Schutz, camelCase-Namen werden zerlegt, Logger-Ketten (``self.logger``,
``logging.getLogger(…)``) und ``fatal`` zählen, und ein Helfer gilt nur als Name, nicht als
beliebige Methode gleichen Namens (``foo.len(query)``).

Bewusste Ausnahmen — öffentliche Katalogdaten wie Titel von Materialien und Sammlungen, der Text
einer Ausnahme (Grundlage §1: Fehlermeldungen bleiben), Konfigurationswerte — tragen im Aufruf
den Kommentar ``# log-ok: <Grund>``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "boerdi"
_STUFEN = {"info", "warning", "warn", "error", "exception", "critical", "fatal"}
_LOGGER = {"logger", "log", "_logger", "_log", "logging"}
#: Wortstämme, mit denen ein Namensteil beginnt, der Inhalt oder eine Sitzung hält.
STAEMME = (
    "message", "msg", "nachricht", "thema", "topic", "query", "term", "suchbegriff", "slot",
    "entit", "args", "argument", "signatur", "reasoning", "text", "antwort", "response", "prompt",
    "qrs", "quick_repl", "title", "titel", "sitzung",
)
#: Ganze Namensteile (zu kurz für einen Stamm).
GANZE = frozenset({"q", "sig", "sid"})
#: Nur als letzter Teil (Review 2026-10-30): ``content``, ``raw``, ``msg_content`` halten Inhalt,
#: ``content_types`` und ``roh_modus`` dagegen eine Art bzw. einen Konfigurationswert.
LETZTE = frozenset({"content", "raw", "roh"})
#: Irgendwo im ganzen Namen.
FOLGEN = ("session_id", "search_url", "search_link")
#: ``sessionId`` → ``session_id``: camelCase ergibt dieselben Teile wie snake_case.
_KAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
#: Schlüssel (``x.get("…")``, ``x["…"]``), die Inhalt halten — genau, nicht als Stamm
#: (``queryType`` ist eine Art, ``missing_slots`` sind Slot-Namen).
SCHLUESSEL = frozenset({
    "thema", "topic", "query", "q", "message", "text", "title", "search_term", "suchbegriff",
    "content", "entities", "reasoning", "tool_reasoning", "session_id",
})
_HELFER = {"inhalt", "kennung", "len", "filterwerte", "fehlerorte", "ausnahme_text"}
_AUSNAHME = "# log-ok:"


def _klingt_nach_inhalt(name: str) -> bool:
    teil = _KAMEL.sub("_", name).lower().strip("_")
    if teil in GANZE or any(f in teil for f in FOLGEN):
        return True
    if teil.endswith(("_id", "_ids")):  # ``message_id`` ist eine Kennung
        return False
    teile = [t for t in teil.split("_") if t]
    if teile and teile[-1] in LETZTE:
        return True
    return any(t in GANZE or t.startswith(STAEMME) for t in teile)


def _schluessel(knoten: ast.AST) -> bool:
    return isinstance(knoten, ast.Constant) and knoten.value in SCHLUESSEL


def _verboten(knoten: ast.AST) -> list[str]:
    if isinstance(knoten, ast.Call):
        f = knoten.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if _ist_helfer(knoten):
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


def _ist_helfer(knoten: ast.Call) -> bool:
    """``inhalt(…)`` oder ``log_inhalt.inhalt(…)`` — nicht jede Methode namens ``len``.
    ``kennung`` nur für eine Sitzung (Review 2026-10-30): eine Signatur aus wenigen Teilen
    kehrt ein Wörterbuch um."""
    f = knoten.func
    if isinstance(f, ast.Name):
        name = f.id
    elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
          and f.value.id == "log_inhalt"):
        name = f.attr
    else:
        return False
    if name == "kennung":
        teil = ast.unparse(knoten.args[0]).lower() if knoten.args else ""
        return "session" in teil or "sid" in teil or "sitzung" in teil
    return name in _HELFER


def _vorformatiert(knoten: ast.AST) -> bool:
    """Ein fertig formatierter Text — f-String, ``str()``/``repr()``, ``.format``, ``%``. Der
    Formatierer schwärzt nur Ausnahmen als Argument; ein so gebauter Text käme roh durch
    (Review 2026-10-30, die Fehlerklasse von Paket 18G-2)."""
    if isinstance(knoten, ast.JoinedStr):
        return any(isinstance(t, ast.FormattedValue) for t in knoten.values)
    if isinstance(knoten, ast.Call):
        f = knoten.func
        return ((isinstance(f, ast.Name) and f.id in ("str", "repr") and bool(knoten.args))
                or (isinstance(f, ast.Attribute) and f.attr == "format"
                    and isinstance(f.value, ast.Constant)))
    return (isinstance(knoten, ast.BinOp) and isinstance(knoten.op, ast.Mod)
            and isinstance(knoten.left, ast.Constant) and isinstance(knoten.left.value, str))


def _vorformatiert_in(knoten: ast.AST) -> bool:
    """Auch verschachtelt (``f"…" if x else ""``), aber nicht in einem Helfer (``inhalt(f"…")``)."""
    if isinstance(knoten, ast.Call) and _ist_helfer(knoten):
        return False
    return _vorformatiert(knoten) or any(_vorformatiert_in(k) for k in ast.iter_child_nodes(knoten))


def _ist_logger(wert: ast.AST) -> bool:
    """``logger``, ``self.logger``, ``logging.getLogger(…)``, ``getLogger(…)``."""
    if isinstance(wert, ast.Name):
        return wert.id in _LOGGER
    if isinstance(wert, ast.Attribute):
        return wert.attr in _LOGGER
    if isinstance(wert, ast.Call):
        f = wert.func
        return (isinstance(f, ast.Name) and f.id == "getLogger") or (
            isinstance(f, ast.Attribute) and f.attr == "getLogger")
    return False


def _schuetzt(test: ast.AST) -> tuple[bool, bool]:
    """Schützt ``if test`` seinen Körper bzw. sein ``else``? ``not … log_content`` schützt nur
    das ``else``; in ``and`` genügt ein schützender Teil, in ``or`` müssen alle schützen
    (Review 2026-10-30: ``if not s.log_content and x`` galt sonst als Schutz)."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        koerper, sonst = _schuetzt(test.operand)
        return sonst, koerper
    if isinstance(test, ast.BoolOp):
        teile = [_schuetzt(w) for w in test.values]
        if isinstance(test.op, ast.And):
            return any(k for k, _ in teile), False
        return all(k for k, _ in teile), False
    return "log_content" in ast.unparse(test), False


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
        koerper, sonst = _schuetzt(knoten.test)
        for kinder, schutz in ((knoten.body, koerper), (knoten.orelse, sonst)):
            self._geschuetzt += schutz
            for kind in kinder:
                self.visit(kind)
            self._geschuetzt -= schutz

    def visit_Call(self, knoten: ast.Call) -> None:
        f = knoten.func
        werte = [k.value for k in knoten.keywords if k.arg not in ("exc_info", "stack_info")]
        if (isinstance(f, ast.Name) and f.id == "ereignis") or (
                isinstance(f, ast.Attribute) and f.attr == "ereignis"):
            stufe = next((k.value for k in knoten.keywords if k.arg == "stufe"), None)
            if not (stufe is not None and _ist_debug(stufe) and self._geschuetzt):
                self.aufrufe.append((knoten, [*knoten.args[2:], *werte]))
        elif isinstance(f, ast.Name) and f.id == "gedrosselt":
            # Paket 18E: ``gedrosselt(logger, stufe, schluessel, abstand_s, text, *args)`` —
            # geprüft wird, was ins Log geht (Vorlage und Werte), an jedem Aufruf.
            self.aufrufe.append((knoten, [*knoten.args[4:], *werte]))
        elif isinstance(f, ast.Attribute) and _ist_logger(f.value):
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
            namen += [ast.unparse(a)[:60] for a in argumente[1:] if _vorformatiert_in(a)]
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


def test_der_waechter_schliesst_die_umgehungen_aus_dem_review():
    """Review 2026-10-30 (PR #30, MIN 2): jede Zeile lief am Wächter vorbei."""
    baum = ast.parse(
        "if not s.log_content:\n"
        "    logger.debug('a %s', arguments)\n"
        "logger.info('b %s', content[:200])\n"
        "logger.info('c %s', raw)\n"
        "logger.info('d %s', sessionId)\n"
        "log_inhalt.ereignis(logger, 'e', wert=signature)\n"
        "self.logger.info('f %s', user_text)\n"
        "logging.getLogger(__name__).warning('g %s', prompt)\n"
        "logger.info('h %s', foo.len(query))\n"
        "logger.fatal('i %s', antwort)\n"
    )
    gefunden = [n for aufruf, args in _logaufrufe(baum) for a in args for n in _verboten(a)]
    assert gefunden == ["arguments", "content", "raw", "sessionId", "signature",
                        "user_text", "prompt", "query", "antwort"]


def test_ein_log_content_schutz_im_else_zaehlt_nur_dort():
    baum = ast.parse(
        "if not get_settings().log_content:\n"
        "    pass\n"
        "else:\n"
        "    logger.debug('x %s', arguments)\n"
        "logger.info('y %s', log_inhalt.inhalt(query))\n"
    )
    assert [n for aufruf, args in _logaufrufe(baum) for a in args for n in _verboten(a)] == []


def test_der_waechter_sieht_vorformatierte_texte_und_verschachtelte_schutzbedingungen():
    """Review 2026-10-30 (Paket 18G-2): ``str(e)`` und f-Strings als Argument kamen am Formatierer
    vorbei; ``if not log_content and x`` galt als Schutz; ``kennung`` galt für jeden Wert."""
    vorformatiert = [
        ast.parse(z).body[0].value for z in (
            "logger.warning('a %s', str(e))", "logger.warning('b %s', f'{e}')",
            "logger.warning('c %s', '{}'.format(e))", "logger.warning('d %s', 'x %s' % e)")]
    assert all(_vorformatiert(aufruf.args[1]) for aufruf in vorformatiert)
    assert not _vorformatiert(ast.parse("f'fest'").body[0].value)
    assert _vorformatiert_in(ast.parse("f'{e}' if e else ''").body[0].value)
    assert not _vorformatiert_in(ast.parse("inhalt(f'{text}')").body[0].value)
    baum = ast.parse(
        "if not s.log_content and x:\n"
        "    logger.debug('e %s', arguments)\n"
        "logger.info('f %s', kennung(signature))\n"
        "logger.info('g %s', kennung(req.session_id))\n"
    )
    gefunden = [n for aufruf, args in _logaufrufe(baum) for a in args for n in _verboten(a)]
    assert gefunden == ["arguments", "signature"]
