# Paket AS-Dc: Sicht „Daten“ (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D8 und §5e.

## Was sich ändert

- **„Prüfen“ liefert die Sicht „Daten“ mit:** eine Zeile je Teil, die der Ablauf schreibt oder liest.
  Jede Zeile nennt:
  - die Typen der Schreiber (`?` heißt: Ausgabe einer KI; `…` heißt: Teil eines Moduls ohne
    bekannte Normalform);
  - die schreibenden Schritte, und ob der Teil vor dem Start da ist (Modul-Auslöser) oder aus dem
    Gespräch kommen kann (ein Modul hinterlässt ihn). Schreibt ihn beides nicht, steht dort rot und
    als Text „von keinem Schritt“ — meist ein Tippfehler;
  - die lesenden Schritte: über `$teil` (auch Auswahlen), Platzhalter in `text` und `freigabe`,
    `wenn_teil` und die Quelle von `wenn_wert`;
  - ein Beispielwert aus den Testfällen, gekürzt.
- **Studio:**
  - Unter der Schrittfolge steht eine aufklappbare Tabelle „Daten: n Teile“ mit Spaltenköpfen und
    verborgener Beschriftung. Sie rollt seitlich, wenn der Platz fehlt.
  - Ein Schritt in der Tabelle ist ein Knopf und führt wie „Zum Schritt“ in die Liste der Schritte.
  - Die Tabelle gilt, solange sie zum geprüften Entwurf passt, wie die Befunde.
- **Abweichung vom Plan:** Der Plan sah vor, die Sicht im Studio aus dem Entwurf zu rechnen. Das
  Backend rechnet sie stattdessen, aus derselben Quelle wie die Prüfung (`services/ablauf/typen`).
  Eine zweite Typtabelle im Studio liefe auseinander; das hat das Review von AS-Db gerade an zwei
  Stellen im Backend gezeigt. Der Preis: Die Sicht erscheint nach „Prüfen“, nicht live wie die
  Schrittfolge.

## Wo

- **Backend:**
  - `services/ablauf/datensicht.py` (neu): `tabelle`;
  - `services/ablauf/typen.py`: `verweis_namen`, `gelesene_teile` — die Leser kommen aus derselben
    Quelle wie die Prüfung;
  - `api/config_ablauf.py`: Schema `AblaufTeil`, Feld `teile` der Antwort von
    `POST /api/config/ablauf-pruefen`.
- **Studio:**
  - `schema-form/ablauf-daten.component.ts` (neu), `ablauf-pruefen.component.ts`;
  - `core/ablauf-api.service.ts` (`AblaufTeil`);
  - Stil in `_sf-meldungen.scss`;
  - Texte in `i18n/catalogue/ablaeufe-seite.ts`.
- **Verträge:** `docs/api/openapi-v1.json`, `bewusste-vertragszusaetze.md`.

## Tests

- Backend `tests/test_ablauf_datensicht.py`: Typ, Schreiber und Leser (Verweis, Platzhalter, `wenn_teil`, `wenn_wert`, Freitext, Modul-Auslöser), Beispiel, Endpunkt; nach dem Review dazu Tippfehler gegen Teil aus dem Gespräch, Auswahl als Leser, Tiefe wie der Treiber, `?` nur für die KI, Beispiel aus Eingaben und gekürzt, zu viele Schritte.
- Studio `ablauf-daten.component.spec.ts`: Tabelle, vor dem Start / aus dem Gespräch / von keinem Schritt, Klick auf einen Schritt, Schritte ohne Liste als Text, nicht geprüft gegen geprüft ohne Teile. `ablauf-pruefen.component.spec.ts`: die Tabelle verschwindet bei einer Änderung und beim Verwerfen.
- Ergebnis: Backend 88 Ablauf-Tests grün, ruff sauber. Studio 171 Dateien / 2113 Tests grün; eslint, a11y, Tokens, Kontrast und Doku-Prüfung sauber.

## Betrieb

Keine Migration, keine neue Variable. Das Image neu bauen (Studio, Backend).

## Review (Befundhebung)

Review gegen Plan §5e und D8, dazu Barrierefreiheit im Audit-Modus. Ergebnis: 0 kritisch, 0 schwer,
5 kleiner, 8 Kleinigkeiten. Alle behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Ein Teil ohne Schreiber stand immer als „aus dem Gespräch“ da, auch ein Tippfehler wie `entwrf` — die Tabelle widersprach dem Befund `verweis_teil`. | kleiner | Neues Feld `aus_gespraech`. Sonst steht „von keinem Schritt“, als Fehler markiert und als Text. |
| 2 | Die Leser waren eine zweite Kopie neben der Prüfung, mit anderer Tiefe als der Treiber; `wenn_wert` zählte an jedem Schritt. | kleiner | `typen.verweis_namen` und `typen.gelesene_teile` sind die eine Quelle für Prüfung und Sicht. Sie gehen bis zur Tiefe `TIEFE` des Treibers und lesen `wenn_*` nur an einer Verzweigung. |
| 3 | Beispiele kamen nur aus `teile` und `werkzeuge` des Testfalls; ein schreibendes Werkzeug mit Freigabe nimmt `werkzeuge` in der Simulation gar nicht. | kleiner | `_werte` liest dazu die Eingaben (`teile`, `text`, `ergebnis`) und lässt `werkzeuge` an einem Werkzeug mit Freigabe aus. |
| 4 | Schritt-Knopf mit kurzer Kennung schmaler als 24 px (SC 2.5.8). | kleiner | `min-inline-size: 1.5rem`, Text mittig. |
| 5 | Testlücken: Auswahl, `?`, Gesprächstyp, Kürzung, Tiefe, Klick, „vor dem Start“, Verschwinden der Tabelle. | kleiner | Tests ergänzt (siehe Tests). |
| 6 | Beispiel hing an der Reihenfolge einer Menge und übersprang falsy Werte. | Kleinigkeit | Reihenfolge der Schritte, Prüfung gegen `None`. |
| 7 | Ein Modul-Teil ohne Normalform hieß „unbekannt (KI)“. | Kleinigkeit | Zwei Marken: `?` (KI) und `…` (unbekannt). |
| 8 | Kein Wächter `MAX_SCHRITTE`. | Kleinigkeit | Leer jenseits davon, wie die Prüfung. |
| 9 | „vor dem Start“ klebte am ersten Knopf. | Kleinigkeit | Hülle `.ad-zelle` mit `inline-flex` und `gap`. |
| 10 | Ein Schritt ohne Liste sah wie ein Knopf aus. | Kleinigkeit | Ohne Rahmen. |
| 11 | Ohne Kennung zeigte die Tabelle `#n`, die Schrittfolge einen Text. | Kleinigkeit | Derselbe Text `ablaufPruefen.ohneKennung`. |
| 12 | Geprüft ohne Teile zeigte nichts. | Kleinigkeit | „Daten: keine Teile.“ |
| 13 | Plan und Kopfkommentar des Dienstes nannten die Abweichung nicht; TS-Typ strenger als das Schema. | Kleinigkeit | Plan §5e und Kopfkommentar ergänzt; optionale Felder im TS-Typ. |

Beim Beheben fiel dazu auf: Die Überschrift las `teile().length` statt der eingeengten Liste — ein
Typfehler, den erst der Studio-Build zeigte. Behoben.
