# Paket AS-4c: Wiederkehr mit Vorgang- oder Auftragskennung (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), R3 und §5f.

## Was sich ändert

- **Endpunkt `POST /api/ui/vorgaenge/wiederkehr`:** mit `{session_id, vorgang}` oder
  `{session_id, auftrag}`, genau eine Kennung, sonst 422.
  - Nur mit bestätigter Anmeldung (403 `nur_angemeldet`). Die Besitzerin ist die Kennung der
    Anmeldung.
  - Für den Auftrag sucht `auftraege/ablage.vorgang_zum_job` den jüngsten eigenen, nicht
    abgelaufenen Vorgang zur Job-ID, auch wenn der Auftrag schon zu Ende ist.
  - **Kein Orakel:** fremd, unbekannt, abgeschlossen, abgelaufen oder ohne Gespräch geben
    dieselbe Antwort, 404 `unbekannt`.
  - Antwort: ein Vorgang wie bei `/offen`, `Cache-Control: private, no-store`, kein Log mit
    Kennung.
- **Widget:**
  - JS-API `vorgangFortsetzen({vorgang} | {auftrag})` und die Attribute `fortsetzen-vorgang` und
    `fortsetzen-auftrag`. Sie öffnen den Chat und warten auf die Shell (wie `startTask`).
  - Gefunden: Der Chat wechselt wie „Gespräch fortsetzen“ (K2a) in das Gespräch des Vorgangs.
    Wartet dort ein Auftrag, fragt er gleich „Stand prüfen“.
  - Nicht gefunden: eine Zeile im Chat (siehe Review, Befund 5); eine Warnung in der Konsole
    ohne die Kennung.
  - „Fortsetzen“ (K2a) und die Wiederkehr teilen `_zumVorgang`.
- **Doku:** `browser-plugin-einbindung.md` §5 „Zurück zur Arbeit“, die Attribute,
  `edu-sharing-einbindung.md`, die Kurzanleitung und die Studio-Referenz (37 Attribute).

## Wo

- **Backend:**
  - `api/ui_vorgaenge.py` (`WiederkehrAnfrage`, `wiederkehr`);
  - `services/auftraege/ablage.py` (`vorgang_zum_job`);
  - `tests/test_openapi_contract.py` (Inventar);
  - `tests/test_i18n_messages.py` (Code `unbekannt`).
- **Frontend:**
  - `ui/src/stream/offene-vorgaenge.ts` (`wiederkehrKennung`, `wiederkehrLesen`);
  - `ui/src/stream/chat-api.ts` (`wiederkehr`);
  - `ui/src/shell/chat-shell.component.ts` (`vorgangFortsetzen`, `_zumVorgang`);
  - `widget/src/element-api.ts`, `widget/src/app/widget/widget.component.ts`;
  - Studio-Referenz.
- **Verträge:** `docs/api/openapi-v1.json`, `bewusste-vertragszusaetze.md`.

## Tests

- Backend `tests/test_ui_vorgaenge_api.py`: eigener Vorgang, über den Auftrag, vier Fälle ohne
  Treffer mit gleicher Antwort, ohne Anmeldung, falsche oder doppelte Kennungen. Ergebnis: 20
  grün, dazu Vertrag, Log-Wache und i18n.
- Frontend:
  - `ui/src/shell/chat-shell-wiederkehr.spec.ts` (neu): Kennung, Antwort, Wechsel mit „Stand
    prüfen“, Wechsel ohne, nichts gefunden, kaputte Kennung;
  - Widget: Attribut und Methode; Element-API.
  - Ergebnis: ui 100 / 1232, Widget 4 / 87, Studio 171 / 2113 grün; eslint sauber.

## Betrieb

Keine Migration (die Suche über `job_id` läuft ohne Index; die Tabelle ist klein), keine neue
Variable. Das Image neu bauen (Backend, Widget, Studio).

## Review (Befundhebung)

Unabhängiges Review. Ergebnis: 0 kritisch, 3 schwer, 6 kleiner, 3 Kleinigkeiten. Alle behoben.
Wegen der drei schweren Befunde prüft das Querschnitts-Review AS-4 die Behebung ausdrücklich nach.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Die 404 war eine Ausnahme-Instanz auf Modulebene. Jeder Wurf hängte die Frames samt Zugangsblock an sie an: ein Speicherleck mit Geheimnissen. | schwer | `_unbekannt()` baut je Wurf eine neue; Test. |
| 2 | Während der Abfrage galt kein Laden. Ein getippter Zug lief im alten Gespräch, und ohne Treffer blieb die Warteschlange liegen. | schwer | Die Abfrage hält das Laden; „Stand prüfen“ reiht sich vorn ein, wenn schon ein Zug läuft; Test mit folgendem `startTask`. |
| 3 | Das Attribut wirkte bei jedem Seitenaufruf: Es holte die Person zurück und fragte jedes Mal nach dem Stand. | schwer | Je Tab nur einmal (FNV-Hash der Kennung in `sessionStorage`, nicht die Kennung); Doku rät zu `history.replaceState`. |
| 4 | Eine kaputte Kennung öffnete den Chat. | kleiner | Prüfung vor dem Öffnen (`wiederkehrKennung`, exportiert). |
| 5 | Bei 403/404 passierte sichtbar nichts. | kleiner | Ohne Anmeldung: Zeile mit dem Knopf „Anmelden“ und ein neuer Versuch nach der Anmeldung; sonst eine neutrale Zeile, für alle Fälle gleich. |
| 6 | Jede Wiederkehr verwarf das Angebot „Fortsetzen“, auch für ein anderes Gespräch. | kleiner | Nur das Angebot zu genau diesem Gespräch. |
| 7 | Testlücken: `vorgang_zum_job` nur gemockt, Warteschlange, dasselbe Gespräch, Wechsel scheitert, 403. | kleiner | Postgres-Test (fremd, abgelaufen, beendet, jüngster) und Shell-Specs ergänzt. |
| 8 | Doku: „danach Stand prüfen“ stimmte nicht immer; Tabelle „Nur beim Start gelesen“ ohne die neuen Attribute. | kleiner | Berichtigt und ergänzt. |
| 9 | `/wiederkehr` liefert auch `aktiv`, das Schema sagte nur die zwei wartenden. | kleiner | Docstring und Vertragsdokument nennen es; bewusst. |
| 10 | Die 403 ohne `no-store`. | Kleinigkeit | Mit `no-store`. |
| 11 | Beide Attribute: still gewann `vorgang`. | Kleinigkeit | Warnung, nichts geschieht (wie API und Backend). |
| 12 | 403 und 404 fehlten in der OpenAPI. | Kleinigkeit | `responses` am Pfad. |

Nach den Behebungen: Backend 70 Tests (mit Postgres), ruff sauber; ui 100 / 1237, Widget 4 / 89,
Studio 171 / 2113 grün; eslint sauber.

## Querschnitts-Review AS-4 (4a, 4b, 4c)

Zusätzliche Review-Schleife über die drei Teilpakete, mit Nachprüfung der drei schweren Befunde aus
AS-4c (alle behoben, ohne neue Fehler). Ergebnis: **1 kritisch**, 1 schwer, 7 kleiner,
1 Sammelbefund. Alle behoben; die Vorarbeit für AS-5 steht im Plan §5f.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Ein Start der Gastseite (ohne Geste der Person) ersetzte einen wartenden Lauf eines **anderen** Ablaufs oder mit anderen Daten — samt Kestra-Auftrag. Nach einer Wiederkehr ist genau dieses Gespräch das aktive. | kritisch | Die Gastseite ersetzt nie still: Läuft ein anderer Lauf, fragt der Chat mit „Neu starten“ (ein Knopf ohne `quelle`) und, wenn ein Auftrag wartet, „Stand prüfen“. `ablauf-start` wirkt je Tab nur einmal. Tests im Backend und im Widget. |
| 2 | Einträge der Warteschlange kannten kein Gespräch: Ein Auftrag der Seite lief nach einem Wechsel im falschen Gespräch; mit beiden Attributen verschwand der Start hinter dem Wechsel. | schwer | Jeder Eintrag merkt sich sein Gespräch und verfällt nach einem Wechsel (Warnung ohne Werte); wirkt eine Wiederkehr, gilt `ablauf-start` in diesem Aufruf nicht. |
| 3 | Das Safety-Gate prüfte je Startfeld nur 500 von bis zu 2000 Zeichen und insgesamt 2000. | kleiner | `max_zeichen` höchstens 500; für `start` bis zu 5000 Zeichen zusätzlich im Gate — jedes Feld wird ganz geprüft. |
| 4 | `vorgangFortsetzen` ohne Abbruch und Sitzungswache: eine späte Antwort wechselte nach einem Neustart doch. | kleiner | `_mitAbbruch`, `sitzungsWache`, `_zerstoert`; das Laden gibt nur frei, wer es gesetzt hat. |
| 5 | Der Hinweis „gesperrt“ blieb im neuen Gespräch stehen. | kleiner | `_zumVorgang` setzt ihn zurück. |
| 6 | Merker je Tab vor dem Ergebnis; kein neuer Versuch nach dem Ticket-Tausch; Netzfehler hießen „nichts mehr“. | kleiner | Merker erst nach „gefunden“/„nichts“; neuer Versuch auch nach dem Ticket; 403 → „anmelden“, Netz/5xx → „gerade nicht prüfbar“ (`WiederkehrAusgang`). |
| 7 | Die Log-Wache kannte `job_id`, `auftrag`, `vorgang`, `startdaten` nicht. | kleiner | Ergänzt; eine Stelle (`zug_basis`, Flow-Name aus der Konfiguration) entsprechend umgestellt. |
| 8 | Doku: Kurzanleitung ohne die neuen Attribute und Methoden; Demo ohne Wiederkehr; Ersetzen und Reihenfolge nicht beschrieben. | kleiner | Nachgetragen. |
| 9 | Testlücken (Treffer mit eingereihtem Auftrag, `unshift`-Zweig, Gastseite gegen wartenden Auftrag). | kleiner | Ergänzt. |
| 10 | Sammel-Nit: Plan §5f veraltet, Notiz 4c widersprüchlich, Kommentar `start-ablauf`, Referenztext, Blasentext, Vertragsdokument ohne `ablauf_starten`, Vorgangskennung groß. | Kleinigkeit | Nachgezogen; Blase „Start des Ablaufs „…“ angefragt“; Kennung klein gewandelt. |

Nach den Behebungen: Backend Startdaten-, Zug-, Wiederkehr-, Log-, Safety- und i18n-Tests grün;
ui 100 / 1242, Widget 4 / 92, Studio 171 / 2113; ruff und eslint sauber.

### Nachprüfung des Querschnitts-Reviews

Wegen des kritischen Befunds eine gezielte Nachprüfung. Ergebnis: **Der kritische Befund ist
behoben** — in keinem Zustand ersetzt ein Start der Gastseite einen nicht beendeten Lauf. Neu:
0 kritisch, 2 schwer, 5 kleiner, 4 Kleinigkeiten. Alle behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Das Gate prüfte nur den Rohanfang eines Felds (führender Leerraum schob die Nutzlast hinaus) und brach vor `start` ab, wenn andere Parameter es füllten. | schwer | Startdaten zuerst, ohne Abbruch, bereinigt wie in `startdaten` (`text_bereinigt`) und dann gekürzt; Tests mit Leerraum und Füll-Parametern. Die Rechtsstufe sah nur `message[:2000]`; seit RB-1 8000 Zeichen. |
| 2 | Der Merker für `ablauf-start` stand schon in `ngOnInit` — ein Neuladen vor dem ersten Öffnen verlor den Start. | schwer | Gemerkt erst, wenn der Start an die Shell geht; Spec „ohne Öffnen neu laden“. |
| 3 | „Neu starten“ und „Stand prüfen“ konnten Deckel der Schnellantworten verlieren; über 2000 Zeichen gab es gar keinen Knopf. | kleiner | Beide tragen die Marke `ersetzt` und gelten in `domain/wahl_knopf` als geschützt; Grenze 8000; ohne Knopf ein eigener Satz. |
| 4 | Der Knopf war an keinen Lauf gebunden — ein zweiter Klick ersetzte den eben gestarteten. | kleiner | Marke aus Vorgang, Ablauf, Schritt, Status und Fassung; passt sie nicht mehr, fragt der Chat neu. |
| 5 | Der Stamm `job_id` griff in der Log-Wache nie. | kleiner | In `FOLGEN`; Test. |
| 6 | Der neue Versuch nach der Anmeldung meldete sein Ergebnis nicht an den Merker des Widgets. | kleiner | `vorgangFortsetzen(kennung, beimErgebnis)`; „anmeldung“ meldet erst der neue Versuch. |
| 7 | Der eigentliche kritische Fall (Gastseite gegen wartenden Auftrag) und der Rundlauf über den Knopf waren nicht getestet. | kleiner | Beide Tests ergänzt. |
| 8–11 | Gescheiterter Wechsel galt als „gefunden“; Alias statt `# log-ok`; Blasentext und „gesperrt“ in der Doku; `|` im Label. | Kleinigkeit | Behoben. |

Nach den Behebungen: Backend 610 betroffene Tests grün, ruff sauber; ui 100 / 1242, Widget 4 / 93,
eslint sauber.
