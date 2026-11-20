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
    # Plan 2026-11-20 §8, E1: ``not_extracted`` ist endgültig — das Repositorium erzeugt den Text
    # synchron beim ersten Lesen und wiederholt eine gescheiterte Extraktion nie (Messung §7). Statt
    # „nochmal“ (Paket K5) die beiden Auswege; im Ablauf tragen sie feste Knöpfe hinter „Weiter im
    # Ablauf“ (Seed ``themenbaum``, Schritt ``ohne_dokumenttext``).
    "volltext_endgueltig": ("Fehler: WLO konnte aus den Strukturdokumenten der Person ({namen}) "
                            "keinen Text gewinnen (etwa ein Scan, oder die Umwandlung in WLO ist "
                            "gescheitert); ein neuer Versuch hilft nicht. Rufe {name} nicht noch "
                            "einmal auf und vertröste die Person nicht auf später. Sag es ihr in "
                            "einem Satz und nenne die zwei Auswege: „Hier im Chat lesen lassen“ "
                            "(das Dokument im Auswahlfeld mit dem Ort „Hier im Chat“ "
                            "hochladen{scan}) oder „Ohne Dokument weiter“ "
                            "(etwa mit einem Thema). In einem Ablauf führt der Knopf „Weiter im "
                            "Ablauf“ zu beiden."),
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
    # Review Paket A (vorbestehend): beim Dokument eigene Sätze — die obigen nennen „Materialien“
    "abgewiesen_dokument": ("Fehler: Den Text des Dokuments der Person hat die Prüfung "
                            "abgewiesen. Rufe {name} nicht noch einmal auf; sag der Person, dass "
                            "aus diesem Dokument kein Entwurf entstehen kann."),
    "pruefung_fehlt_dokument": ("Fehler: Der Text des Dokuments ließ sich gerade nicht prüfen. "
                                "Rufe {name} jetzt nicht noch einmal auf; sag der Person, dass sie "
                                "es gleich noch einmal versuchen kann (einfach „nochmal“ "
                                "schreiben)."),
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
    # Plan 2026-11-19, A1 (E3, Befund S1): der Anbieter war auch nach einer Wiederholung nicht
    # erreichbar — keine Sackgasse; der Ablauf bleibt am Schritt (wie ``volltext_fehlt``)
    "voruebergehend": ("Fehler: Das KI-Modell für den Entwurf ist gerade nicht erreichbar "
                       "(vorübergehend). Rufe {name} jetzt nicht noch einmal auf; sag der Person: "
                       "gerade nicht erreichbar — in einem Moment einfach „nochmal“ schreiben."),
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


def namen(fehlend: tuple[tuple[str, str], ...]) -> str:
    """Die Namen fehlender Dokumente für die KI — eine Zeile je Name, ohne Anführungs- und
    Rahmenzeichen (Text der Person, Review TG-3d–f, MINOR 3)."""
    from boerdi.ui_module.rahmen import name_fuer_ki

    return ", ".join(f"„{name_fuer_ki(n)}“" for n, _grund in fehlend[:5])


def volltext_satz(fehlend: tuple[tuple[str, str], ...]) -> str:
    """Nachprüfung TG-3d–f, MINOR 4: welcher Satz zu ``volltext_fehlt`` passt — kein Text
    (endgültig, E1), später (Lesefehler, Frist), Anmeldung fehlt, oder kein Zugriff bzw. nicht
    gefunden. Der Satz ``volltext_endgueltig`` ist zugleich der Code des Ergebnisses."""
    from boerdi.services.dokumente.strukturdokument import NICHT_EXTRAHIERT, SPAETER

    gruende = {g for _n, g in fehlend}
    if NICHT_EXTRAHIERT in gruende:
        # Durchtest TG-7, m3: vor dem Lesefehler. E1: endgültig — die Auswege statt „nochmal“
        return "volltext_endgueltig"
    if gruende & SPAETER:
        return "volltext_fehlt"
    if gruende == {"ohne_anmeldung"}:
        return "volltext_fehlt_anmeldung"
    return "volltext_fehlt_zugriff"


def _chat_mit_texterkennung() -> bool:
    """Review Paket E, MINOR 7: liest „Hier im Chat“ gerade auch Scans (Studio, Texterkennung)?"""
    from boerdi.services.config_loader.upload import load_upload_config
    from boerdi.services.dokumente import ocr

    cfg = load_upload_config()
    return bool(cfg.dokument_im_chat) and ocr.aktiv(cfg)


def volltext_fehler(name: str, fehlend: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    """Text an die KI und Code des Ergebnisses, wenn kein Strukturdokument einen Volltext hat.
    Review Paket E, MINOR 3: ``volltext_endgueltig`` nennt nur die Dokumente ohne Text; zu den
    übrigen folgt je ein Satz aus :func:`ohne_volltext`. MINOR 7: „auch Text in Scans“ nur, wenn
    hier im Chat die Texterkennung läuft."""
    from boerdi.services.dokumente.strukturdokument import NICHT_EXTRAHIERT

    satz = volltext_satz(fehlend)
    if satz != "volltext_endgueltig":
        return FEHLER[satz].format(name=name, namen=namen(fehlend)), "volltext_fehlt"
    ohne_text = tuple(f for f in fehlend if f[1] == NICHT_EXTRAHIERT)
    rest = tuple(f for f in fehlend if f[1] != NICHT_EXTRAHIERT)
    scan = "; dort wird auch Text in Scans erkannt" if _chat_mit_texterkennung() else ""
    text = FEHLER[satz].format(name=name, namen=namen(ohne_text), scan=scan)
    return (f"{text} {ohne_volltext(rest)}" if rest else text), satz


def ohne_volltext(fehlend: tuple[tuple[str, str], ...]) -> str:
    from boerdi.services.dokumente.strukturdokument import ABGELAUFEN, NICHT_EXTRAHIERT, SPAETER

    def satz(n: str, g: str) -> str:
        name = namen(((n, g),))
        if g == NICHT_EXTRAHIERT:
            # Durchtest TG-7, m3; E1: endgültig, mit dem Ausweg
            return (f"Dokument {name}: WLO konnte keinen Text gewinnen — es lässt sich hier im "
                    "Chat lesen lassen.")
        if g in SPAETER:
            return f"Dokument {name}: Volltext gerade nicht lesbar, später erneut."
        if g == ABGELAUFEN:
            # Nachprüfung, NIT 6: ein Sitzungsdokument, das nicht mehr lesbar ist
            return f"Dokument {name}: nicht mehr lesbar (abgelaufen), bitte neu lesen lassen."
        if g == "ohne_anmeldung":
            return f"Dokument {name}: nur mit Anmeldung bei WLO lesbar."
        return f"Dokument {name}: kein Volltext lesbar."

    return " ".join(satz(n, g) for n, g in fehlend[:5])
