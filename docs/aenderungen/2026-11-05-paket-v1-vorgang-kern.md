# Paket V1: Vorgang-Kern — Arbeitsstand über Züge und Sitzungen (2026-11-05)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §2, §3,
§6 (freigegeben 2026-11-05). Ersetzt das geplante U3-1c.

## Was entsteht

Ein **Vorgang** hält den Arbeitsstand einer Person: die erfassten Ordner (`structure`), ein gelesenes
Dokument (`document`, Verweis auf `dokument_uploads`) und den zuletzt übernommenen Entwurf (`draft`, mit
früheren Fassungen). Er entsteht ohne Ablauf, sobald eine dieser Modul-Antworten kommt, und überdauert das
Gespräch: die angemeldete Person findet ihn auch aus einer neuen Sitzung, ohne Anmeldung gehört er der
Sitzung. Die KI sieht je Zug eine Kennzeile `[ARBEITSSTAND — Vorgang „…“; Teile: draft v2 (…) …]`, nie die
Daten. `ui_strukturentwurf` mit `vorlage: true` nimmt den Entwurf aus dem Vorgang, wenn mit der Nachricht
keiner kam — auch Tage später.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Datenbank | Migration `0018_vorgaenge`: `vorgaenge` (Besitzerin, Titel, Zweck, Status, Akte `wlo.vorgang@1`, `akte_version`, Frist) und `vorgang_ablage` (große Teile > 8 KB, frühere Fassungen, CASCADE) |
| Dienste | `services/vorgaenge.py`: anlegen (höchstens 3 je Besitzerin, abgeschlossene weichen zuerst), lesen (nur Besitzerin, nicht abgelaufen), `teil_setzen` (Version je Teil, Historie ≤ 5, bedingtes Update → `VorgangKonflikt`), `teil_wert`/`historie_wert`, löschen, Aufräumen |
| | `services/arbeitsstand.py`: Teile aus geprüften Antworten (`ui_upload` → `structure`/`document`, `ui_strukturentwurf` → `draft`), Verweis `_vorgang` in den `entities` (nur Kennung, Titel, Versionen, Kurztexte, Frist), Kennzeile (≤ 300, eine Zeile, Endmarken entschärft), Übernahme mit einem Neuversuch bei Konflikt, Lader und Teil-Lader |
| Zug | `persist`: Übernahme vor dem Speichern der Sitzung (nicht bei hohem Risiko); Preflight „Ordner als Entwurf“: dort, weil dieser Zug `persist` nie erreicht; Kennzeile vor der Nachricht in beiden Maschinen |
| Dienste-Umgebung | `Umgebung.teile` (Agent: `run_agent_loop(modul_teile=…)`, Muster: `TEIL_LADER_KEY`); Vorlage aus dem Vorgang im Strukturentwurf |
| Aufräumen | Aufbewahrungslauf löscht abgelaufene Vorgänge; `delete_session` löscht anonyme Vorgänge mit (`deleted.vorgaenge`) |
| Manifest | `ui_strukturentwurf.vorlage` nennt den Teil `draft` aus `[ARBEITSSTAND]` |

**Frist:** fest 3 Tage nach letzter Nutzung (Nutzerentscheid E-16); das Studio-Feld kommt mit dem
Ablauf-Bereich in A1. **simplify:** V1 verdrahtet die drei Module fest (`teile_aus_antwort`); V2 liest
dasselbe aus dem Manifest.

## Tests

Neu: `test_vorgaenge` (Postgres: Besitzerin, Versionen/Historie, Ablage, Konflikt, Grenze 3, Frist,
anonyme mit Sitzung, Löschen), `test_arbeitsstand` (Teile, Kennzeile, Übernahme, anonym → Person, Konflikt,
Lader); ergänzt: `test_persist_node`, `test_preflight_node`, `test_respond_agent` (Kennzeile im Prompt),
`test_ui_strukturentwurf_aufruf` (Vorlage aus dem Vorgang), `test_db_sessions_pg`.

## Review V1 (2026-11-05, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 2 MAJOR, 9 MINOR, 3 NIT; alle gegen den Code geprüft.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | eine neue Sitzung der Person fand ihren Vorgang nicht (nur über den Verweis) | `vorgaenge.juengster`; `kennzeile_fuer_zug` setzt den Verweis neu, `_speichern` nimmt ihn statt einen neuen anzulegen | `test_eine_neue_sitzung_der_person_findet…`, `test_juengster_offener_vorgang…` |
| 2 | MAJOR | Kennzeile prüfte die Besitzerin nicht (Ab-/Ummelden → Titel der vorigen Person) | Streuwert der Besitzerin im Verweis; fremder Verweis fällt beim Zug weg | `test_ohne_abgelaufen_fremd…`, `test_ein_fremder_verweis_faellt…` |
| 3 | MINOR | `update().returning()` ließ nach einem Konflikt ein Phantom im Speicher | `synchronize_session=False`, `populate_existing` beim Lesen | `test_ein_gescheitertes_update_hinterlaesst_kein_phantom` |
| 4 | MINOR | Commit/Rollback der ganzen geteilten Sitzung; Ablage vor dem Versionsabgleich | Savepoint je Versuch; zuerst die Version beanspruchen, dann Ablage, dann Akte | `test_gleichzeitiges_schreiben…`, `test_ein_konflikt…` |
| 5 | MINOR | `bis` ohne Zeitzone → `TypeError` im Agent-Zug; andere Fehler brachen `persist` ab | Zeitzone verlangt, `TypeError` abgefangen; `uebernehmen` fängt jeden Fehler, protokolliert, rollt zurück | `test_ohne_abgelaufen…`, `test_ein_anderer_fehler_beendet_den_zug_nicht` |
| 6 | MINOR | `]` im Titel schloss die Kennzeile | `[`/`]` im Inhalt → runde Klammern | `test_eckige_klammern…` |
| 7 | MINOR | Preflight-Weg „nur Text“ speicherte den Verweis nicht | `update_session` direkt nach der Übernahme; dazu heilt Befund 1 verwaiste Vorgänge einer Person | `test_ordner_als_entwurf_wird_geprueft…` |
| 8 | MINOR | Grenze 3 ohne Sperre | `pg_advisory_xact_lock(hashtext(aufrufer))` beim Anlegen | (Sperre; Grenze per `test_hoechstens_drei…`) |
| 9 | MINOR | `document` trug die Kennung des Widgets ungeprüft | nur wenn sie zum Dokument der Sitzung passt; gespeichert als `ref: dokument:<id>` mit Befund des Servers | `test_das_dokument_gilt_nur_wenn…` |
| 10 | MINOR | `purge_all(sessions=True)` und gelöschte Sitzungen ließen anonyme Vorgänge stehen | `alle_anonymen_loeschen`; Aufbewahrung löscht anonyme ohne Sitzung | `test_juengster_offener_vorgang_und_purge…` |
| 11 | MINOR | Testlücken | siehe oben; Muster-Weg über `tool_loop_module` weiter nur indirekt | — |
| 12 | NIT | Vorgänge im Log als „Dokumente“ gezählt | eigener Zähler | — |
| 13 | NIT | `draft` auch bei `uebernommen: false` | **so gewollt:** der mitgeschickte Stand ist der aktuelle der Person; dokumentiert | — |
| 14 | NIT | Frist nur beim Schreiben neu; 64-KB-Deckel der Akte nicht durchgesetzt | Lesen verlängert (`beruehren`); Deckel: jeder Teil ≤ 8 KB inline, größer in der Ablage — offen bis V2 mehr Teile bringt | `test_lesen_verlaengert_die_frist` |

Außerhalb des Umfangs (vorher schon): `aufrufer_kennung` fällt bei bestätigter Person ohne Kennung auf
den Fingerabdruck des Blocks zurück; `merge.py` übernimmt Entities des Klassifikators ungefiltert.
