"""K3 — Preisrechnung (``domain/pricing.py``) und Preistafel als Bereich.

Geld wird in ``Decimal`` gerechnet, nie in ``float``. Die Tests prüfen die drei
Zusagen des Plans (§5.3/§5.4): ein von Hand gerechnetes Beispiel, „Modell nicht
in der Tafel" → ``None`` und **nicht** ``0``, und die Präfix-Auflösung für
versionierte Modellnamen.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.pricing import ModelPrice, PricingArea
from boerdi.domain.pricing import TokenCounts, cost_for, resolve_model_price

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


def _tafel(**modelle: dict) -> PricingArea:
    return PricingArea.model_validate({"currency": "EUR", "models": modelle})


# ── Die Rechnung ────────────────────────────────────────────────────────

def test_rechenbeispiel_von_hand_gerechnet() -> None:
    """1 Mio. Eingabe (davon 400k aus dem Cache) + 200k Ausgabe.

        (1.000.000 − 400.000) / 1e6 · 3,00 =  1,80
                     400.000  / 1e6 · 0,30 =  0,12
                     200.000  / 1e6 · 15,00 = 3,00
                                            = 4,92
    """
    tafel = _tafel(**{"gpt-5.4-mini": {"input": 3.0, "cached_input": 0.3,
                                       "output": 15.0}})
    tokens = TokenCounts(model="gpt-5.4-mini", prompt=1_000_000,
                         cached=400_000, completion=200_000)

    assert cost_for(tokens, tafel) == Decimal("4.92")


def test_cache_wird_vom_eingabepreis_abgezogen_nicht_zusaetzlich_berechnet() -> None:
    """``cached`` steckt IN ``prompt``. Würde es obendrauf gerechnet, käme bei
    voll gecachter Eingabe mehr heraus als ohne Cache — der Cache würde teurer
    statt billiger."""
    tafel = _tafel(**{"m": {"input": 10.0, "cached_input": 1.0, "output": 0.0}})

    ohne = cost_for(TokenCounts("m", prompt=1_000_000, cached=0, completion=0), tafel)
    voll = cost_for(TokenCounts("m", prompt=1_000_000, cached=1_000_000, completion=0),
                    tafel)

    assert ohne == Decimal("10")
    assert voll == Decimal("1")


def test_reasoning_ist_kein_feld_der_rechnung() -> None:
    """Wächter gegen Doppelberechnung: ``reasoning`` ist in ``completion``
    enthalten (``obs/usage.extract_usage``). Ein eigenes Feld hier wäre die
    Einladung, es noch einmal mit dem Ausgabepreis zu multiplizieren."""
    assert set(TokenCounts.__dataclass_fields__) == {
        "model", "prompt", "cached", "completion"}


def test_mehr_cache_als_eingabe_verkleinert_die_rechnung_nicht() -> None:
    """Die Zahlen kommen vom Anbieter, nicht von uns. Ohne Deckel würde
    ``prompt − cached`` negativ und die Rechnung schrumpfte."""
    tafel = _tafel(**{"m": {"input": 10.0, "cached_input": 1.0, "output": 0.0}})

    betrag = cost_for(TokenCounts("m", prompt=1_000_000, cached=5_000_000,
                                  completion=0), tafel)

    assert betrag == Decimal("1")


# ── „Nicht gepflegt" ist None, nicht 0 ──────────────────────────────────

def test_unbekanntes_modell_ist_none_und_nicht_null() -> None:
    tafel = _tafel(**{"gpt-5.4-mini": {"input": 3.0, "cached_input": 0.3,
                                       "output": 15.0}})
    tokens = TokenCounts("ein-fremdes-modell", prompt=1000, cached=0, completion=10)

    assert resolve_model_price("ein-fremdes-modell", tafel) is None
    betrag = cost_for(tokens, tafel)
    assert betrag is None
    assert betrag != Decimal(0)


def test_eintrag_mit_lauter_nullen_gilt_als_ungepflegt() -> None:
    """Der ausgelieferte Seed steht auf 0,0. Läse man das als „0 €", zeigte die
    Auswertung einer frischen Installation „hat nichts gekostet" — genau der
    Fehler, den C2 (``/quality/tight-races``) schon einmal gemacht hat."""
    tafel = _tafel(**{"m": {"input": 0.0, "cached_input": 0.0, "output": 0.0}})

    assert resolve_model_price("m", tafel) is None
    assert cost_for(TokenCounts("m", prompt=1_000_000, cached=0, completion=0),
                    tafel) is None


def test_ein_einziger_gepflegter_preis_genuegt() -> None:
    """Manche Anbieter berechnen die Eingabe, aber nichts fürs Cache-Lesen.
    Solch ein Eintrag ist gepflegt und rechnet."""
    tafel = _tafel(**{"m": {"input": 2.0, "cached_input": 0.0, "output": 0.0}})

    assert cost_for(TokenCounts("m", prompt=1_000_000, cached=0, completion=0),
                    tafel) == Decimal("2")


def test_leerer_modellname_ist_none() -> None:
    tafel = _tafel(**{"m": {"input": 2.0, "cached_input": 0.0, "output": 0.0}})
    assert resolve_model_price("", tafel) is None
    assert cost_for(TokenCounts("", prompt=1000, cached=0, completion=0), tafel) is None


# ── Präfix-Auflösung ────────────────────────────────────────────────────

def test_versionierter_modellname_trifft_den_kurznamen() -> None:
    """``resp.model`` trägt oft ein Datum, die Tafel den Kurznamen."""
    tafel = _tafel(**{"gpt-5.4-mini": {"input": 3.0, "cached_input": 0.3,
                                       "output": 15.0}})

    treffer = resolve_model_price("gpt-5.4-mini-2026-03-01", tafel)

    assert treffer is not None and treffer.input == Decimal("3.0")


def test_der_laengste_passende_praefix_gewinnt() -> None:
    tafel = _tafel(**{
        "gpt-5.4": {"input": 30.0, "cached_input": 3.0, "output": 150.0},
        "gpt-5.4-mini": {"input": 3.0, "cached_input": 0.3, "output": 15.0},
    })

    treffer = resolve_model_price("gpt-5.4-mini-2026-03-01", tafel)

    assert treffer is not None and treffer.input == Decimal("3.0")


def test_praefix_endet_an_der_bindestrich_grenze() -> None:
    """Abweichung vom Plan-Wortlaut („längster passender Präfix"): ohne diese
    Grenze bepreiste der Eintrag ``gpt-5`` stillschweigend auch ``gpt-55-turbo``
    — falsches Geld ohne jede Meldung."""
    tafel = _tafel(**{"gpt-5": {"input": 1.0, "cached_input": 0.0, "output": 0.0}})

    assert resolve_model_price("gpt-55-turbo", tafel) is None
    assert resolve_model_price("gpt-5-mini", tafel) is not None


def test_exakter_treffer_ohne_preis_faellt_nicht_auf_den_kuerzeren_zurueck() -> None:
    """Ein Eintrag ist die ausdrückliche Aussage der Redaktion über dieses
    Modell. Dass er ungepflegt ist, ist eine Auskunft — kein Anlass, den
    gröberen Preis zu nehmen."""
    tafel = _tafel(**{
        "gpt-5.4": {"input": 30.0, "cached_input": 3.0, "output": 150.0},
        "gpt-5.4-mini": {"input": 0.0, "cached_input": 0.0, "output": 0.0},
    })

    assert resolve_model_price("gpt-5.4-mini", tafel) is None
    assert resolve_model_price("gpt-5.4-mini-2026-03-01", tafel) is None


# ── Bereichsmodell ──────────────────────────────────────────────────────

def test_kommazahl_aus_der_tafel_rechnet_ohne_binaerartefakt() -> None:
    """Der Grund für ``Decimal`` — ein gemessenes Paar (2026-08-11):
    486.531 Token zu 27,29 € je Mio. ergeben in ``float``
    13,277430990000001, in ``Decimal`` glatt 13,27743099."""
    tafel = _tafel(**{"m": {"input": 27.29, "cached_input": 0.0, "output": 0.0}})

    betrag = cost_for(TokenCounts("m", prompt=486_531, cached=0, completion=0),
                      tafel)

    assert str(betrag) == "13.27743099"
    assert repr(486_531 * 27.29 / 1_000_000) == "13.277430990000001", (
        "Die Vergleichsmessung selbst ist veraltet"
    )


def test_negativer_preis_wird_beim_speichern_abgewiesen() -> None:
    """Das Studio schreibt über ``PUT /config/data/{area}`` gegen dieses Modell.
    Ein negativer Preis ergäbe eine Gutschrift statt einer Rechnung."""
    with pytest.raises(ValidationError):
        ModelPrice.model_validate({"input": -1.0, "cached_input": 0.0,
                                   "output": 0.0})


def test_negativer_preis_am_studio_vorbei_ergibt_keine_gutschrift() -> None:
    """``seed_io.import_tree`` schreibt ungeprüfte Dicts in die DB — der
    ``ge=0``-Riegel des Studios greift dort nicht. Ein von Hand in die
    YAML getippter Minuspreis darf trotzdem keine Gutschrift erzeugen."""
    tafel = PricingArea.model_construct(currency="EUR", models={
        "m": ModelPrice.model_construct(input=-3.0, cached_input=0.0, output=0.0),
    })

    assert resolve_model_price("m", tafel) is None
    assert cost_for(TokenCounts("m", prompt=1_000_000, cached=0, completion=0),
                    tafel) is None


def test_fehlende_felder_stehen_auf_null_und_damit_ungepflegt() -> None:
    tafel = _tafel(**{"m": {}})
    assert resolve_model_price("m", tafel) is None


# ── Währungscode ────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["EUR", "usd", "Chf"])
def test_dreistelliger_waehrungscode_wird_angenommen(code: str) -> None:
    """Gross/klein ist egal — ``Intl`` nimmt beide, und die Redaktion tippt,
    was sie kennt."""
    assert PricingArea.model_validate({"currency": code, "models": {}}).currency == code


@pytest.mark.parametrize("code", ["EURO", "€", "E", "", "EUR "])
def test_alles_andere_weist_das_studio_beim_speichern_ab(code: str) -> None:
    """Ohne diesen Riegel nimmt ``PUT /config/data/{area}`` „Euro" entgegen,
    und die Kostenschau muss den Fehler danach jedes Mal auffangen: ``Intl``
    wirft bei einem unbrauchbaren Code einen ``RangeError``, der die ganze
    Ansicht leerte. Der Rückfall dort bleibt — geprüft wird trotzdem hier, an
    der Stelle, an der der Wert entsteht."""
    with pytest.raises(ValidationError):
        PricingArea.model_validate({"currency": code, "models": {}})


def test_verkorkster_code_macht_die_tafel_unlesbar_statt_still_falsch(monkeypatch) -> None:
    """``seed_io.import_tree`` schreibt ungeprüfte Dicts — am Studio vorbei
    kann „Euro" also trotzdem im Store landen. Dann ist die Tafel unlesbar und
    sagt das (``price_config_broken``), statt einen Betrag in einer Währung zu
    zeigen, die es nicht gibt."""
    from boerdi.services.config_loader import pricing as loader

    monkeypatch.setattr(loader, "area", lambda _: {"currency": "Euro", "models": {}})

    assert loader.load_pricing() is None


# ── Loader: „kaputt" ist nicht dasselbe wie „ungepflegt" ────────────────

def test_kaputte_tafel_ist_von_einer_ungepflegten_unterscheidbar(monkeypatch) -> None:
    """Beide Fälle enden ohne Preis — aber nicht aus demselben Grund.

    Läsen sie sich gleich, sähe die Redaktion nach einem Tippfehler in der
    YAML genau den Bildschirm, den auch eine frische Installation zeigt: sie
    pflegte nach und wunderte sich. ``seed_io.import_tree`` schreibt
    ungeprüfte Dicts in den Store, der Fall ist also erreichbar.
    """
    from boerdi.services.config_loader import pricing as loader

    monkeypatch.setattr(loader, "area", lambda _: {"models": {"m": "kein Dict"}})

    assert loader.load_pricing() is None


def test_lesbare_aber_leere_tafel_gilt_nicht_als_kaputt(monkeypatch) -> None:
    """Der Normalfall einer frischen Installation: nichts gepflegt, aber
    einwandfrei lesbar."""
    from boerdi.services.config_loader import pricing as loader

    monkeypatch.setattr(loader, "area", lambda _: {"currency": "EUR", "models": {}})

    tafel = loader.load_pricing()

    assert tafel is not None and tafel.models == {}


# ── Seed ────────────────────────────────────────────────────────────────

def test_seed_tafel_validiert_gegen_das_bereichsmodell() -> None:
    import yaml

    roh = yaml.safe_load((_SEEDS / "01-base" / "pricing.yaml").read_text(
        encoding="utf-8"))
    tafel = PricingArea.model_validate(roh)

    assert tafel.currency == "EUR"
    assert tafel.models, "Die ausgelieferte Tafel nennt kein einziges Modell"


def test_ausgelieferte_tafel_behauptet_keinen_preis() -> None:
    """§5.4: alle Seed-Preise stehen auf 0,0. Ein erfundener Preis sähe aus wie
    eine Abrechnung."""
    import yaml

    roh = yaml.safe_load((_SEEDS / "01-base" / "pricing.yaml").read_text(
        encoding="utf-8"))
    tafel = PricingArea.model_validate(roh)

    gepflegt = [name for name in tafel.models
                if resolve_model_price(name, tafel) is not None]
    assert gepflegt == [], f"Seed behauptet Preise für {gepflegt}"


def test_seed_baum_bleibt_mit_der_preistafel_roundtrip_fest(tmp_path: Path) -> None:
    """Wie bei den übrigen Bereichen: importieren, exportieren, erneut
    importieren — strukturgleich."""
    from boerdi.services import seed_io

    erst: dict[str, dict] = {}

    async def put1(area: str, data: dict) -> None:
        erst[area] = data

    asyncio.run(seed_io.import_tree(_SEEDS, put1))
    assert "01-base/pricing" in erst

    out = tmp_path / "roundtrip"
    seed_io.export_tree(erst, out)

    zweit: dict[str, dict] = {}

    async def put2(area: str, data: dict) -> None:
        zweit[area] = data

    asyncio.run(seed_io.import_tree(out, put2))
    assert zweit == erst
