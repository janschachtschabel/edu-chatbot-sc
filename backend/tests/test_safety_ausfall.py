"""Paket 18A — eine ausgefallene Sicherheitsstufe wird nie als „geprüft“ verbucht.

Externes Audit 2026-10 (Störversuch „falscher Schlüssel“) und eigene Prüfung
2026-10-28: Die Moderation ist fail-open (der Regex-Boden bleibt). Bis hierher
stand ein Ausfall aber nirgends in der Entscheidung, ``_maybe_downgrade`` stufte
ein „medium“ trotzdem mit ``downgraded_by_llm_check`` herab, ohne Zugangsdaten
schwieg die Stufe ganz, und das Aufwärmen meldete Erfolg. Der Schalter
``MODERATION_BEI_AUSFALL=geschlossen`` beantwortet einen Zug ohne Moderation
gar nicht (Nutzer-Entscheid E1: Vorgabe ``offen``).
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from prometheus_client import REGISTRY

from boerdi.api.schemas import ChatRequest, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import pruefung_fehlt as pf
from boerdi.services import warmup
from boerdi.services.safety import legal as legal_mod
from boerdi.services.safety import moderation as mod
from boerdi.services.safety import service as ss

_CFG = {
    "security_level": "max",
    "presets": {"max": {
        "moderation": "always", "legal_classifier": "always",
        "prompt_injection": True, "threshold_multiplier": 1.0,
    }},
    "escalation": {
        "thresholds": {"violence": 0.5},
        "hard_block_categories": ["violence"],
        "legal_thresholds": {"flag": 0.4, "high": 0.7},
        "downgrade_false_positives": True,
    },
    "crisis_blocked_tools": ["search_wlo_content"],
}


#: So antwortet eine gelaufene Rechtsprüfung ohne Befund; ``{}`` hieße „ausgefallen“.
_LEGAL_SAUBER = {"strafrecht": {"risk": 0.0, "reason": ""}}


def _bewerte(monkeypatch, *, moderation, legal=_LEGAL_SAUBER):
    monkeypatch.setattr(ss, "load_safety_config", lambda: dict(_CFG))
    monkeypatch.setattr(mod, "moderate", moderation)

    async def _legal(_m, usage_acc=None):
        return legal

    monkeypatch.setattr(legal_mod, "classify_legal", _legal)
    return asyncio.run(ss.assess_safety("harmlos"))


async def _leer(_m):
    return {}


async def _sauber(_m):
    return {"flagged": False, "categories": {}, "scores": {"violence": 0.01}}


def _zaehler(stufe: str, ausgang: str) -> float:
    return REGISTRY.get_sample_value(
        "boerdi_safety_stage_total", {"stage": stufe, "outcome": ausgang}) or 0.0


# ── Entscheidung ─────────────────────────────────────────────────────────

def test_eine_leere_moderation_steht_als_ausfall_in_der_entscheidung(monkeypatch):
    d = _bewerte(monkeypatch, moderation=_leer)
    assert d.stages_failed == ["openai_moderation"]
    assert "moderation_unavailable" in d.reasons


def test_ohne_moderation_wird_nicht_herabgestuft(monkeypatch):
    # 0.45 flaggt (>= 0.4) → medium. Ohne gelaufene Moderation darf das nicht
    # mit „downgraded_by_llm_check“ wieder auf low fallen.
    d = _bewerte(monkeypatch, moderation=_leer,
                 legal={"persoenlichkeitsrechte": {"risk": 0.45}})
    assert d.risk_level == "medium"
    assert "downgraded_by_llm_check" not in d.reasons


def test_mit_sauberer_moderation_bleibt_die_herabstufung(monkeypatch):
    d = _bewerte(monkeypatch, moderation=_sauber,
                 legal={"persoenlichkeitsrechte": {"risk": 0.45}})
    assert d.risk_level == "low"
    assert "downgraded_by_llm_check" in d.reasons
    assert d.stages_failed == []


def test_eine_abgebrochene_stufe_bricht_die_pruefung_nicht(monkeypatch):
    # ``gather(return_exceptions=True)`` liefert ``CancelledError`` als Ergebnis —
    # eine BaseException. Die Prüfung ``isinstance(res, Exception)`` ließ sie als
    # „Daten“ durch, und ``_merge_moderation`` stürzte auf ``.get``.
    async def _abgebrochen(_m):
        raise asyncio.CancelledError

    d = _bewerte(monkeypatch, moderation=_abgebrochen)
    assert "openai_moderation" in d.stages_failed
    assert "moderation_unavailable" in d.reasons


def test_eine_ausgefallene_rechtspruefung_steht_in_der_entscheidung(monkeypatch):
    # Review 18: ``classify_legal`` gibt bei jedem Fehler ``{}`` zurück — das galt als
    # „sauber“ und erlaubte die Herabstufung eines „medium“ aus dem Regex-Gate.
    monkeypatch.setattr(ss, "regex_gate", lambda _m, _s: SafetyDecision(
        risk_level="medium", stages_run=["regex"]))
    d = _bewerte(monkeypatch, moderation=_sauber, legal={})
    assert "llm_legal" in d.stages_failed
    assert d.risk_level == "medium"
    assert "downgraded_by_llm_check" not in d.reasons
    assert "moderation_unavailable" not in d.reasons


def test_eine_teilweise_moderation_steht_in_der_entscheidung(monkeypatch):
    async def _teilweise(_m):
        return {"flagged": False, "categories": {}, "scores": {"violence": 0.01},
                "teilweise": True}

    d = _bewerte(monkeypatch, moderation=_teilweise)
    assert "openai_moderation" in d.stages_failed
    assert "moderation_partial" in d.reasons
    assert "moderation_unavailable" not in d.reasons


def test_der_regex_rueckfall_gilt_als_ungeprueft():
    # Scheitert ``assess_safety`` als Ganzes, bleibt nur das Regex-Gate — geprüft
    # hat dann niemand (Review 18: der geschlossene Schalter griff hier nicht).
    d = ss.regex_rueckfall("hallo", [])
    assert d.stages_run == ["regex"]
    assert "openai_moderation" in d.stages_failed
    assert "moderation_unavailable" in d.reasons


# ── Moderation selbst: Zähler, Log, lange Nachrichten ────────────────────

def test_ohne_zugangsdaten_warnt_sie_einmal_und_zaehlt_jeden_zug(monkeypatch, caplog):
    monkeypatch.setattr(mod, "_moderation_target", lambda: None)
    monkeypatch.setattr(mod, "_ohne_zugang_gemeldet", False)
    vorher = _zaehler("openai_moderation", "keine_zugangsdaten")
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        assert asyncio.run(mod.moderate("x")) == {}
        assert asyncio.run(mod.moderate("y")) == {}
    assert caplog.text.count("moderation not configured") == 1
    assert _zaehler("openai_moderation", "keine_zugangsdaten") == vorher + 2


def _ergebnis(flagged: bool, score: float):
    return SimpleNamespace(
        flagged=flagged, categories={"sexual": flagged},
        category_scores={"sexual": score})


def test_fehler_und_erfolg_werden_gezaehlt(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    fehler_vorher = _zaehler("openai_moderation", "fehler")
    ok_vorher = _zaehler("openai_moderation", "ok")

    async def _kaputt(**kwargs):
        raise RuntimeError("401")

    monkeypatch.setattr(mod, "_amoderation", _kaputt)
    asyncio.run(mod.moderate("x"))

    async def _gut(**kwargs):
        return SimpleNamespace(results=[_ergebnis(False, 0.0)])

    monkeypatch.setattr(mod, "_amoderation", _gut)
    asyncio.run(mod.moderate("x"))
    assert _zaehler("openai_moderation", "fehler") == fehler_vorher + 1
    assert _zaehler("openai_moderation", "ok") == ok_vorher + 1


def test_eine_lange_nachricht_wird_bis_zum_ende_geprueft(monkeypatch):
    # Bisher nur die ersten 4000 Zeichen: ein harmloser Vorspann schob den
    # eigentlichen Inhalt aus dem Blick.
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    gesehen = {}

    async def _je_abschnitt(**kwargs):
        gesehen["input"] = kwargs["input"]
        teile = kwargs["input"] if isinstance(kwargs["input"], list) else [kwargs["input"]]
        return SimpleNamespace(results=[
            _ergebnis("BOESE" in t, 0.99 if "BOESE" in t else 0.01) for t in teile])

    monkeypatch.setattr(mod, "_amoderation", _je_abschnitt)
    r = asyncio.run(mod.moderate("a" * 9000 + " BOESE"))
    assert isinstance(gesehen["input"], list) and len(gesehen["input"]) == 3
    assert r["flagged"] is True
    assert r["scores"]["sexual"] == 0.99
    assert r["categories"]["sexual"] is True


def test_eine_sehr_lange_nachricht_wird_am_anfang_und_am_ende_geprueft(monkeypatch):
    # Mehr als acht Abschnitte: die ersten und die letzten vier, und die Prüfung
    # meldet sich als teilweise (Review 18: Inhalt ab Zeichen 32 000 blieb ungeprüft).
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    gesehen = {}

    async def _je_abschnitt(**kwargs):
        gesehen["input"] = kwargs["input"]
        return SimpleNamespace(results=[
            _ergebnis("BOESE" in t, 0.99 if "BOESE" in t else 0.01) for t in kwargs["input"]])

    monkeypatch.setattr(mod, "_amoderation", _je_abschnitt)
    vorher = _zaehler("openai_moderation", "teilweise")
    r = asyncio.run(mod.moderate("a" * 60000 + " BOESE"))
    assert len(gesehen["input"]) == 8
    assert r["flagged"] is True and r["teilweise"] is True
    assert _zaehler("openai_moderation", "teilweise") == vorher + 1


def test_ein_wort_auf_der_abschnittsgrenze_wird_gesehen(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))

    async def _je_abschnitt(**kwargs):
        teile = kwargs["input"] if isinstance(kwargs["input"], list) else [kwargs["input"]]
        return SimpleNamespace(results=[_ergebnis("BOESE" in t, 0.5) for t in teile])

    monkeypatch.setattr(mod, "_amoderation", _je_abschnitt)
    r = asyncio.run(mod.moderate("a" * 3998 + "BOESE" + "b" * 100))
    assert r["flagged"] is True
    assert "teilweise" not in r


def test_eine_unvollstaendige_antwort_gilt_als_ausfall(monkeypatch):
    # Bisher wurde eine leere ``results``-Liste zu „sauber“ zusammengefasst.
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))

    async def _leer_ergebnis(**kwargs):
        return SimpleNamespace(results=[])

    monkeypatch.setattr(mod, "_amoderation", _leer_ergebnis)
    vorher = _zaehler("openai_moderation", "fehler")
    assert asyncio.run(mod.moderate("x")) == {}
    assert _zaehler("openai_moderation", "fehler") == vorher + 1


def test_die_rechtspruefung_wird_gezaehlt(monkeypatch):
    async def _kaputt(**kwargs):
        raise RuntimeError("503")

    monkeypatch.setattr(legal_mod, "chat_completion", _kaputt)
    vorher = _zaehler("llm_legal", "fehler")
    assert asyncio.run(legal_mod.classify_legal("x")) == {}
    assert _zaehler("llm_legal", "fehler") == vorher + 1


def test_eine_kurze_nachricht_geht_wie_bisher_als_text(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    gesehen = {}

    async def _fake(**kwargs):
        gesehen["input"] = kwargs["input"]
        return SimpleNamespace(results=[_ergebnis(False, 0.0)])

    monkeypatch.setattr(mod, "_amoderation", _fake)
    asyncio.run(mod.moderate("kurz"))
    assert gesehen["input"] == "kurz"


# ── Schalter MODERATION_BEI_AUSFALL ──────────────────────────────────────

class _Spy:
    def __init__(self):
        self.calls = []

    async def __call__(self, *a, **k):
        self.calls.append((a, k))


def _ctx(gruende: list[str]) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message="hallo"))
    ctx.safety = SafetyDecision(reasons=gruende)
    return ctx


def _schalter(monkeypatch, wert: str):
    monkeypatch.setattr(ss, "get_settings", lambda: SimpleNamespace(moderation_bei_ausfall=wert))


def test_geschlossen_beantwortet_einen_zug_ohne_moderation_nicht(monkeypatch):
    _schalter(monkeypatch, "geschlossen")
    speichern = _Spy()
    monkeypatch.setattr(pf, "save_message", speichern)
    out = asyncio.run(pf.pruefung_fehlt(_ctx(["moderation_unavailable"]), session=object()))
    assert out.early_response is not None
    assert "prüfen" in out.early_response.content
    assert out.early_response.quick_replies == []
    assert len(speichern.calls) == 1
    assert pf.nach_der_pruefung(out) == pf.END


def test_offen_laesst_den_zug_weiterlaufen(monkeypatch):
    _schalter(monkeypatch, "offen")
    out = asyncio.run(pf.pruefung_fehlt(_ctx(["moderation_unavailable"]), session=object()))
    assert out.early_response is None
    assert pf.nach_der_pruefung(out) == "merge"


def test_geschlossen_beantwortet_auch_eine_teilweise_gepruefte_nachricht_nicht(monkeypatch):
    _schalter(monkeypatch, "geschlossen")
    assert ss.sperrt_ohne_moderation(SafetyDecision(reasons=["moderation_partial"]))


def test_die_absage_wird_in_der_auswertung_verbucht(monkeypatch):
    # Review 18: der Zug endet vor ``persist`` — ohne eigene Zeile fehlten die
    # abgewiesenen Personen in der Auswertung.
    _schalter(monkeypatch, "geschlossen")
    monkeypatch.setattr(pf, "save_message", _Spy())
    auswertung = _Spy()
    monkeypatch.setattr(pf, "log_turn_quality", auswertung)
    asyncio.run(pf.pruefung_fehlt(_ctx(["moderation_unavailable"]), session=object()))
    assert len(auswertung.calls) == 1
    debug = auswertung.calls[0][0][2]
    assert debug.pattern == "SAFETY: moderation_unavailable"


def test_der_agent_endpunkt_folgt_dem_schalter(monkeypatch):
    # Review 18: ``/api/agent`` prüfte, aber fragte den Schalter nicht.
    from boerdi.services import agent_gate

    _schalter(monkeypatch, "geschlossen")
    text = agent_gate.stopp_text(SafetyDecision(reasons=["moderation_unavailable"]), "de")
    assert text is not None and "prüfen" in text
    _schalter(monkeypatch, "offen")
    assert agent_gate.stopp_text(SafetyDecision(reasons=["moderation_unavailable"]), "de") is None


def test_geschlossen_ohne_ausfall_laesst_den_zug_weiterlaufen(monkeypatch):
    _schalter(monkeypatch, "geschlossen")
    out = asyncio.run(pf.pruefung_fehlt(_ctx([]), session=object()))
    assert out.early_response is None


def test_die_vorgabe_des_schalters_ist_offen():
    from boerdi.settings import Settings

    assert Settings.model_fields["moderation_bei_ausfall"].default == "offen"


def _startwarnungen(monkeypatch, caplog, roh: str, *, zugang: bool) -> str:
    from boerdi.main import _warn_insecure_config
    from boerdi.settings import Settings

    monkeypatch.setenv("MODERATION_BEI_AUSFALL", roh)
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("u", "k", None) if zugang else None)
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(Settings())
    return "\n".join(r.getMessage() for r in caplog.records)


def test_ein_unbekannter_schalterwert_wird_beim_start_gemeldet(monkeypatch, caplog):
    # Review 18: „closed“ fiel still auf „offen“ zurück — ein Schalter, der
    # schließen soll, öffnete ohne Zeichen.
    text = _startwarnungen(monkeypatch, caplog, "closed", zugang=True)
    assert "MODERATION_BEI_AUSFALL" in text and "closed" in text


def test_geschlossen_ohne_moderationszugang_wird_beim_start_gemeldet(monkeypatch, caplog):
    text = _startwarnungen(monkeypatch, caplog, "geschlossen", zugang=False)
    assert "MODERATION_BEI_AUSFALL" in text


def test_geschlossen_mit_zugang_bleibt_beim_start_still(monkeypatch, caplog):
    assert "MODERATION_BEI_AUSFALL" not in _startwarnungen(
        monkeypatch, caplog, "geschlossen", zugang=True)


# ── Aufwärmen ────────────────────────────────────────────────────────────

def test_das_aufwaermen_meldet_eine_ungepruefte_moderation(monkeypatch, caplog):
    async def _leer_mod(_m):
        return {}

    monkeypatch.setattr(warmup, "moderate", _leer_mod)
    with caplog.at_level(logging.INFO, logger=warmup.__name__):
        asyncio.run(warmup.warm_llm_connection())
    assert "llm warmup done" not in caplog.text
    assert "moderation" in caplog.text and "nicht" in caplog.text
