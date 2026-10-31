"""Stimmt die Person der offenen Vorschau zu? Liste, Veto, dann ein kurzer LLM-Aufruf.

Paket 10, A-6 (Nutzer-Entscheid 2026-10-15): Eine Person darf nicht daran scheitern,
dass ihr Wortlaut nicht in der Erlaubnisliste steht — „ja, rein damit“ führte bis hier
zu einer neuen Vorschau statt zur Ausführung (Kurzaudit S-5). Die Reihenfolge hält die
alte Sicherheit:

1. Erlaubnisliste (``domain/zustimmung.is_affirmation``) — trifft sie, ist es Zustimmung.
2. Veto (``hat_veto``) — Absage, Rückfrage oder Änderungswunsch ist nie Zustimmung.
3. Erst dann das Modell, Temperatur 0, mit fester Antwortform. Nur ``zustimmung`` zählt;
   jede andere Antwort heißt „nein“ — der Preis ist eine zweite Frage, keine Änderung
   ohne Zustimmung.

**Drei Ausgänge** (Paket 19, M-2): ein vorübergehender Fehlschlag ist keine Antwort. Frist,
kein LLM-Platz oder ein vorübergehender Anbieterfehler ergeben :data:`UNKLAR` — bis hier
hießen sie „nein“, und unter Last verwarf ``discard_stale_approval`` die vorbereitete
Änderung einer Person, die frei zugestimmt hatte. Ein dauerhafter Fehler bleibt „nein“.
``unklar`` schreibt nie: der Vorgang bleibt (nur im Speicher), der Vorlauf zeigt die
Vorschau erneut mit der „ausgelastet“-Blase und dem Bestätigungs-Chip
(``write_approval.redeem_write_approval``).

Geprüft wird einmal je Zug (``write_approval.discard_stale_approval``); die Leser im
Vorlauf und in der Werkzeug-Schleife nehmen das Urteil über :func:`zugestimmt` — für sie
ist ``unklar`` keine Zustimmung.
"""

from __future__ import annotations

import logging

from boerdi.domain.zustimmung import hat_veto, is_affirmation
from boerdi.obs.drossel import gedrosselt
from boerdi.obs.usage import current_turn_usage
from boerdi.services import llm
from boerdi.services.llm_ereignisse import ist_voruebergehend
from boerdi.services.llm_parallel import LlmAusgelastet

logger = logging.getLogger(__name__)

#: Die drei Urteile von :func:`urteil`.
JA = "ja"
NEIN = "nein"
UNKLAR = "unklar"

#: Das Urteil dieses Zugs — ein Schlüssel auf oberster Ebene von ``session_state``,
#: lebt also nur diesen Zug. ``True`` nur bei :data:`JA`.
MERKER = "_zustimmung"
#: Das Urteil war :data:`UNKLAR` — gesetzt neben ``MERKER = False``, gelesen vom Vorlauf.
UNKLAR_MERKER = "_zustimmung_unklar"

#: So lange darf der Aufruf selbst dauern — gezählt erst ab der Platzvergabe
#: (``llm.chat_completion(frist_s=…)``); danach ist das Urteil unklar.
FRIST_S = 3.0
#: So lange wartet die Prüfung höchstens auf einen LLM-Platz (Review 19-5, 4) — nicht
#: ``LLM_SLOT_WAIT_S`` (30 s): ``setup`` hält die Sitzungssperre, und „unklar“ endet glimpflich.
PLATZ_FRIST_S = 3.0
#: Höchstens eine Warnzeile je Minute, wenn die Prüfung kein Urteil bekam.
_WARN_ABSTAND_S = 60.0

# Lange Nachrichten sind ein neues Anliegen, keine Antwort auf die Vorschau.
_HOECHSTENS_ZEICHEN = 300

_ANWEISUNG = (
    "Der Chatbot hat einen Schreibvorgang im Bildungsportal WLO vorbereitet "
    "(Werkzeug: {werkzeug}) und die Person gefragt, ob er ausgeführt werden soll. "
    "Ordne ihre Antwort genau einer Klasse zu:\n"
    "zustimmung — sie will den Vorgang so ausführen, wie er gezeigt wurde\n"
    "absage — sie will ihn nicht, nicht jetzt oder bricht ab\n"
    "aenderung — sie will ihn mit anderen Werten oder fragt nach einer Änderung\n"
    "anderes — eine Rückfrage, ein neues Anliegen oder unklar\n"
    "Im Zweifel nicht zustimmung. Antworte nur mit dem einen Wort."
)


async def _llm_urteil(nachricht: str, werkzeug: str) -> bool | None:
    """Das Modell entscheidet — nur ein klares ``zustimmung`` zählt (``True``), jede andere
    Antwort ist ``False``, ebenso ein dauerhafter Fehler. ``None``: kein Urteil wegen Last,
    Frist oder eines vorübergehenden Anbieterfehlers (``llm_ereignisse.ist_voruebergehend``)."""
    try:
        resp = await llm.chat_completion(
            messages=[
                {"role": "system", "content": _ANWEISUNG.format(werkzeug=werkzeug or "?")},
                {"role": "user", "content": nachricht[:_HOECHSTENS_ZEICHEN]},
            ],
            max_tokens=5,
            temperature=0,
            usage_acc=current_turn_usage(),
            phase="zustimmung",
            frist_s=FRIST_S,
            platz_frist_s=PLATZ_FRIST_S,
        )
        urteil = (resp.choices[0].message.content or "").strip().strip(".").lower()
    except LlmAusgelastet:
        # Last, kein Fehler — ``llm_platz_frist`` meldet sie gedrosselt (Paket 18F).
        logger.info("Zustimmungs-Prüfung: kein LLM-Platz frei — Urteil unklar, Vorgang bleibt")
        return None
    except Exception as fehler:  # noqa: BLE001 — nie „ja“
        # Ohne Traceback und ohne Text der Ausnahme: der kann die Nachricht tragen.
        if isinstance(fehler, TimeoutError) or ist_voruebergehend(fehler):
            gedrosselt(logger, logging.WARNING, "zustimmung_pruefen:unklar", _WARN_ABSTAND_S,
                       "Zustimmungs-Prüfung ohne Urteil (%s) — unklar, der Vorgang bleibt",
                       type(fehler).__name__)
            return None
        # Review 19-5 (3): ein Fehler, der beim nächsten Versuch genauso käme (400, 401,
        # eine unerwartete Antwortform), hält keinen Vorgang fest — „nein“ wie vor Paket 19.
        gedrosselt(logger, logging.WARNING, "zustimmung_pruefen:fehler", _WARN_ABSTAND_S,
                   "Zustimmungs-Prüfung gescheitert (%s) — gilt als keine Zustimmung",
                   type(fehler).__name__)
        return False
    logger.info("Zustimmungs-Prüfung für %s: %s", werkzeug, urteil[:20])
    return urteil == "zustimmung"


async def urteil(nachricht: str, werkzeug: str) -> str:
    """Stimmt ``nachricht`` der offenen Vorschau für ``werkzeug`` zu? :data:`JA`,
    :data:`NEIN` oder :data:`UNKLAR` (das Modell gab kein Urteil)."""
    if is_affirmation(nachricht):
        return JA
    if hat_veto(nachricht) or len(nachricht or "") > _HOECHSTENS_ZEICHEN:
        return NEIN
    ergebnis = await _llm_urteil(nachricht, werkzeug)
    if ergebnis is None:
        return UNKLAR
    return JA if ergebnis else NEIN


def zugestimmt(session_state: dict, nachricht: str) -> bool:
    """Das Urteil dieses Zugs — ohne gespeichertes Urteil die Erlaubnisliste."""
    if MERKER in session_state:
        return bool(session_state[MERKER])
    return is_affirmation(nachricht)
