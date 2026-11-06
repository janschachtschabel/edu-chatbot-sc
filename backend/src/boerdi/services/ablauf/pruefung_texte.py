"""Die Befundtexte der Ablauf-Prüfung (aus ``pruefung`` gelöst, Querschnitts-Review 2026-11-06,
Q4) — Deutsch und Englisch, der Sprache des Studios folgend.
"""

from __future__ import annotations

from typing import Any, Final

_T: Final[dict[str, dict[str, str]]] = {
    "anzahl": {"de": "1 bis {max} Schritte erwartet, {n} gefunden",
               "en": "1 to {max} steps expected, {n} found"},
    "doppelt": {"de": "Schritt-IDs doppelt: {ids}", "en": "Duplicate step ids: {ids}"},
    "text": {"de": "Schritt {s}: Text (de) fehlt", "en": "Step {s}: text (de) missing"},
    "modul": {"de": "Schritt {s}: Modul {m!r} gibt es nicht",
              "en": "Step {s}: module {m!r} does not exist"},
    "daten": {"de": "Schritt {s}: Daten passen nicht zum Modul {m} ({f})",
              "en": "Step {s}: data do not fit module {m} ({f})"},
    "schreibend": {"de": "Schritt {s}: Werkzeug {w} ist schreibend (erst mit Freigabe, Paket S)",
                   "en": "Step {s}: tool {w} writes (only with approval, package S)"},
    "werkzeug": {"de": "Schritt {s}: Werkzeug {w!r} ist unbekannt",
                 "en": "Step {s}: tool {w!r} is unknown"},
    "mcp_teil": {"de": "Schritt {s}: lesende WLO-Werkzeuge bekommen keine Teile des Vorgangs",
                 "en": "Step {s}: read-only WLO tools get no parts of the work item"},
    "teil": {"de": "Schritt {s}: Teil {t!r} hat keine gültige Form",
             "en": "Step {s}: part {t!r} has no valid form"},
    "regeln_fehlen": {"de": "Schritt {s}: Verzweigung braucht Regeln (Liste unter weiter)",
                      "en": "Step {s}: branch needs rules (a list under next)"},
    "regeln_falsch": {"de": "Schritt {s}: Regeln unter weiter gibt es nur bei einer Verzweigung",
                      "en": "Step {s}: rules under next only exist for a branch"},
    "regel_dann": {"de": "Schritt {s}: jede Regel braucht entweder Bedingung und dann oder sonst",
                   "en": "Step {s}: each rule needs either a condition with then, or else (sonst)"},
    "sonst": {"de": "Schritt {s}: Verzweigung ohne sonst als letzte Regel",
              "en": "Step {s}: branch without sonst as the last rule"},
    "ziel": {"de": "Schritt {s}: Ziel {z!r} gibt es nicht",
             "en": "Step {s}: target {z!r} does not exist"},
    "ende": {"de": "Kein Schritt ende — der Lauf hätte kein Ende",
             "en": "No end step — the run would never end"},
    "auslaufen": {"de": "Schritt {s}: der Lauf liefe ohne Ende aus (letzter Schritt ohne weiter)",
                  "en": "Step {s}: the run would stop without an end step (last step, no next)"},
    "unerreichbar": {"de": "Schritt {s}: nicht erreichbar", "en": "Step {s}: unreachable"},
    "schleife": {"de": "Schleife ohne wartenden Schritt — der Treiber käme nicht zum Halt",
                 "en": "Loop without a waiting step — the driver would never stop"},
    "zu_lang": {"de": "Ab Schritt {s} mehr als {max} Schritte ohne Halt",
                "en": "From step {s} more than {max} steps without a stop"},
    "voraussetzung": {"de": "Voraussetzung {v!r} gibt es nicht",
                      "en": "Requirement {v!r} does not exist"},
    "ausloeser": {"de": "Auslöser modul: Modul {m!r} gibt es nicht",
                  "en": "Trigger module: module {m!r} does not exist"},
    "wendung": {"de": "Auslöser text: 1 bis {max} Wendungen mit je 4 bis 80 Zeichen erwartet",
                "en": "Trigger text: 1 to {max} phrases of 4 to 80 characters each expected"},
    "modul_schritt": {"de": "Auslöser modul: kein Schritt mit diesem Modul {m!r} (gefolgt von "
                            "einem weiteren)",
                      "en": "Trigger module: no step with this module {m!r} (followed by another)"},
    "ausloeser_teil": {"de": "Auslöser: Teil {t!r} hat keine gültige Form",
                       "en": "Trigger: part {t!r} has no valid form"},
    "auftrag_flow": {"de": "Schritt {s}: Art auftrag braucht einen Flow",
                     "en": "Step {s}: kind auftrag needs a flow"},
    "auftrag_frei": {"de": "Schritt {s}: Flow {f!r} ist im Betrieb nicht freigeschaltet "
                           "(B_API_JOBS_FLOWS)",
                     "en": "Step {s}: flow {f!r} is not enabled by operations (B_API_JOBS_FLOWS)"},
    "auftrag_schreibt": {"de": "Schritt {s}: Ergebnis-Teil (schreibt) fehlt",
                         "en": "Step {s}: result part (schreibt) missing"},
    "auftrag_anmeldung": {"de": "Aufträge brauchen die Voraussetzung Anmeldung",
                          "en": "Jobs need the requirement sign-in"},
    "agent_fehlt": {"de": "Schritt {s}: Art agent braucht den Block agent",
                    "en": "Step {s}: kind agent needs the agent block"},
    "agent_werkzeuge": {"de": "Schritt {s}: 1 bis {max} Werkzeuge erwartet",
                        "en": "Step {s}: 1 to {max} tools expected"},
    "agent_werkzeug": {"de": "Schritt {s}: Werkzeug {w!r} ist unbekannt oder für die KI gesperrt",
                       "en": "Step {s}: tool {w!r} is unknown or not allowed for the AI"},
    "agent_hinweis": {"de": "Schritt {s}: Hinweis an die KI höchstens {max} Zeichen je Sprache",
                      "en": "Step {s}: hint to the AI at most {max} characters per language"},
    "agent_zuege": {"de": "Schritt {s}: 1 bis {max} Züge erwartet",
                    "en": "Step {s}: 1 to {max} turns expected"},
    "modus": {"de": "Auslöser: Modus {m!r} gibt es nicht",
              "en": "Trigger: mode {m!r} does not exist"},
}


def t(lang: str, schluessel: str, **werte: Any) -> str:
    vorlagen = _T[schluessel]
    return (vorlagen.get(lang) or vorlagen["de"]).format(**werte)
