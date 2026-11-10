"""Die Befundtexte der Ablauf-Prüfung (aus ``pruefung`` gelöst, Querschnitts-Review 2026-11-06,
Q4) — Deutsch und Englisch, der Sprache des Studios folgend.
"""

from __future__ import annotations

from typing import Any, Final

_T: Final[dict[str, dict[str, str]]] = {
    "anzahl": {"de": "1 bis {max} Schritte erwartet, {n} gefunden",
               "en": "1 to {max} steps expected, {n} found"},
    "doppelt": {"de": "Schritt-IDs doppelt: {ids}", "en": "Duplicate step ids: {ids}"},
    "optionen_anzahl": {"de": "Schritt {s}: höchstens {max} Schnellantworten",
                        "en": "Step {s}: at most {max} quick replies"},
    "optionen_doppelt": {"de": "Schritt {s}: Kennungen der Schnellantworten doppelt: {ids}",
                         "en": "Step {s}: duplicate quick reply ids: {ids}"},
    "optionen_label_doppelt": {"de": "Schritt {s}: Schnellantworten gleich beschriftet: {l}",
                               "en": "Step {s}: quick replies with the same label: {l}"},
    "optionen_label": {"de": "Schritt {s}: Schnellantwort {o} braucht eine Beschriftung "
                             "(mindestens auf Deutsch)",
                       "en": "Step {s}: quick reply {o} needs a label (at least in German)"},
    "verweis_teil": {"de": "Schritt {s}: liest den Teil {t} — den schreibt kein Schritt und kein "
                           "Modul",
                     "en": "Step {s}: reads the part {t} — no step or module writes it"},
    "verweis_text": {"de": "Schritt {s}: Pfad oder Auswahl im Teil {t} — der Teil ist Text, darin "
                           "findet der Lauf keine Stelle",
                     "en": "Step {s}: path or selection in the part {t} — the part is text, the "
                           "run finds no field in it"},
    "dienst_auswahl": {"de": "Schritt {s}: das Argument {a} ist eine Auswahl (eine Liste), der "
                             "Dienst {w} erwartet dort ein Objekt — einen ganzen Teil oder pfad "
                             "nehmen",
                       "en": "Step {s}: argument {a} is a selection (a list); the service {w} "
                             "expects an object there — use a whole part or pfad"},
    "auswahl_einzeln": {"de": "Schritt {s}: das Argument {a} von {w} nimmt einen einzelnen Wert, "
                              "eine Auswahl ergibt eine Liste — pfad nehmen",
                        "en": "Step {s}: argument {a} of {w} takes a single value, a selection "
                              "yields a list — use pfad"},
    "auswahl_liste": {"de": "Schritt {s}: die Auswahl im Teil {t} sucht die Liste {l} — der Teil "
                            "trägt {k}",
                      "en": "Step {s}: the selection in the part {t} looks for the list {l} — the "
                            "part has {k}"},
    "verweis_typ": {"de": "Schritt {s}: der Teil {t} hat den Typ {i}, erwartet ist {e}",
                    "en": "Step {s}: the part {t} has type {i}, expected is {e}"},
    "verweis_spaeter": {"de": "Schritt {s}: liest den Teil {t}, den der Ablauf erst nach diesem "
                              "Schritt schreibt — er kommt nur aus einem früheren Gespräch",
                        "en": "Step {s}: reads the part {t}, which the workflow only writes after "
                              "this step — it can only come from an earlier conversation"},
    "verweis_gespraech": {"de": "Schritt {s}: liest den Teil {t}, den der Ablauf nicht selbst "
                                "schreibt — er muss aus dem Gespräch im Vorgang liegen, sonst "
                                "scheitert der Schritt (Bei Fehler, falls gesetzt)",
                          "en": "Step {s}: reads the part {t}, which the workflow does not write "
                                "itself — it must come from the conversation, otherwise the step "
                                "fails (on error, if set)"},
    "verweis_form": {"de": "Schritt {s}: Verweis auf {t} hat keine gültige Form ($teil mit pfad "
                           "oder mit liste/wo/feld)",
                     "en": "Step {s}: reference to {t} is malformed ($teil with pfad or with "
                           "liste/wo/feld)"},
    "daten_auswahl": {"de": "Schritt {s}: eine Auswahl ergibt eine Liste, Moduldaten sind ein "
                            "Objekt — die Auswahl unter einem Feld eintragen",
                      "en": "Step {s}: a selection yields a list, module data is an object — put "
                            "the selection under a field"},
    "auswahl_form": {"de": "Schritt {s}: Auswahl aus {t} — ungültig: {f}",
                     "en": "Step {s}: selection from {t} — invalid: {f}"},
    "platzhalter_form": {"de": "Schritt {s}: Platzhalter {p} hat keine gültige Form "
                               "({{teil.name}}, {{teil.name.pfad}} oder {{start.feld}})",
                         "en": "Step {s}: placeholder {p} is malformed "
                               "({{teil.name}}, {{teil.name.pfad}} or {{start.feld}})"},
    "platzhalter_start": {"de": "Schritt {s}: Platzhalter {p} — kein Feld der Startdaten heißt {t}",
                          "en": "Step {s}: placeholder {p} — no start data field is called {t}"},
    "start_doppelt": {"de": "Startdaten: Feld doppelt: {f}",
                      "en": "Start data: duplicate field: {f}"},
    "start_pflicht_ausloeser": {"de": "Auslöser {a} startet nie: Pflichtfelder in den Startdaten "
                                      "kommen nur von der Gastseite oder der KI",
                                "en": "Trigger {a} never starts: required start data fields only "
                                      "come from the host page or the AI"},
    "start_feld": {"de": "Schritt {s}: Verweis auf start.{f} — kein Feld der Startdaten heißt {f}",
                   "en": "Step {s}: reference to start.{f} — no start data field is called {f}"},
    "start_auftrag": {"de": "Schritt {s}: Startdaten der Gastseite gehen ohne Rückfrage in den "
                            "Auftrag — eine Wahl oder ein Modul davor zeigt sie der Person erst",
                      "en": "Step {s}: start data from the host page go into the job without a "
                            "check-back — a choice or a module before it shows them to the person "
                            "first"},
    "start_reserviert": {"de": "Schritt {s}: der Teil start ist für die Startdaten reserviert",
                         "en": "Step {s}: the part start is reserved for the start data"},
    "start_pflicht": {"de": "Pflichtfelder in den Startdaten brauchen den Auslöser extern "
                            "(Gastseite) oder agent (KI) — sonst startet der Ablauf nie",
                      "en": "Required start data fields need the trigger extern (host page) or "
                            "agent (AI) — otherwise the workflow never starts"},
    "agent_zu_viele": {"de": "{n} aktive Abläufe schlägt die KI vor — ein Zug bekommt höchstens "
                             "{m} als Werkzeug, die übrigen bietet er nie an",
                       "en": "{n} active workflows are suggested by the AI — a turn gets at most "
                             "{m} as tools, it never offers the others"},
    "start_beschreibung": {"de": "Startdaten: Feld {f} ohne Beschreibung — mit dem Auslöser agent "
                                 "ist sie die Anleitung für die KI",
                           "en": "Start data: field {f} has no description — with the trigger "
                                 "agent it is the instruction for the AI"},
    "platzhalter_teil": {"de": "Schritt {s}: Platzhalter {p} — kein Schritt und kein Modul "
                               "schreibt den Teil {t}",
                         "en": "Step {s}: placeholder {p} — no step or module writes the part "
                               "{t}"},
    "platzhalter_spaeter": {"de": "Schritt {s}: Platzhalter {p} — der Teil {t} entsteht erst "
                                  "nach diesem Schritt",
                            "en": "Step {s}: placeholder {p} — the part {t} is only created "
                                  "after this step"},
    "wert_allein": {"de": "Schritt {s}: wenn_wert steht allein — nicht zusammen mit wenn_teil "
                          "oder wenn_gewaehlt",
                    "en": "Step {s}: wenn_wert stands alone — not together with wenn_teil or "
                          "wenn_gewaehlt"},
    "wert_quelle": {"de": "Schritt {s}: Quelle {q} — erwartet teil.<name> oder "
                          "teil.<name>.<pfad>",
                    "en": "Step {s}: source {q} — expected teil.<name> or teil.<name>.<pfad>"},
    "wert_teil": {"de": "Schritt {s}: Quelle {q} — kein Schritt und kein Modul schreibt den Teil "
                        "{t}",
                  "en": "Step {s}: source {q} — no step or module writes the part {t}"},
    "wert_spaeter": {"de": "Schritt {s}: Quelle {q} — der Teil {t} entsteht erst nach diesem "
                           "Schritt",
                     "en": "Step {s}: source {q} — the part {t} is only created after this "
                           "step"},
    "wert_fehlt": {"de": "Schritt {s}: der Vergleich {v} braucht einen Wert",
                   "en": "Step {s}: the comparison {v} needs a value"},
    "wert_ohne": {"de": "Schritt {s}: der Vergleich {v} prüft ohne Wert — Wert leer lassen",
                  "en": "Step {s}: the comparison {v} checks without a value — leave it empty"},
    "wert_zahl": {"de": "Schritt {s}: der Vergleich {v} braucht eine Zahl als Wert",
                  "en": "Step {s}: the comparison {v} needs a number as value"},
    "platzhalter_label": {"de": "Schritt {s}: in Beschriftungen von Schnellantworten wirken "
                                "Platzhalter nicht",
                          "en": "Step {s}: placeholders do not work in quick reply labels"},
    "wahl_typ": {"de": "Schritt {s}: Schnellantworten und Freitext gibt es nur an nachricht und "
                       "modul",
                 "en": "Step {s}: quick replies and free text only exist on nachricht and modul"},
    "wahl_weiter": {"de": "Schritt {s}: mit Schnellantworten entscheidet die Wahl — weiter "
                          "bleibt leer",
                    "en": "Step {s}: with quick replies the choice decides — leave weiter "
                          "empty"},
    "wahl_abfragend": {"de": "Schritt {s}: das Modul {m} ist abfragend und wartet selbst auf die "
                             "Antwort — keine Schnellantworten daneben",
                       "en": "Step {s}: module {m} asks and waits for its own answer — no quick "
                             "replies next to it"},
    "text": {"de": "Schritt {s}: Text (de) fehlt", "en": "Step {s}: text (de) missing"},
    "modul": {"de": "Schritt {s}: Modul {m!r} gibt es nicht",
              "en": "Step {s}: module {m!r} does not exist"},
    "daten": {"de": "Schritt {s}: Daten passen nicht zum Modul {m} ({f})",
              "en": "Step {s}: data do not fit module {m} ({f})"},
    "schreibend": {"de": "Schritt {s}: Werkzeug {w} ist schreibend — das geht nur in einem "
                         "werkzeug-Schritt mit Freigabe, mit einem bestätigbaren WLO-Werkzeug, das "
                         "nicht löscht",
                   "en": "Step {s}: tool {w} writes — only possible in a werkzeug step with "
                         "approval, with a confirmable WLO tool that does not delete"},
    "schluessel_fest": {"de": "Schritt {s}: argumente dürfen keinen Schlüssel tragen ({f}) — den "
                              "setzt nur die Freigabe der Person",
                        "en": "Step {s}: arguments must not carry a key ({f}) — only the person's "
                              "approval sets it"},
    "freigabe_typ": {"de": "Schritt {s}: freigabe gibt es nur an einem werkzeug-Schritt",
                     "en": "Step {s}: freigabe only exists on a werkzeug step"},
    "freigabe_fehlt": {"de": "Schritt {s}: das schreibende Werkzeug {w} braucht eine Freigabe (der "
                             "Satz über der Vorschau, mindestens auf Deutsch)",
                       "en": "Step {s}: the writing tool {w} needs an approval (the sentence above "
                             "the preview, at least in German)"},
    "freigabe_lesend": {"de": "Schritt {s}: eine Freigabe gibt es nur an einem schreibenden "
                              "Werkzeug ({w} schreibt nicht)",
                        "en": "Step {s}: an approval only exists on a writing tool ({w} does not "
                              "write)"},
    "freigabe_anmeldung": {"de": "Schreibende Schritte brauchen die Voraussetzung Anmeldung",
                           "en": "Writing steps need the requirement sign-in"},
    "werkzeug": {"de": "Schritt {s}: Werkzeug {w!r} ist unbekannt",
                 "en": "Step {s}: tool {w!r} is unknown"},
    "dienst_argument": {"de": "Schritt {s}: Dienst {w} kennt das Argument {a} nicht "
                              "(erwartet: {e})",
                        "en": "Step {s}: service {w} does not know the argument {a} (expected: "
                              "{e})"},
    "dienst_argument_fehlt": {"de": "Schritt {s}: Dienst {w} braucht das Argument {a}",
                              "en": "Step {s}: service {w} needs the argument {a}"},
    "mcp_teil": {"de": "Schritt {s}: lesende WLO-Werkzeuge bekommen keine Teile des Vorgangs — "
                       "nur eine Kennung aus den Startdaten (Feld vom Typ Knoten-Kennung, als "
                       "ganzes Argument, mit dem Auslöser Gastseite)",
                 "en": "Step {s}: read-only WLO tools get no parts of the work item — only an id "
                       "from the start data (field of type node id, as a whole argument, "
                       "with the trigger host page)"},
    "teil": {"de": "Schritt {s}: Teil {t!r} hat keine gültige Form",
             "en": "Step {s}: part {t!r} has no valid form"},
    "dateien_holen": {"de": "Schritt {s}: dateien_holen gibt es nur an einem Auftragsschritt",
                      "en": "Step {s}: dateien_holen only exists on a job step"},
    "pfad": {"de": "Schritt {s}: Pfad {p!r} in Teil {t!r} hat keine gültige Form "
                   "(höchstens acht Glieder mit Punkt getrennt, je 1 bis 64 Zeichen aus A–Z, "
                   "a–z, 0–9, _ und -)",
             "en": "Step {s}: path {p!r} in part {t!r} has no valid form "
                   "(at most eight segments separated by dots, each 1 to 64 characters from "
                   "A–Z, a–z, 0–9, _ and -)"},
    "argumente_ganz": {"de": "Schritt {s}: argumente können kein ganzer Verweis sein — nur die "
                             "einzelnen Werte (ein ganzer Verweis geht nur bei daten)",
                       "en": "Step {s}: arguments cannot be a whole reference — only the single "
                             "values (a whole reference only works for data)"},
    "zu_tief": {"de": "Schritt {s}: Verweis auf Teil {t!r} liegt tiefer als {max} Ebenen — der "
                      "Lauf setzt ihn nicht ein",
                "en": "Step {s}: reference to part {t!r} is nested deeper than {max} levels — "
                      "the run does not fill it in"},
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
    "wendung_doppelt": {"de": "Die Wendung „{w}“ überschneidet sich mit: {andere} — es gilt der "
                               "Ablauf mit der kleinsten Kennung",
                        "en": "The phrase “{w}” overlaps with: {andere} — the workflow with the "
                              "smallest id wins"},
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
    "bei_fehler_typ": {"de": "Schritt {s}: bei_fehler wirkt bei der Art {typ} nicht (nur bei "
                             "modul, werkzeug, agent und auftrag)",
                       "en": "Step {s}: bei_fehler has no effect on kind {typ} (only on modul, "
                             "werkzeug, agent and auftrag)"},
    "warten": {"de": "Schritt {s}: warten gilt nur an Schritten der Art auftrag",
               "en": "Step {s}: warten only applies to steps of kind auftrag"},
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
    # AS-7a (Plan 2026-11-09 §5m): Führungen
    "seite_url": {"de": "Schritt {s}: url muss ein Pfad mit / oder eine https-Adresse ohne "
                        "Zugangsdaten sein",
                  "en": "Step {s}: url must be a path starting with / or an https address "
                        "without credentials"},
    "seite_label": {"de": "Schritt {s}: label (Aufschrift des Chips) fehlt auf Deutsch",
                    "en": "Step {s}: label (text of the chip) is missing in German"},
    "seite_felder": {"de": "Schritt {s}: url, label und ankunft gibt es nur bei Art seite",
                     "en": "Step {s}: url, label and arrival only exist for kind page"},
    "seite_muster": {"de": "{wo}: Muster {m!r} ungültig ({f}) — erwartet ein Pfad mit / und * als "
                           "Platzhalter",
                     "en": "{wo}: pattern {m!r} invalid ({f}) — expected a path with / and * as "
                           "wildcard"},
    "seite_anzahl": {"de": "{wo}: höchstens {max} Muster",
                     "en": "{wo}: at most {max} patterns"},
    "seite_unerreichbar": {"de": "Schritt {s}: das Ziel (url) passt zu keinem Muster der ankunft — "
                                  "der Lauf wartete für immer",
                            "en": "Step {s}: the target (url) matches no arrival pattern — the run "
                                  "would wait forever"},
    "muster_leer": {"de": "leer", "en": "empty"},
    "muster_lang": {"de": "länger als 200 Zeichen", "en": "longer than 200 characters"},
    "muster_form": {"de": "beginnt nicht mit / oder enthält Zeichen außer Pfad und *",
                    "en": "does not start with / or contains characters other than path and *"},
    "seite_allein": {"de": "Schritt {s}: wenn_seite steht allein in seiner Regel",
                     "en": "Step {s}: wenn_seite stands alone in its rule"},
    "schritt_wo": {"de": "Schritt {s}", "en": "Step {s}"},
    "ausloeser_wo": {"de": "Auslöser seite", "en": "Trigger page"},
    "seite_ausloeser": {"de": "Auslöser seite: 1 bis {max} Muster erwartet",
                        "en": "Trigger page: 1 to {max} patterns expected"},
}


def t(lang: str, schluessel: str, **werte: Any) -> str:
    vorlagen = _T[schluessel]
    return (vorlagen.get(lang) or vorlagen["de"]).format(**werte)
