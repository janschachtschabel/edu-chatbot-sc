"""Das Antwort-Werkzeug ``respond_to_user``: Antwort UND Schnellantworten in einem Aufruf.

Warum (Plan ``docs/plans/2026-09-30-muster-kette-zeit.md``): Der eigene
Schnellantwort-Aufruf NACH der Antwort kostete im Median 5,3 s Wartezeit und
kannte die Antwort nur als Auszug — bei Rückfragen kamen unpassende Vorschläge
(„Klimawandel" auf „Welcher Bereich der Optik interessiert dich?"). Entstehen
sie im Antwort-Aufruf, fällt die Wartezeit weg und sie passen zur Antwort.
Ruft das Modell das Werkzeug nicht, läuft der exakte Aufruf wie zuvor
(``services/turn_assembly``) — es geht nur die Zeitersparnis dieses Zugs verloren.

Die Beschreibung hängt nur an der Konfiguration (Anzahl, Zeichengrenze), nie am
Zug: der Werkzeugblock gehört zum cachebaren Präfix des Antwort-Aufrufs
(``docs/plans/2026-09-29-responses-systemteil-und-cache.md``).
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.quick_reply_policy import _qr_default_count, _qr_policy
from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.settings import get_settings

RESPOND_TO_USER: Final[str] = "respond_to_user"


def antwort_aus_argumenten(args: dict[str, Any]) -> tuple[str, list[str]]:
    """Text und Vorschläge aus einem ``respond_to_user``-Aufruf — in beiden
    Schleifen (Muster und Agent) dieselbe Lesart.

    Nur nichtleere Zeichenketten zählen als Vorschlag; eine Zeichenkette statt
    einer Liste ergäbe sonst Einzelbuchstaben-Pillen. Anzahl und Länge kappt
    erst die Zusammenstellung (``quick_replies_llm.filtere_vorschlaege``).
    """
    text = strip_reasoning_markers(str(args.get("text") or "").strip())
    roh = args.get("quick_replies")
    vorschlaege = [v.strip() for v in roh if isinstance(v, str) and v.strip()] \
        if isinstance(roh, list) else []
    return text, vorschlaege


def inline_anzahl(pattern_output: dict[str, Any]) -> int:
    """Wie viele Schnellantworten der Antwort-Aufruf selbst liefern soll; 0 = Weg aus.

    Aus, wenn der Betreiber ihn abschaltet (``CHAT_INLINE_QUICK_REPLIES=0``) oder
    das Muster keine Schnellantworten will: ``quick_replies_mode: none`` (Krise
    M01, Bedrohung M02) oder ``format_follow_up: none``. Sonst dieselbe Zahl wie
    im exakten Aufruf — ``quick_replies_max`` des Musters, sonst die globale
    Anzeige-Regel (``display-rules.quick_replies.max_count``).
    """
    if not get_settings().chat_inline_quick_replies:
        return 0
    if pattern_output.get("format_follow_up", "quick_replies") == "none":
        return 0
    modus, anzahl = _qr_policy(pattern_output.get("id") or "")
    if modus == "none":
        return 0
    return anzahl if anzahl is not None else _qr_default_count()


def antwort_werkzeug(anzahl: int, max_zeichen: int) -> dict[str, Any]:
    """Die Werkzeugdefinition — ``text`` Pflicht, ``quick_replies`` optional.

    ``anzahl`` ist die Zahl der Pillen. Angefragt wird eine mehr: zu lange
    Vorschläge werden verworfen, nicht gekürzt, und ohne Ersatzzeile kostete
    jeder eine Pille (Paket A, Tor E-5 — wie ``generate_quick_replies``). Der
    Bring-mich-hin-Eintrag kommt zusätzlich und belegt keinen Platz (R-6).
    Gekappt wird in ``quick_replies_llm.filtere_vorschlaege``.
    """
    angefragt = anzahl + 1
    return {
        "type": "function",
        "function": {
            "name": RESPOND_TO_USER,
            "description": (
                "FINALE Antwort an den Nutzer. Nutze dieses Tool NUR wenn du "
                "alle nötigen Such-/Vokabular-/Knowledge-Tools bereits gerufen "
                "hast und die finale Antwort fertig ist. Liefere die Markdown-"
                f"formatierte Antwort als ``text`` und {angefragt} kurze nutzerseitige "
                f"Folgevorschläge "
                f"als ``quick_replies`` (höchstens {max_zeichen} Zeichen pro "
                "Vorschlag — längere werden verworfen; vom NUTZER formuliert — "
                "der Text MUSS so klingen, als würde der Nutzer ihn selbst "
                "tippen, z.B. 'Mehr davon zeigen', 'Anderes Thema wählen', "
                "'Ja, gerne', 'Nein danke'). "
                "ANREDE-REGEL (kritisch): Der Nutzer spricht BOERDi mit DU an, "
                "nicht mit Sie — auch wenn die Persona-Modulation 'siezen' "
                "auf den BOT-Text gesetzt ist (das gilt nur für die Antwort "
                "des Bots an den Nutzer, NICHT für die Pillen-Vorschläge). "
                "Quick-Replies dürfen daher NICHT 'Können Sie mir helfen?' "
                "enthalten, sondern 'Kannst du mir helfen?' / 'Zeig mir mehr' / "
                "'Erklär mir den Unterschied'. Du-Form ist Pflicht. "
                "Wenn keine Folgevorschläge passen (z.B. CRISIS), gib leere Liste. "
                "BRING-MICH-HIN-VORSCHLAG: Wenn deine Antwort eine konkrete "
                "WLO-Webseiten-URL adressiert (z.B. /themenseite/<slug>, "
                "/fachportale, /mitmachen, /ueber-uns), darfst du EINEN Eintrag "
                "in folgendem Spezialformat einfügen: "
                "``__guide__|<kurzer Anzeigetext>|<vollständige URL>`` — "
                "Frontend rendert das als hervorgehobenen Same-Tab-Navigations-"
                "Button. Beispiel: "
                "``__guide__|Themenseite Klimawandel|"
                "https://wirlernenonline.de/themenseite/klimawandel``. "
                "Nutze NUR vollständige URLs (Schema + Host), keine relativen "
                "Pfade. Maximal EIN solcher Eintrag pro Antwort."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "Die Markdown-formatierte Antwort an den Nutzer. "
                            "WICHTIG: Schreibe die Folgevorschläge (quick_replies) "
                            "und den ``__guide__``-Link NICHT zusätzlich in den "
                            "text — die erscheinen separat als Pillen/Buttons UNTER "
                            "der Antwort. Der text endet mit dem letzten "
                            "inhaltlichen Satz; KEINE aufgelisteten Klick-Optionen "
                            "am Ende (kein 'Zeig mir mehr' / 'Anderes Thema wählen' "
                            "und keine 'Bring mich hin:'-Zeile)."
                        ),
                    },
                    "quick_replies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            f"{angefragt} kurze Folgevorschläge, je höchstens "
                            f"{max_zeichen} Zeichen. Jeder Vorschlag ist ein "
                            "Satz, den der Nutzer als nächste Eingabe sagen würde "
                            "(NICHT was der Bot vorschlägt zu tun). "
                            "ANREDE: Du-Form, weil der Nutzer den Bot duzt — "
                            "auch dann, wenn die Bot-Antwort selbst siezt. "
                            "Beispiele: 'Zeig mir mehr', 'Anderes Thema wählen', "
                            "'Kannst du das genauer erklären?'. KEINE Sie-Form "
                            "wie 'Können Sie mir ...?' / 'Zeigen Sie mir ...'. "
                            "Zusätzlich darf EIN Eintrag ein Bring-mich-hin-"
                            "Spezialformat sein: ``__guide__|<Label>|<URL>`` — "
                            "siehe Tool-Description."
                        ),
                        "minItems": 0,
                        "maxItems": angefragt + 1,
                    },
                },
                "required": ["text"],
            },
        },
    }
