# Paket K1a: Aufträge über die b-api (Kestra) im Ablauf (2026-11-06)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §5,
§9 (Feinentwurf K1). Grundlage: Team-Info 2026-11-03 (Konzept `2026-10-24-ablaeufe-und-ui-module.md`
§16.15). Gebaut gegen eine **Vertrags-Attrappe**: der Start-Pfad ist offen (K16).

## Was entsteht

Ein Ablauf kann einen **Auftrag** starten — einen Kestra-Flow hinter der b-api — und das Ergebnis später
abholen:

```yaml
- id: lesen
  typ: auftrag
  flow: wlo/volltext                 # nur Flows, die der Betrieb freischaltet
  argumente: {dokument: {$teil: document}}
  schreibt: volltext                 # die Ausgaben werden dieser Teil
  bei_fehler: schade
  text: {de: "Ich lasse das Dokument lesen."}
```

- **Start** durch den Treiber, nur mit **bestätigter Anmeldung** (Plan V-3) und nur, wenn die Anlage Aufträge
  eingerichtet hat. Der Lauf hält an (`wartet_auftrag`); die Job-ID liegt in **`vorgang_auftraege`**
  (Migration **0019**, geht mit dem Vorgang). Je Vorgang ein offener Auftrag.
- **Abholen** mit dem Knopf **„Stand prüfen“** (Direktaktion `ablauf_auftrag_pruefen`, hinter der
  Sicherheitsprüfung): läuft noch → Hinweis; fertig → `outputs` und Dateien (nur Name/Größe) werden Teil
  `schreibt`, der Treiber setzt fort; Fehler → `bei_fehler` oder Ende mit Hinweis; b-api nicht erreichbar →
  Hinweis, Knopf bleibt.
- **Warum nur im Zug der Person:** Der durchgereichte Schlüssel der Person wird nie gespeichert (Paket 17).
  Ein Wächter im Hintergrund hätte nur `B_API_KEY` und könnte einen mit dem Personenschlüssel gestarteten
  Auftrag womöglich nicht lesen → neue Frage **K22** an das Team.
- **Der Betrieb schaltet frei, nicht die Redaktion:**
  - `B_API_JOBS_START_PATH`: Vorlage mit `{flow}`; leer = Aufträge aus (Vorgabe).
  - `B_API_JOBS_STATUS_PATH`: Vorgabe `/api/v1/jobs/{job_id}`.
  - `B_API_JOBS_FLOWS`: Liste der erlaubten Flows.

  Das Studio weist einen Ablauf mit nicht freigeschaltetem Flow oder ohne Voraussetzung „Anmeldung“ ab.
  Es geht **kein `X-Edu-User-Id`** mit (K18 offen), also nur lesende Flows. Aufträge laufen **nur mit dem
  durchgereichten Schlüssel der Person** (hinter dem b-api-Proxy), nie mit `B_API_KEY` — sonst teilten alle
  Angemeldeten dessen 20 Aufträge.
- **Datenschutz:** Eingaben (etwa `{"$teil": "document"}`) und Ausgaben liegen bei Kestra 30 Tage im Klartext
  und gehen mit dem Vorgang nicht weg — nur Flows freischalten, deren Eingaben dort liegen dürfen
  (`deploy/.env.example`).
- **Offen (V-4):** Ein Vorgang mit laufendem Auftrag hält heute nur `vorgang_tage` (Vorgabe 3); siehe
  `docs/offene-befunde-und-todo.md` §2.
- 429 (20 offene Jobs), 401/403, 404 und unbrauchbare Antworten werden zu einem Grund (`voll`, `abgewiesen`,
  `unbekannt`, `fehler`), nie zu Text aus der Antwort. Job-IDs werden geprüft, bevor sie in einen Pfad gehen.

Nebenbei: Die gemeinsamen Bausteine der Ablauf-Züge stehen jetzt in `services/ablauf/zug_basis.py`
(verhaltensgleich aus `zug.py` gelöst, das sonst über 300 Zeilen gewachsen wäre).

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Einstellungen | `B_API_JOBS_START_PATH`, `B_API_JOBS_STATUS_PATH`, `B_API_JOBS_FLOWS` (+ `deploy/.env.example`) |
| Datenbank | Migration 0019 `vorgang_auftraege`, Modell `VorgangAuftrag` |
| Backend | `services/auftraege/client.py` (Start, Stand, Gründe), `ablage.py` (anlegen/offen/abschließen) |
| Backend | Modell: Art `auftrag`, Feld `flow`; `pruefung` (Flow, Freischaltung, `schreibt`, Anmeldung); `treiber` (`WARTET_AUFTRAG`, `Umgebung.auftrag_starten`, `Ausgabe.auftrag`, `weiter_auftrag`) |
| Backend | `services/ablauf/auftrag_zug.py` (`starter`, `pruefen`, Knopf); `zug_basis` (Umgebung mit Start-Naht, Job-ID festhalten, Knopf in der Antwort); Preflight (Direktaktion), `turn_assembly` (Knopf), Kennzeile, `lauf_wartet` |
| i18n | `action.ablauf.auftragKnopf`, `auftragLaeuft`, `auftragNichtAbrufbar` (DE/EN) |
| Studio | Feldtexte `Schritt.flow`, `Schritt.typ.wahl.auftrag`; Schema-Fixture neu |

## Tests

Neu: `test_auftraege_client` (aus ohne Pfad, Freischaltung, Start mit Schlüssel und ohne `X-Edu-User-Id`,
nicht freigeschaltet, Fehlergründe, Stand je Kestra-Status, Dateien ohne URL, Job-ID nicht in den Pfad,
unbekannter Job), `test_auftraege_ablage` (Postgres: anlegen/offen, Ersetzen, Abschließen, Löschen mit dem
Vorgang), `test_ablauf_auftrag` (Prüfung, Treiber startet und hält, Fehlerwege, Ergebnis wird Teil, im Zug:
Start mit Knopf, läuft/fertig/Fehler/nicht abrufbar, ohne Anmeldung kein Start, ohne Lauf).

Läufe nach den Review-Fixes: Backend 8459 grün, Studio 1967; ruff und eslint sauber.

## Review K1a (2026-11-06, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 2 MAJOR, 6 MINOR, 3 NIT. Geprüft und in Ordnung: Schlüssel nie gespeichert oder geloggt;
Job-IDs nur aus der Datenbank mit Besitzprüfung; Freischaltung beim Speichern und beim Start; `starter` je Zug;
Sicherheitsprüfung vor der Direktaktion; `downloadUrl` verworfen; `wartet_auftrag` zählt als offen;
Abschließen, Anlegen und Lauf in einer Transaktion; Migration mit `IF NOT EXISTS` und Kaskade; Job-Ausgaben
erreichen die KI nur als Kurztext der Kennzeile.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Ohne durchgereichten Schlüssel liefen Aufträge auf `B_API_KEY` (alle teilen 20 Plätze) | Start und Abfrage nur mit durchgereichtem Schlüssel der Person | `test_ohne_durchgereichten_schluessel_startet_kein_auftrag`, `…_wird_nicht_abgefragt`, `test_der_durchgereichte_schluessel_gewinnt` |
| 2 | MAJOR | Jeder unbekannte Stand galt als endgültiger Fehlschlag | nur `FAILED`/`KILLED`/`CANCELLED`; Unbekanntes/Leeres → erneut abfragbar | `test_ein_unbekannter_stand_ist_erneut_abfragbar` |
| 3 | MINOR | Konflikt nach dem Start: Auftrag läuft, ist aber nirgends festgehalten | Warnung im Log (ohne Abbruch-Schnittstelle K21 bleibt nur das) | — (Log) |
| 4 | MINOR | Ausgaben ohne Größengrenze in die Akte | höchstens 1 MB JSON, größer gilt als gescheitert | `test_eine_zu_grosse_ausgabe_gilt_als_gescheitert` |
| 5 | MINOR | Pfad-Vorlage konnte den Server wechseln; `InvalidURL` → 500 | Vorlage nur ab `/`, ohne `//`, `@`, `?`, `#`, `\`; `InvalidURL` gefangen | `test_eine_unsichere_pfad_vorlage_schaltet_aus` |
| 6 | MINOR | Frist mit laufendem Auftrag (V-4) nicht umgesetzt | als offener Entscheid eingetragen | — |
| 7 | MINOR | Datenschutz der Eingaben an Kestra nicht beschrieben | Hinweis in Notiz und `.env.example` | — |
| 8 | MINOR | Testlücken (Schlüssel, Stände, Konflikt, Abbruch, Wurzel) | ergänzt | `test_ein_konflikt_beim_abholen…`, `test_ein_ausgeschalteter_ablauf_bricht_lauf_und_auftrag_ab`, `test_die_wurzel_ohne_llm_pfad` |
| 9 | NIT | Abbruch ließ den Auftrag offen; Schritt nicht verglichen | Abbruch schließt ihn (`abgebrochen`), Schritt muss passen | `test_ein_ausgeschalteter_ablauf_bricht…` |
| 10 | NIT | Job-ID `..` möglich | reine Punkt-IDs abgewiesen | `test_unbrauchbare_job_ids` |
| 11 | NIT | Knopf „Stand prüfen“ auch für ausgeschaltete Abläufe | wie beim Agent-Schritt nur mit gültigem Ablauf | `test_ein_ausgeschalteter_ablauf_bricht…` |
| — | Wächter | Compose, Helm, Log-Wächter rot | Variablen verdrahtet, Log ohne Antwortobjekt | `test_deploy_compose`, `test_helm_values`, `test_log_ohne_inhalt` |
