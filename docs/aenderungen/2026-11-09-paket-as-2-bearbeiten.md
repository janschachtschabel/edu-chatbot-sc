# Paket AS-2: Abläufe bearbeiten, ohne JSON (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D4 (Regel-Editor)
und D6 (Ablaufbild, Querverweise).

## Was sich ändert

- **AS-2a: Regel-Editor für `weiter`.** Bisher stand dort eine JSON-Box. Jetzt wählt man eine von drei Arten:
  - „mit dem nächsten Schritt der Liste“: das Feld bleibt leer;
  - „mit einem bestimmten Schritt“: das Ziel kommt aus einer Auswahl der Schritte, ohne den eigenen;
  - „nach Regeln“: je Regel eine Bedingung („gewählt ist“, „Teil vorhanden“, „sonst“), ihr Wert
    und das Ziel, mit Knöpfen zum Verschieben und Entfernen.
  - **Vorschläge:** die Möglichkeiten der Auswahlfelder und die Teile, die der Ablauf schreibt
    (`datalist`).
  - **Unbekanntes Ziel:** es bleibt sichtbar und ist markiert.
  - **Halbe Regel:** fehlt der Wert oder das Ziel, oder steht „sonst“ nicht zuletzt, meldet sich
    das Feld wie ein fehlerhaftes JSON-Feld und sperrt das Speichern.
  - **Was der Editor nicht zeigen kann** (zwei Bedingungen in einer Regel, fremde Felder), bleibt
    eine JSON-Box.
  - **Backend:** nur eine Auszeichnung im Schema (`x-widget: weiter` an `Schritt.weiter`). Modell,
    Prüfung und Treiber bleiben unverändert.
- **AS-2b: das Ablaufbild** unter „Prüfen und Schrittfolge“, als SVG und nur lesend.
  - **Kästen:** je Schritt ein Kasten, untereinander.
  - **Linien:** der reguläre Weg zum nächsten Schritt ist eine gerade Linie. Sprünge, Regeln und
    „bei Fehler“ sind Bögen rechts daneben, je Bogen auf einer eigenen Spur.
  - **„Bei Fehler“** ist gestrichelt.
  - **Unbekanntes Ziel:** der Kasten hat einen kräftigen Rand und ein ⚠, denn Farbe allein reicht
    nicht.
  - **Ein Klick auf einen Kasten** wählt den Schritt in der Liste der Schritte. Die Liste klappt
    ihren Abschnitt auf, hebt eine Suche auf, die den Schritt verbergen würde, und setzt den Fokus
    auf ihn.
  - **Für Vorlesehilfe und Tastatur** ist das Bild `aria-hidden`. Dieselbe Auskunft steht in der
    Schrittfolge darunter, und dort führt je Schritt ein Knopf „Zum Schritt“ an dieselbe Stelle.
  - **Mehr als zwölf Schritte:** das Bild ist zugeklappt. Ist es breiter als der Platz, rollt es
    seitlich.
  - **Umbau:** die Schrittfolge steht jetzt in einer eigenen Komponente (`ablauf-schrittfolge`),
    getrennt von „Prüfen/Tests“.
- **AS-2c: Querverweise Modul ↔ Ablauf.**
  - **Seite „UI-Module“:** je Modul steht „In Abläufen“ mit den Abläufen, die es zeigen (aus
    `GET /config/ablaeufe`). Ein ausgeschalteter Ablauf ist als „aus“ markiert. Jeder Eintrag
    verweist auf `/ablaeufe?ablauf=<id>`.
  - **Liste kommt nicht:** die Stelle sagt es und bietet „Erneut versuchen“. Der Rest der Seite
    bleibt bedienbar.
  - **Schrittfolge:** ein Modul-Schritt verweist auf `/ui-module?modul=<name>`. Ohne Router, etwa
    in Tests, steht der Name als Text da.
  - **Wahl über die Adresse:** `?ablauf=` wählt den Ablauf, sobald die Liste da ist, und zwar nur
    einmal, damit eine neu geladene Liste nach dem Speichern nicht zurückspringt. `?modul=` wählt
    das Modul.

## Wo

- **Backend:**
  - `domain/config_models/_shared.py`: `WeiterRegeln()`;
  - `domain/config_models/ablauf.py`: `weiter` mit der Auszeichnung;
  - Schema-Exporte `docs/api/openapi-v1.json` und `area-schemas.fixture.ts` neu erzeugt.
- **Studio, Formular (`schema-form/`):**
  - Regel-Editor: `weiter-regeln.ts` (rein), `weiter-editor.component.ts`;
    `schema-to-fields.ts` und `field-control.component.*` binden ihn ein;
  - Ablaufbild: `ablauf-bild.ts` (Geometrie, rein), `ablauf-bild.component.ts`;
  - Schrittfolge: `ablauf-schrittfolge.component.ts` (aus `ablauf-pruefen` herausgelöst);
    `ablauf-folge.ts` liefert dazu das Modul eines Modul-Schritts;
  - Sprung zur Liste: `form-listenwahl.ts` (Token, von `schema-form` bereitgestellt);
    `object-list.component.ts` nimmt den Wunsch an;
  - Stil: `_sf-meldungen.scss`.
- **Studio, Seiten (`views/`):**
  - `ablauf-sprung.ts` (`?ablauf=` und `?modul=` als Signal);
  - `group-section.component.ts`;
  - `ui-module.component.{ts,html}`;
  - `core/ablauf-api.service.ts` (`liste()`).
- **Texte:** `i18n/catalogue/ablaeufe-seite.ts`, Schlüssel `weiter.*`, `ablaufBild.*` und
  `uiModule.ablaeufe*`, auf Deutsch und Englisch.
- **Tests:**
  - `weiter-regeln.spec.ts`, `weiter-editor.component.spec.ts`;
  - `ablauf-bild.spec.ts` (Geometrie und Komponente), `ablauf-schrittfolge.component.spec.ts`;
  - `ablauf-pruefen.component.spec.ts`: „Zum Schritt“ und der Klick ins Bild wählen und fokussieren
    den Schritt im echten Formular;
  - `ablauf-folge.spec.ts`;
  - `ablaeufe-seite.spec.ts` (`?ablauf=`);
  - `ui-module.component.spec.ts` (Liste, Fehler, `?modul=`).

## Nicht in diesem Paket

- Grafisches Bearbeiten per Ziehen (Plan D6: kommt nicht).
- Bedingungen `wenn_wert`, `wenn_seite`, `wenn_auftrag` (AS-3 bzw. AS-6). Der Editor zeigt sie,
  bis sie kommen, als JSON-Box.

## Review (2026-11-09)

Ein frischer Reviewer: 2 hoch, 7 klein, 4 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| Hoch: Der Editor bot an jedem Schritt alle drei Arten an. An einer Verzweigung gelten aber nur Regeln, an jedem anderen Schritt ist eine Liste ein Fehler (`pruefung._regeln`). Die Folge: zwei widersprüchliche Aussagen auf einer Seite oder ein 422 erst beim Speichern. | Die Arten richten sich jetzt nach dem Typ. Eine Verzweigung zeigt nur Regeln, ein anderer Schritt „nächster“ oder „bestimmter Schritt“. Eine dort vorhandene Liste bleibt sichtbar, ist markiert und lässt sich umstellen. Ein Schritt ohne Typ darf alles. |
| Hoch: Die Sperre bei halben Regeln hing an Ereignissen des Editors. Eine Instanz zeigt aber nacheinander verschiedene Schritte, und die Rücknahme traf über `jsonFehlerPfad` den falschen. Gesperrt blieb dann ein heiler Schritt, oder frei ein halber. | Das Formular rechnet die Sperre aus dem Dokument (`regelFehlerOrte`, je `schritte.<i>.weiter`) und meldet sie mit den übrigen Feldfehlern. Der Editor zeigt die Meldung nur noch am Feld. Ein Test im echten Formular deckt den Wechsel zwischen Schritten ab. |
| „`sonst` fehlt“ war unbekannt: Das Studio sagte „fertig“, das Speichern lieferte 422. | Neue Meldung `sonstFehlt`. Die erste Regel bringt ihr „sonst“ gleich mit, mit dem bisherigen Ziel. |
| Der eigene Schritt kam über die gefilterte Liste: Ein Schritt ohne Kennung davor verschob ihn. Ein Sprung auf sich selbst hieß „unbekannt“. | Der Schritt wird roh aus dem Dokument gelesen (`eigenerSchritt`, Ablauf aus dem Pfad). Der eigene Schritt steht als „x (dieser Schritt)“ in der Auswahl, die Vorgabe ist der folgende. |
| „Bestimmter Schritt“ ohne Ziel ließ die Auswahl falsch stehen. | Die Auswahl springt auf die gültige Art zurück. |
| Fokus nach Hinzufügen, Entfernen und Verschieben ging verloren. | Nach dem Hinzufügen steht der Fokus in der neuen Regel. Nach dem Verschieben bleibt er am selben Knopf der Regel; ist der gesperrt, am anderen. Nach dem Entfernen geht er an die Nachbarregel, sonst an „Regel hinzufügen“ bzw. die Art. |
| Die Meldung war mit keinem Feld verbunden, die Live-Region wurde erst mit der Meldung eingefügt. | Das betroffene Feld hat `aria-invalid` und `aria-describedby`. Die Region steht immer da. |
| Die Zeile „Ablaufbild“ ließ sich für Vorlesehilfen aufklappen, ohne Inhalt. Wuchs ein Ablauf über 12 Schritte, klappte das Bild von selbst zu. | Die Zeile hat einen verborgenen Hinweis: „Grafik, dieselbe Auskunft steht in der Liste darunter“. Die Zahl der Schritte legt nur den Anfangszustand fest. |
| Auf der Modulseite stand „Liste kam nicht“ nicht in einer Live-Region, und der Fokus fiel nach „Erneut versuchen“ ins Leere. | Ein Statusbereich, der immer da ist. Der Fokus geht an die Überschrift „In Abläufen“. |
| Kleinigkeiten | `?modul=` wirkt nur einmal. Das Bild führt die Art der Bedingung mit, statt am Zauberwert `sonst` zu hängen; ein Teil steht mit „+“ da, Beschriftungen werden gekürzt. Bei doppelten Kennungen gilt die letzte, wie im Treiber. Bei „sonst“ bleiben Ziel und Knöpfe in ihrer Spalte. |
| Vorbestehend: Die Liste der Abläufe zählte unter `module` nur `modul`-Schritte. Am Modul fehlten so die Abläufe, deren KI-Schritt das Modul zeigen darf oder die auf seine Antwort starten. | `api/config_ablauf._module` nimmt UI-Module aus `agent.werkzeuge` (laut Katalog) und Auslöser `art: modul` hinzu (Test `test_die_liste_nennt_module_aus_agent_schritt_und_ausloeser`). |

Prüfung nach den Behebungen:
- Studio: 169 von 169 Testdateien grün; eslint, Tokens, a11y und Kontrast sauber.
- Backend: volle Suite vor der letzten Ergänzung grün (9169 passed, 5 skipped); danach `test_ablauf_dokumente.py` und `test_openapi_contract.py` grün (26 passed).

## Querschnitts-Review AS-0…AS-2 (2026-11-09)

Nach der Paketgruppe ein zweiter, frischer Reviewer über alle drei Pakete hinweg: 3 hoch, 3 klein,
4 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| Hoch: Das Zeitbudget der Simulation griff innerhalb eines Testfalls nie, denn die Kette gibt die Ereignisschleife nicht frei. „Tests ausführen“ konnte so alle Chat-Züge der Replika anhalten. | Die Frist prüft jetzt jeder besuchte Schritt selbst (`protokoll`) und jede Eingabe. Dazu kommt ein Deckel von 500 Schritten je Testfall. Der Endpunkt rechnet in einem eigenen Thread mit eigener Schleife (`simulation.im_thread`). Tests decken die Frist mitten im Fall, den Deckel und den Thread ab. |
| Hoch: Ein Verzeichnisbaum von vor AS-0 (`export-config`) mit `06-ablaeufe/katalog.yaml` ging an der Aufteilung vorbei. Ohne Schalter entstand die gestrichene Zeile wieder, mit `--exact` wurden alle Ablauf-Dokumente gelöscht. | `seed_sync._lesen` (Werksabgleich, `exact`, Probelauf) und `import-config` teilen den Katalog wie eine ZIP-Sicherung. Gestrichene Bereiche legt `import-config` nicht mehr an. Zwei CLI-Tests gegen eine Wegwerf-Datenbank decken beide Wege ab. |
| Hoch: Die Simulation reichte Modul-Antworten ungeprüft an den Treiber. Eine Antwort, die der Betrieb verwirft (eine nicht angebotene Möglichkeit), führte trotzdem in den Zweig, und der Test war grün. | Die Simulation merkt sich die offene Frage wie der Zug (`merke_frage`) und prüft jede Antwort mit `antwort_pruefen`. Was der Betrieb verwürfe, ist die Abweichung „passt nicht zur Frage“, und der Lauf hält an. Ein bestehender Test hatte genau so eine Antwort benutzt; seine Erwartung ist angepasst. |
| Die Laufzeit las die Testfälle mit: Hash und Prüfung je Zug wuchsen mit den Testdaten. Ein Testteil, der nicht mehr zum Modell passt, nahm den echten Ablauf still aus der Laufzeit. | `ausloeser._roh_liste` lässt `tests` weg (Test). |
| Werte einer Bedingung wurden ungekürzt gespeichert: „neu “ griffe nie. | `weiterAus` speichert ohne Leerzeichen am Rand (Test). |
| Die Notiz versprach für Migration 0021 „ohne etwas zu verlieren“. | Notiz und Deploy-Hinweis nennen jetzt, was nicht übernommen wird. Die Migration gibt die betroffenen Kennungen aus. |
| Kleinigkeiten | Die Meldung „Kennung vergeben“ nennt bei Abläufen die andere Kennung. Ein zu großer Ablauf (413 beim Testen) bekommt eine verständliche Meldung. In der Doku sind die Vertragszusätze ergänzt (`nr`, `warnungen`, `x-widget: weiter`), ebenso der Verweis in `ui-module.md` und der Plan-Stand. |

Nicht übernommen: Der Vorschlag, die Warnung zu einem kaputten Ablauf-Dokument solle seine Kennung nennen. Die Kennung schreibt die Redaktion, sie ist also Inhalt, und Logs tragen keine Inhalte (`tests/test_log_ohne_inhalt`). Es bleibt bei der Stelle in der nach Schlüssel sortierten Liste.

Prüfung: Die volle Backend-Suite ergab 9176 passed und 1 failed. Der Fehler war genau diese Log-Zeile; nach der Rücknahme sind `test_log_ohne_inhalt.py` und die Ablauf-Tests grün.
