"""Was eine Umwandlung meldet, wenn sie kein Dokument liefert (Paket 4b, A3; Paket 6, B6).

Aus ``umwandeln`` gelöst (Paket 9): den Typ brauchen der Umwandler, der Kindprozess
(``umwandeln_kind``) und der Router (``api/rag_umwandlung``), ohne dass sie einander
importieren müssen.
"""

from __future__ import annotations

#: Vorsilbe für „dieses Format liest der Server nicht“ — in einem
#: :class:`Umwandlungsfehler`; der Router macht daraus 415.
FORMAT_NICHT_LESBAR = "Fehler (Format nicht lesbar)"


class Umwandlungsfehler(str):
    """Der Fehlertext einer Umwandlung, kein Dokument (Paket 4b, A3).

    Die Umwandler bleiben ALT-treu und melden Fehler als Text. Am Präfix
    „Fehler“ ließ sich der aber nicht von einem Dokument unterscheiden, das so
    beginnt („Fehlerkultur …“): Der Router wies es mit 400 ab. Der Typ sagt es,
    der Text bleibt derselbe.

    Seit Paket 6 (B6) trägt er dazu die Art; daran wählt der Router Status und
    Satz in der Sprache des Studios. Vorher ging der deutsche Text roh hinaus,
    und ein fehlendes Paket im Image hieß 400 statt Fehler des Servers.

    * ``datei`` — die Datei oder Seite ließ sich nicht umwandeln (400)
    * ``format`` — kein Wandler für das Format im Image (415)
    * ``server`` — ein Paket fehlt im Image (500)
    * ``adresse`` — die Adresse ist nicht erlaubt, auch ein Umleitungs-Schritt (400)
    * ``abruf`` — die Seite ließ sich nicht laden (400)
    * ``zu_gross`` / ``zu_langsam`` — Deckel bzw. Frist des Abrufs (400, ``wert``)
    * seit Paket 9 die Grenzen der Umwandlung selbst (400, ``wert``):
      ``entpackt_zu_gross`` (MB), ``zu_viele_seiten`` (Seiten),
      ``umwandlung_zu_langsam`` (s), ``umwandlung_zu_gross`` (MB Speicher), seit
      Paket 10 ``text_zu_lang`` (Millionen Zeichen)

    ``detail`` ist der technische Rest für die Klammer im Satz, ``wert`` die
    Grenze. Picklebar (der Kindprozess schickt ihn zurück): ``str`` mit ``__dict__``.
    """

    art: str
    detail: str
    wert: float | None

    def __new__(cls, text: str, art: str = "datei", detail: str = "",
                wert: float | None = None) -> Umwandlungsfehler:
        fehler = super().__new__(cls, text)
        fehler.art = art
        fehler.detail = detail
        fehler.wert = wert
        return fehler


def kurz(fehler: BaseException) -> str:
    """Der lesbare Rest einer Ausnahme — manche haben keinen Text."""
    return str(fehler) or type(fehler).__name__


def format_nicht_lesbar(fehler: Exception) -> bool:
    """Scheiterte markitdown am Format statt an der Datei?

    ``UnsupportedFormatException``: kein Wandler für das Format.
    ``MissingDependencyException``: der Wandler fehlt im Image; markitdown hüllt
    sie in eine ``FileConversionException`` und nennt sie in ``attempts``.
    """
    from markitdown._exceptions import (
        FileConversionException,
        MissingDependencyException,
        UnsupportedFormatException,
    )

    if isinstance(fehler, (UnsupportedFormatException, MissingDependencyException)):
        return True
    if isinstance(fehler, FileConversionException):
        return any(
            versuch.exc_info and issubclass(versuch.exc_info[0], MissingDependencyException)
            for versuch in fehler.attempts or ())
    return False
