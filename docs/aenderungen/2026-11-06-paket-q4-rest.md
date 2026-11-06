# Paket Q4: Rest — Befunde des Querschnitts-Reviews (2026-11-06)

Grundlage: [`../audits/2026-11-06-querschnitts-review.md`](../audits/2026-11-06-querschnitts-review.md),
Plan [`../plans/2026-11-06-querschnitts-befunde.md`](../plans/2026-11-06-querschnitts-befunde.md) (Q4).

## Was sich ändert

- **Moderation vor Ebene 2 des Strukturentwurfs.** Die Moderation beim Hochladen sieht nur Übersicht und
  Anfang eines Dokuments; Ebene 2 schickt aber Abschnitte von beliebiger Stelle ans Modell. Jeder Auszug
  geht jetzt einmal durch die Moderation (`services/strukturentwurf_auszug.py`): je Text einmal, auch
  wenn zwei Punkte ihn zugleich brauchen; nacheinander (ein Moderationsplatz je Entwurf — die Plätze
  teilt er mit den Chat-Zügen aller Personen); gezählt unter eigener Stufe `strukturentwurf_auszug`; die
  Zeit der Moderation zählt vor der Frist-Prüfung des Modellaufrufs. Beanstandet → kein Auszug (der
  Punkt entsteht aus Titel und Gliederung); ohne Urteil entscheidet `MODERATION_FAILURE_MODE` wie bei
  Nachrichten (`closed` schickt nichts, `open` schickt ihn ungeprüft — eine Warnung je Entwurf). Ins
  Log gehen nur Fehlerarten, kein Text; ebenso jetzt in `safety/moderation` und im Preflight (älter).
- **Die Ordner-Brücke merkt ihren Entwurf.** „Ordnerstruktur als Entwurf“ ersetzt den gemerkten Entwurf
  durch den aus den Ordnern — ein Folgezug mit `vorlage` griff sonst auf einen älteren KI-Entwurf oder
  einen alten `draft` im Vorgang zurück. Die Ordnernamen gingen durch die Sicherheitsprüfung des Zugs.
- **Dateien geteilt** (Code verschoben, nicht umgeschrieben; Aufrufer und Tests unverändert):
  `arbeitsstand` → `arbeitsstand_teile` (Normalform) und `arbeitsstand_verweis` (Verweis, Kennzeile);
  `ablauf/pruefung` → `pruefung_texte`; `ablauf/treiber` → `treiber_bloecke`; `strukturentwurf_dienst` →
  `strukturentwurf_dokument` (Aufforderung und Fundstelle aus dem Dokument); `graph/nodes/preflight` →
  `preflight_ablauf` (Auslöser bestimmen, Ablauf- und Vorgangs-Aktionen); im Widget-Modul
  `ui-upload.element.ts` → `upload-ansicht.ts` (Darstellung aus einem Abbild des Zustands).
- **Postgres-Integrationstests** für Ablauf, Auftrag und Ablage (`tests/test_ablauf_pg.py`).
- Schon zu Beginn von Q4: `/widget/boerdi-widget.<digest>.js` liefert das Bündel nur zum passenden
  Streuwert (sonst 404); `rag/umwandeln.py` protokolliert keinen Ausnahmetext.

## Beim Deploy

- Widget-Bündel neu bauen (`npm run build:widget`), das Upload-Modul hat einen neuen Streuwert.
- Mehr Moderationsaufrufe: je Strukturentwurf aus einem Dokument höchstens einer je Punkt der Ebene 1
  mit Abschnitten (bis `anzahl_oben`, höchstens 20), je Text einmal, nacheinander (ein Platz je Entwurf).
  Gezählt unter der Stufe `strukturentwurf_auszug` in `boerdi_safety_stage_total` — ein Alarm auf
  `openai_moderation` sieht sie nicht.

## Bewusst anders als geplant

- Die Brücke aus dem Bestand („Als Entwurf bearbeiten“ im Themenbaum) merkt weiter nichts: Titel aus WLO
  erreichen das Modell erst, wenn die Person den Entwurf zurückschickt. Der Rückgriff auf einen alten
  `draft` des Vorgangs bleibt damit in einem schmalen Fenster möglich (Review Q4, Befund 5): nur wenn
  die Person den offenen Bestands-Entwurf weder übernimmt noch dazu tippt (eine getippte Nachricht
  schickt ihn mit) und das Modell trotzdem `vorlage` ruft. Bewusst nicht gebaut — die Abhilfe (eine
  Marke durch drei Schichten) wöge mehr als der seltene Fall; die Kennzeile nennt den alten Entwurf.
- `treiber.py` (314) und `strukturentwurf_dienst.py` (318) liegen knapp über 300 Zeilen; der Rest ist je
  eine Aufgabe (Schritte rechnen bzw. Ebenen erzeugen) — weiter teilen hieße zerreißen.

## Review

Unabhängiges Review nach dem Bau: 0 kritisch, 0 hoch, 8 MINOR, 5 NIT; die Teilungen ohne
Verhaltensänderung bestätigt. Behoben: Kosten und geteilte Plätze der Moderation (ein Platz je
Entwurf, eigene Stufe, Zeit vor der Frist-Prüfung), laufende Prüfung je Text geteilt, eine Warnung je
Entwurf, falsche Zahl in dieser Notiz, Postgres-Tests um Kaskade und zwei gleichzeitige Schreiber
ergänzt (Docstring ehrlich), `offene-befunde` und `ui-module.md`/README nachgezogen, tote
Wiederausgaben, Leerzeilen, Docstring des Preflights, `sicht()` einmal je Zeichnen. Älter, mit
behoben: Ausnahmetext im Log von `moderate` und des Preflights. Begründet nicht gebaut: Befund 5
(siehe oben). Offen (älter): `Teil` ist in `treiber` und `arbeitsstand_teile` je einmal definiert.

**Nachprüfung** (1 MAJOR, 3 MINOR, 3 NIT): das Warten auf die Moderation war nicht durch die Frist des
Entwurfs begrenzt — mit einem Platz je Entwurf konnten sich unter Last bis zu fünf Prüfungen zu je 8 s
stauen, der Entwurf überzog die Frist, und der Lauf brach ihn samt Ebene 1 ab (MAJOR, nachgestellt;
jetzt endet das Warten vor der Frist, der Punkt bleibt `ausstehend`). Dazu: der Test „Moderation nur
mit Dokument“ prüfte das nicht (neu geschrieben), Test für die Restzeit nach der Moderation, die
geteilte Prüfung fängt alles ab, Docstring zu `erzeugen(moderieren=…)`, Stufen-Tabelle in
`uebergabe-betrieb.md`, Docstring des Zwei-Schreiber-Tests (die Sperre sichert ihn — ohne sie 8 von 8
Läufen falsch). Mit behoben (älter): die Moderation beim Hochladen zählt unter eigener Stufe
`dokument_aufnahme`. Bewusst gelassen: eine Warnung je Entwurf ohne Moderationszugang (AcademicCloud)
bleibt WARNING.

## Tests

- `tests/test_strukturentwurf_dokument.py` (+7), `tests/test_ui_strukturentwurf_aufruf.py` (+1),
  `tests/test_safety_ausfall.py` (+1): beanstandeter Auszug fehlt, `closed` ohne Urteil fehlt, derselbe
  Auszug zugleich einmal geprüft, höchstens ein Platz, eine Warnung je Entwurf, eigene Stufe; die
  Moderation geht nur mit einem Dokument mit. Die drei Review-Tests liefen vor dem Code rot.
- `tests/test_ordner_aktion.py`: der Entwurf aus den Ordnern ist gemerkt (lief vor der Änderung rot).
- `tests/test_ablauf_pg.py` (neu, 8, Postgres).
- `tests/test_widget_router.py` (+1).
- Teilungen: die bestehenden Suiten unverändert grün (Backend voll, ui-module 300, E2E Upload/Fortschritt
  16, Budget, Lint, Wächter).
