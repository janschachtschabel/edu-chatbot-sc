"""Content-type intent classification (whole-module verbatim port of ALT
``chat_content_types.py``): reads the wanted resource types out of a user message
(plus accumulated entities) and matches cards against them. Stateless keyword/string
logic — no I/O, no config → ``domain/``.

Produces the ``wanted_content_types`` set consumed by ``domain/cards/{normalize,select}``
and ``services/card_pipeline``; feeds the type-focus path in the response finalizer.

**NEU-Portierung:** the module has zero app imports and was copied byte-for-byte
from ALT. Deliberate deviations since: bilingual keywords (C1-f2c-b), „Sammlung"
is no content type (2026-08-16), and a ``material_typ`` never becomes a raw
filter word (2026-09-27).
"""

from __future__ import annotations

import re
from typing import Any

# Mapping von User-Stichworten zu kanonischen Substrings, die in den
# Card-Feldern ``learning_resource_types`` matchen sollten. WLO emittiert
# diese Labels mit Capitalisation (z.B. ``['Video']``, ``['Arbeitsblatt']``),
# Match läuft case-insensitive via ``substring in lower(blob)``.
#
# **C1-f2c-b: die Stichwörter sind zweisprachig, der kanonische Schlüssel NICHT.**
# Der Schlüssel ist kein blosser Name — er geht als ``learningResourceType`` in
# die WLO-Suche (``services/prefetch.py:250``) und wird unten in
# ``_card_matches_wanted_types`` als Teilzeichenkette gegen die deutschen
# Labels der Karte gehalten. Übersetzt träfe er nie; dieselbe Doppelrolle wie
# beim Typ-Label in C1-f2b3. Nur die linke Seite, das was der Nutzer schreibt,
# wächst also um englische Wörter.
_CONTENT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "video":          ("video", "videos"),
    "arbeitsblatt":   ("arbeitsblatt", "arbeitsblätter", "arbeitsblaetter",
                       "worksheet", "worksheets", "work sheet"),
    "übung":          ("übung", "uebung", "übungen", "uebungen",
                       "exercise", "exercises", "practice task"),
    "quiz":           ("quiz", "test", "tests", "quizzes"),
    "audio":          ("audio", "podcast", "podcasts", "hörspiel", "hoerspiel",
                       "audio play", "radio play"),
    "präsentation":   ("präsentation", "praesentation", "präsentationen", "praesentationen",
                       "presentation", "presentations", "slide deck", "slides"),
    "interaktiv":     ("interaktiv", "interaktive", "interactive"),
    "kurs":           ("kurs", "kurse", "tutorial", "tutorials",
                       "course", "courses"),
    "spiel":          ("lernspiel", "lernspiele", "spiel", "spiele",
                       "learning game", "learning games", "educational game"),
    "grafik":         ("infografik", "grafik", "infographic", "infographics",
                       "graphic", "graphics"),
}


#: Stichwörter, die nur am Wortende zählen: als ganzes Wort oder als Ende eines
#: Kompositums („Klassentest“, „Onlinekurs“, „Rollenspiel“). Als Teilzeichenkette
#: trafen sie Alltagswörter — „testen“ und „Testnachricht“ wurden zum Quiz (Paket
#: 18B). Ein englisches „test“ als eigenes Wort bleibt ein Quiz: „Test“ ist auch
#: das deutsche Wort dafür.
_NUR_AM_WORTENDE: frozenset[str] = frozenset({"test", "tests", "spiel", "spiele", "kurs",
                                              "kurse"})

#: Wörter, die auf ein solches Stichwort enden und doch keinen Medientyp meinen
#: („Protest“ war ein Quiz, „Beispiel“ ein Spiel, „Exkurs“ ein Kurs).
_KEIN_MEDIENTYP: tuple[str, ...] = (
    "protest", "protests", "attest", "attests", "contest", "contests",
    "latest", "greatest", "fastest", "shortest", "smartest", "brightest",
    "beispiel", "beispiele", "schauspiel", "schauspiele", "zusammenspiel",
    "exkurs", "exkurse", "diskurs", "diskurse", "konkurs", "konkurse",
    "wechselkurs", "wechselkurse",
)


def _kommt_vor(stichwort: str, text: str) -> bool:
    """Steht ``stichwort`` in der Nachricht ``text``? Teilzeichenkette, außer für
    :data:`_NUR_AM_WORTENDE` — dort nur am Ende eines Worts, das nicht in
    :data:`_KEIN_MEDIENTYP` steht."""
    if stichwort not in _NUR_AM_WORTENDE:
        return stichwort in text
    return any(not wort.endswith(_KEIN_MEDIENTYP)
               for wort in re.findall(rf"(?<!\w)\w*{re.escape(stichwort)}(?!\w)", text))


#: Medientyp-Wörter, die die Sammlung SELBST meinen und keinen Inhalt darin.
#:
#: Sie stehen bewusst NICHT in :data:`_CONTENT_TYPE_KEYWORDS`: dort ist jeder
#: Eintrag ein ``resourceType``, nach dem sich Einzelinhalte filtern lassen —
#: „Sammlung" ist keiner, sondern die Gattung darüber. Ein Test hält fest, dass
#: die beiden Kataloge sich nicht überschneiden.
_SAMMLUNGS_MEDIENTYPEN: frozenset[str] = frozenset({
    "sammlung", "sammlungen", "themenseite", "themenseiten",
})


def medientyp_meint_sammlungen(medientyp: object) -> bool:
    """Meint dieser Medientyp die Sammlung selbst statt eines Inhalts darin?

    **Wofür.** ``response_tool_selection`` nimmt bei einem gesetzten Medientyp
    die Sammlungs- und Themenseiten-Suche aus der Werkzeugliste, weil sich
    Sammlungen nicht nach ``resourceType`` filtern lassen — die Inhaltssuche ist
    dann der einzig richtige Weg. Genau diese Begründung dreht sich um, sobald
    der Medientyp die Sammlung SELBST benennt.

    Live gemessen 2026-08-16: „Suche mir Sammlungen zum Thema Optik" ergab
    ``medientyp='Sammlung'``, worauf ``search_wlo_all``,
    ``search_wlo_collections`` und ``search_wlo_topic_pages`` verschwanden. Die
    Suche lief als Inhaltssuche mit ``learningResourceType='Sammlung'`` und
    brachte keine einzige Sammlungskarte — womit auch die Skill-Notiz
    (``domain/skill_precedence.merke_skill_sammlung``) leer blieb und der
    Vorrang der freigegebenen Anleitungen nicht griff. Derselbe Satz lief eine
    halbe Stunde vorher normal durch; die Ableitung des Medientyps schwankt.

    Fremdbeschrieben: der Wert kommt aus der LLM-Klassifikation und darf jede
    Form haben.
    """
    if not isinstance(medientyp, str):
        return False
    return medientyp.strip().casefold() in _SAMMLUNGS_MEDIENTYPEN


def _user_wants_specific_content_type(message: str) -> bool:
    """Heuristik: fragt der User nach einem konkreten Material-Format?

    Wenn der User „Such mir ein Arbeitsblatt zu …" oder „Hast du Videos
    zu …" schreibt, will er Einzelinhalte — keine kuratierten Sammlungen.
    Dann kehren wir in der Inline-Link-Reihenfolge die Standardgruppierung
    um (Einzel zuerst statt Themenseite zuerst).
    """
    msg = (message or "").lower()
    for keywords in _CONTENT_TYPE_KEYWORDS.values():
        if any(_kommt_vor(kw, msg) for kw in keywords):
            return True
    return False


def _extract_wanted_content_types(message: str) -> set[str]:
    """Welche konkreten Material-Typen hat der User in der Nachricht
    erwähnt? Returns lower-case substrings, die in
    ``card.learning_resource_types`` matchen sollten — z.B. ``{"video"}``
    bei „Hast du Videos zur …?" oder ``{"arbeitsblatt"}`` bei
    „Such mir Arbeitsblätter zu …".

    Returns leere Menge, wenn der User keinen Typ-Fokus ausgedrückt hat.
    """
    msg = (message or "").lower()
    wanted: set[str] = set()
    for canonical, keywords in _CONTENT_TYPE_KEYWORDS.items():
        if any(_kommt_vor(kw, msg) for kw in keywords):
            wanted.add(canonical)
    return wanted


def als_text(wert: object) -> str:
    """Ein Entitätswert als Text. Der Klassifikator liefert Entitäten untypisiert
    (``dict[str, Any]``): eine Liste („Arbeitsblatt oder interaktives Material“)
    ergibt ihren ersten nichtleeren Eintrag, alles andere außer Text ``""``."""
    if isinstance(wert, str):
        return wert.strip()
    return next(iter(als_liste(wert)), "")


def als_liste(wert: object) -> list[str]:
    """Ein Entitätswert als Liste nichtleerer, entdoppelter Texte."""
    if isinstance(wert, str):
        return [wert.strip()] if wert.strip() else []
    if not isinstance(wert, (list, tuple)):
        return []
    werte: list[str] = []
    for w in wert:
        if isinstance(w, str) and w.strip() and w.strip() not in werte:
            werte.append(w.strip())
    return werte


#: Entitäten, die überall als EIN Wert gelesen werden (Werkzeugargumente, Such-URL,
#: Wächter). Ein mehrfacher Medientyp bleibt zusätzlich als ``medientypen`` erhalten.
_EINZELWERT_ENTITAETEN = ("medientyp", "fach", "stufe", "bildungsstufe", "thema", "topic",
                          "lizenz")


def _ist_zahl(wert: object) -> bool:
    """``int``/``float`` — aber kein ``bool`` (in Python eine Unterklasse von ``int``)."""
    return isinstance(wert, (int, float)) and not isinstance(wert, bool)


def _zahl_als_text(wert: float) -> str:
    """``7`` und ``7.0`` → ``"7"`` (Review 19-5, 9), ``5.5`` → ``"5.5"``."""
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    return str(wert)


def normalisiere_entitaeten(entities: dict[str, Any]) -> dict[str, Any]:
    """Listen in Einzelwert-Entitäten auflösen (Paket 18B).

    Bisher lief eine Liste unverändert bis in die MCP-Argumente (-32602) und in den
    Anti-Halluzinations-Wächter (``list.strip``). Jetzt gilt der erste Wert; ein
    mehrfacher Medientyp steht zusätzlich vollständig in ``medientypen``, damit die
    Suche alle Typen abfragt. Leere Listen fallen weg, Texte bleiben unverändert.

    Zahlen (``"stufe": 7``) werden zu Text, auch in Listen (Paket 19, Audit N-24) — seit 18B
    fielen sie still weg, davor liefen sie weiter. Wahrheitswerte, ``None`` und Zuordnungen
    sind kein Entitätswert und fallen wie bisher weg."""
    aus = dict(entities)
    for schluessel in _EINZELWERT_ENTITAETEN:
        if schluessel not in aus or isinstance(aus[schluessel], str):
            continue
        roh = aus[schluessel]
        if _ist_zahl(roh):
            aus[schluessel] = _zahl_als_text(roh)
            continue
        if isinstance(roh, (list, tuple)):
            roh = [_zahl_als_text(w) if _ist_zahl(w) else w for w in roh]
        werte = als_liste(roh)
        if not werte:
            aus.pop(schluessel)
            continue
        aus[schluessel] = werte[0]
        if schluessel == "medientyp" and len(werte) > 1:
            aus["medientypen"] = werte
    return aus


def _resolve_wanted_content_types(
    message: str,
    session_entities: dict | None = None,
    classification_entities: dict | None = None,
) -> set[str]:
    """Welle C Sprint 6 Hotfix — Vollständiger Type-Filter aus 3 Quellen.

    Zieht den Material-Typ-Wunsch aus:
      1. Aktueller User-Nachricht ("nur videos zeigen" → {"video"})
      2. ``classification.entities.medientyp`` (frisch vom Classifier)
      3. ``session_state.entities.medientyp`` (aus vorherigem Turn akkumuliert)

    Damit überlebt der Filter ein Follow-up wie „nur Videos zeigen"
    auch wenn der Classifier den medientyp nicht erneut extrahiert hat
    (weil das alte session-Wissen bereits präsent ist).

    User-Bug-Report Sprint 6: Ohne diesen Resolver landete der Bot bei
    „nur Videos zeigen" auf M12 und zeigte trotzdem Sammlungen
    statt nur Videos.
    """
    wanted = _extract_wanted_content_types(message)

    for src in (classification_entities, session_entities):
        if not isinstance(src, dict):
            continue
        # Paket 18B: auch mehrere Typen (``medientypen`` oder eine Liste).
        medientypen = als_liste(src.get("medientypen")) + als_liste(src.get("medientyp"))
        aus_medientyp = bool(medientypen)
        for mt in dict.fromkeys(medientypen or als_liste(src.get("material_typ"))):
            _uebernimm_typ(wanted, mt, aus_medientyp=aus_medientyp)

    return wanted


def _uebernimm_typ(wanted: set[str], mt: str, *, aus_medientyp: bool) -> None:
    """Einen Typ-Wert aus den Entitäten auf den kanonischen Schlüssel abbilden."""
    # Map auf canonical key — wenn der Wert direkt einem Keyword
    # entspricht (z.B. "Video"), nutze ihn als Filter-String.
    mt_lower = mt.strip().lower()
    # Bevorzuge canonical-Match wenn möglich
    matched = False
    for canonical, keywords in _CONTENT_TYPE_KEYWORDS.items():
        # Teilzeichenkette wie bisher: der Wert IST ein Typwort („Onlinekurs“). Mit der
        # Wortregel der Nachricht fiel er auf das rohe Wort zurück (Review 18).
        if mt_lower == canonical or any(kw in mt_lower for kw in keywords):
            wanted.add(canonical)
            matched = True
            break
    if (not matched and mt_lower and aus_medientyp
            and not medientyp_meint_sammlungen(mt_lower)):
        # Fallback: das raw-Wort als Substring nutzen.
        #
        # NUR für ``medientyp`` (2026-09-27, ST-5-Lesart Befund 3):
        # ``material_typ`` trägt Canvas-Typen aus
        # ``05-canvas/material-types``, kein WLO-Vokabular. „Zusammenfassung"
        # → ``infoblatt`` wurde so ein Filterwort, das in keinem
        # ``learning_resource_types`` steht — der Kartenfilter warf jede
        # Karte weg, in beiden Maschinen. Wo ein Canvas-Typ einem
        # Ressourcentyp entspricht (Quiz, Arbeitsblatt), trifft er oben.
        #
        # NICHT bei „Sammlung"/„Themenseite" (2026-08-16): der Rueckfall
        # macht aus jedem unbekannten Medientyp ein Filterwort, gegen das
        # ``_card_matches_wanted_types`` die ``learning_resource_types``
        # der Karte haelt — und dort steht „sammlung" nie. Live gemessen
        # warf der Filter daraufhin ALLE Karten weg („universal
        # type-filter: 3 -> 0 cards"), obwohl die Suche die Sammlungen
        # gerade gefunden hatte. Der Wunsch „zeig mir Sammlungen" ist kein
        # Typfilter, sondern das Gegenteil eines Inhaltsfilters.
        wanted.add(mt_lower)


def _card_matches_wanted_types(card: Any, wanted: set[str]) -> bool:
    """True, wenn die ``learning_resource_types`` der Card einen der vom
    User gewünschten Typen enthalten. Wenn ``wanted`` leer ist (kein Typ-
    Fokus), gibt's keine Einschränkung → True. Substring-Match auf der
    lowercase-konkatenierten Type-Liste.
    """
    if not wanted:
        return True
    lrt = (card.get("learning_resource_types") if isinstance(card, dict)
           else getattr(card, "learning_resource_types", None))
    if not lrt:
        return False
    blob = " ".join(str(t).lower() for t in lrt if t)
    return any(w in blob for w in wanted)
