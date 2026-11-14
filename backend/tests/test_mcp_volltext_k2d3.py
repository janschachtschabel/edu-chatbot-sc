"""Paket K2d-3 (Plan 2026-11-08): die MCP-Werkzeuge W1–W3 angebunden (MCP-Stand 2026-11-08).

- ``wlo_attach_fulltext`` (W1): ein Volltext (Markdown) in den ``textContent`` eines Datensatzes —
  zweistufig wie jedes kuratierende Werkzeug (Vorschau, „ja“, der Chat setzt den Schlüssel ein).
- ``wlo_attach_fulltexts`` (W2) und ``wlo_update_contents`` (W3): viele Datensätze unter EINER
  Bestätigung — **Pläne** wie M5 (der Vorlauf löst ein, „Plan fortsetzen“ setzt fort).
- ``would_replace_file`` (Datensatz mit Inhalt; seit dem 14.11.2026 dauerhaft) ist kein Fehler: die
  Beschreibung sagt dem Modell, es als „hier noch nicht möglich“ zu nennen — ohne Nachtragen zu
  versprechen (Review K2d-3, Befund 3).
- Die Argumente gehen nur mit den Feldern zum Server, die er kennt, und ohne leere Werte.
"""

from __future__ import annotations

import json
from pathlib import Path

from boerdi.domain.write_confirm import CONFIRMABLE_TOOLS, CURATION_TOOLS, is_plan
from boerdi.services.mcp.tool_args import validate_tool_args
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

W1, W2, W3 = "wlo_attach_fulltext", "wlo_attach_fulltexts", "wlo_update_contents"
_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


def _def(name: str) -> dict:
    return next(d["function"] for d in CURATION_TOOL_DEFINITIONS if d["function"]["name"] == name)


def test_die_drei_sind_kuratierend_und_zweistufig_w2_w3_sind_plaene():
    for name in (W1, W2, W3):
        assert name in CURATION_TOOLS and name in CONFIRMABLE_TOOLS, name
    assert not is_plan(W1)
    assert is_plan(W2) and is_plan(W3)


def test_die_beschreibungen_sagen_wann_und_wie():
    w1, w2, w3 = _def(W1), _def(W2), _def(W3)
    assert w1["parameters"]["required"] == ["nodeId", "markdown", "source"]
    assert set(w1["parameters"]["properties"]["source"]["enum"]) == {"binary", "website", "manual"}
    assert w2["parameters"]["required"] == ["items"] and w3["parameters"]["required"] == ["items"]
    for d in (w1, w2):
        # kein Fehler beim Datensatz mit Inhalt (Nutzer-Entscheid 2026-11-08, Review Befund 3)
        assert "would_replace_file" in d["description"]
        # Seit dem 14.11.2026 dauerhaft: kein „später erneut“, kein „vorgemerkt“.
        assert "nur an einen Datensatz ohne Datei" in d["description"]
        assert "vorgemerkt" not in d["description"] and "spaeter erneut" not in d["description"]
    for d in (w2, w3):
        assert "NICHT erneut auf" in d["description"]          # Plan: der Chat löst ein
    assert "erneut auf" in w1["description"] and "NICHT erneut auf" not in w1["description"]
    # kein Feld, das nur ein Programm setzt
    for d in (w1, w2, w3):
        props = d["parameters"]["properties"]
        assert "confirmToken" not in props and "continuationToken" not in props


def test_w1_argumente():
    out = validate_tool_args(W1, {"nodeId": "n-1", "markdown": "# T", "source": "binary",
                                  "replace": True, "fremd": 1})
    assert out == {"nodeId": "n-1", "markdown": "# T", "source": "binary", "replace": True}


def test_w2_argumente_nur_bekannte_felder_je_eintrag():
    out = validate_tool_args(W2, {"items": [
        {"nodeId": "n-1", "markdown": "# A", "source": "website", "sourceUrl": "https://x.de",
         "titel": "fremd"},
        {"nodeId": "n-2", "markdown": "# B", "source": "manual", "language": "de"}]})
    assert out["items"] == [
        {"nodeId": "n-1", "markdown": "# A", "source": "website", "sourceUrl": "https://x.de"},
        {"nodeId": "n-2", "markdown": "# B", "source": "manual", "language": "de"}]


def test_w3_argumente_nur_die_metadatenfelder():
    out = validate_tool_args(W3, {"items": [
        {"nodeId": "n-1", "title": "Optik", "keywords": ["Licht"], "reason": "aus dem Volltext",
         "content": "kein Metadatenfeld", "fileBase64": "x", "mode": "write"}]})
    assert out["items"] == [{"nodeId": "n-1", "title": "Optik", "keywords": ["Licht"],
                             "reason": "aus dem Volltext"}]


def test_seeds_kennen_die_werkzeuge():
    server = (_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(encoding="utf-8")
    muster = (_SEEDS / "03-patterns" / "m18-kuration.md").read_text(encoding="utf-8")
    for name in (W1, W2, W3):
        assert f"- {name}\n" in server.replace("\r\n", "\n"), name
        assert f"- {name}\n" in muster.replace("\r\n", "\n"), name


# ── Review K2d-3 ─────────────────────────────────────────────────────────────────────────────

def test_review_leere_werte_in_eintraegen_fallen_weg():
    out = validate_tool_args(W3, {"items": [
        {"nodeId": "n-1", "title": "Neu", "description": "", "keywords": [], "author": None}]})
    assert out["items"] == [{"nodeId": "n-1", "title": "Neu"}]


def test_review_ein_zu_grosser_plan_kommt_gar_nicht_erst_zur_vorschau():
    from boerdi.domain.write_confirm import PLAN_ZU_GROSS_TEXT, plan_zu_gross, remember_pending
    from boerdi.services.agent_write import WriteGate

    gross = {"items": [{"nodeId": f"n-{i}", "markdown": "x" * 60_000, "source": "binary"}
                       for i in range(5)]}
    merk = remember_pending(W2, gross, "Schluessel-0123456789abcd", now=0.0)
    assert plan_zu_gross(merk)
    klein = remember_pending(W2, {"items": gross["items"][:1]}, "Schluessel-0123456789abcd",
                             now=0.0)
    assert not plan_zu_gross(klein)
    # W1 ist kein Plan: dort trägt der Fingerabdruck-Weg
    assert not plan_zu_gross(remember_pending(W1, {"markdown": "x" * 300_000}, "S" * 24, now=0.0))
    gate = WriteGate("propose")
    text = gate.observe(W2, gross, "Vorschau … mit confirmToken: Schluessel-0123456789abcd "
                                   "wiederholen.")
    assert text == PLAN_ZU_GROSS_TEXT and gate.offene_abnahme() is None


def test_review_volltexte_nicht_in_zugakte_und_protokoll():
    from boerdi.services import zugakte
    from boerdi.services.mcp import client

    assert zugakte._wert("markdown", "x" * 5000) == "‹5000 Zeichen›"
    zeile = client._args_for_log({"items": [{"nodeId": "n", "markdown": "x" * 5000}],
                                  "confirmToken": "geheim"})
    assert zeile["confirmToken"] == "‹geschwärzt›"
    assert zeile["items"][0] == {"nodeId": "n", "markdown": "‹5000 Zeichen›"}


def test_review_der_grund_bei_volltexten_wird_gezeigt():
    from boerdi.services.write_approval import _GRUND_ZEIGEN

    assert {"would_replace_file", "link_record", "exists"} <= _GRUND_ZEIGEN


def test_review_die_beschreibung_verspricht_kein_nachtragen():
    w1 = _def(W1)["description"]
    assert "versprich kein Nachtragen" in w1 and "link_record" in w1


# ── Zweites Review K2d-3 ──────────────────────────────────────────────────────────────────────

def test_review2_nur_leerzeichen_und_leere_listeneintraege_fallen_weg():
    out = validate_tool_args(W3, {"items": [
        {"nodeId": "n-1", "title": "  ", "keywords": ["", "  ", "Licht"], "subjects": [" "],
         "description": "Neu"}]})
    assert out["items"] == [{"nodeId": "n-1", "keywords": ["Licht"], "description": "Neu"}]


def test_review2_zu_grosser_plan_in_der_werkzeug_schleife(monkeypatch):
    from boerdi.domain.write_confirm import PLAN_ZU_GROSS_TEXT
    from tests.test_tool_loop import _OutcomeFake, _resp_text, _resp_tools, _run_loop

    gross = {"items": [{"nodeId": f"n-{i}", "markdown": "x" * 60_000, "source": "binary"}
                       for i in range(5)]}
    mcp = _OutcomeFake({W2: "Vorschau … mit confirmToken: Schluessel-0123456789abcd "
                            "wiederholen."})
    zustand: dict = {"turn_count": 3, "entities": {}}
    fake, _result, _st = _run_loop(
        monkeypatch, [_resp_tools([("c1", W2, json.dumps(gross))]), _resp_text("ok")],
        outcome=mcp, session_state=zustand, message="haenge die Volltexte an")
    assert "_pending_write" not in zustand["entities"]
    assert "_write_preview" not in zustand["entities"]
    # das Modell las den Hinweis statt der Vorschau — und keinen Schlüssel
    gesehen = json.dumps(fake.calls[-1], ensure_ascii=False, default=str)
    assert "NUR den" in PLAN_ZU_GROSS_TEXT and PLAN_ZU_GROSS_TEXT[:40] in gesehen
    assert "Schluessel-0123456789abcd" not in gesehen


def test_review2_zugakte_kuerzt_volltexte_auch_in_eintraegen():
    from boerdi.services import zugakte

    akte = json.dumps(zugakte._argumente({"items": [{"nodeId": "n", "markdown": "x" * 5000}]}),
                      ensure_ascii=False)
    assert "xxxxxxxxxx" not in akte and "5000 Zeichen" in akte


def test_review2_m18_liest_viele_datensaetze_auf_einmal():
    muster = (_SEEDS / "03-patterns" / "m18-kuration.md").read_text(encoding="utf-8")
    assert "- get_nodes_details\n" in muster.replace("\r\n", "\n")
    assert "`get_node_details` je Datensatz" not in muster
