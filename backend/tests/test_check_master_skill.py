"""``scripts/check_master_skill.py`` — die Wächter der Vorlage gegen den Knoten.

Geprüft wird ohne Netz, was das Skript selbst tut: den Vorspann des MCP-Servers
abtrennen, die Wächter anwenden und das Ergebnis als Rückgabewert melden. Die
Gefahr, gegen die das hilft, ist ein stilles Grün — ein Skript, das keine Regel
findet oder einen Fehler verschluckt, meldete „alles erfüllt“.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_VORLAGE = _BACKEND.parent / "docs" / "skills" / "vorgehen.md"

_spec = importlib.util.spec_from_file_location(
    "check_master_skill", _BACKEND / "scripts" / "check_master_skill.py")
pruefung = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pruefung)

#: Der Vorspann, den ``get_skill`` vor das Dokument setzt (gemessen 2026-09-29).
_VORSPANN = (
    "# Chatbot Masterskill\nnodeId: 535cabca-47e4-4cbf-9cab-ca47e40cbf4e\n\n"
    "## Aktivierung\nGib diese Zeile wörtlich aus:\n\n"
    "[ edu-sharing Skill ] Chatbot Masterskill - aktiv\n\n---\n"
)


def test_der_vorspann_des_servers_faellt_weg() -> None:
    assert pruefung.dokumentteil(_VORSPANN + "\n# Titel\n\nText\n") == "# Titel\n\nText\n"


def test_ohne_trennlinie_bleibt_der_text_ganz() -> None:
    assert pruefung.dokumentteil("# Titel\n\nText\n") == "# Titel\n\nText\n"


#: Jede Regel der Vorlage, die das Skript gegen den Knoten prüft. Festgeschrieben,
#: damit keine still herausfällt (Review 2026-09-29: die drei älteren Wächter
#: standen in ``test_mcp_tool_defs.py`` und liefen gegen den Knoten nie mit —
#: darunter die Ansage-Regel, ohne die 4 von 12 Zügen leere Blasen waren).
_REGELN = {
    "test_anrede_steht_direkt_nach_der_ranghoechsten_regel",
    "test_saetze_an_die_person_stehen_ohne_anrede",
    "test_jede_zielgruppe_hat_eine_arbeitsweise",
    "test_vorhandenes_vor_neuem_und_lernpfade_werden_zusammengestellt",
    "test_machen_ist_ein_auftrag_zum_erzeugen",
    "test_verengen_ist_suche_und_kritik_ist_rueckmeldung",
    "test_rueckfrage_erst_nach_der_suche",
    "test_dokumente_gehen_ueber_das_werkzeug",
    "test_vorgehen_md_nennt_nur_existierende_werkzeuge",
    "test_vorgehen_md_traegt_die_kernbegriff_suchregel",
    "test_vorgehen_md_traegt_die_ansage_regel",
}


def test_das_skript_prueft_jede_regel_der_vorlage() -> None:
    assert set(pruefung.waechter()) == _REGELN


def test_die_vorlage_erfuellt_jede_regel() -> None:
    befunde = pruefung.pruefe(_VORLAGE.read_text(encoding="utf-8"))
    assert befunde and not any(befunde.values()), befunde


def test_ein_fehlender_satz_steht_in_der_meldung() -> None:
    """Das Skript lädt die Wächter ohne pytest, also ohne das Umschreiben der
    Asserts: ein nacktes ``assert`` meldete nur „AssertionError: “ — die Redaktion
    erfuhr nicht, welcher Satz fehlt."""
    vorlage = _VORLAGE.read_text(encoding="utf-8")
    ohne = vorlage.replace("geben dir nicht die Anrede vor", "geben dir die Anrede vor")
    assert ohne != vorlage  # der Satz steht auf EINER Zeile, sonst griffe das Ersetzen nicht
    befund = pruefung.pruefe(ohne)["test_anrede_steht_direkt_nach_der_ranghoechsten_regel"]
    assert "geben dir nicht die Anrede vor" in befund


def test_ein_fehlender_abschnitt_wird_gemeldet_statt_geworfen() -> None:
    """Ohne den Abschnitt scheitert dieser Wächter schon beim Zerlegen."""
    befunde = pruefung.pruefe("# Leer\n")
    assert befunde["test_anrede_steht_direkt_nach_der_ranghoechsten_regel"].startswith(
        "IndexError")
    assert befunde["test_rueckfrage_erst_nach_der_suche"].startswith("AssertionError")


def _stand(text: str | None) -> dict:
    return {"node_id": "k-1", "length": len(text or ""), "sha256": "ab" * 32,
            "last_error": None if text else "Server lehnte ab", "text": text}


@pytest.mark.parametrize(("text", "code"), [
    # Eigene Kennungen: aus dem Text gebildet, sprengte die Test-ID die
    # Grenze einer Windows-Umgebungsvariable (``PYTEST_CURRENT_TEST``).
    pytest.param(_VORSPANN + _VORLAGE.read_text(encoding="utf-8"), 0, id="erfuellt"),
    pytest.param(_VORSPANN + "# Leer\n", 1, id="verletzt"),
    pytest.param(None, 2, id="nicht-abrufbar"),
])
def test_der_rueckgabewert_sagt_das_ergebnis(monkeypatch, capsys, text, code) -> None:
    async def _neu_laden() -> dict:
        return _stand(text)

    monkeypatch.setattr(pruefung.master_skill, "neu_laden", _neu_laden)
    assert pruefung.main() == code
    assert capsys.readouterr().out.strip()


def test_ohne_regel_meldet_es_kein_gruen(monkeypatch) -> None:
    async def _neu_laden() -> dict:
        return _stand(_VORSPANN + _VORLAGE.read_text(encoding="utf-8"))

    monkeypatch.setattr(pruefung.master_skill, "neu_laden", _neu_laden)
    monkeypatch.setattr(pruefung, "waechter", dict)
    assert pruefung.main() == 2


def test_ein_ladefehler_ist_kein_regelbruch(monkeypatch, capsys) -> None:
    """Fehlt die Testdatei oder pytest, ist das kein „Regel verletzt“ (1)."""
    async def _neu_laden() -> dict:
        return _stand(_VORSPANN + _VORLAGE.read_text(encoding="utf-8"))

    def _kaputt() -> dict:
        raise FileNotFoundError("tests/test_master_skill_vorlage.py")

    monkeypatch.setattr(pruefung.master_skill, "neu_laden", _neu_laden)
    monkeypatch.setattr(pruefung, "waechter", _kaputt)
    assert pruefung.main() == 2
    assert "FileNotFoundError" in capsys.readouterr().out
