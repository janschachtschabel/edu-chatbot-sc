"""Zustimmung zu einer offenen Vorschau erkennen — Liste, Veto, LLM (Paket 10, A-6).

Nutzer-Entscheid 2026-10-15: kein Wortlaut darf durchfallen, aber eine Absage darf nie
ausführen. Die Erlaubnisliste (``domain/zustimmung``) bleibt der schnelle, sichere Weg;
passt sie nicht, prüft ein kurzer LLM-Aufruf. Eine feste Vetoliste geht dem Modell vor,
und ein klares anderes Urteil heißt „keine Zustimmung“ — dann kommt eine zweite Frage, keine
Änderung. Ein Fehlschlag (Frist, ausgelastet, Anbieterfehler) ist seit Paket 19 (M-2) „unklar“.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import litellm
import pytest

from boerdi.domain.zustimmung import hat_veto
from boerdi.services import zustimmung_pruefen as zp
from boerdi.services.llm_parallel import LlmAusgelastet

# Die echte Prüfung — ``conftest`` ersetzt sie für alle übrigen Tests (kein Netz).
_ECHTES_URTEIL = zp._llm_urteil


@pytest.fixture(autouse=True)
def _echtes_urteil(monkeypatch):
    monkeypatch.setattr(zp, "_llm_urteil", _ECHTES_URTEIL)


def _modell(monkeypatch, antwort: str | Exception) -> list[dict]:
    aufrufe: list[dict] = []

    async def chat_completion(**kwargs):
        aufrufe.append(kwargs)
        if isinstance(antwort, Exception):
            raise antwort
        msg = SimpleNamespace(content=antwort)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(zp.llm, "chat_completion", chat_completion)
    return aufrufe


class TestVeto:
    @pytest.mark.parametrize("satz", [
        "nein", "Nee, lass mal", "nicht ausführen", "Freigabe abgesagt", "Freigabe aufgehoben",
        "Ausführung abgebrochen", "ok, vergiss es", "Do not proceed", "ok, cancelled",
        "ok nevermind", "Ja?", "Freigabe zurückgewiesen", "Freigabe storniert",
        "ja, aber mit anderem Titel", "ok, nimm stattdessen das zweite",
        "Ja, ändere vorher den Titel",
    ])
    def test_absagen_und_fragen_haben_ein_veto(self, satz):
        assert hat_veto(satz), satz

    @pytest.mark.parametrize("satz", [
        "ja, rein damit", "Ja, das kann noch rein", "Ja bitte füge das Material jetzt hinzu",
        "passt, mach", "Ja, aber schnell",
    ])
    def test_zustimmungen_haben_kein_veto(self, satz):
        assert not hat_veto(satz), satz


class TestUrteil:
    def test_die_liste_entscheidet_ohne_modell(self, monkeypatch):
        aufrufe = _modell(monkeypatch, "absage")
        assert asyncio.run(zp.urteil("Ja, so ausführen", "wlo_add_to_collection")) == zp.JA
        assert aufrufe == []

    def test_ein_veto_entscheidet_ohne_modell(self, monkeypatch):
        aufrufe = _modell(monkeypatch, "zustimmung")
        assert asyncio.run(zp.urteil("ok, vergiss es", "wlo_add_to_collection")) == zp.NEIN
        assert aufrufe == []

    @pytest.mark.parametrize("satz", [
        "ja, rein damit", "Ja, das kann noch rein", "Ja bitte füge das Material jetzt hinzu",
    ])
    def test_freie_zustimmung_erkennt_das_modell(self, monkeypatch, satz):
        """Kurzaudit S-5: diese Sätze fielen durch die Liste — es kam eine neue Vorschau."""
        aufrufe = _modell(monkeypatch, "zustimmung")
        assert asyncio.run(zp.urteil(satz, "wlo_add_to_collection")) == zp.JA
        assert len(aufrufe) == 1 and aufrufe[0]["temperature"] == 0

    @pytest.mark.parametrize("urteil", ["aenderung", "absage", "anderes", "", "Zustimmung?! nein"])
    def test_nur_ein_klares_urteil_fuehrt_aus(self, monkeypatch, urteil):
        _modell(monkeypatch, urteil)
        assert asyncio.run(zp.urteil("na gut, rein damit", "wlo_create_content")) == zp.NEIN


class TestUnklar:
    """Paket 19, M-2: ein Fehlschlag ist keine Antwort. Bis hier hieß jeder Fehler „nein“ —
    unter Last verlor eine frei formulierte Zustimmung so die vorbereitete Änderung."""

    @pytest.mark.parametrize("fehler", [
        litellm.Timeout(message="t", llm_provider="openai", model="gpt-x"),
        litellm.RateLimitError(message="429", llm_provider="openai", model="gpt-x"),
        TimeoutError(), LlmAusgelastet("kein Platz"),
    ], ids=["anbieter-timeout", "429", "frist", "ausgelastet"])
    def test_ein_voruebergehender_fehlschlag_ist_unklar(self, monkeypatch, fehler):
        _modell(monkeypatch, fehler)
        assert asyncio.run(zp.urteil("ja, rein damit", "wlo_add_to_collection")) == zp.UNKLAR

    @pytest.mark.parametrize("fehler", [
        RuntimeError("kaputt"), IndexError("choices"),
        litellm.BadRequestError(message="400", llm_provider="openai", model="gpt-x"),
        litellm.AuthenticationError(message="401", llm_provider="openai", model="gpt-x"),
    ], ids=["laufzeit", "index", "400", "401"])
    def test_ein_dauerhafter_fehler_ist_nein_wie_frueher(self, monkeypatch, fehler):
        """Review 19-5 (3): „unklar“ nur für Last, Frist und vorübergehende Anbieterfehler —
        ein Fehler, der beim nächsten Versuch genauso käme, hält den Vorgang nicht fest."""
        _modell(monkeypatch, fehler)
        assert asyncio.run(zp.urteil("ja, rein damit", "wlo_add_to_collection")) == zp.NEIN

    def test_die_platzfrist_ist_kurz(self, monkeypatch):
        """Review 19-5 (4): ``setup`` läuft unter der Sitzungssperre — 30 s Warten auf einen
        Platz für eine Prüfung, die ohnehin glimpflich „unklar“ endet, lohnen nicht."""
        aufrufe = _modell(monkeypatch, "zustimmung")
        asyncio.run(zp.urteil("ja, rein damit", "wlo_add_to_collection"))
        assert aufrufe[0]["platz_frist_s"] == zp.PLATZ_FRIST_S <= 5

    def test_ein_haengendes_modell_ist_unklar(self, monkeypatch):
        monkeypatch.setattr(zp, "FRIST_S", 0.05)

        async def haengt(**kwargs):
            # Wie ``llm.chat_completion``: die Frist gilt dem Aufruf, nicht dem Warten.
            async with asyncio.timeout(kwargs["frist_s"]):
                await asyncio.Event().wait()

        monkeypatch.setattr(zp.llm, "chat_completion", haengt)
        assert asyncio.run(zp.urteil("ja, rein damit", "wlo_add_to_collection")) == zp.UNKLAR

    def test_die_frist_gilt_erst_nach_der_platzvergabe(self, monkeypatch):
        aufrufe = _modell(monkeypatch, "zustimmung")
        asyncio.run(zp.urteil("ja, rein damit", "wlo_add_to_collection"))
        assert aufrufe[0]["frist_s"] == zp.FRIST_S

    def test_das_log_traegt_keinen_traceback_und_keinen_inhalt(self, monkeypatch, caplog):
        _modell(monkeypatch, litellm.RateLimitError(
            message="Anbieter weg: ja, rein damit", llm_provider="openai", model="gpt-x"))
        with caplog.at_level(logging.DEBUG, logger=zp.__name__):
            asyncio.run(zp.urteil("ja, rein damit", "wlo_add_to_collection"))
        zeilen = [r for r in caplog.records if r.name == zp.__name__]
        assert zeilen and not any(r.exc_info for r in zeilen)
        assert not any("rein damit" in r.getMessage() for r in zeilen)


class TestEinmalJeZug:
    def test_das_urteil_des_zuges_gilt_fuer_alle_leser(self):
        stand = {zp.MERKER: True}
        assert zp.zugestimmt(stand, "irgendwas")
        assert not zp.zugestimmt({zp.MERKER: False}, "Ja, so ausführen")

    def test_ohne_urteil_gilt_die_liste(self):
        assert zp.zugestimmt({}, "Ja, so ausführen")
        assert not zp.zugestimmt({}, "ja, rein damit")
