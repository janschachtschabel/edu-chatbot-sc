# Paket K2c-2 — Studio: ein Ablaufschritt zeigt die Felder seines Typs (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2c,
Teil K2c-2. Grundlage ist die Auszeichnung `x-nur-bei` aus K2c-1.

## Was die Redaktion sieht

- Ein Schritt mit `typ: auftrag` zeigt `text`, `flow`, `argumente`, `schreibt`, `warten`, `weiter`, `bei_fehler`
  — nicht mehr `modul`, `daten`, `werkzeug` oder `agent`. Jeder Typ entsprechend (Tabelle in der Notiz zu K2c-1).
- Wechselt der Typ, erscheinen dessen Felder; leere Felder des alten Typs verschwinden.
- **Ein gesetzter Wert verschwindet nie still:** Ein Feld, das beim aktuellen Typ nicht wirkt, aber noch einen Wert
  oder eine Meldung trägt, bleibt sichtbar, mit dem Hinweis „„Flow“ wirkt beim gewählten Wert von „Art“ nicht –
  der Wert bleibt gespeichert.“ und dem Knopf **Wert entfernen** (nimmt den Schlüssel heraus, auch eine ganze
  Gruppe; der Fokus geht an „Art“). Der Hinweis hängt per `aria-describedby` am Feld.
- Wer einen Restwert von Hand leert, tippt gerade darin: das Feld bleibt stehen, bis der Typ wechselt.
- Ohne gewählten Typ (neuer Schritt) bleiben alle Felder sichtbar.

## Geändert

- `schema-form/field-hints.ts`: `nurBei(raw)` liest die Auszeichnung an der Eigenschaft; `gesetzt(wert)` (nicht
  leer, keine leere Liste, kein leeres Objekt).
- `schema-form/schema-to-fields.ts`: `SchemaField.nurBei`.
- `schema-form/schema-field.component.{ts,html}`:
  - `gilt(child)` mit `ja` | `rest` | `aus`;
  - die Gruppe rendert ein Kind nur, wenn es nicht `aus` ist, sonst mit Hinweis;
  - `nurBeiId(child)` aus dem Pfad, eindeutig je Schritt einer Liste;
  - `zusatzId` geht ins `aria-describedby`.
- `i18n/catalogue/area-editor.ts`: `schemaField.nurBei` (de/en).

## Bewusst so

- Nur Darstellung: Daten, Speichern und Prüfung bleiben unverändert. Ein ausgeblendetes leeres Feld wird nicht
  geschrieben, ein Restwert wird nicht still gelöscht.
- Die Regel gilt in Gruppen (ein Schritt ist eine). Die Abschnitte oberster Ebene (`form-sections.ts`) kennen sie
  nicht; dort gibt es heute keine Auszeichnung.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 2 hoch, 5 mittel, 1 Kleinigkeit. Geprüft und in Ordnung: die Schritte laufen
durch den filternden Zweig (`object-list` → Gruppe), `gilt` liest den angezeigten Wert, ausgeblendete Felder
schreiben nichts, die Kennungen sind je Eintrag eindeutig.

| Befund | Behebung |
|---|---|
| **Hoch:** Wer einen Restwert leerte, verlor das Feld mitten im Tippen (Fokus auf `body`). | Ein Feld, das `rest` war, bleibt sichtbar, bis das Nachbarfeld wechselt; dazu „Wert entfernen“ mit Fokus auf das Nachbarfeld. |
| **Hoch:** Eine Meldung an einem leeren, ausgeblendeten Feld (etwa `daten: ""` aus dem YAML-Reiter) stand nirgends. | Ein Feld mit Meldung gilt als `rest` und bleibt sichtbar. |
| Älter, jetzt leichter erreichbar: die Meldung einer JSON-Box blieb nach ihrem Verschwinden stehen und sperrte das Speichern. | (Erst `ngOnDestroy` — im zweiten Review ersetzt, siehe unten.) |
| Die Gruppe `agent` ließ sich im Formular nicht ganz leeren. | „Wert entfernen“ nimmt den ganzen Schlüssel. |
| Der Hinweis erreichte die JSON-Box bei falscher Form nicht. | `zusatzId` auch dort. |
| Der Hinweis nannte Rohschlüssel („typ“), Englisch mit deutschem Wort, „diesem {nachbar}“ nur für ein Geschlecht. | Katalogbeschriftungen, Wortlaut „beim gewählten Wert von „…““. |
| Tests nur am Beispielschema, kein Typwechsel im Formular. | Test am echten Schema `06-ablaeufe/katalog` mit Typwechsel im Formular, ohne geschriebene Änderung beim Öffnen; dazu Restwert leeren, „Wert entfernen“, Meldung, JSON-Box. |
| Kleinigkeiten | `gilt` einmal je Änderung für alle Kinder (`computed`); `leer()` nutzt `gesetzt()`. |

Offen und bewusst gelassen: An einer Gruppe, Map oder Liste (`agent`, `text`) hängt der Hinweis am `fieldset`,
nicht an jedem Eingabefeld darin — ihn in alle Steuerelemente durchzureichen wäre ein Umbau aller Feldarten.

## Zweites Review (2026-11-08)

Ein frischer Reviewer nach den Korrekturen: 0 kritisch, 2 hoch, 2 mittel, 3 Kleinigkeiten, dazu 1 älterer hoher
Befund. Alles behoben.

| Befund | Behebung |
|---|---|
| **Hoch:** Der klebende Zustand hing nur am Feldnamen; eine Instanz zeigt nacheinander mehrere Schritte (Liste mit Auswahl) — ein geleertes `modul` in Schritt 1 erschien leer mit Hinweis in Schritt 2, und „Wert entfernen“ tat dort nichts. | Je vollständigem Pfad, geleert beim Wechsel des Schritts; „Wert entfernen“ zeichnet immer neu. |
| **Hoch:** `ngOnDestroy` nahm die Meldung einer Box auch beim Reiterwechsel zurück — die gewollte Speichersperre (A7, `feld-reiter.ts`) fiel weg, Speichern behielt still den alten Wert. | Kein Zurücknehmen beim Abbau. Die Gruppe nimmt die Meldungen eines Felds (samt Unterpfaden, `mitUnterpfaden`) zurück, wenn der Typ es ausblendet oder „Wert entfernen“ es nimmt. |
| Älter (hoch): Zeigte eine Instanz danach einen anderen Eintrag, nahm die Box ihre Meldung für den NEUEN Pfad zurück; die alte sperrte unsichtbar. | Die Rücknahme gilt dem Pfad, an dem die Meldung entstand (`jsonFehlerPfad`). Test mit Gegenprobe (ohne Korrektur rot). |
| „der Wert bleibt gespeichert“ auch ohne Wert (klebend leer, nur Meldung). | Eigener Satz `schemaField.nurBeiLeer`. |
| Der Knopf stand im Text, auf den `aria-describedby` zeigt. | Die Kennung sitzt am Satz (`span`), der Knopf daneben. |
| Kleinigkeiten | Gruppen ohne Auszeichnung rechnen nichts; Englisch „with the selected value of …“. |

## Tests

- neu `schema-form/schema-form-nur-bei.spec.ts`:
  - die Auszeichnung wird gelesen;
  - nur die Felder des Typs erscheinen;
  - ein anderer Typ blendet seine Felder ein;
  - ein Restwert bleibt sichtbar, mit Hinweis im `aria-describedby`;
  - ohne Typ ist alles sichtbar;
  - ein geleerter Restwert bleibt bis zum Typwechsel;
  - „Wert entfernen“;
  - eine Meldung hält das Feld sichtbar;
  - das echte Ablaufschema mit Typwechsel;
  - das Ausblenden durch den Typ nimmt die Meldungen des Felds zurück, der Abbau einer Box nicht (A7);
  - der klebende Zustand geht nicht auf den nächsten Schritt über;
  - eine JSON-Meldung wird für ihren eigenen Pfad zurückgenommen.
- Studio-Suite 1990 grün, eslint sauber.
- Eine Browser-Abnahme steht aus: Sie braucht die Studio-Anmeldung und ein Backend gegen eine Wegwerf-DB.

## Betrieb

Nichts zu tun außer dem gewohnten Bau des Studio-Bündels.
