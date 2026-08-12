"""01-base/pricing — die Preistafel als redaktionell pflegbarer Bereich (K3).

Preise stehen **je 1 Mio. Token**, so wie die Anbieter sie ausweisen; die
Umrechnung macht ``domain/pricing.py``. Der Schlüssel ist der Modellname, wie
ihn der Anbieter in der Antwort meldet (``resp.model``) — nicht der
konfigurierte Alias, sonst trifft die Tafel bei Aliassen daneben.

**Hier ``float``, gerechnet wird in ``Decimal``.** Das Geld-Typ gehört in
``domain/pricing.py`` (Plan §5.3); auf der Leitung gibt es ihn ohnehin nicht,
YAML wie JSON kennen nur Kommazahlen. Ein ``Decimal``-Feld hier hätte einen
Preis, der beim Bauen sichtbar wurde: pydantic verschemat es als
``anyOf: [number, string]`` mit ``pattern`` — Formen, die der Studio-Typ
``JsonSchema`` bewusst NICHT führt (gemessene Teilmenge), worauf der Editor
laut eigener Politik auf ein JSON-Textfeld zurückfiele. Eine Preistafel, die
man nur noch als JSON tippen kann, verfehlt den Zweck dieses Bereichs.

``ge=0`` ist kein Zierrat: das Studio schreibt über ``PUT /config/data/{area}``
direkt gegen dieses Modell, und ein negativer Preis ergäbe eine Gutschrift
statt einer Rechnung. Der Seed-Import schreibt allerdings **ungeprüfte** Dicts
(``seed_io.import_tree``), deshalb hält ``domain/pricing`` denselben Fall
zusätzlich aus.
"""

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel


class ModelPrice(AreaModel):
    """Preise eines Modells je 1 Mio. Token.

    Alle drei auf 0 heißt **nicht gepflegt** und ausdrücklich nicht „kostenlos"
    — die Auslegung trifft ``domain/pricing.resolve_model_price``.

    Für Reasoning gibt es keinen eigenen Preis: die Anbieter berechnen es zum
    Ausgabepreis, es steckt also schon in ``output``.
    """

    input: float = Field(default=0.0, ge=0)
    cached_input: float = Field(default=0.0, ge=0)
    output: float = Field(default=0.0, ge=0)


class PricingArea(AreaModel):
    """Währung und Preise der Tafel.

    ``currency`` ist ein ISO-4217-Code (drei Buchstaben), keine freie Angabe:
    die Kostenschau reicht ihn an ``Intl.NumberFormat`` weiter, und das wirft
    bei allem anderen einen ``RangeError``, der die ganze Ansicht leerte.
    Der Rückfall dort (Zahl plus roher Code) bleibt für den Weg am Studio
    vorbei — ``seed_io.import_tree`` schreibt ungeprüft, genau wie bei
    ``ge=0``. Gross- und Kleinschreibung ist egal; ``Intl`` nimmt beide.
    """

    currency: str = Field(default="EUR", pattern=r"^[A-Za-z]{3}$")
    models: dict[str, ModelPrice] = {}
