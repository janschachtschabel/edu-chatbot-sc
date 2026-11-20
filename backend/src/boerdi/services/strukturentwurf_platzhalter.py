"""Ein Thema, das nur ein Platzhalter für „die Dateien der Person“ ist (Durchtest themenbaum r2-1,
Paket K, 19.11.) — aus ``strukturentwurf_dienst`` verschoben (Review Paket A, zweites Review,
MINOR 7), verhaltensgleich."""

from __future__ import annotations

from typing import Final

#: Durchtest themenbaum r2-1 bzw. Paket K (19.11.): Wörter, die bei ``aus_inhalten`` nur auf die
#: Dateien der Person zeigen — ein Thema, das ein solches Wort trägt und SONST nur Füllwörter, ist
#: ein Platzhalter („Themen aus den bereitgestellten eigenen Dateien“), kein Sachgebiet.
_PLATZHALTER_HINWEIS: Final = frozenset({
    "dateien", "datei", "bereitgestellt", "bereitgestellte", "bereitgestellten", "hochgeladen",
    "hochgeladenen", "inhalte", "inhalten", "materialien", "unterlagen", "person",
    "files", "file", "provided", "uploaded", "contents", "materials"})
_PLATZHALTER_FUELLWORT: Final = frozenset({
    "themen", "thema", "aus", "den", "der", "die", "des", "dem", "von", "zu", "mit", "und",
    "meine", "meinen", "meiner", "eigene", "eigenen", "deine", "deinen", "ihre", "ihren",
    "topics", "topic", "from", "the", "my", "own", "your", "of", "and"})


def platzhalter_thema(thema: str | None) -> bool:
    """Ist ``thema`` nur ein Platzhalter für „die Dateien der Person“ — ein Hinweiswort
    (:data:`_PLATZHALTER_HINWEIS`) und kein Sachbegriff daneben (nur Füllwörter)?"""
    woerter = {w.strip(".,;:!?()[]„“\"'«»-").casefold() for w in str(thema or "").split()} - {""}
    return bool(woerter & _PLATZHALTER_HINWEIS) and woerter <= (
        _PLATZHALTER_HINWEIS | _PLATZHALTER_FUELLWORT)
