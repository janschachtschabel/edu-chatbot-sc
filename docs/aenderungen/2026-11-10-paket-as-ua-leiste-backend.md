# Paket AS-Ua: Backend der Ablauf-Leiste (2026-11-10)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5h
(D10, E5). Die Entscheide U-1 bis U-8 stehen dort. Eine Änderung gegenüber dem Plan ist unten
begründet.

Keine Migration, keine neue Variable. Das Backend-Image muss neu gebaut werden.

## Was sich ändert

- **`ui.ablauf` (U-1, U-2):** Solange im Gespräch ein Lauf nicht beendet ist, trägt **jede**
  Antwort den Stand: `{id, titel, nr, von, status, teile: [{name, text}]}`.
  - Gerechnet wird er nach dem Zug aus dem Sitzungsverweis, ohne Datenbank
    (`fortschritt.stand`, angehängt in `api/chat._anmeldestand`, für POST und Strom gleich).
  - Den Titel gibt es in der Sprache des Zugs. Die Teile sind die Kurztexte des Arbeitsstands,
    **ohne** den Teil `start` und ohne Kennungen in UUID-Form (ersetzt durch „…“).
  - Ein beendeter Lauf, ein unbekannter Ablauf oder ein Schritt, den der Ablauf nicht mehr hat,
    ergeben keinen Stand.
- **Nach dem Neuladen — Änderung gegenüber U-1:**
  - **Wie:** Der Verlauf (`GET /api/sessions/{id}/messages`) rechnet den **aktuellen** Stand aus
    der Sitzung und hängt ihn an die letzte Bot-Nachricht (`publikum.mit_ablauf_stand`).
  - **Statt:** den Stand bei jeder Nachricht im Debug-Block mitzuschreiben.
  - **Grund:** Es gibt mehrere Speicherwege (Zug, Ablauf-Antworten, Hinweise), und ein
    gespeicherter Stand wäre nach einem späteren Zug veraltet.
  - ~~**Grenze:** Trägt der Abruf des Verlaufs die Anmeldung einer angemeldeten Person nicht, bleibt
    die Leiste bis zum nächsten Zug aus.~~ Behoben mit dem Querschnitts-Review (Plan §5k, Q-1): der
    Verlauf trägt den Zugangsblock, `_ablauf_stand` übernimmt und bestätigt ihn.
- **„Schritt n von m“ (U-3):** `fortschritt.position`.
  - `n` ist der längste einfache Weg vom ersten Schritt bis hierher; `m` = `n` − 1 + der längste
    einfache Weg bis zum Ende.
  - Es zählen nur reguläre Kanten (`pruefung.regulaere_nachfolger`, ohne `bei_fehler`) und keine
    `ende`-Schritte. Rückwege zählen nicht, denn jeder Schritt kommt höchstens einmal je Weg vor.
  - Ein Besuchsbudget schützt vor sehr verzweigten Abläufen.
- **`ui.fester_text` (U-7):** Antworten des Ablauf-Treibers (`zug_basis.antwort`) und seine festen
  Hinweise (`zug_basis.nur_text`) tragen den Merker, live und im Verlauf (Debug-Schlüssel
  `_fester_text`). Das Widget lässt dort „KI-generierte Antwort“ weg (AS-Ub).
- **Direktaktion `ablauf_abbrechen` (U-5):** `services/ablauf/abbruch_zug.py`.
  - Erst eine Rückfrage, ihr Knopf trägt `bestaetigt` und die Marke des Laufs. Hat sich der Lauf
    bewegt, fragt der Zug neu.
  - Danach `zug_basis.abbrechen`, das auch einen wartenden Auftrag beendet, samt den Knöpfen
    „neues Vorhaben“/„Arbeitsstand löschen“.
  - Ohne Lauf kommt ein Hinweis. Die Aktion ist auch im gesperrten Lauf erlaubt (K2b).
- **Texte:**
  - Neu: `action.ablauf.keinLauf`, `abbrechenFrage`, `abbrechenJa`, `abgebrochenPerson` (DE/EN).
  - Die Rückfrage `action.ablauf.ersetzen` ist neutral formuliert („Ein Ablauf soll starten …“),
    denn seit AS-5 löst sie auch ein Vorschlag der KI aus, nicht nur die Seite.

## Tests

- **Neu:** `tests/test_ablauf_leiste.py` (15 Tests). Er deckt ab:
  - Position: gerade, nach einer Verzweigung, mit Rückweg und `bei_fehler`, unbekannter Schritt;
  - Stand: Sprache, ohne `start`, ohne Kennungen; kein Stand nach dem Ende oder für eine fremde
    Besitzerin;
  - `antwort_fuer` behält Stand und Merker; der Merker bleibt im Verlauf, der Stand steht an der
    letzten Antwort;
  - Abbrechen: Rückfrage, Abbruch, alte Bestätigung, ohne Lauf; Registrierung im Preflight.
- **Angepasst:** `test_publikum.py` hält die neuen öffentlichen Schlüssel `ablauf` und
  `fester_text` fest. OpenAPI ist neu exportiert.
- **Gezielt** (Abläufe, Publikum, Chat, Sitzung, Preflight, Vorgang, Auftrag, Freigabe, Wahl,
  i18n, OpenAPI, Arbeitsstand): 1790 grün, 2 Vertragswächter bewusst nachgezogen.

## Review (unabhängig, 2026-11-10)

Ergebnis: 0 kritisch, 2 schwer, 6 klein, 4 Kleinigkeiten. Bestätigt wurde:
- Beide Wege (POST, Strom) hängen den Stand an; `antwort_fuer` behält ihn.
- Die neue Aktion läuft durch das Safety-Gate. Abbrechen darf nur die Besitzerin, die Marke greift.
- Der Verlauf zeigt angemeldeten Personen ohne Anmeldung im Abruf keinen Stand; der Rest ist ohnehin
  Teil des Verlaufs.

Alle Befunde sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Ein Abbruch am Freigabe-Schritt ließ einen angelaufenen Schreib-Plan stehen. Ein älterer Knopf „Plan fortsetzen“ hätte danach weiter in WLO geschrieben, und die Antwort verschwieg es. | schwer | Wie das eigene „Abbrechen“ am Freigabe-Schritt: Der offene Plan fällt weg, und bei einem angelaufenen Plan sagt die Antwort `freigabeAbgebrochenPlan`. Test. |
| 2 | `fester_text` stand an jeder Treiber-Antwort, auch wenn Platzhalter KI-Ausgabe einsetzten (`{teil.…}`, `{start.…}` eines KI-Vorschlags). | schwer | `treiber.Ausgabe.ki_inhalt` wird beim Einsetzen gesetzt (`platzhalter.herkuenfte`). Fest ist eine Antwort nur ohne KI-Inhalt und ohne Modul-Blöcke, weil ein Block einen KI-Entwurf zeigen kann. Startdaten der Gastseite bleiben fest. Tests. |
| 3 | `bis` und `ab` teilten sich ein Budget; `bis` durchsuchte auch Zweige, die das Ziel nie erreichen. Ergebnis war „Schritt 6 von 6“ statt etwa „6 von 39“. | klein | Ein eigenes Budget je Suche; `bis` geht nur über Schritte, die das Ziel erreichen (Rückwärts-Erreichbarkeit). Ist das Budget erschöpft, schätzt `ab` nach oben. Test mit 40 Schritten. |
| 4 | Die Suche lief synchron bei jedem Zug und jedem Abruf des Verlaufs. | klein | Zwischenspeicher je `(Ablauf, Fassung, Schritt)`, höchstens 512 Einträge. Test. |
| 5 | Ein Schritt nur hinter `bei_fehler` zeigte „Schritt 1“. | klein | Rückfall über alle Kanten, samt `bei_fehler`. Test. |
| 6 | Ohne den Schlüssel der Person endet ein Auftrag nur hier; die Antwort sagte „abgebrochen“. | klein | Text `auftragNurHierAbgebrochen` wie beim Abbruch am Auftragsschritt. Test. |
| 7 | Fehler- und „ausgelastet“-Blasen trugen keinen Stand, die Leiste verschwand. | klein | `_fehlerblase` hängt den Stand aus der gespeicherten Sitzung an. Das Log steht auf DEBUG, weil die Datenbank dort oft der Grund des Fehlers ist; der Wächter „ausgelastet ohne Warnung“ bleibt grün. |
| 8 | Testlücken (Auftrag, Freigabe, Platzhalter, großer Graph). | klein | Ergänzt (insgesamt 23 Tests). |
| 9 | Nach einer Änderung der Fassung zeigte der Stand eine Position im neuen Graphen. | Kleinigkeit | Bei abweichender Fassung oder ausgeschaltetem Ablauf kein Stand. Test. |
| 10 | Private Helfer von `zug` wurden über die Modulgrenze genutzt. | Kleinigkeit | Öffentliche Namen: `aktiver_lauf`, `lauf_marke`, `rueckfrage_knopf`. |
| 11 | Plan U-2 nannte `wartet_wahl` nicht. | Kleinigkeit | Nachgezogen (offene Liste, das Widget zeigt bei Unbekanntem nur den Schritt). |
| 12 | Zwei feste Hinweise in `freigabe_zug` trugen keinen Merker. | Kleinigkeit | Merker gesetzt, live und im Verlauf. |
