"""K4 — Auswertung der Verbrauchszeilen (``services/usage_analytics.py``).

Gegen die echte Compose-Postgres, aus demselben Grund wie bei K2b: die
Aggregation IST die SQL. Eine Attrappe prüfte hier nur, dass ich meine eigene
Erwartung abgetippt habe.

Die Preistafel kommt über ``load_pricing`` aus dem Config-Store; die Tests
tauschen genau diese eine Stelle aus, statt einen Store zu binden — der
Bereich selbst ist in ``test_pricing.py`` gepinnt.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_TEST_DB = "boerdi_k4_test"
_JAN = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_TEST_DB)
    yield pg_utils.sqlalchemy_url(_TEST_DB)
    pg_utils.drop_db(_TEST_DB)


def _factory(url):
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.settings import Settings

    engine = make_engine(Settings(_env_file=None, database_url=url))
    return engine, make_session_factory(engine)


def _tafel(**modelle):
    from boerdi.domain.config_models.pricing import PricingArea

    return PricingArea.model_validate({"currency": "EUR", "models": modelle})


@pytest.fixture()
def keine_preise(monkeypatch):
    """Vorgabe: ungepflegte Tafel — so wie der ausgelieferte Seed."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel())


def _lauf(db, szenario):
    """Engine aufbauen, Szenario fahren, Engine sicher schließen."""

    async def wrapper():
        engine, factory = _factory(db)
        try:
            return await szenario(factory)
        finally:
            await engine.dispose()

    return asyncio.run(wrapper())


async def _saee(factory, session_id: str, zeilen: list[dict]) -> None:
    """Eine Sitzung mit ihren Verbrauchszeilen anlegen."""
    from boerdi.db.models import ChatSession, UsageEvent

    async with factory() as s:
        s.add(ChatSession(session_id=session_id))
        await s.commit()
    async with factory() as s:
        for z in zeilen:
            s.add(UsageEvent(session_id=session_id, **z))
        await s.commit()


# ── Summen je Sitzung ───────────────────────────────────────────────────

def test_summiert_ueber_die_zeilen_einer_sitzung(db, keine_preise) -> None:
    from boerdi.services.usage_analytics import session_usage

    async def szenario(factory):
        await _saee(factory, "k4-summe", [
            {"model": "a", "prompt_tokens": 100, "cached_tokens": 60,
             "completion_tokens": 20, "reasoning_tokens": 8, "calls": 2},
            {"model": "a", "prompt_tokens": 10, "cached_tokens": 0,
             "completion_tokens": 5, "reasoning_tokens": 0, "calls": 1},
            {"model": "b", "prompt_tokens": 7, "cached_tokens": 0,
             "completion_tokens": 3, "reasoning_tokens": 0, "calls": 1},
        ])
        async with factory() as s:
            return await session_usage(s, "k4-summe")

    ergebnis = _lauf(db, szenario)

    assert ergebnis["empty"] is False
    assert ergebnis["calls"] == 4
    assert ergebnis["prompt_tokens"] == 117
    assert ergebnis["cached_tokens"] == 60
    assert ergebnis["completion_tokens"] == 28
    assert ergebnis["reasoning_tokens"] == 8
    # Je Modell zusammengefasst, nicht je Zeile — zwei Modelle, drei Zeilen.
    assert [m["model"] for m in ergebnis["models"]] == ["a", "b"]
    assert ergebnis["models"][0]["prompt_tokens"] == 110
    assert ergebnis["models"][0]["calls"] == 3


def test_fremde_sitzung_zaehlt_nicht_mit(db, keine_preise) -> None:
    from boerdi.services.usage_analytics import session_usage

    async def szenario(factory):
        await _saee(factory, "k4-meine", [
            {"model": "a", "prompt_tokens": 5, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        await _saee(factory, "k4-fremde", [
            {"model": "a", "prompt_tokens": 999, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await session_usage(s, "k4-meine")

    assert _lauf(db, szenario)["prompt_tokens"] == 5


def test_sitzung_ohne_zeilen_meldet_leer(db, keine_preise) -> None:
    """Kein 404: eine Sitzung ohne LLM-Aufruf ist der Normalfall (Tour,
    Kontext-Begrüßung), kein Fehler."""
    from boerdi.services.usage_analytics import session_usage

    async def szenario(factory):
        async with factory() as s:
            return await session_usage(s, "gibt-es-nicht")

    ergebnis = _lauf(db, szenario)
    assert ergebnis["empty"] is True
    assert ergebnis["calls"] == 0 and ergebnis["prompt_tokens"] == 0
    assert ergebnis["models"] == []
    assert ergebnis["amount"] is None


# ── Zeitraum ────────────────────────────────────────────────────────────

def test_zeitraum_filtert_zwei_zuege_auseinander(db, keine_preise) -> None:
    from boerdi.services.usage_analytics import period_usage

    async def szenario(factory):
        await _saee(factory, "k4-zeit", [
            {"model": "a", "prompt_tokens": 11, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": _JAN},
            {"model": "a", "prompt_tokens": 22, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": _JAN + timedelta(days=40)},
        ])
        async with factory() as s:
            frueh = await period_usage(s, _JAN - timedelta(days=1),
                                       _JAN + timedelta(days=1))
            spaet = await period_usage(s, _JAN + timedelta(days=39),
                                       _JAN + timedelta(days=41))
            beide = await period_usage(s, _JAN - timedelta(days=1),
                                       _JAN + timedelta(days=41))
            return frueh, spaet, beide

    frueh, spaet, beide = _lauf(db, szenario)
    assert frueh["prompt_tokens"] == 11
    assert spaet["prompt_tokens"] == 22
    assert beide["prompt_tokens"] == 33


def test_leerer_zeitraum_liefert_nullen_und_sagt_dass_er_leer_ist(db, keine_preise) -> None:
    """Ausdrückliche Forderung des Plans. Nullen allein wären nicht
    unterscheidbar von „hat nichts gekostet"."""
    from boerdi.services.usage_analytics import period_usage

    async def szenario(factory):
        async with factory() as s:
            return await period_usage(s, datetime(2000, 1, 1, tzinfo=UTC),
                                      datetime(2000, 1, 2, tzinfo=UTC))

    ergebnis = _lauf(db, szenario)
    assert ergebnis["empty"] is True
    assert ergebnis["calls"] == 0
    assert ergebnis["prompt_tokens"] == 0
    assert ergebnis["models"] == []


# ── Preise ──────────────────────────────────────────────────────────────

def test_gepflegter_preis_ergibt_einen_betrag(db, monkeypatch) -> None:
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 3.0, "cached_input": 0.3, "output": 15.0}}))

    async def szenario(factory):
        await _saee(factory, "k4-preis", [
            {"model": "a", "prompt_tokens": 1_000_000, "cached_tokens": 400_000,
             "completion_tokens": 200_000, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await usage_analytics.session_usage(s, "k4-preis")

    ergebnis = _lauf(db, szenario)
    # Dasselbe Beispiel wie in test_pricing, hier durch die ganze Kette.
    assert ergebnis["amount"] == "4.92"
    assert ergebnis["currency"] == "EUR"
    assert ergebnis["price_unavailable"] == []
    assert ergebnis["models"][0]["amount"] == "4.92"


def test_betrag_ist_eine_zeichenkette_und_kein_gleitkommawert(db, monkeypatch) -> None:
    """Der Betrag verlässt den Server als Text. Als JSON-Zahl würde aus
    13,27743099 wieder 13,277430990000001 — die ganze Decimal-Rechnung wäre
    auf dem letzten Meter verloren."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 27.29, "cached_input": 0.0, "output": 0.0}}))

    async def szenario(factory):
        await _saee(factory, "k4-text", [
            {"model": "a", "prompt_tokens": 486_531, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await usage_analytics.session_usage(s, "k4-text")

    betrag = _lauf(db, szenario)["amount"]
    assert isinstance(betrag, str)
    assert betrag == "13.27743099"


def test_grosse_betraege_kommen_nicht_in_wissenschaftlicher_schreibweise(
    db, monkeypatch,
) -> None:
    """Gemessen 2026-08-11: ``Decimal('100').normalize()`` ist ``1E+2``. Ohne
    das ``format(…, 'f')`` daneben stünde genau das im JSON und im Studio."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 10.0, "cached_input": 0.0, "output": 0.0}}))

    async def szenario(factory):
        await _saee(factory, "k4-gross", [
            {"model": "a", "prompt_tokens": 10_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await usage_analytics.session_usage(s, "k4-gross")

    betrag = _lauf(db, szenario)["amount"]
    assert betrag == "100"
    assert "E" not in betrag and "e" not in betrag


def test_ohne_gepflegten_preis_kein_betrag_sondern_die_modellnamen(db, keine_preise) -> None:
    from boerdi.services.usage_analytics import session_usage

    async def szenario(factory):
        await _saee(factory, "k4-ohne", [
            {"model": "a", "prompt_tokens": 100, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1},
            {"model": "b", "prompt_tokens": 100, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await session_usage(s, "k4-ohne")

    ergebnis = _lauf(db, szenario)
    assert ergebnis["amount"] is None
    assert ergebnis["price_unavailable"] == ["a", "b"]
    assert all(m["amount"] is None for m in ergebnis["models"])


def test_ungepflegte_tafel_gilt_nicht_als_kaputt(db, keine_preise) -> None:
    """Der Normalfall — frisch installiert, nichts gepflegt. Stünde hier
    „kaputt", verlöre der Merker seinen Wert."""
    from boerdi.services.usage_analytics import session_usage

    async def szenario(factory):
        await _saee(factory, "k4-heil", [
            {"model": "a", "prompt_tokens": 100, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await session_usage(s, "k4-heil")

    assert _lauf(db, szenario)["price_config_broken"] is False


def test_kaputte_tafel_sagt_das_und_meldet_nicht_nur_keinen_preis(db, monkeypatch) -> None:
    """Ohne diesen Merker sieht die Redaktion nach einem YAML-Tippfehler
    denselben Bildschirm wie bei einer nie gepflegten Tafel — Strich plus
    „für kein Modell ein Preis". Der Grund stünde nur im Log."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: None)

    async def szenario(factory):
        await _saee(factory, "k4-kaputt", [
            {"model": "a", "prompt_tokens": 100, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await usage_analytics.session_usage(s, "k4-kaputt")

    ergebnis = _lauf(db, szenario)
    assert ergebnis["price_config_broken"] is True
    # Die Zahlen bleiben trotzdem stehen: der Verbrauch ist gemessen, nur der
    # Preis fehlt. Ein 500 wäre hier die falsche Antwort.
    assert ergebnis["prompt_tokens"] == 100
    assert ergebnis["amount"] is None


def test_teilweise_gepflegt_nennt_die_luecke_beim_namen(db, monkeypatch) -> None:
    """Der Betrag deckt nur die bepreisten Modelle. Ohne die Liste daneben
    läse man ihn als Gesamtsumme."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 2.0, "cached_input": 0.0, "output": 0.0}}))

    async def szenario(factory):
        await _saee(factory, "k4-teil", [
            {"model": "a", "prompt_tokens": 1_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1},
            {"model": "b", "prompt_tokens": 5_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await usage_analytics.session_usage(s, "k4-teil")

    ergebnis = _lauf(db, szenario)
    assert ergebnis["amount"] == "2"
    assert ergebnis["price_unavailable"] == ["b"]


# ── Teuerste Sitzungen (K5a) ────────────────────────────────────────────
#
# Nur beim Zeitraum, nicht bei der Einzelsitzung: „die teuersten Sitzungen
# dieser einen Sitzung" ergibt keinen Satz. Die Antwortform je Eintrag ist
# dieselbe wie oben, damit die Ansicht EINEN Formatierungsweg hat.

def test_zeitraum_nennt_die_teuersten_sitzungen_zuerst(db, monkeypatch) -> None:
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 1.0, "cached_input": 0.0, "output": 0.0}}))

    async def szenario(factory):
        for name, token in (("k5-klein", 1_000_000), ("k5-gross", 3_000_000),
                            ("k5-mittel", 2_000_000)):
            await _saee(factory, name, [
                {"model": "a", "prompt_tokens": token, "cached_tokens": 0,
                 "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
                 "created_at": _JAN}])
        async with factory() as s:
            return await usage_analytics.period_usage(
                s, _JAN - timedelta(days=1), _JAN + timedelta(days=1))

    # Gefiltert, weil alle Tests dieselbe Modul-Datenbank teilen: zugesagt ist
    # die Rangfolge UNTER diesen dreien, nicht ihre Nachbarschaft.
    zeilen = [z for z in _lauf(db, szenario)["sessions"]
              if z["session_id"].startswith("k5-")]

    assert [z["session_id"] for z in zeilen] == ["k5-gross", "k5-mittel", "k5-klein"]
    assert [z["amount"] for z in zeilen] == ["3", "2", "1"]
    assert zeilen[0]["calls"] == 1
    assert zeilen[0]["prompt_tokens"] == 3_000_000


def test_ohne_preise_ordnen_die_sitzungen_nach_token(db, keine_preise) -> None:
    """Der ausgelieferte Seed pflegt KEINE Preise. Nach Betrag zu sortieren
    hiesse dann, gar nicht zu sortieren — die Liste wäre beim ersten Blick
    auf die Anlage nutzlos, also genau dann, wenn man sie zuerst öffnet."""
    from boerdi.services.usage_analytics import period_usage

    # Die Kennungen laufen der Erwartung ABSICHTLICH zuwider: alphabetisch
    # käme „a" zuerst, nach Token „b". Mit sprechenden Namen („gross"/„klein")
    # war dieser Test in der Rot-Probe grün geblieben — die Kennung ist der
    # letzte Rang, und sie hätte hier zufällig dasselbe Ergebnis geliefert.
    async def szenario(factory):
        for name, token in (("k5o-a-wenig", 10), ("k5o-b-viel", 900)):
            await _saee(factory, name, [
                {"model": "a", "prompt_tokens": token, "cached_tokens": 0,
                 "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
                 "created_at": _JAN}])
        async with factory() as s:
            return await period_usage(s, _JAN - timedelta(days=1),
                                      _JAN + timedelta(days=1))

    zeilen = [z for z in _lauf(db, szenario)["sessions"]
              if z["session_id"].startswith("k5o-")]
    assert [z["session_id"] for z in zeilen] == ["k5o-b-viel", "k5o-a-wenig"]
    assert all(z["amount"] is None for z in zeilen)
    assert zeilen[0]["price_unavailable"] == ["a"]


def test_eine_sitzung_mit_zwei_modellen_ist_eine_zeile(db, monkeypatch) -> None:
    """Die Modelltabelle gruppiert je Modell, diese Liste je Sitzung — sonst
    erschiene dieselbe Sitzung zweimal und ihre Kosten wären halbiert."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 1.0, "cached_input": 0.0, "output": 0.0},
           "b": {"input": 4.0, "cached_input": 0.0, "output": 0.0}}))

    async def szenario(factory):
        await _saee(factory, "k5-zwei", [
            {"model": "a", "prompt_tokens": 1_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 2,
             "created_at": _JAN},
            {"model": "b", "prompt_tokens": 1_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 3,
             "created_at": _JAN}])
        async with factory() as s:
            return await usage_analytics.period_usage(
                s, _JAN - timedelta(days=1), _JAN + timedelta(days=1))

    zeilen = [z for z in _lauf(db, szenario)["sessions"]
              if z["session_id"] == "k5-zwei"]
    assert len(zeilen) == 1
    assert zeilen[0]["calls"] == 5
    assert zeilen[0]["prompt_tokens"] == 2_000_000
    assert zeilen[0]["amount"] == "5"


def test_teilweise_bepreiste_sitzung_nennt_ihre_luecke(db, monkeypatch) -> None:
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        **{"a": {"input": 1.0, "cached_input": 0.0, "output": 0.0}}))

    async def szenario(factory):
        await _saee(factory, "k5-teil", [
            {"model": "a", "prompt_tokens": 1_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": _JAN},
            {"model": "z", "prompt_tokens": 9_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": _JAN}])
        async with factory() as s:
            return await usage_analytics.period_usage(
                s, _JAN - timedelta(days=1), _JAN + timedelta(days=1))

    zeile = next(z for z in _lauf(db, szenario)["sessions"]
                 if z["session_id"] == "k5-teil")
    assert zeile["amount"] == "1"
    assert zeile["price_unavailable"] == ["z"]


def test_die_sitzungsliste_ist_gedeckelt(db, keine_preise) -> None:
    """Ein Monat kann Tausende Sitzungen haben; die Ansicht zeigt die Spitze."""
    from boerdi.services.usage_analytics import _TOP_SESSIONS, period_usage

    stunde = _JAN + timedelta(days=200)

    async def szenario(factory):
        for i in range(_TOP_SESSIONS + 1):
            await _saee(factory, f"k5d-{i:02d}", [
                {"model": "a", "prompt_tokens": (i + 1) * 10, "cached_tokens": 0,
                 "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
                 "created_at": stunde}])
        async with factory() as s:
            return await period_usage(s, stunde - timedelta(days=1),
                                      stunde + timedelta(days=1))

    ergebnis = _lauf(db, szenario)
    assert len(ergebnis["sessions"]) == _TOP_SESSIONS
    # Die kleinste fällt heraus, die Summen oben bleiben vollständig.
    assert "k5d-00" not in [z["session_id"] for z in ergebnis["sessions"]]
    assert ergebnis["prompt_tokens"] == sum(
        (i + 1) * 10 for i in range(_TOP_SESSIONS + 1))


def test_die_sitzungsliste_haelt_sich_an_den_zeitraum(db, keine_preise) -> None:
    from boerdi.services.usage_analytics import period_usage

    async def szenario(factory):
        await _saee(factory, "k5-drin", [
            {"model": "a", "prompt_tokens": 5, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": _JAN + timedelta(days=300)}])
        await _saee(factory, "k5-draussen", [
            {"model": "a", "prompt_tokens": 5000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": _JAN + timedelta(days=400)}])
        async with factory() as s:
            return await period_usage(s, _JAN + timedelta(days=299),
                                      _JAN + timedelta(days=301))

    namen = [z["session_id"] for z in _lauf(db, szenario)["sessions"]]
    assert namen == ["k5-drin"]


def test_die_einzelsitzung_fuehrt_keine_sitzungsliste(db, keine_preise) -> None:
    """„Die teuersten Sitzungen dieser Sitzung" ist keine Frage."""
    from boerdi.services.usage_analytics import session_usage

    async def szenario(factory):
        await _saee(factory, "k5-einzeln", [
            {"model": "a", "prompt_tokens": 5, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1}])
        async with factory() as s:
            return await session_usage(s, "k5-einzeln")

    assert "sessions" not in _lauf(db, szenario)


def test_bekannte_kosten_schlagen_viele_token(db, monkeypatch) -> None:
    """Eine billige, aber bepreiste Sitzung steht über einer token-schweren
    ohne Preis. Sonst führte die Liste eine Sitzung an, von der niemand weiss,
    was sie gekostet hat — und der Betrag daneben wäre nicht ihrer."""
    from boerdi.services import usage_analytics

    monkeypatch.setattr(usage_analytics, "load_pricing", lambda: _tafel(
        # Nur Ausgabe bepreist; die billige Sitzung verbraucht nur Eingabe und
        # kommt darum auf GENAU 0 — der Gleichstand, den der Rang auflösen muss.
        **{"a": {"input": 0.0, "cached_input": 0.0, "output": 7.0}}))
    spaet = _JAN + timedelta(days=500)

    async def szenario(factory):
        await _saee(factory, "k5r-bepreist", [
            {"model": "a", "prompt_tokens": 10, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": spaet}])
        await _saee(factory, "k5r-unbekannt", [
            {"model": "z", "prompt_tokens": 9_000_000, "cached_tokens": 0,
             "completion_tokens": 0, "reasoning_tokens": 0, "calls": 1,
             "created_at": spaet}])
        async with factory() as s:
            return await usage_analytics.period_usage(
                s, spaet - timedelta(days=1), spaet + timedelta(days=1))

    zeilen = _lauf(db, szenario)["sessions"]
    assert [z["session_id"] for z in zeilen] == ["k5r-bepreist", "k5r-unbekannt"]
    assert zeilen[0]["amount"] == "0"
    assert zeilen[1]["amount"] is None
