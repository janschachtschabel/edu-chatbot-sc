"""Token + Preistafel → Betrag (K3). Rein: kennt weder DB noch Config-Laden.

Die Rechnung (Plan §5.3):

    Betrag = (prompt − cached) · P_eingabe
           +  cached           · P_cache
           +  completion       · P_ausgabe      # Reasoning ist darin enthalten

**``None`` heißt „Preis nicht gepflegt" und ausdrücklich nicht ``0``.** Ein
stummes ``0`` läse sich als „hat nichts gekostet"; dieselbe Verwechslung hat
schon einmal einen Messwert vorgetäuscht (C2, ``/quality/tight-races``). Wer
den Betrag anzeigt, muss den ``None``-Fall benennen.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from boerdi.domain.config_models.pricing import ModelPrice, PricingArea

# Die Anbieter weisen ihre Preise je 1 Mio. Token aus; die Tafel übernimmt das
# unverändert, damit die Redaktion abtippen statt umrechnen kann.
_JE_MILLION = Decimal(1_000_000)


def _als_decimal(preis: float) -> Decimal:
    """Der Übergang von der Leitung zum Geld-Typ — die einzige Stelle.

    Über ``str``, nicht direkt: ``Decimal(0.1)`` ergäbe das Binärartefakt
    ``0.1000000000000000055511151231257827…``, ``Decimal(str(0.1))`` die
    gemeinte Zahl. (Genau diese Umwandlung nimmt pydantic bei einem
    ``Decimal``-Feld vor — gemessen 2026-08-11; hier steht sie sichtbar da,
    statt in einer Modellzeile zu verschwinden.)
    """
    return Decimal(str(preis))


@dataclass(frozen=True, slots=True)
class TokenCounts:
    """Die Token EINER Verbrauchszeile, so wie sie ``obs/usage.py`` je Modell
    führt — ohne ``reasoning``.

    Dessen Fehlen ist Absicht und der Wächter gegen Doppelberechnung:
    ``reasoning`` steckt bereits in ``completion`` (``extract_usage``), es wird
    nur getrennt **gespeichert**, um sichtbar zu machen, wofür die Ausgabe
    draufging. Wer es hier einführte, hätte es gleich zweimal bezahlt.
    """

    model: str
    prompt: int
    cached: int
    completion: int


def _ist_gepflegt(preis: ModelPrice) -> bool:
    """Ein Eintrag aus lauter Nullen ist eine Lücke, kein Nulltarif.

    Der ausgelieferte Seed steht auf 0,0 (Plan §5.4: ein erfundener Preis wäre
    schlimmer als keiner). Läse man ihn als „0 €", meldete eine frische
    Installation „hat nichts gekostet". Der Preis, den kein Anbieter je
    verlangt, ist damit nicht ausdrückbar — bewusst, für eine interne
    Kostenschau ist das kein Verlust.

    Ein negativer Wert zählt ebenfalls als ungepflegt. Das Studio weist ihn
    schon beim Speichern ab (``ge=0``), aber der Seed-Import schreibt ungeprüft
    (``seed_io.import_tree``) — und eine Gutschrift wäre der stillere Fehler
    von beiden.
    """
    werte = (preis.input, preis.cached_input, preis.output)
    if any(wert < 0 for wert in werte):
        return False
    return any(wert > 0 for wert in werte)


def resolve_model_price(model: str, table: PricingArea) -> ModelPrice | None:
    """Den Preis für einen gemeldeten Modellnamen suchen; ``None`` = nicht
    gepflegt.

    ``resp.model`` trägt oft eine Version (``gpt-5.4-mini-2026-03-01``), die
    Tafel aber den Kurznamen. Gesucht wird darum erst exakt, dann der längste
    passende Präfix — der **an einer ``-``-Grenze enden muss**. Ohne diese
    Grenze bepreiste ein Eintrag ``gpt-5`` stillschweigend auch ``gpt-55``:
    falsches Geld ohne jede Meldung. (Abweichung vom Plan-Wortlaut, der nur
    „längster passender Präfix" sagt.)

    Ein exakter Eintrag ohne Preis fällt **nicht** auf einen kürzeren zurück:
    er ist die ausdrückliche Aussage der Redaktion über dieses Modell.
    """
    name = (model or "").strip()
    if not name:
        return None
    preis = table.models.get(name)
    if preis is None:
        kandidaten = [
            schluessel for schluessel in table.models
            if name.startswith(schluessel) and name[len(schluessel):].startswith("-")
        ]
        if not kandidaten:
            return None
        preis = table.models[max(kandidaten, key=len)]
    return preis if _ist_gepflegt(preis) else None


def cost_for(tokens: TokenCounts, table: PricingArea) -> Decimal | None:
    """Betrag einer Verbrauchszeile, oder ``None`` wenn kein Preis gepflegt ist.

    ``cached`` ist ein „davon"-Wert innerhalb von ``prompt`` und wird deshalb
    abgezogen, nicht addiert. Der Deckel darauf ist kein Zierrat: die Zahlen
    kommen vom Anbieter, und ohne ihn machte ein ``cached > prompt`` die
    Differenz negativ und die Rechnung kleiner.
    """
    preis = resolve_model_price(tokens.model, table)
    if preis is None:
        return None
    prompt = max(0, int(tokens.prompt))
    cached = min(max(0, int(tokens.cached)), prompt)
    completion = max(0, int(tokens.completion))
    return (
        Decimal(prompt - cached) * _als_decimal(preis.input)
        + Decimal(cached) * _als_decimal(preis.cached_input)
        + Decimal(completion) * _als_decimal(preis.output)
    ) / _JE_MILLION
