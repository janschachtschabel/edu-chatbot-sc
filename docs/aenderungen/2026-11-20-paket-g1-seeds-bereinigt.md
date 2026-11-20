# Paket G1: Werks-Seeds bereinigt — nur noch „Themenbaum erstellen“ (2026-11-20)

Plan: `docs/plans/2026-11-20-konto-vorgaenge-und-warten-auf-volltext.md`, §5 (G1).

## Warum

Nutzer-Auftrag: Im Werk bleibt nur der neue Themenbaum-Ablauf, der alle Fälle abdeckt. Die vier
alten Einzel-Abläufe waren seit TG-6 (Plan 2026-11-16) ab Werk aus und abgelöst, lagen aber weiter
als Werksfassung in jeder Anlage.

## Was

### Seeds

Entfernt aus `backend/seeds/06-ablaeufe/`: `sammlungsstruktur.yaml`, `themenbaum_aus_thema.yaml`,
`themenbaum_aus_dokument.yaml`, `themenbaum_aus_inhalten.yaml`. Es bleiben `themenbaum.yaml`,
`fuehrung.yaml`, `sammlung_pruefen.yaml`.

Kein anderer Seed, kein Master-Skill (`docs/skills/`), kein Studio- oder Widget-Code nennt die vier
Kennungen. Der Name `sammlungsstruktur` lebt weiter als Upload-Zweck (`ui_upload`, `zweck:
sammlungsstruktur`, auch in `sammlung_pruefen.yaml`) und als Datentyp `wlo.sammlungsstruktur@1` —
beides ist nicht der Ablauf und bleibt. Der Code bleibt unverändert: was die alten Abläufe nutzten
(`strukturentwurf_aus_ordnern`, `aus_dokument`, `aus_inhalten`, `bereitgestellt`, Auftrag
`node-metadata-write`), nutzt auch `themenbaum.yaml`. Kommentar in `01-base/kestra-flows.yaml`
nennt jetzt „Themenbaum erstellen“.

### Werksabgleich: Werksbereiche ohne Seed

Bisher sah der Abgleich nur Bereiche des Seeds an; ein Bereich, dessen Seed fehlt, blieb in der
Datenbank und erschien im Studio als „nur eigen“. Neu (`services/werkfassung.plane_werksabgleich`,
`seed_sync.werksabgleich`, `ConfigStore.werk_entfernen`):

- **Entfernt** wird ein Bereich ohne Seed nur, wenn er nachweislich unberührt ist (Inhalt gleicht
  der gemerkten Werksbasis `werk_hash`) und keine eigene Fassung stillliegt — bedingt auf die
  gelesene Version wie jedes Schreiben des Abgleichs (dazwischen Geändertes zählt als
  `uebersprungen`). Kein Löschvermerk: kehrt der Seed zurück, legt ihn der nächste Abgleich wieder an.
- **Angepasstes bleibt** (eigene Fassungen werden nie still gelöscht) und wird gezählt (`verwaist`)
  und im Log mit Bereichsnamen genannt. Studio-Anlagen ohne Werksbasis bleiben still stehen.
- **Schutz:** abgeräumt wird nur in Ordnern, die der Seed kennt — ein leerer oder falsch gesetzter
  Seed löscht nichts.
- Bericht und Ausgabe: neue Zahlen `entfernt` und `verwaist` (Kommandozeile, Studio-Knopf
  „Werksabgleich starten“ mit eigenem Satz, Hinweistext ergänzt).
- `--exact` war schon richtig: Er löscht alles, was nur in der Datenbank steht, außer Bereichen mit
  stillgelegter eigener Fassung — mit Schnappschuss. Unverändert.

### Tests

Neu (zuerst rot, dann grün):

- `test_werkfassung.py::test_g1_werksbereich_ohne_seed_entfaellt_nur_unberuehrt` — Plan: unberührt
  → entfernen; angepasst / stillgelegte eigene Fassung → `verwaist`; Studio-Anlage still; Ordner
  nicht im Seed und leerer Seed → nichts.
- `test_werksabgleich.py::test_g1_ablauf_entfernt_unberuehrtes_ohne_seed_bedingt_auf_die_version` —
  Versionen an den Rückruf, Zählung, Übersprungenes.
- `test_cli_werksabgleich.py::test_g1_werksbereich_ohne_seed_entfaellt_angepasstes_bleibt` — echte
  Wegwerf-Datenbank: unberührter Ablauf entfällt, angepasster und Studio-Anlage bleiben, fremder
  Ordner bleibt, zweiter Lauf stabil.
- `test_ablauf_beispiele.py::test_g1_die_abgeloesten_themenbaum_ablaeufe_sind_nicht_mehr_im_werk`.
- Studio `fassungen-panel.component.spec.ts`: „meldet entfernte und angepasst behaltene Bereiche“.

**Eingefrorene Testbeispiele** `backend/tests/ablauf_beispiele/` (die vier alten YAMLs, mit Kopfzeile
„kein Werks-Seed“): Die Tests der Ablauf-Maschine (Zug, Vorgang, Wahl, Leiste, KI-Zeile,
Umlenkung) brauchen einen kleinen festen Ablauf als Beispiel; sie prüfen Verhalten, das weiter gilt
(auch für Anlagen, die eine angepasste Fassung behalten). Auf `themenbaum.yaml` umgeschrieben
hätten sich rund 60 Tests in Schrittnamen und Wegen geändert, ohne mehr zu prüfen.

Je Datei:

| Datei | Entscheidung | Grund |
|---|---|---|
| `test_ablauf_zug.py` | Beispiel | Maschine (Start, Fortsetzen, Tabs, Wahl); andere Dateien importieren `_katalog`/`_start`/`umgebung` von hier. Test umbenannt in `test_der_beispiel_ablauf_besteht_die_pruefung`. |
| `test_ablauf_leiste.py`, `test_ablauf_pg.py`, `test_querschnitt_vorgang.py`, `test_r2b_voraussetzung_dokument.py`, `test_tg7_durchtest.py` | über `test_ablauf_zug` | folgen dem Beispiel ohne eigene Änderung |
| `test_ablauf_leiste.py::test_wf1_…` | generisch | derselbe Schritt `ohne_metadaten` in `themenbaum.yaml` |
| `test_ablauf_ki_daten.py` | Beispiel + generisch | KI-Zeile/Antwort-Teile = Maschine (`_beispiel`); „jeder KI-Schritt hat Antworten“ am Werk-Seed `themenbaum` |
| `test_ablauf_frageschritte_freitext.py` | generisch | `themenbaum` hat dieselbe Frage `wofuer` |
| `test_ablauf_feste_argumente.py` | Fall gelöscht | Zeile `themenbaum_aus_inhalten`; die zwei `themenbaum`-Fälle prüfen dasselbe |
| `test_ablauf_datenfluss.py` | generisch, erweitert | jetzt jeder ausgelieferte Ablauf statt nur „aus Ordnern“ |
| `test_ablauf_dokumente_laufzeit.py` | Zeile gelöscht | Vergleich mit dem heutigen Seed „aus Ordnern“ (TW-6-Fassung) — Seed weg; Umstellung AS-0 bleibt geprüft |
| `test_ablauf_beispiele.py` | generisch + neu | Handbuch-Beispiele `themenbaum`/`sammlung_pruefen`/`fuehrung`; G1-Test |
| `test_r1_auftrag_teile.py` | generisch | Schritt `metadaten` von `themenbaum` (Sprache, Aufteilen) |
| `test_r2b_voraussetzung_dokument.py::test_der_dokument_ablauf_braucht_das_lesen` | gelöscht | Werks-Aussage über `themenbaum_aus_dokument`; `themenbaum` hat bewusst keine Voraussetzung. Die Regel `dokument_lesen` prüfen die übrigen Tests der Datei an einem eigenen Ablauf. |
| `test_tg2_bereit_und_verwirft.py` | generisch | `bereit`/`vorhanden` zuerst, Leiste ohne Sprung, `einstieg_mit` an Stelle 1 — an vier Fällen von `themenbaum` |
| `test_tg6_review2.py` | Fall gelöscht | `themenbaum_aus_dokument` aus der Liste; `themenbaum`, `fuehrung` bleiben |
| `test_tg6_themenbaum.py` | gelöscht + Beispiel | `test_die_alten_vier_sind_aus_und_abgeloest` gelöscht (ersetzt durch G1-Test); Wendungen der alten weiter in `themenbaum` (aus den Beispielen); Vorrang eines Ablaufs ohne Upload (Beispiel) |
| `test_tw4_seeds.py` | generisch + Beispiel | Werk-Aussagen an `themenbaum`/`sammlung_pruefen`; „Ausgestiegenen auslassen“ braucht einen zweiten vorschlagbaren Ablauf → Beispiel |
| `test_ui_upload.py` | Beispiel | Rückwärts-Regeln (alte Ordner-Antwort setzt wartenden Lauf fort; Rahmentext je Art) |
| `test_cli_werksabgleich.py` | umgestellt | alter Katalog-Baum mit `sammlung_pruefen` statt `sammlungsstruktur` |
| `test_ablauf_upload_schalter.py` | Kommentar | Herkunft der Daten |
| `test_arbeitsstand.py`, `test_migration_ablauf_dokumente.py`, `test_ablauf_pruefung.py`, `test_preflight_node.py`, `test_ablauf_ausloeser.py`, `test_dokument_ablage.py`, `test_vorgaenge.py`, `test_ui_vorgaenge_liste.py`, `test_tb_f1_*`, `test_tb_f2_*`, `test_tw6_umlenkung.py`, `test_sammlungen_sw5.py`, `test_ui_strukturentwurf_daten.py`, `test_ablauf_struktur_mit_nodeids.py` | belassen | nur Kennung als erfundene Testdaten, Upload-Zweck, Datentyp oder Migrationsdaten — kein Seed |

### Doku

`docs/ablaeufe.md` (Grundmuster statt „Beispiel: Sammlung aus Ordnern“, Hinweise zu G1, Kestra-Satz),
`docs/architektur.md` (migrate-Absatz), `docs/offene-befunde-und-todo.md` §4 (Deploy). Ältere
Änderungsnotizen und Pläne bleiben als Geschichte unverändert.

## Deploy

Keine Migration, keine neue Variable. Image neu bauen (Seed, Studio-Text). Der `migrate`-Dienst
(`import-config --werksabgleich`) entfernt die vier Abläufe aus Staging/Prod, wo sie unberührt
sind; ein Lauf, der noch in einem davon wartet, wird beim nächsten Zug abgebrochen (wie bei einem
gelöschten Ablauf; sie sind seit TG-6 ab Werk aus). Hat die Redaktion einen angepasst (etwa
eingeschaltet), bleibt er; die Ausgabe nennt ihn als „angepasst ohne Werk behalten“, das Log mit
Namen — im Studio prüfen und bei Bedarf selbst löschen. `--exact` entfernt sie ohnehin (mit
Schnappschuss), außer bei stillgelegter eigener Fassung.

## Review behoben (2026-11-20)

Review G1: 0 MAJOR, 3 MINOR, 2 NIT. Tests zuerst (rot gesehen), dann grün.

- **5 (MINOR) Still übersprungene Seed-Dateien:** `seed_io.import_tree` zählt übersprungene Dateien
  (`uebersprungen`, YAML-Wurzel keine Abbildung); `seed_sync` trägt die Zahl mit dem gelesenen Seed
  (`_seed_gelesen`), und `werksabgleich` zählt dazu, was `pruefen` (`pruefe_bereiche`, ungültiger
  Schlüssel) verwirft. Ist etwas ausgelassen, plant der Abgleich kein Entfernen (Log-Warnung „Seed
  nicht vollständig gelesen“); Anlegen und Anheben laufen wie bisher. Tests
  `test_werksabgleich::test_g1_review_5_…` (Listen-YAML im Seed; von der Prüfung verworfener
  Bereich).
- **6 (MINOR) Fremder Baum:** `seed_sync.werksabgleich(…, abraeumen=…)`; die Kommandozeile setzt
  ihn auf `_ist_seed(src)` und sagt sonst „--from ist nicht der Seed-Ordner … nicht entfernt“.
  `migrate` (ohne `--from`, also `CONFIG_SEED_DIR`) und der Studio-Knopf räumen weiter ab. Tests
  `test_werksabgleich::test_g1_review_6_…` und `test_cli_werksabgleich::test_g1_review_6_…`
  (Wegwerf-Datenbank); der G1-Test der Kommandozeile setzt `CONFIG_SEED_DIR` jetzt auf seinen Baum.
- **7 (MINOR) Verwaist mit stillgelegter eigener Fassung:** **Betriebsweg statt Studio-Aktion.**
  Der Fall entsteht nur, wenn die Redaktion einen alten Ablauf angepasst und danach auf die
  Werksfassung umgeschaltet hatte. Eine Studio-Aktion bräuchte Endpunkt, Store-Methode,
  Schnappschuss, Knopf mit Rückfrage und Tests in Backend und Studio — zu viel für diesen seltenen
  Fall. Der Weg (sichern per `SELECT`, dann `DELETE`; der Trigger aus Migration 0003 benachrichtigt
  alle Kopien) steht in `docs/offene-befunde-und-todo.md` §4.
- **8 (NIT):** Entfernte Bereiche stehen mit Namen im Log („nicht mehr im Werk, entfernt: …“).
- **9 (NIT):** `deploy/compose.prod.yml`, `deploy/INSTALL-schnellstart.md` und der Hilfetext von
  `--werksabgleich` nennen das Entfernen.

Angepasst: `test_seed_io.py::test_import_tree_maps_yaml_and_md` erwartet die neue Zahl
`uebersprungen: 0` in den Statistiken.
