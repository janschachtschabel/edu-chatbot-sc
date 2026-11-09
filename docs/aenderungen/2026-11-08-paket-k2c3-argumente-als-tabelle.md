# Paket K2c-3 — Studio: Argumente eines Ablaufschritts als Tabelle (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2c,
Teil K2c-3.

## Was die Redaktion sieht

- `argumente` (Werkzeug- und Auftragsschritt) und `daten` (Modulschritt) stehen nicht mehr als rohes JSON da,
  sondern als Tabelle: je Zeile **Name**, **Art** (Text | Teil | JSON) und **Wert**.
  - **Text:** ein fester Wert, gespeichert als Zeichenkette.
  - **Teil:** ein Teil des Vorgangs, gespeichert als `{"$teil": "<name>"}`; die Auswahl schlägt die Teile der
    Schritte **davor** vor (`schreibt`, `agent.ausgabe`) und die Teile der Module (`structure`, `document`,
    `draft`, `ablage`). Freitext bleibt möglich.
  - **JSON:** alles andere (Zahl, Liste, Objekt) — nichts geht beim Öffnen verloren.
- „Eintrag hinzufügen“, „Entfernen“ je Zeile, „Als JSON bearbeiten“ (die gewohnte JSON-Box, zurück mit „Als
  Tabelle bearbeiten“). Ein Wert, der kein Objekt ist, und ein Verweis auf einen ganzen Teil
  (`daten: {$teil: draft}`) stehen nur in der JSON-Box. Gewechselt wird nur ohne offene Meldung.
- Eine JSON-Zeile wird beim Verlassen gelesen, nicht bei jedem Tastendruck. Namen und Teile bleiben, wie sie
  getippt sind; ohne Zeilen wird `null` gespeichert, nicht `{}`.
- **Ein halber Stand schreibt nichts:** leerer oder doppelter Name, Teil ohne Namen, kaputtes JSON in einer Zeile.
  Die Tabelle meldet es („Zeile 2: „titel“ gibt es schon — noch nicht übernommen.“), und das Formular sperrt das
  Speichern wie bei einer JSON-Box.

## Geändert

- **Backend**
  - `domain/config_models/_shared.py`: Auszeichnung `TeilWerte()` (`x-widget: teil-werte`).
  - `domain/config_models/ablauf.py`: `TeilWerte()` an `daten` und `argumente` (am Objekt, innen in `… | None`).
  - `api/config_choices.py`: Katalog `vorgang_teile` — `vorgang.schreibt` aus den Manifesten der Module, dazu
    `ablage`; ohne Sprungziel.
  - Schema-Fixture und Vertrag neu erzeugt (nur das Schema von `Schritt` ändert sich, keine neue Operation).
- **Studio** (`schema-form/`)
  - neu `teil-werte.ts` (Regeln ohne DOM: `zeilenAus`, `wertAus`, `alsTabelleLesbar`, `vorigeTeile`);
  - neu `teil-werte.component.ts` (die Tabelle);
  - neu `form-dokument.ts` (`FORM_DOKUMENT`: das ganze Dokument für Felder, die über ihren Teilbaum hinaus lesen;
    das Formular stellt es bereit);
  - `schema-to-fields.ts`: `widget: 'teil-werte'` samt Katalog `vorgang_teile` (einmal je Formular geholt);
  - `field-control.component.{ts,html}`: die Tabelle statt der JSON-Box, Eingabe `pfad`;
    `schema-field.component.html` reicht den Pfad durch;
  - `_sf-meldungen.scss`: Raster der Zeilen, auf schmalen Flächen umbrechend;
  - `i18n/catalogue/area-editor.ts`: `teilWerte.*` (de/en); `i18n/en.spec.ts`: „Name“, „Text“, „JSON“ sind in
    beiden Sprachen dasselbe Wort.

## Bewusst so

- **Pfad in `$teil`** (`{"$teil": "volltext", "pfad": "outputs.markdown"}`) kommt mit K2d; eine solche Zeile steht
  bis dahin als JSON da und bleibt erhalten.
- Ob ein Teil vor dem Schritt wirklich entsteht, prüft weder die Tabelle noch die Prüfung (sie prüft nur die Form
  des Namens). Die Auswahl ist ein Vorschlag — ein Modul kann Teile schreiben, die kein Manifest nennt.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 4 hoch, 5 mittel, 2 Kleinigkeiten. Die Erkennung eines Verweises entspricht
der des Treibers (`{"$teil": "x", "pfad": …}` bleibt JSON). Behoben:

| Befund | Behebung |
|---|---|
| **Hoch:** `daten: {$teil: draft}` (Seed, ein Verweis auf den ganzen Teil) öffnete als Zeile „$teil“; eine weitere Zeile oder die Art „Teil“ machte daraus still etwas anderes. | Ein ganzer Verweis steht nur in der JSON-Box. |
| **Hoch:** JSON-Zeilen wurden bei jedem Tastendruck gelesen — das Echo formatierte um, der Cursor sprang, `"abc"` wechselte mitten im Tippen zur Art Text. | Gelesen wird beim Verlassen; das eigene Echo des Formulars lässt den Entwurf stehen. |
| **Hoch:** Fehler in der JSON-Box, dann „Als Tabelle“ — die Meldung blieb registriert, das Speichern unsichtbar gesperrt. | „Als Tabelle“ erst ohne Meldung der Box; umgekehrt „Als JSON“ erst ohne Meldung der Tabelle. |
| **Hoch:** Eine Instanz zeigt nacheinander mehrere Schritte; bei gleichem Wert (beide leer) wanderten Entwurf, Meldung und Ansicht mit. | Eine andere Kennung (und „Verwerfen“) setzt alles zurück; die Rücknahme der Meldung gilt dem alten Pfad. |
| Namen und Teile wurden still gekürzt (Umbenennen beim Speichern). | Keine Kürzung mehr; nur ein Name aus Leerzeichen gilt als leer. |
| Die letzte Zeile entfernen speicherte `{}` — die Fassung lässt nur `None` weg, wartende Läufe brächen ab. | Ohne Zeilen `null`. |
| Bedienbarkeit: die Gruppe hatte keinen Namen, `aria-invalid` nur am Namen, Fokus nach „Entfernen“ auf `body`. | `aria-labelledby` auf die Beschriftung des Felds, Meldung (`aria-invalid`, `aria-describedby`) am gemeinten Feld, Fokus auf die nächste Zeile bzw. „Eintrag hinzufügen“. |
| Das Raster reagierte auf das Fenster, die Tabelle steht aber neben der Liste. | Container-Abfrage auf die Tabelle. |
| Kleinigkeiten | Beschriftungen der Teile in der Auswahl; Katalog-Test robust gegen neue Manifeste. |

Offen: Eine Meldung des Servers am ganzen Feld (`invalid`) färbt die Tabelle nicht ein — sie steht wie bisher unter
dem Feld. Ganzzahl-artige Namen („2“) sortiert JavaScript im Objekt nach vorn.

## Zweites Review (2026-11-08)

Ein zweiter frischer Reviewer: 0 kritisch, 1 hoch, 3 mittel, 3 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| **Hoch:** Ein Fehler in der JSON-Box („Als JSON bearbeiten“) blieb nach dem Wechsel zu einem anderen Schritt registriert — das Speichern war unsichtbar gesperrt, und „Als Tabelle“ blieb in jedem weiteren Schritt gesperrt (auch nach „Verwerfen“). | Ein anderer Schritt nimmt die Meldung der Box zurück (am alten Pfad) und gibt den Knopf frei. |
| Ein Text mit Zeilenumbruch verlor ihn im einzeiligen Feld (still, auch in der Anzeige). | Er steht als JSON-Zeile da — verlustfrei. |
| Fokus fiel nach „Als JSON“ / „Als Tabelle“ auf `body`. | Fokus auf die Box bzw. die erste Zeile („Eintrag hinzufügen“ ohne Zeilen). |
| Die Spalten hatten keine sichtbare Beschriftung. | Kopfzeile Name · Art · Wert (im selben Raster). |
| Kleinigkeiten | Der Name `__proto__` ging verloren (jetzt `Object.fromEntries`); die JSON-Meldungen (Tabelle und JSON-Box) ohne englischen Text der JS-Engine und in der Sprache des Studios; „Zeile 2 entfernen“ statt „Zeile 2 () entfernen“; Tests prüfen die Reihenfolge der Schlüssel, `null`, Verschachteltes, `{$teil, pfad}`, `""` und die Rücknahme am alten Pfad im echten Formular. |

## Tests

- neu `schema-form/teil-werte.spec.ts`:
  - lesen und zurückschreiben ohne Verlust;
  - halber Stand (vier Fälle);
  - nur ein Objekt ist als Tabelle lesbar;
  - die Teile der Schritte davor.
- neu `schema-form/teil-werte.component.spec.ts`:
  - Zeilen;
  - Text schreibt;
  - Teil schreibt einen Verweis;
  - Auswahl aus den Schritten davor und den Modulen;
  - doppelter Name sperrt und gibt frei;
  - kaputtes JSON;
  - Entfernen;
  - „Als JSON“;
  - kein Objekt nur als JSON;
  - im echten Ablaufschema.
- Backend: neu `tests/test_ablauf_studio_k2c3.py` (Auszeichnung, Katalog); die Goldfassung aus K2c-1 bleibt
  gleich.
- dazu (Review): ein ganzer Verweis nur als JSON; JSON-Zeile erst beim Verlassen, Art und Text bleiben nach dem
  Echo; Leerzeichen im Namen bleibt; Wechsel der Ansicht nur ohne Meldung; anderer Schritt nimmt nichts mit;
  letzte Zeile → `null`; Name der Gruppe und Meldung am gemeinten Feld.
- Studio-Suite 2012 grün, eslint sauber.
- dazu (zweites Review): Box-Meldung beim Schrittwechsel, Zeilenumbruch, `__proto__`, Fokus beim Wechsel der Ansicht, Spaltenköpfe, „Entfernen“ ohne Namen, Rücknahme am alten Pfad im Formular.

## Betrieb

Nichts außer dem gewohnten Bau des Studio-Bündels.
