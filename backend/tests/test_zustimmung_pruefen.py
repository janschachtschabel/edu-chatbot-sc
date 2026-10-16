"""Zustimmung zu einer offenen Vorschau erkennen — Liste, Veto, LLM (Paket 10, A-6).

Nutzer-Entscheid 2026-10-15: kein Wortlaut darf durchfallen, aber eine Absage darf nie
ausführen. Die Erlaubnisliste (``domain/zustimmung``) bleibt der schnelle, sichere Weg;
passt sie nicht, prüft ein kurzer LLM-Aufruf. Eine feste Vetoliste geht dem Modell vor,
und jeder Fehler heißt „keine Zustimmung“ — dann kommt eine zweite Frage, keine Änderung.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.domain.zustimmung import hat_veto
from boerdi.services import zustimmung_pruefen as zp

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


class TestStimmtZu:
    def test_die_liste_entscheidet_ohne_modell(self, monkeypatch):
        aufrufe = _modell(monkeypatch, "absage")
        assert asyncio.run(zp.stimmt_zu("Ja, so ausführen", "wlo_add_to_collection"))
        assert aufrufe == []

    def test_ein_veto_entscheidet_ohne_modell(self, monkeypatch):
        aufrufe = _modell(monkeypatch, "zustimmung")
        assert not asyncio.run(zp.stimmt_zu("ok, vergiss es", "wlo_add_to_collection"))
        assert aufrufe == []

    @pytest.mark.parametrize("satz", [
        "ja, rein damit", "Ja, das kann noch rein", "Ja bitte füge das Material jetzt hinzu",
    ])
    def test_freie_zustimmung_erkennt_das_modell(self, monkeypatch, satz):
        """Kurzaudit S-5: diese Sätze fielen durch die Liste — es kam eine neue Vorschau."""
        aufrufe = _modell(monkeypatch, "zustimmung")
        assert asyncio.run(zp.stimmt_zu(satz, "wlo_add_to_collection"))
        assert len(aufrufe) == 1 and aufrufe[0]["temperature"] == 0

    @pytest.mark.parametrize("urteil", ["aenderung", "absage", "anderes", "", "Zustimmung?! nein"])
    def test_nur_ein_klares_urteil_fuehrt_aus(self, monkeypatch, urteil):
        _modell(monkeypatch, urteil)
        assert not asyncio.run(zp.stimmt_zu("na gut, rein damit", "wlo_create_content"))

    def test_ein_fehler_des_modells_ist_keine_zustimmung(self, monkeypatch):
        _modell(monkeypatch, RuntimeError("Anbieter weg"))
        assert not asyncio.run(zp.stimmt_zu("ja, rein damit", "wlo_add_to_collection"))

    def test_ein_haengendes_modell_ist_keine_zustimmung(self, monkeypatch):
        monkeypatch.setattr(zp, "FRIST_S", 0.05)

        async def haengt(**_kwargs):
            await asyncio.Event().wait()

        monkeypatch.setattr(zp.llm, "chat_completion", haengt)
        assert not asyncio.run(zp.stimmt_zu("ja, rein damit", "wlo_add_to_collection"))


class TestEinmalJeZug:
    def test_das_urteil_des_zuges_gilt_fuer_alle_leser(self):
        stand = {zp.MERKER: True}
        assert zp.zugestimmt(stand, "irgendwas")
        assert not zp.zugestimmt({zp.MERKER: False}, "Ja, so ausführen")

    def test_ohne_urteil_gilt_die_liste(self):
        assert zp.zugestimmt({}, "Ja, so ausführen")
        assert not zp.zugestimmt({}, "ja, rein damit")
