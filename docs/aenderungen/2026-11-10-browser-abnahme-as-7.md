# Browser-Abnahme AS-7 (Führungen) und Behebung (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5m. Die Abnahme folgt auf das Querschnitts-Review
(`2026-11-10-querschnitt-as-7.md`).

## Aufbau

- **Wegwerf-DB** `boerdi_fuehrung_browser`: migriert, Seeds importiert, danach gelöscht.
- **Backend** aus dem Staging auf `127.0.0.1:8100`; **Widget** aus dem frisch gebauten Bündel
  (`no-store`), Demoseiten `/widget/classic` und `/widget/inline`; ohne Anmeldung.
- **Probe-Ablauf** `fuehrung_probe`, angelegt über das Studio-API:
  - Auslöser `seite` auf `/widget/classic*` und Wendung „probe fuehrung“;
  - Schritt `hin`: Typ `seite` → `/widget/inline`, Ankunft `/widget/inline*`;
  - danach Ende „Angekommen - die Fuehrung ist zu Ende.“

## Fälle

| Fall | Ergebnis |
|---|---|
| A — Angebot unter der Begrüßung | Nach „Neuer Chat“ auf `/widget/classic` steht „Probe-Führung“ als erster Chip, die vier üblichen Chips bleiben. |
| B — Start | Der Text kündigt die Seite an, darunter der Führungs-Chip. Die Leiste zeigt „Schritt 1 von 1, wartet auf den Seitenwechsel“ mit dem Knopf „Zur eingebetteten Seite“ und „Ablauf abbrechen“. |
| C — Neuladen auf einer anderen Seite | Die Leiste steht wieder da, mit dem Weg-Knopf. **Befund L-3**, behoben (siehe unten). Nach der Behebung erscheint kein Kontext-Gruß mehr; der Server sah nur den Seiten-Ping mit leerer Antwort. |
| D — Ankunft | Der Weg-Knopf führt nach `/widget/inline`, die Sitzung wird fortgesetzt, der Seiten-Ping erkennt die Ankunft, und „Angekommen - die Fuehrung ist zu Ende.“ erscheint ohne KI-Etikett. Die Leiste ist weg. Seiten-Pings dauern 82–116 ms. |
| Logs | Keine Fehler auf dem Server. |

## Befund und Behebung

- **L-3 — Kontext-Gruß neben einer wartenden Führung.**
  - Nach dem Neuladen auf einer Seite, die nicht zur Ankunft passt, kam neben der wartenden Führung
    der Kontext-Gruß („Du bist auf localhost …“). Er führt die Person vom Weg weg; die Seite gehört
    der Führung, solange sie wartet.
  - **Ursache:** `_afterResume` ließ den Gruß nur aus, wenn der Seiten-Ping eine Antwort brachte.
    Passt die Seite nicht, ist die Antwort leer, und der Gruß kam.
  - **Behebung:** Kein Kontext-Gruß, solange `seitenPingWartet()` gilt
    (`frontend/projects/ui/src/shell/lifecycle.ts`). Spec zuerst (rot, dann grün):
    `lifecycle.spec.ts` „Browser-Abnahme AS-7, L-3“.
  - Dasselbe gilt schon für SPA-Seitenwechsel (`onSpaContextChange` pingt statt zu grüßen).

## Prüfung

- `ng test ui`: 113 Dateien, 1377 Tests grün.
- `npm run build:widget`: gebaut; Warnung zum Roh-Budget (651,57 von 650 kB) wie bisher.
- Browser: Fall C nach der Behebung erneut geprüft, bestanden.

**Offen:** E2E für den Führungs-Kernpfad (`offene-befunde-und-todo.md` §1).

**Deploy:** Widget-Bündel neu bauen. Keine Migration.
