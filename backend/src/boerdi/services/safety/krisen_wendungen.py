"""Krisen-Wendungen: Andeutungen, die die Moderation nicht trennt (Paket 8, K2).

Gemessen 2026-10-09 (``evals/moderation_messung.py``, 28 Andeutungen, 28 Gegenproben
aus dem Unterricht): Bei der Schwelle 0,25 erkennt die Moderation sechzehn
Andeutungen, die eingebauten Muster des Gates zwei. Zwölf fielen durch beide Stufen —
meist mit einer typischen Wendung („Niemand würde mich vermissen“, „Ich sehe keinen
Ausweg mehr“), die die Moderation zwischen 0,005 und 0,16 bewertet. Dort liegt auch
Unterricht über Suizid in der Literatur (Romeo und Julia: 0,158), eine niedrigere
Schwelle hätte also nur Fehlalarme gebracht. Auf ``b-api-academiccloud`` gibt es
keine Moderation; dort ist das Gate der einzige Boden.

Jede Wendung ist **selbstbezogen und eng gefasst**: „ich sehe keinen Ausweg mehr“,
nicht „sieht keinen Ausweg“ (eine Romanfigur); „ich will sterben“, nicht „Faust will
sterben“. Geprüft an den Gegenproben der Messung (``tests/test_krisen_wendungen.py``).
Gelesen wird wie im Gate (``normalize_for_matching``: NFKC, ohne Format-Zeichen,
klein); Umlaute gelten auch ausgeschrieben.

Abschiede („ich verabschiede mich hiermit von allen“, „mein Abschiedsbrief ist fertig“)
zählen nur ohne gewöhnlichen Anlass (Beruf, Ruhestand, Ferien) in derselben Nachricht:
Lehrkräfte gehen in den Ruhestand und lassen den Abschiedsbrief an die Kollegen
gegenlesen (Review Paket 8, Gegenproben im Test).

Fest eingebaut wie die ALT-Muster, nicht im Studio abschaltbar: ein Boden, den eine
Einstellung nicht senken darf. Eigene Wendungen ergänzt das Studio über
``extra_crisis_terms``. Die bewusst offenen Fälle (verhüllte Andeutungen wie „ich habe
alles vorbereitet“) stehen im Test.
"""

from __future__ import annotations

import re
from typing import Final

_WUERDE = r"(?:würde|wuerde)"
_WAERE = r"(?:wäre|waere)"


def _selbst(verb: str) -> str:
    """„ich <verb>“ — oder, mit etwas davor, „Manchmal <verb> ich“ (Review Paket 9).

    Nicht die Frage am Satzanfang („Würde ich nach der Narkose …?“): dort steht vor
    dem Verb kein Wort."""
    return rf"(?:\bich\s+{verb}|\w\s+{verb}\s+ich)\b"


# Zwischen Verb und Wendung: derselbe Satz und kein Nebensatz über jemand anderen
# („… wissen, warum Dornröschen nie wieder aufwachen sollte“; Review Paket 9).
_FENSTER = r"(?:(?!\b(?:warum|wieso|weshalb|ob|wie|dass|er|sie|man)\b)[^.?!]){0,60}"
_WUNSCH = rf"(?:will|möchte|moechte|{_WUERDE}|wünsche|wuensche|wünschte|wuenschte)"
_WOLLEN = r"(?:will|möchte|moechte)"
_VORHABEN = r"(?:will|möchte|moechte|werde|mache)"
# Zwischen „ich werde“ und „mit dem Leben Schluss“ nur Zeit- und Füllwörter, kein
# Fenster: „Ich werde erklären, warum Werther mit dem Leben Schluss macht.“
_ZEIT = r"(?:einfach|jetzt|nur|endlich|heute|morgen|bald|noch|dann|abend|nacht)"

#: Die Wendungen, je mit dem Satz der Messung, den sie fangen.
_WENDUNGEN: Final = (
    # „Niemand würde mich vermissen, wenn ich weg wäre.“ — Moderation 0,018. Nur am
    # Satzende oder mit „wenn ich weg/tot/nicht mehr …“, nicht im Witz über die AG.
    rf"\b(?:niemand|keiner)\s+(?:{_WUERDE}|wird)\s+mich\s+vermissen"
    r"(?:\s*[.!]|\s*$|,?\s+wenn\s+ich\s+(?:weg|tot|nicht\s+mehr))",
    r"\b(?:no\s*one|nobody)\s+would\s+(?:even\s+)?miss\s+me\b",
    # „Ich sehe keinen Ausweg mehr.“ — 0,158; „sieht keinen Ausweg“ (Figur) bleibt stumm.
    r"\bsehe\s+(?:einfach\s+|überhaupt\s+|ueberhaupt\s+)?keinen\s+ausweg\s+mehr\b",
    # „Ich bin allen nur eine Last.“ — 0,122.
    rf"\b(?:bin|{_WAERE})\s+(?:allen|euch|jedem|meiner\s+familie|meinen\s+eltern)\s+"
    r"(?:nur\s+)?(?:noch\s+)?eine\s+last\b",
    # „Es wäre besser, wenn es mich nicht gäbe.“ — 0,161.
    rf"\bwenn\s+es\s+mich\s+nicht\s+(?:mehr\s+)?(?:gäbe|gaebe|geben\s+{_WUERDE})\b",
    # „Ich will nur noch schlafen und nie wieder aufwachen.“ — selbst (Modalverb oder
    # „aufwache“) oder als Zweck („damit man nicht mehr aufwacht?“); nicht Dornröschen,
    # nicht „wenn man nach der Narkose nicht mehr aufwacht“ (Biologie).
    rf"{_selbst(_WUNSCH)}{_FENSTER}\b(?:nie|nicht)\s+(?:mehr|wieder)\s+aufwachen\b",
    r"\b(?:nie|nicht)\s+(?:mehr|wieder)\s+aufwache\b",
    r"\bdamit\s+(?:man|ich)\s+(?:nie|nicht)\s+(?:mehr|wieder)\s+aufwach\w*",
    # „Ich will sterben.“, „Ich will tot sein.“ — nur selbst, nicht „Faust will sterben“.
    rf"{_selbst(_WOLLEN)}\s+(?:einfach\s+|nur\s+|noch\s+|lieber\s+){{0,3}}"
    r"(?:sterben|tot\s+sein)\b",
    # „Ich will nicht mehr.“ — 0,125; nur als ganze Nachricht („nicht mehr warten“ bleibt).
    r"^\s*ich\s+will\s+(?:einfach\s+)?nicht\s+mehr\s*[.!…]*\s*$",
    # „Ich will einfach Schluss machen, endgültig.“ — 0,160; „ich“ und Verb direkt davor,
    # also nicht „mit meinem Freund“ oder „mit dem Rauchen“ (Review Paket 8).
    r"\bich\s+(?:will|möchte|moechte|werde|mache)\s+(?:einfach\s+|jetzt\s+|nur\s+|endlich\s+){0,2}"
    r"schluss(?:\s+machen)?,?\s+(?:endgültig|endgueltig|für\s+immer|fuer\s+immer)\b",
    # Mit dem eigenen Leben — nicht „Warum macht Werther mit dem Leben Schluss?“.
    r"\bmit\s+meinem\s+leben\s+schluss\b",
    rf"{_selbst(_VORHABEN)}\s+(?:{_ZEIT}\s+){{0,3}}mit\s+dem\s+leben\s+schluss\b",
    # „Ich überlege / habe vor, mit dem Leben Schluss zu machen.“ — mit „zu machen“:
    # „Ich überlege, warum Werther mit dem Leben Schluss macht.“ bleibt stumm.
    r"\bich\s+(?:überlege|ueberlege|plane|habe\s+vor|denke\s+daran|bin\s+entschlossen)\b"
    rf"{_FENSTER}\bmit\s+(?:dem|meinem)\s+leben\s+schluss\s+zu\s+machen\b",
    # „… und weiß schon, wie ich es beende.“ — 0,123.
    r"\b(?:weiß|weiss)\s+(?:schon|genau|jetzt),?\s+wie\s+ich\s+(?:es|alles|mein\s+leben)\s+beende\b",
    # „I don't want to be here anymore.“ — 0,005.
    r"\b(?:don['’]?t|do\s+not)\s+want\s+to\s+be\s+here\s+any\s*more\b",
    # „Ich will einfach verschwinden und nie wiederkommen.“
    r"\bverschwinden\s+und\s+nie\s+(?:mehr\s+|wieder\s+)?wiederkommen\b",
    r"\b(?:want|wanna)\s+(?:to\s+)?disappear\s+forever\b",
    # „… darüber nach, mir etwas anzutun.“ — „er will mir etwas antun“ bleibt (Drohung).
    r"\b(?:denke|dachte|nach|überlege|ueberlege)\b[^.?!]{0,30}\bmir\s+(?:et)?was\s+anzutun\b",
    r"\bmir\s+selbst\s+(?:et)?was\s+an(?:zu)?tun\b",
    # „Mein Leben hat keinen Sinn mehr.“, „Ich habe keine Kraft mehr zu leben.“
    r"\bmein\s+leben\s+(?:hat\s+)?keinen\s+sinn\s+mehr\b",
    r"\bkeine\s+kraft\s+mehr\s+(?:zu|zum)\s+leben\b",
    # „… wenn ich nicht mehr da wäre.“ — Konjunktiv; „… da bin“ (Elternzeit) bleibt stumm.
    rf"\bwenn\s+ich\s+nicht\s+mehr\s+(?:da|am\s+leben|hier)\s+{_WAERE}\b",
    # „Everyone would be better off without me.“
    r"\bbetter\s+off\s+without\s+me\b",
)

#: Abschiede — sie zählen nur, wenn die Nachricht keinen :data:`_ANLASS` nennt.
_ABSCHIEDE: Final = (
    # „Ich verabschiede mich hiermit von allen, macht's gut.“ — 0,018.
    r"\bverabschiede\s+mich\s+hiermit\s+von\s+(?:allen|euch)\b",
    # „Ich habe meinen Abschiedsbrief schon geschrieben.“ — nicht „einen … an die Kollegin“.
    r"\bmeinen\s+abschiedsbrief\s+(?:schon\s+|bereits\s+)?(?:geschrieben|fertig)\b",
    r"\b(?:wrote|written|finished)\s+my\s+goodbye\s+(?:letter|note)\b",
)

#: Ein gewöhnlicher Anlass für einen Abschied: Beruf, Ruhestand, Ferien.
_ANLASS: Final = re.compile(
    r"\b(?:ruhestand|rente|pension|elternzeit|sabbatical|kolleg\w*|team|abteilung|firma"
    r"|arbeitgeber|abschiedsfeier|\w*ferien|\w*urlaub|retire\w*|colleague\w*"
    r"|vacation|holidays?)\b")

_MUSTER: Final = tuple(re.compile(w) for w in _WENDUNGEN)
_ABSCHIEDS_MUSTER: Final = tuple(re.compile(w) for w in _ABSCHIEDE)


def ist_krisen_wendung(normalisiert: str) -> bool:
    """Trägt die (wie im Gate normalisierte) Nachricht eine der Wendungen?"""
    if any(m.search(normalisiert) for m in _MUSTER):
        return True
    return (any(m.search(normalisiert) for m in _ABSCHIEDS_MUSTER)
            and not _ANLASS.search(normalisiert))
