"""Die Anmelde-Rückfrage als Quick-Reply-Paar (C5-c2a).

Wollte ein Muster kuratieren, ohne dass für diesen Zug ein Zugangsblock gilt,
dann sagt der Bot das seit E3 zwar ehrlich — aber die Person kann nichts
dagegen tun. Dieses Modul hängt die zwei Chips an, die ihr die Wahl geben:

1. ``__auth__`` — das Widget startet damit die WLO-Anmeldung.
2. „Such einfach, ohne Anmeldung" — eine gewöhnliche Nachricht.

**Warum der erste Chip keine Beschriftung trägt.** Die beiden vorhandenen
Magic-Präfixe führen ihre Beschriftung mit (``__guide__|Label|url``,
``__action__|Label|action|json``) — dort ist sie **Inhalt**: vom Modell
formuliert bzw. aus der Config gepflegt. Hier ist sie **Beiwerk**: sie
benennt eine Handlung des Widgets, wird nirgends hingeschickt und soll dem
Sprachumschalter des Widgets sofort folgen. Beiwerk gehört dorthin, wo es
gezeigt wird — also in den Widget-Katalog, nicht in diesen String.

**Warum der zweite Chip sie sehr wohl trägt.** Ein Klick darauf sendet seinen
Text als Nachricht. Die Beschriftung IST die Nachricht; sie unübersetzt zu
lassen hiesse, eine englischsprachige Person einen deutschen Satz absenden zu
lassen (die Regel aus C1-g2b).

**Warum der Chip erscheint, obwohl heute kein Muster kuratiert.** Gemessen
2026-08-10: keines der 17 Muster im Seed nennt ein kuratierendes Werkzeug, die
Bedingung ist also im Auslieferungsstand ruhend. Sie ist aber **ohne
Auslieferung erreichbar** — ``tools:`` ist ein Studio-Feld, und in dem
Augenblick, in dem eine Redaktion dort ``wlo_add_to_collection`` einträgt,
greift sie. Genau dann braucht die Person diesen Chip. Ein Kurations-Intent
samt Muster zu schreiben ist die getrennte Produktentscheidung aus Paket F/G.

Rein: keine I/O, kein Zustand. Die Bedingung selbst berechnet
``services/response_tool_selection.curation_blocked_by_mode`` — sie liest den
Zugangsblock und gehört damit in die Dienst-Schicht, nicht hierher.
"""

from __future__ import annotations

from boerdi.i18n import DEFAULT, Locale, bot_text

# Der Marker, den das Widget erkennt (``ui/src/chips/auth-qr.ts``). MUSS dort
# zeichengleich stehen. Bewusst ohne ``|``: er trägt nichts ausser sich selbst.
AUTH_QR_MARKER = "__auth__"


def inject_auth_qr(
    quick_replies: list[str] | None,
    *,
    blocked: bool,
    lang: Locale = DEFAULT,
    max_qrs: int = 4,
) -> list[str]:
    """Gibt ``quick_replies`` mit den zwei Anmelde-Chips an der Spitze zurück.

    ``blocked=False`` → unverändert (nur als Liste kopiert). Ein bereits
    vorhandener ``__auth__``-Marker verhindert das zweite Paar: der Zug läuft
    über mehrere Stationen, und ein doppelter Chip ist billiger zu verhindern
    als auszuschliessen.

    Die beiden neuen stehen **vor** einem etwaigen Lotsen-Chip: der Lotse ist
    ein Nebenangebot, die Anmeldung beantwortet die gerade gestellte Frage.
    ``max_qrs`` deckelt wie bei den Nachbarn auf vier — die hintersten
    Bestands-Chips fallen zuerst.
    """
    qrs = list(quick_replies or [])
    if not blocked or AUTH_QR_MARKER in qrs:
        return qrs
    qrs = [AUTH_QR_MARKER, bot_text(lang, "auth.readOnly"), *qrs]
    if max_qrs >= 0:
        qrs = qrs[:max_qrs]
    return qrs
