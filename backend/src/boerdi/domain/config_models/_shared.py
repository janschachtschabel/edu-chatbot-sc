"""Shared bases for area models (P2-1). extra='allow' everywhere — the ALT
loaders tolerate unknown keys, and editors must not 422 on additive fields.

Dazu (S2) die zwei Auszeichnungen, mit denen ein Feld dem Studio sagt, dass es
eine Auswahl verdient statt eines leeren Textfeldes. Sie reisen als
Zusatzschlüssel im JSON-Schema mit, das ``GET /api/config/schema/{area}`` ohnehin
ausliefert — das Studio braucht dafür keine eigene Tabelle. Eine solche Tabelle
wäre auch falsch: ``pattern`` heißt in ``01-base/classify-overrides`` eine
Muster-ID und in ``02-domain/guide-rules`` ein Regex. Was ein Feld bedeutet,
weiß nur das Feld.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AreaModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def Choices(*values: str) -> Any:  # noqa: N802 — wie ``Field``: an der Typangabe gelesen
    """Geschlossener Wertevorrat; das Studio zeigt ein Auswahlfeld.

    Bewusst KEIN ``Literal``: ``PUT /api/config/data/{area}`` validiert gegen das
    Modell, ein ``Literal`` würde also jeden Bestandswert außerhalb der Liste ab
    sofort mit 422 abweisen — womöglich denselben, den ein Redakteur gerade
    korrigieren will. Dies ist eine Bedienhilfe, keine Verschärfung. Damit die
    Liste trotzdem nicht lügt, prüft ein Wächter jeden ausgelieferten Seed-Wert
    gegen sie (``tests/test_config_choices_annotations.py``).

    Verwendung::

        mode: Annotated[str, Choices("off", "smart", "always")] = ""
    """
    return Field(json_schema_extra={"x-choices": list(values)})


def Catalog(name: str) -> Any:  # noqa: N802 — s.o.
    """Verweis auf anderswo Angelegtes; das Studio zeigt eine Vorschlagsliste.

    ``name`` ist einer der Kataloge aus ``api/config_choices.CATALOG_NAMES``.
    Offen und nicht geschlossen: ein RAG-Bereich entsteht durch Einlesen, ein
    Muster durch Anlegen — wer den neuen Namen schon kennt, soll ihn tippen
    dürfen, bevor er im Katalog steht.

    An einer Liste gehört die Auszeichnung an den EINTRAG, nicht an die Liste::

        rag_areas: list[Annotated[str, Catalog("rag_areas")]] | None = None
    """
    return Field(json_schema_extra={"x-catalog": name})
