"""Die Fehlertexte des Dienstes ``strukturentwurf`` an die KI (aus ``ui_module/dienst`` gelöst,
Review N3, MINOR 8 — verhaltensgleich). Ein Fehlertext nennt nie Inhalte des Modells oder
Ausnahmetexte — nur die Art; ``{name}`` ist der Name des Moduls."""

from __future__ import annotations

from typing import Final

FEHLER_ARGUMENTE: Final = ("Fehler: Der Aufruf von {name} passt nicht zur Beschreibung des "
                            "Werkzeugs. Berichtige die Argumente und rufe es noch einmal, oder "
                            "antworte in Prosa. Abweichungen: {fehler}")
FEHLER: Final = {
    "kein_dokument": ("Fehler: Es liegt kein Dokument der Person vor (nicht hochgeladen, oder es "
                      "ist abgelaufen). Rufe {name} nicht mit aus_dokument auf; bitte die Person, "
                      "das Dokument im Auswahlfeld (ui_upload) noch einmal zu wählen."),
    # Review TG-3d–f, MINOR 3: nur Strukturdokumente aus WLO, und keins hat schon einen Volltext
    # Plan 2026-11-16, Durchtest TG-7 (m3): ein Lesefehler (Frist, Abruf) — der Text ist womöglich
    # da, nur gerade nicht zu bekommen
    "volltext_fehlt": ("Fehler: Den Volltext der Strukturdokumente der Person ({namen}) konnte "
                       "WLO gerade nicht liefern. Rufe {name} jetzt nicht noch einmal auf; sag "
                       "der Person, dass es in einigen Minuten noch einmal geht."),
    # m3: ``not_extracted`` heißt „aus der Datei kam (noch) kein Text“ — für eine Datei, deren Text
    # gerade entsteht, ebenso wie für einen Scan oder ein Bild, das nie Text hat. Das MCP
    # unterscheidet beides nicht; der Satz nennt beides ehrlich.
    # Paket K5 (E14): meist entsteht der Text nach dem Übertragen gerade — der Ablauf scheitert
    # nicht, er wartet an seinem KI-Schritt; erneut anstoßen ist eine neue Nachricht dort (Review
    # B5: konkret „nochmal“ schreiben).
    "volltext_fehlt_datei": ("Fehler: Aus den Strukturdokumenten der Person ({namen}) hat WLO "
                             "(noch) keinen Text gewonnen — meist wird er nach dem Übertragen "
                             "gerade erzeugt (das dauert einige Minuten); selten enthält die "
                             "Datei keinen lesbaren Text (etwa ein Scan oder ein Bild). Der Ablauf "
                             "wartet an diesem Schritt, nichts ist verloren. Rufe {name} jetzt "
                             "nicht noch einmal auf; sag der Person: Der Text wird gerade erzeugt "
                             "— in ein paar Minuten einfach „nochmal“ schreiben; geht es dann "
                             "nicht, eine Fassung mit Text hochladen (etwa ein PDF mit Textschicht "
                             "oder Word)."),
    # Nachprüfung TG-3d–f, MINOR 4: derselbe Code, der Satz nach dem Grund
    "volltext_fehlt_anmeldung": ("Fehler: Die Strukturdokumente der Person liegen in ihrem "
                                 "persönlichen Bereich in WLO ({namen}); ohne Anmeldung lassen "
                                 "sie sich nicht lesen. Rufe {name} jetzt nicht noch einmal auf; "
                                 "bitte die Person, sich bei WLO anzumelden."),
    "volltext_fehlt_zugriff": ("Fehler: Auf die Strukturdokumente der Person ({namen}) gibt es "
                               "keinen Zugriff, oder WLO findet sie nicht mehr. Rufe {name} nicht "
                               "noch einmal auf; sag der Person, dass sie die Dokumente neu "
                               "hochladen oder lesen lassen kann."),
    "keine_inhalte": ("Fehler: Im Vorgang liegen keine Metadaten der Materialien (Teil "
                      "metadaten). Rufe {name} nicht mit aus_inhalten auf; sag der Person, dass "
                      "die Materialien erst hochgeladen und gelesen sein müssen."),
    "abgewiesen": ("Fehler: Die Angaben zu den Materialien der Person hat die Prüfung "
                   "abgewiesen. Rufe {name} nicht noch einmal auf; sag der Person, dass aus diesen "
                   "Materialien kein Entwurf entstehen kann."),
    "pruefung_fehlt": ("Fehler: Die Angaben zu den Materialien ließen sich gerade nicht prüfen. "
                       "Rufe {name} nicht noch einmal auf; sag der Person, dass sie es gleich noch "
                       "einmal versuchen kann."),
    "inhalte_ausschluss": ("Fehler: aus_inhalten schließt vorlage und aus_dokument aus. Rufe "
                           "{name} für einen neuen Entwurf aus den Materialien nur mit "
                           "aus_inhalten auf."),
    "dokument_vorlage": ("Fehler: aus_dokument und vorlage schließen sich aus. Rufe {name} für "
                         "einen neuen Entwurf aus dem Dokument ohne vorlage auf."),
    "vorlage": ("Fehler: Mit dieser Nachricht wurde kein Entwurf mitgeschickt. Rufe {name} ohne "
                "vorlage auf (ein neuer Entwurf) oder antworte in Prosa."),
    "ausgelastet": ("Fehler: Der Entwurf ließ sich gerade nicht erzeugen, das System ist "
                    "ausgelastet. Rufe {name} nicht noch einmal auf; sag der Person, dass sie es "
                    "gleich noch einmal versuchen kann."),
    "erneut": ("Fehler: erneut_zeigen gilt nur mit vorlage: true (dem Entwurf aus [ENTWURF DER "
               "PERSON] oder [DEIN LETZTER ENTWURF]). Rufe {name} mit vorlage auf."),
    "ohne_texte": ("Fehler: Der letzte Entwurf war zu groß und ist nur ohne Beschreibungen und "
                   "Schlagworte gemerkt; unverändert zeigen ginge nicht ohne sie. Rufe {name} "
                   "nicht mit erneut_zeigen auf; sag der Person, dass sie ihn aus dem früheren "
                   "Entwurf herunterladen kann, oder biete einen neuen oder vertieften an."),
    "vertiefen": ("Fehler: vertiefen gilt nur mit vorlage: true (dem Entwurf, den die Person "
                  "mitgeschickt hat). Rufe {name} mit vorlage auf oder ohne vertiefen."),
    "nichts_zu_vertiefen": ("Fehler: Im mitgeschickten Entwurf gibt es nichts zu vertiefen: kein "
                            "Punkt trägt einen der genannten Titel, oder alle haben schon genug "
                            "Unterpunkte. Nenne in vertiefen Titel genau wie im Entwurf "
                            "([ENTWURF DER PERSON]) oder antworte in Prosa."),
    "frist": ("Fehler: Für den Entwurf reichte die Zeit nicht. Rufe {name} nicht noch einmal auf; "
              "biete an, es mit weniger Punkten (anzahl_oben) oder tiefe 1 zu versuchen."),
}
FEHLER_SONST: Final = ("Fehler: Der Entwurf ließ sich nicht erzeugen. Rufe {name} nicht noch "
                        "einmal auf; antworte ohne Entwurf.")
