# Paket K, Teil a: Kestra-Flows über den MCP (2026-11-18)

Plan: `docs/plans/2026-11-17-b-api-delegation-und-upload.md`, §4a (E13–E18) und §5 Paket K, Tasks
K1, K2, K3, K4, K8. Vertrag des MCP: Antwort vom 18.11. (`wlo-mcp-server-sc`, Commit `da33918`,
`src/tools/bapi-flows.ts`, `src/services/bapi/*`) samt Nachtrag (zweite Fassung).

## Warum

Das Delegations-Token der b-api deckt keine Jobs. Eine Person gilt bei der b-api nur, wenn das
Repository für sie bürgt (`{repo}/rest/bapi/**`). Diese Anmeldung hält nur der MCP. Er bietet dafür
`wlo_start_flow`, `wlo_flow_status`, `wlo_cancel_flow` und `wlo_list_flows`. Der Chatbot steuert
weiter (wann, welcher Flow, Zustimmung), gestartet wird über den MCP (E1/E2).

## Was

### K1 `services/auftraege/mcp_starter.py` (neu)

- Gleiche Schnittstelle wie `client.starten/stand/abbrechen`, aber über die MCP-Werkzeuge.
- Gerufen wird wie bei der Stapel-Ablage: direkt über `transport.call_tool`, nur mit bestätigter
  Anmeldung und dem Zugangsblock des Zuges. Gelesen wird `structuredContent`. Kein Modell, kein
  Cache, keine Zugakte.
- **Start in zwei Schritten:** erst die Vorschau (ohne `confirmToken`), dann derselbe Aufruf mit
  `confirm.token`. Der Schlüssel lebt nur in dieser Funktion, nie im Modell, im Vorgang oder im Log.
- **`error.outcomeOpen` entscheidet:** `true`, keine Antwort nach der Bestätigung, `inProgress`
  oder `started` ohne brauchbare `jobId` → Grund `offen`. Dann wird nie neu gestartet. `false` →
  nichts gestartet (`eingaben`, `abgewiesen`, `fehler`).
- Kennung im Vorgang: `mcp:<jobId>`. Der Doppelpunkt kommt in keiner jobId vor. So erkennt jeder
  spätere Zug den Träger, und der Direktweg weist die Kennung ab. Ein offener Start bekommt
  `mcp:offen:<zufall>`, eine jobId gibt es dann nicht.
- **Stand:** `running` → läuft, mit `progress` als „k von n fertig“ (`Stand.fortschritt`, neu).
  `succeeded` → fertig, Ausgaben ohne Job-Kennungen. `failed`/`cancelled`/`truncated` → Fehler.
  `unknown` → erneut abfragbar, nie „läuft“. `unknown_job` → `job_unbekannt`.
- **Nachtrag MCP:** Nach einem Neustart fehlen die Werkzeuge kurz. Das SDK des MCP (1.32) antwortet
  dann `isError` mit `MCP error -32602: Tool … not found`. Der Starter holt die Fähigkeiten neu
  (`faehigkeiten.erkunden`) und meldet `nicht_verfuegbar`, also vorübergehend.
- Unbekannte `reason`-Werte ergeben den allgemeinen Grund `fehler`.

### K2 Wahl des Trägers (`services/ablauf/auftrag_zug.py`)

`traeger(repo_schreibt=…)` liefert `(träger, grund)` (Regel seit dem Review vom 19.11., A4/A7):

| Schritt | Lage | Träger |
|---|---|---|
| mit `repo_schreibt` | MCP führt alle drei Werkzeuge, Person bestätigt angemeldet (auch bei Delegation) | `mcp` |
| mit `repo_schreibt` | Werkzeuge fehlen, waren aber vor ≤ 10 Minuten da | keiner: `mcp_kurz_weg` („gleich noch einmal“) |
| mit `repo_schreibt` | sonst | keiner: `ohne_mcp` (`auftragNurUeberWlo`) |
| ohne `repo_schreibt` | b-api eingerichtet und `darf_jobs()` | `direkt` (wie vor Paket K) |
| ohne `repo_schreibt` | sonst | keiner: `delegation`, `nicht_eingerichtet`, `ohne_schluessel` |
| jeder | ohne Anmeldung | keiner: `ohne_anmeldung` |

- Die Naht `starter()` wählt den Träger je Schritt (`_Wahl.fuer(repo_schreibt)`). Der Treiber
  startet einen Schritt mit `repo_schreibt` nie über den Direktweg und einen ohne nie über den
  MCP. Ohne MCP sagt er es mit `auftragNurUeberWlo` und nimmt `bei_fehler`. Das gilt auch für
  weitere Teile eines Stapels.
- Über den MCP gilt die Flow-Freigabe des Studios bzw. `B_API_JOBS_FLOWS`. Der Startpfad der b-api
  (`B_API_JOBS_START_PATH`) gilt dort nicht. Der MCP hält zusätzlich `WLO_BAPI_FLOWS`.
- Start mit offenem Ausgang: Der Schritt wartet am Auftrag mit dem Satz `auftragOffen`. „Stand
  prüfen“ fragt den MCP nicht und geht weiter zu `lesen` (die Datensätze zeigen, was geschah).
- Werkzeug gerade nicht da (Nachtrag): Der Treiber führt zurück an die Rückfrage vor dem Schritt.
  Die Person liest „gerade nicht verfügbar, gleich noch einmal“ und kann erneut „Ja“ wählen. Das ist
  kein endgültiger Fehlschlag. Ohne Rückfrage davor bleibt es beim Ersatzweg.

### K3 „Gründlich über WLO“ und Upload-Feld

- `zug_basis.wlo_erschliessen` (seit dem Review öffentlich) fragt `auftrag_zug.kann_starten(METADATEN_FLOW, repo_schreibt=True)`.
  Damit geht der gründliche Weg nur mit dem MCP als Träger, auch bei Delegation.
- `dienst_upload`: Die Schalter bleiben gleich. Die Ablage hängt nicht am Träger, der Vertrag des
  Moduls (`additionalProperties: false`) bleibt unberührt. Der Satz an die KI verspricht Metadaten
  nur noch, wenn der Träger sie erzeugen kann.

### K4 Abbruch im Zug (`zug_basis.auftraege_beenden`, neu)

- Ersetzt für Aufträge des MCP den Hinweis aus D4 („läuft im Repository zu Ende“). Ein Auftrag des
  MCP wird **im Zug** über `wlo_cancel_flow` abgebrochen, nach dem Festschreiben. Aufträge des
  Direktwegs gehen den alten Weg (`bei_der_b_api_abbrechen`).
- Ausgang: `beendet` (abgebrochen oder schon fertig), `offen` (keine Antwort, `outcomeOpen`,
  `unknown_job`, offener Start), `weiter` (ohne Anmeldung, abgewiesen, Werkzeug nicht da).
- Sätze: `auftragAbgebrochen`, `auftragStandUnklar` („unklar, im Vorgang bzw. in WLO
  nachsehen“), `auftragLaeuftWeiter`. Beim Arbeitsstand: `vorgang.auftragUnklar` hinter dem Satz,
  wenn es offen bleibt.
- Betroffen: „Auftrag abbrechen“, „Abbrechen“ der Leiste, „Neues Vorhaben“, „Arbeitsstand löschen“,
  `POST /api/ui/vorgaenge/loeschen` (Meine Vorgänge) (`auftrag_laeuft_weiter`), Ersetzen eines Laufs,
  `nicht_festgehalten` (jetzt `async`).
- `zug_basis.abbrechen` gibt statt `True` den Ausgang zurück (`None` bleibt der Konflikt).

### K8 Bericht, `unknown_job`, jobId

- Der Bericht je Knoten (`outputs.report[]`) geht an die Person nur als Zahlen: „n Materialien
  erschlossen, m nicht“. Erschlossen heißt `written.changedKeys` nicht leer oder ein
  Erfolgs-`status`.
- `unknown_job` eines Auftrags dieses Vorgangs ist kein Fehlschlag. Der Ablauf geht weiter zum
  nächsten Schritt (`lesen` → `metadaten_lesen`) mit `auftragStandWeg`.
- `POST /api/ui/auftrag/stand` (Modul `ui_fortschritt`) fragt Aufträge des MCP über
  `wlo_flow_status` ab. `unknown_job` → `fertig`, das Abholen geht dann zu `lesen`.
- **jobId geprüft:** Der Teil `wlo.auftrag@1` (`metadatenlauf`) trägt Ausgaben, Dateien und
  Warnungen, aber keine jobId. `[ARBEITSSTAND]` nennt nur Namen und „Ergebnis von <flow>“. Der
  Fortschritts-Block trägt nur das Kürzel. Zur Absicherung entfernt der Starter `jobId`, `job_id`
  und `executionId` aus den Ausgaben eines Flows. Die Aufrufe gehen nicht durch Zugakte oder
  Werkzeug-Log. Die Texte des MCP (sie nennen die jobId) gelangen nirgends hin. Die jobId steht nur
  in `vorgang_auftraege.job_id` (Datenbank, wie bisher).

## Entscheide und Abweichungen vom Plan

1. **Keine Freigabe-Box am Auftragsschritt.** Plan bzw. Auftrag gehen von einer Paket-S-Box mit
   Chip am Schritt `auftrag` aus. Im Code ist die Zustimmung zu einem schreibenden Flow die
   **Rückfrage direkt davor** (Prüfung `auftrag_rueckfrage`, N15, im Seed `metadaten_frage`). Eine
   Box gibt es dort nicht. Der Starter holt deshalb die Vorschau des MCP und bestätigt sie im selben
   Zug serverseitig. Die Prüfung des MCP (jeder Datensatz als die Person, keine Verknüpfung,
   schreibbar) gilt trotzdem: Eine abgelehnte Vorschau startet nichts. Eine Box mit der Liste
   „nodeId Titel“ wäre ein eigenes Paket. Sie müsste die Freigabe-Mechanik von Paket S auf
   `auftrag`-Schritte ausdehnen, je Teil eines Stapels mit eigener Vorschau.
2. **K4 bei einem offenen Start:** Es gibt keine jobId, also auch keinen Abbruch beim MCP. Der Satz
   ist „Stand unklar“.
3. **`unknown_job` beim Abbruch** gilt als „Stand unklar“, nicht als „beendet“. Nach einem Neustart
   des MCP kann der Job noch laufen.
4. **Dateien eines MCP-Auftrags** (`dateien_holen`) werden nicht geholt, W5 baut der MCP erst
   später. Sie stehen als `nicht_verfuegbar` in `dateien_fehlen`.

## Deploy

- Chatbot: keine Migration, keine neue Variable.
- MCP: **Auf Staging ist nichts zu setzen.** Der MCP erkennt den b-api-Proxy des Repositorys beim
  Start selbst und bietet dann die vier Werkzeuge. `node-metadata-write` ist ab Werk startbar.
  - `WLO_BAPI_VIA_REPOSITORY=1` bzw. `0` legt fest, ob die Werkzeuge da sind (statt der
    Erkennung).
  - `WLO_BAPI_FLOWS` schränkt die startbaren Flows nur ein.
- Nach einem Neustart des MCP fehlen die Werkzeuge Sekunden bis Minuten. Der Chatbot holt die
  Werkzeugliste nach einem „unbekanntes Werkzeug“ sofort neu, sonst im Takt von fünf Minuten.
- Staging-Durchtest nach dem Rollout (Plan §9): Ablage → Flow-Start → Stand → `metadaten_lesen`.

## Tests

- `tests/test_paket_k_mcp_starter.py`: Drahtform des MCP für Start, Stand, Abbruch,
  `outcomeOpen`, unbekannte Werkzeuge, Log ohne jobId.
- `tests/test_paket_k_traeger.py`: Matrix des Trägers, `repo_schreibt` nur über den MCP,
  `_wlo_erschliessen`, Satz des Upload-Felds.
- `tests/test_paket_k_zug.py`: im Zug Bericht als Zahlen, `unknown_job`, unbekanntes Werkzeug bei
  Stand und Start, offener Start, Abbruch im Zug, Arbeitsstand löschen. Dazu jeweils die Prüfung,
  dass die jobId nicht in Antwort, Kennzeile, Vorgang oder Log steht.

## Teil b (2026-11-19): K5, K6, K7, K9

### K5 Strukturdokumente durch den Flow (E14)

- Seed `06-ablaeufe/themenbaum.yaml`, Schritt `metadaten`: `node_ids` sind jetzt alle abgelegten
  Einträge der Ablage (`wo: {stand: stored}`). Die Ablage kennt nur die Rollen `inhalt` und
  `struktur` (`ablage/vorgang_teil`), ohne Filter auf die Rolle sind es also beide. Der Kommentar
  „MINOR 7“ ist ersetzt (E14 hebt ihn auf). Die Rückfrage `metadaten_frage` nennt die
  Strukturdokumente („auch für Strukturdokumente wie einen Lehrplan“).
- `services/ablauf/vorbelegung.py`: `_aus_strukturdokumenten` liest Fach, Bildungsstufe und Thema
  (Titel) aus dem Teil `metadaten`, aber nur für Knoten, die `ablage` als abgelegtes
  Strukturdokument führt. Die Rolle, die `metadaten` selbst nennt, zählt nicht. Fach und Stufe
  laufen durch dieselben Prüfer wie im Entwurf (`strukturentwurf.fach`/`bildungsstufe`).
  Unbekannte Stufen fallen weg. `fach` ist neu unter den vorbelegten Argumenten (auch in der Zeile
  `[VORBELEGT]`).
- Vorrang: Argument der KI vor Antwort der Person vor Strukturdokument vor den übrigen Daten. Eine
  Stufen-Antwort, auch „Für alle“, schlägt die Stufe des Dokuments. Eine getippte Grundlage schlägt
  dessen Titel. Der Titel des Strukturdokuments geht dem Ordnernamen bzw. dem Dateinamen vor
  (`_thema_aus_daten`).
- **Volltext fehlt noch** (`volltext_fehlt_datei`): Geprüft wurde, wie es heute läuft. Gelesen wird
  der Volltext nur am KI-Schritt `entwurf_dokument` (`ui_strukturentwurf` mit `aus_dokument`). Fehlt
  er, meldet das Werkzeug der KI einen Fehler. Der Lauf scheitert dabei nicht: Er hält am
  KI-Schritt. Erneutes Anstoßen ist dort das „Stand prüfen“, und „Weiter im Ablauf“ führt ohne
  Entwurf zu `ohne_entwurf` mit „Nochmal versuchen“. Die kleinste saubere Lösung ist deshalb nur
  der Satz an die KI: Der Text wird nach dem Übertragen gerade erzeugt, der Ablauf wartet an diesem
  Schritt, in ein paar Minuten noch einmal anstoßen. Einen eigenen Halt gibt es nicht, der Seed
  hat schon die erlaubten 40 Schritte.
- Seed-Selbsttests: Der Fall „Ordner nach WLO übertragen“ bleibt unverändert. Eine vorab gelegte
  Ablage mit Strukturdokument meldet `bereitgestellt` schon beim Start als Dokument, der Lauf
  begänne dann an `einstieg_mit`. Die Auswahl über beide Rollen prüft
  `test_paket_k5_strukturdokumente` am Seed (`aufloesen`). `test_tg6_review` prüft statt MINOR 7
  jetzt E14. `pruefe`, `warnungen` und alle Selbsttests bleiben ohne Befund.

### K6 „k von n fertig“ (E16)

- `POST /api/ui/auftrag/stand` antwortet mit `{"stand": …, "fertig": k, "gesamt": n}`, wenn
  `Stand.fortschritt` gültig ist (ganze Zahlen, `0 ≤ k ≤ n`, `n > 0`). Sonst kommt nur `stand`.
  Ausgaben und jobId gehen nie mit. Der eingefrorene OpenAPI-Vertrag ist neu erzeugt
  (`scripts/export_openapi.py`).
- Widget `ChatApiClient.auftragStand` reicht `fertig`/`gesamt` nur weiter, wenn beide ganze
  Zahlen sind.
- Modul `ui_fortschritt`: `fortschrittZahlen` prüft die Zahlen. Das Modul zeigt „12 von 40 fertig“
  bzw. „12 of 40 done“ (Zahlen über `Intl.NumberFormat`). Der `<progress>` bekommt `value`/`max`,
  und ein neuer Stand wird über die bleibende `aria-live`-Zeile angesagt. Ohne Zahlen bleibt die
  Anzeige wie bisher (Balken unbestimmt, „Läuft noch …“). Es gilt immer die letzte Antwort.

### K7 „Später weitermachen“ (E16, E17)

- Neue Direktaktion `ablauf_auftrag_spaeter` (`services/ablauf/auftrag_spaeter.py`). Der Knopf
  steht zwischen „Stand prüfen“ und „Auftrag abbrechen“, aber **nur an einem Schritt mit
  `warten: gesperrt`**: In einem freien Warten ist der Chat ohnehin frei.
- Der Lauf bleibt `wartet_auftrag`, der Auftrag läuft weiter. Es gibt keine Abfrage beim Träger
  und keinen Abbruch, und am Vorgang wird nichts geschrieben. Die Sperre ruht für diese Sitzung:
  Die Marke `_auftrag_spaeter` (Vorgang:Schritt:Fassung:Teil, der Teil seit Review B3) liegt in
  `entities`. `auftrag_zug.gesperrt` beachtet sie, `sperre_aufraeumen` entfernt eine veraltete
  Marke.
- Satz (seit Review B2): „Die Erschließung läuft in WLO weiter. Du kannst hier jederzeit „Stand
  prüfen“ wählen oder später wiederkommen – ich führe dich dann zurück. Das geht bis {datum}.“
  Darunter steht nur „Stand prüfen“. **Korrektur:** „Meine Vorgänge“ ist nicht der Weg zurück —
  dort stehen nur die Vorgänge anderer Gespräche. Zurück führt „Stand prüfen“ in diesem Gespräch;
  wer später wiederkommt, landet über den Verweis der Sitzung (bzw. angemeldet über den jüngsten
  offenen Vorgang, `arbeitsstand.auffrischen`) wieder beim wartenden Lauf.
- Frist: die frühere von `vorgang.verfaellt_am` und Start des Jobs (`vorgang_auftraege.erstellt`)
  plus 30 Tage (`client.JOB_TAGE`). `verfaellt_am` setzt sich aus den Tagen aus dem Studio
  zusammen (wartend mindestens 8, höchstens 30). Der Aufbewahrungslauf (`services/aufbewahrung.py`)
  löscht danach. Genannt wird der Tag vor dem Ablauf (UTC), weil die Uhrzeit unbekannt ist — nie
  ein Tag vor heute (Review B7).
- Rückkehr: „Stand prüfen“ entfernt die Marke und speichert `entities` sofort. „Fortsetzen“ unter
  „Meine Vorgänge“ (aus einem anderen Gespräch) schickt dieselbe Aktion, ebenso das Abholen des
  Moduls. Läuft der Auftrag noch,
  greift die Sperre wieder, mit den drei Knöpfen. Geprüft ist das für den Direktweg, für
  MCP-Aufträge (`mcp:<id>`, „k von n fertig“) und für `unknown_job`: Der Lauf geht dann weiter zu
  `lesen`, eine Sperre gibt es nicht mehr.
- Widget: Hier war keine Änderung nötig. Die Sperre folgt `eingabe_gesperrt` jeder Antwort. Die
  neue Spec deckt „frei nach Später, wieder gesperrt nach Stand prüfen“ ab.
- Steuer-Listen: `preflight._DIRECT_ACTIONS`, `_STEUER_OHNE_TEXT`,
  `preflight_ablauf._IM_GESPERRTEN_LAUF`, `wahl_knopf._STEUER_AKTIONEN` und
  `auftrag_zug.ist_knopf`. So übersteht der Knopf jeden Deckel der Schnellantworten.
- Studio-Hinweis `feld.Schritt.warten.hint` nennt den dritten Knopf.
- Behoben (K2b-Fehler): Die Krisen-Marke `SPERRE_RUHT` (jetzt `_auftrag_sperre_ruht`) liegt wie
  `_auftrag_spaeter` in `entities` und ruht deshalb das ganze Warten über. Vorher lag sie im
  Wurzel-Dict von `session_state` und ging nach dem Zug verloren. „Stand prüfen“ bzw. das Abholen
  nehmen beide Marken zurück, solange der Job läuft. Test:
  `test_ablauf_auftrag_abbruch::test_der_preflight_setzt_die_sperre_nach_einer_krise_aus`.

### K9 Flow-Katalog im Studio

- `flow_katalog.vorschlaege`: Das Studio hat keine Person, die Liste kommt weiter über `B_API_KEY`.
  Ohne Schlüssel schlägt der Katalog die Werksvorgabe vor (`client.WERKSVORGABE`, innerhalb von
  `B_API_JOBS_FLOWS`) und dazu die freigegebenen Flows. Die freie Eingabe bleibt, einen Abruf gibt
  es nicht.
- Studio-Katalog `fields-ablaeufe.ts`, `feld.Schritt.flow.hint` (de/en): Mit Anmeldung startet der
  WLO-MCP den Flow. Welche Flows er wirklich startet, legt dort `WLO_BAPI_FLOWS` fest.

### Abweichungen vom Plan bzw. Auftrag

1. K5, eigener Halt für einen fehlenden Volltext: Es gibt keinen neuen Halt, siehe oben. Der Halt
   ist der KI-Schritt.
2. K5, der Weg „Dokument“ mit Übertragung nach WLO startet den Metadaten-Flow weiterhin nicht.
   `dokument_gelesen` führt nicht über `metadaten_frage`. Das zu ändern verschöbe `zum_entwurf`
   auf `entwurf_inhalte` und bräuchte Schritte, die der Seed nicht mehr hat. Für das Strukturdokument
   gibt es dort also weiter keine Vorbelegung aus WLO.
3. K7, Frist: Statt eines Werts aus `services/aufbewahrung.py` gilt `vorgang.verfaellt_am`. Danach
   löscht der Aufbewahrungslauf, und darin stecken die Tage aus dem Studio.
4. K7: Der Knopf steht nur bei gesperrter Eingabe, nicht an jedem Auftragsschritt.

### Tests (Teil b)

- `tests/test_paket_k5_strukturdokumente.py`, `test_paket_k6_fortschritt.py`,
  `test_paket_k7_spaeter.py`, `test_paket_k9_katalog.py`.
- Angepasst wurden Tests mit altem Soll: `test_tg6_review` (MINOR 7 → E14),
  `test_ablauf_auftrag_abbruch` (drei Knöpfe im gesperrten Lauf), `test_r2e_steuer_knoepfe`
  (Liste der Steuer-Aktionen) und `test_kf_kestra_flows` (ohne Schlüssel mit Werksvorgabe).
- Frontend: `ui-fortschritt` (`fortschritt-ablauf.spec.ts`, `ui-fortschritt.element.spec.ts`),
  Widget (`chat-api-auftrag.spec.ts`, `chat-shell-turn.spec.ts`) und Studio
  (`fields-ablaeufe.spec.ts`).
- Deploy: keine Migration, keine neue Variable. Das Modul-Bündel `ui-fortschritt` und das Widget
  müssen neu gebaut werden.

## Review-Befunde behoben (19.11.)

Zwei unabhängige Reviews (A: Kern, B: Flow, Warten, Oberfläche). Je Befund erst ein Test gegen
den Code, rot gesehen, dann behoben.

### Review A (Kern)

- **A1 (MAJOR) Offener Start und `ui_fortschritt`.** Ein Start mit offenem Ausgang
  (`mcp:offen:…`) bekommt keinen Block `ui_fortschritt` mehr (`treiber_bloecke.fortschritt`).
  `POST /api/ui/auftrag/stand` antwortet für eine offene Kennung 409 `kein_auftrag`, ohne den MCP
  zu fragen — ein alter Block hört damit auf. Weiter geht es nur über „Stand prüfen“. Dort steht
  statt `auftragStandWeg` („die Ergebnisse stehen an den Materialien“) der neue Satz
  `auftragOffenGelesen`: Ob der Auftrag lief, ist offen (etwa 429), gelesen wird trotzdem.
- **A2 (MAJOR) Zweites „Ja“ nach einem Neustart des MCP.** `faehigkeiten` merkt sich je Werkzeug,
  wann der MCP es zuletzt nannte (`alter`). Fehlen die drei Flow-Werkzeuge, waren sie aber vor
  höchstens `KUERZLICH_S` = 600 s noch da (`mcp_starter.kuerzlich_verfuegbar`), meldet der Starter
  eines Schritts mit `repo_schreibt` `nicht_verfuegbar` — zurück an die Rückfrage mit „gleich noch
  einmal“, nie der Direktweg. Vorher holt er die Fähigkeiten neu, höchstens alle
  `TAKT_NACH_FEHLER_S` = 20 s (`mcp_starter.nachholen`); sind die Werkzeuge zurück, startet er
  sofort. Dasselbe Nachholen vor „Stand prüfen“ und im Endpunkt `/stand`.
- **A3 (MINOR) Code einer Abweisung.** Bei `rejected` reicht der Starter den Code des MCP
  (`code` oben in `structuredContent`) an `AuftragFehler.code` weiter, nur aus
  `client.BEKANNTE_CODES`. `EDU_USER_NOT_VERIFIED` ergibt so `auftragAbgelehntKonto`. Der Satz
  `auftragAbgelehntPerson` (de/en) sagt jetzt ehrlich, dass keine angemeldete Person erkannt wurde
  und neu anmelden hilft — nicht mehr „wird gerade umgestellt“.
- **A4 + A7 (MINOR, Entscheid) Der MCP-Weg nur für `repo_schreibt`.** Siehe die Tabelle bei K2.
  Flows ohne `repo_schreibt` gehen den Direktweg mit `darf_jobs()` wie vor Paket K; ohne ihn gibt
  es keinen Träger (Grund im DEBUG-Log). Die Prüfung meldet einen Auftragsschritt mit einem
  bekannt schreibenden Flow (`kestra_flows.SCHREIBENDE_FLOWS`, ab Werk `node-metadata-write`)
  ohne `repo_schreibt` (`auftrag_repo_schreibt`). Antwortet der MCP `not_allowed`, liest die
  Person `auftragNichtErlaubt` (Frage der Einrichtung) vor dem Ersatzweg; der Direktweg bleibt
  dabei unverändert. Studio-Hinweis `feld.Schritt.repo_schreibt.hint` (de/en): nur angekreuzte
  Schritte startet der MCP, der Flow muss dort auch in `WLO_BAPI_FLOWS` stehen.
  `METADATEN_FLOW` liegt jetzt in `domain/config_models/kestra_flows.py` (`zug_basis` führt den
  Namen weiter).
- **A5 (MINOR) Ausgang `weiter`.** „Neues Vorhaben“ und „Arbeitsstand löschen“ hängen auch bei
  `weiter` einen Satz an (`action.vorgang.auftragLaeuftWeiter`). Ersetzt ein Start einen Lauf
  samt Auftrag (`zug.starten_mit`, `_ziel_vorbereiten`), geht der Ausgang nicht mehr verloren: der
  Satz zu `offen` bzw. `weiter` steht vor der Antwort (`zug_basis.auftrag_satz`).
- **A6 (MINOR) `isError` ohne Code nach dem Bestätigen** gilt als `offen` (kein neuer Start).
  Ausgenommen bleibt das „unbekannte Werkzeug“ (vorübergehend). Bei der Vorschau bleibt es
  `fehler` (ohne Schlüssel startet nichts).
- **A8 (NIT)** `auftrag_zug.abrufbar` verlangt auch für eine offene Kennung `has_personal_auth()`.
- **A9 (NIT)** `zug_basis._wlo_erschliessen` heißt `wlo_erschliessen`; `dienst_upload` und
  die Tests rufen den öffentlichen Namen.

### Review B (Flow, Warten, Oberfläche)

- **B1 (MAJOR) Start-Knopf beendet einen wartenden Lauf nicht still.** Wartet der Lauf auf einen
  Auftrag (nach „Später weitermachen“ oder bei `warten: frei`), fragt `zug.starten` auch beim
  gewöhnlichen Start-Knopf erst nach (`_ersetzen_fragen`: „Neu starten“ oder „Stand prüfen“).
- **B2 (MINOR)** Neuer Satz `auftragSpaeter` (siehe K7), Notiz zur Rückkehr korrigiert.
- **B3 (MINOR)** Die Marke der ruhenden Sperre trägt den Teil eines Stapels; der Verweis der
  Sitzung führt ihn (`lauf.teil`, nur ab Teil 2). Teil 2 ist in einer Sitzung, die bei Teil 1
  „Später“ wählte, wieder gesperrt.
- **B4 (MINOR, Entscheid)** Seed `06-ablaeufe/themenbaum.yaml`, Schritt `metadaten`:
  `warten: gesperrt` (E16).
- **B5 (MINOR)** Satz an die KI bei `volltext_fehlt_datei`: „in ein paar Minuten einfach
  „nochmal“ schreiben“.
- **B6 (MINOR)** `/api/ui/auftrag/stand` mit Antwortmodell `StandAntwort`
  (`stand: laeuft|fertig|fehler`, `fertig`/`gesamt: int|None`, `ge=0`,
  `response_model_exclude_none`). OpenAPI neu erzeugt: inhaltlich ändert sich nur dieser Pfad
  (ein Schema mehr, die öffentliche Spezifikation bleibt gleich). `bewusste-vertragszusaetze.md`
  nennt die K6-Felder.
- **B7 (NIT)** `auftrag_spaeter.datum`: nie ein Tag vor heute.
- **B8 (NIT)** Studio-Hinweis `feld.Schritt.warten.hint`: „Später weitermachen“ hebt die Sperre
  für diese Sitzung auf, „Stand prüfen“ setzt sie wieder.
- **B9 (NIT)** Seed `metadaten_frage`: „… auch für Strukturdokumente (falls dabei)?“.
- **B10 (NIT)** `auftrag_zug.pruefen`: Schleife statt List-Comprehension mit Nebenwirkung.

### Tests (Review)

- Neu: `tests/test_paket_k_review.py` (A1–A9, B2–B5, B7, B9), `tests/test_paket_k_review_api.py`
  (A1 über `/stand`, B6).
- Ergänzt: `test_paket_k7_spaeter.py` (B1, auch mit `warten: frei`; Satz B2).
- Angepasst (altes Soll): `test_paket_k_traeger.py` (Matrix mit `repo_schreibt`, Starter je
  Schritt), `test_paket_k_zug.py` (der MCP trägt dort jetzt einen Schritt mit `repo_schreibt`),
  `test_tg6_review.py` (A9), `test_paket_d_auftrag.py`, `test_paket_d_review.py` und
  `test_tg7_durchtest.py` (Starter je Schritt, neuer Satz A3), `test_ablauf_auftrag.py` und
  `test_querschnitt_ablaeufe.py` (B1: ein zweiter Start fragt erst, dann „Neu starten“ —
  Hilfsfunktion `_neu_starten`).
- Studio: `fields-ablaeufe.spec.ts` (B8, A4).

### Zweites Review behoben (19.11.)

0 MAJOR, 4 MINOR, 3 NIT — alle behoben, je Test zuerst (`test_paket_k_review.py`, Abschnitt
„Zweites Review“):
- **Z1:** `EDU_USER_REQUIRED` auf dem Direktweg hat einen eigenen Satz
  (`auftragAbgelehntDirekt`: geht nur über den WLO-Dienst mit Anmeldung); über den MCP bleibt
  `auftragAbgelehntPerson`.
- **Z2:** Ein offener Start ab Teil 2 eines Stapels sagt `auftragOffen` wie der erste Teil
  (`treiber._naechster_teil`). „Stand prüfen“ eines offenen Teils mit Folgeteil sagt
  `auftragTeilUnklar` („Teil k unklar, weiter mit Teil k+1“), sonst `auftragOffenGelesen`
  (`auftrag_zug.stand_weg_satz`).
- **Z3:** `auftragStandWeg` (de/en) ehrlich: bei `unknown_job` können Teile noch fehlen, dann
  später noch einmal lesen. Der Weg (weiter zu `lesen`, E17) bleibt.
- **Z4:** 429 beim Start über den MCP ohne offenen Ausgang (`voll`) führt zurück an die Rückfrage
  mit `auftragVoll` („in etwa N Minuten“ aus `retryAfter`, sonst `auftragVollOhneZeit`).
  `outcomeOpen: true` bleibt offen. Der Direktweg ist unverändert.
- **Z5:** `auftragNichtErlaubt` neutral („hier nicht freigegeben – Frage der Einrichtung“).
- **Z6:** `test_tg6_review::test_minor8…` misst jetzt über `_Wahl` mit gestubbtem `traeger`.
- **Z7:** Auch nach „unbekanntes Werkzeug“ holt der Starter die Fähigkeiten nur im Takt
  `TAKT_NACH_FEHLER_S`, über das neue `faehigkeiten.nachfragen` — dessen Fehlschläge zählen nicht
  zu `_fehlversuche`, verwerfen also nie alle Fähigkeiten (das bleibt dem Takt).

### Deploy (Nachtrag zum Review)

- Keine Migration, keine neue Variable.
- **B4: die Fassung des Seeds „Themenbaum erstellen“ ändert sich.** Läufe dieses Ablaufs, die
  beim Werksabgleich laufen oder warten, brechen ab (`treiber.gilt`: andere Fassung) — auch ein
  Lauf, der gerade auf den Metadaten-Flow wartet. Werksabgleich deshalb in einer ruhigen Zeit;
  der Flow selbst läuft beim MCP zu Ende, seine Ergebnisse stehen an den Datensätzen.
- **A4: jeder schreibende Flow braucht `repo_schreibt` am Schritt und beim MCP einen Eintrag in
  `WLO_BAPI_FLOWS`** (ab Werk nur `node-metadata-write`, auf Staging nichts zu setzen). Eigene
  Abläufe mit einem Auftragsschritt ohne `repo_schreibt` laufen jetzt über den Direktweg der b-api
  (nur mit `darf_jobs()`), nicht mehr über den MCP — die Prüfung meldet den Metadaten-Flow ohne
  Vermerk.
- Das Studio-Bündel muss neu gebaut werden (Hinweise). Widget und `ui-fortschritt` ändern sich
  durch das Review nicht.

## Durchtest-Befunde behoben (19.11.)

Je Punkt erst der Test (rot gesehen), dann der Fix. Tests: `tests/test_paket_k_durchtest.py`, dazu
die genannten Ergänzungen. Angepasst (altes Soll): `test_ablauf_auftrag::test_stand_pruefen_fehler_…`
(Satz zu Punkt 2 vor dem Ersatzweg), `test_tg2_bereit_und_verwirft` (Feld `ohne_gruendlich`),
`test_paket_k_mcp_starter` (Punkt 3), `test_ablauf_pg` (Punkt 9).

1. **md/txt nicht an den Metadaten-Flow (Entscheid).** `auftrag_teile.ohne_textdateien` nimmt für
   `METADATEN_FLOW` die Knoten aus `node_ids`, die die Ablage mit der Endung `md`, `markdown` oder
   `txt` führt (`art` oder Endung des Dateinamens; Liste `METADATEN_FLOW_OHNE`, kommentiert mit
   Verweis auf diesen Durchtest). Gefiltert wird beim Bilden der Argumente im Treiber
   (`_auftrag_stuecke`), vor dem Aufteilen — der Stapel friert die gefilterte Liste ein. Fiel etwas
   weg, steht `action.ablauf.metadatenOhneText` („Für Markdown- und Textdateien kann WLO gerade
   keine Angaben erzeugen.“) vor dem Start; bleibt nichts, startet nichts (leere Auswahl) und der
   Ablauf nimmt `bei_fehler` (`ohne_metadaten`) mit diesem Satz davor. Andere Flows bekommen md
   weiter. Strukturdokumente in md bleiben nutzbar: ihren Volltext liest der MCP selbst. Eintrag in
   `offene-befunde-und-todo.md` §1 (an Flow-Autor/MCP gemeldet).
2. **Gescheiterter Flow mit eigenem Satz.** `auftrag_zug.pruefen` setzt bei `Stand("fehler")` vom
   Träger `action.ablauf.auftragFehlgeschlagen` („Die Erschließung in WLO ist fehlgeschlagen
   (FLOW_FAILED). Du kannst ohne die Angaben weitermachen.“, de/en) vor den Ersatzweg. Der Code nur
   aus `FEHLERCODES` (`TIMEOUT`, `FLOW_FAILED`), sonst ohne Klammer. `treiber.weiter_auftrag` nimmt
   den Satz als `fehlschlag` und setzt ihn nur, wenn der Lauf `bei_fehler` wirklich nimmt (nicht ohne
   Ersatzweg, nicht bei einem Teilerfolg im Stapel). Ein Stand aus einem endgültigen Grund des
   Clients (Auftrag weg, Aufträge aus) bleibt ohne den Satz.
3. **„k von n fertig“ ohne Fehlschläge.** `mcp_starter._fortschritt`: `fertig` = gelungen + mit
   Warnung, gescheiterte getrennt als `fehlgeschlagen` (nur > 0). Chat: „… 3 von 5 sind fertig,
   1 fehlgeschlagen …“ (`auftragLaeuftFortschrittFehler`). `POST /api/ui/auftrag/stand`: neues
   optionales Feld `fehlgeschlagen` in `StandAntwort` (≥ 1, mit `fertig` höchstens `gesamt`, sonst
   fällt nur es weg) — additiv, kein Vertragsbruch; OpenAPI neu erzeugt (nur dieses Schema,
   öffentliche Spezifikation unverändert), `bewusste-vertragszusaetze.md` ergänzt. Widget
   `ChatApiClient.auftragStand` reicht es als ganze Zahl weiter; `ui_fortschritt` zeigt
   „2 von 5 fertig, 1 fehlgeschlagen“ bzw. „2 of 5 done, 1 failed“, der Balken zeigt das
   Abgearbeitete (fertig + fehlgeschlagen). Ein altes Widget oder Modul ignoriert das Feld.
   Specs: `fortschritt-ablauf.spec.ts`, `ui-fortschritt.element.spec.ts`, `chat-api-auftrag.spec.ts`;
   Tests `test_paket_k6_fortschritt.py` (ergänzt), `test_paket_k_mcp_starter.py` (altes Soll 3/4 →
   2/4 + 1 fehlgeschlagen).
4. **Wendung an einer wartenden Frage.** Ursache bestätigt: Die Übernahme des jüngsten offenen
   Vorgangs in einer neuen Sitzung (`arbeitsstand.auffrischen`, Review V1) ist gewollt; der Fehler
   war, dass jeder getippte Text an einer Frage mit `freitext` still Antwort wurde (der Preflight
   prüft Wendungen nur ohne wartenden Lauf, A2a). Jetzt prüft `wendung_trifft` (seit dem dritten Review in `wendung_zug`) vor dem
   Freitext: trifft der Text eine Wendung (`ausloeser.per_text`) und ist keine Beschriftung bzw. kein
   Synonym der Frage, antwortet `wendung_beantworten` ohne zu speichern — derselbe Ablauf:
   „Du bist schon mitten in „Themenbaum erstellen“ – hier geht es weiter.“ (`schonMitten`) und die
   offene Frage mit ihren Chips; ein anderer Ablauf (nur mit erfüllten Voraussetzungen, nicht der eben
   abgelehnte): die vorhandene Ersetzen-Rückfrage (`zug.ersetzen_fragen`). Gilt an jeder wartenden
   Frage; bei einer Krise geht der Zug wie beim Freitext den gewöhnlichen Weg. Tests auch in
   `test_preflight_node.py` (zwei neue).
5. **Abbruch: Plan angeglichen.** E16 im Plan sagt jetzt: Abbrechen beendet den Lauf, mit „Neues
   Vorhaben“ und „Arbeitsstand löschen“. Der Code bleibt.
6. **Ohne Anmeldung nennt `schnell` den Grund.** Der Dienst `bereitgestellt` liefert
   `ohne_gruendlich`: ohne Anmeldung `gruendlichNurAngemeldet` („„Gründlich über WLO“ geht nur mit
   einer WLO-Anmeldung – dann erschließt WLO die Inhalte deiner Dateien.“), angemeldet ohne Dienst
   `gruendlichNichtDa`; geht der gründliche Weg, `None`. Dafür kennt `DienstKontext` bzw. die
   Treiber-Umgebung `angemeldet` (Zug: `has_personal_auth`, Simulation: die Anmeldung des
   Testfalls). Seed `schnell` setzt `{teil.bereit.ohne_gruendlich}` ein — kein neuer Schritt (weiter
   40). `pruefe`, `warnungen` und Seed-Selbsttests ohne Befund.
7. **NIT Leiste — abgelehnt.** Gemessen: an `metadaten` mit 6 Halten „6 von 14“, nach dem Sprung
   „7 von 15“. `m` = `n` − 1 + die meisten Halte ab hier über reguläre Kanten; `ohne_metadaten` ist
   ein zusätzlicher Halt hinter `bei_fehler`, der im regulären Weg nicht vorkommt. Die Leistentests
   verlangen beides, was den Sprung erzwingt: `n` steigt je Halt um genau 1 (`leiste_halte.ohne_sprung`,
   `test_tg2_bereit_und_verwirft`, `test_tg6_themenbaum`), und `bei_fehler` zählt für `m` nicht
   (`test_ablauf_leiste::test_rueckwege_und_bei_fehler_zaehlen_nicht`). `m` gleich zu halten hieße,
   eine neue Frage mit derselben Nummer zu zeigen oder jeden möglichen Ersatzweg in `m`
   einzurechnen. Der Sprung zeigt ehrlich einen zusätzlichen Halt.
8. **Platzhalter-Thema.** `strukturentwurf_dienst.platzhalter_thema`: ein Thema mit einem Wort, das
   nur auf die Dateien der Person zeigt („Dateien“, „bereitgestellt…“, „Inhalte“, „Materialien“,
   „Person“ …), und sonst nur Füllwörtern ist ein Platzhalter. Bei `aus_inhalten` nimmt
   `ui_module/dienst._strukturentwurf` dann den Titel des Entwurfs als Thema.
9. **`test_ablauf_pg::test_vorgaenge_der_person_bleiben_unter_der_grenze`** (rot seit Review B1):
   kein Code-Fehler — ein Start bei `wartet_auftrag` fragt jetzt erst nach. Der Test (und
   `test_verdraengte_vorgaenge_nehmen_ihre_auftraege_mit`, der sonst still nichts mehr prüfte)
   bestätigt jeden Ersatz mit „Neu starten“ (`_starten_bestaetigt`, wie `_neu_starten`).

**Deploy:** keine Migration, keine neue Variable. Die Fassung des Seeds „Themenbaum erstellen“
ändert sich (Text `schnell`) — wie bei B4 brechen laufende oder wartende Läufe dieses Ablaufs beim
Werksabgleich ab. Das Modul-Bündel `ui-fortschritt` und das Widget müssen neu gebaut werden.

## Drittes Review behoben (19.11.)

1 MAJOR, 5 MINOR, 3 NIT — je Test zuerst (rot gesehen). Tests: `test_paket_k_durchtest.py`
(Abschnitt „Drittes Review“), dazu die genannten.

1. **MAJOR — Wendung als Teilwort.** `ausloeser.per_text` sucht Teilzeichenketten; an einer
   offenen Frage galt so „Virtueller Stadtrundgang durch Rom“ als Wendung „rundgang“, und die
   Antwort wurde nie gespeichert. Jetzt (Entscheid): `ausloeser.per_text_genau` — die Nachricht ist
   im Wesentlichen die Wendung: gleich, oder vorn die Wendung und danach höchstens 3 Wörter, oder
   die Wendung als ganze Wörter darin und höchstens 15 Zeichen länger (`woerter`, Wortgrenzen; ein
   Teilwort trifft nie). Derselbe Text an derselben Frage ein zweites Mal ist die Antwort (Marke
   `_ablauf_wendung_an_frage` aus Vorgang, Schritt und Prüfwert, nie der Text). Die Ersetzen-
   Rückfrage bei einem fremden Ablauf hat zusätzlich „Hier weitermachen“ (Wahl `_hier` der
   Direktaktion `ablauf_wahl`, zeigt die offene Frage mit ihren Chips); wer sie übergeht, hat den
   fremden Ablauf abgelehnt (`ausstieg_merken`). Die Logik liegt jetzt in
   `services/ablauf/wendung_zug.py` (aus `wahl_zug` gelöst, das sonst über 330 Zeilen wuchs).
   Regressionen: alle drei Beispiele. „Themenbaum zu einem Thema für Klasse 7“ hat genau 3 Wörter
   nach der Wendung — es gilt nach der Regel beim ersten Mal als Wendung, beim zweiten Mal ist es
   die Antwort (Test). Mit 4 Wörtern danach („… für die Klassen 7 und 8“) ist es sofort Freitext.
2. **„Neu starten“ beim selben Ablauf.** Unter den Chips der Frage steht `zug.neu_starten_knopf`
   (gebunden an den Lauf wie in `_ersetzen_fragen`); `schonMitten` endet mit „– oder „Neu
   starten“.“ (de/en).
3. **`ohne_metadaten` neutral:** „Die Angaben aus WLO ließen sich gerade nicht erzeugen oder lesen.
   Wie soll es weitergehen?“ (de/en) — den Grund nennt der Satz davor. `pruefe`, `warnungen` und
   die 20 Seed-Selbsttests ohne Befund, 40 Schritte.
4. **„Nur mit Anmeldung“ nur, wenn sie hilft.** `DienstKontext.nach_anmeldung` (statt
   `angemeldet`) = `zug_basis.gruendlich_nach_anmeldung`: das Upload-Feld böte die Ablage nach der
   Anmeldung an (`ablage_nach_anmeldung`), der MCP führt die Flow-Werkzeuge, der Metadaten-Flow ist
   freigegeben. Sonst `gruendlichNichtDa`. Simulation: hilft, wenn der Testfall nicht angemeldet
   ist. Angepasst: `test_tg2_bereit_und_verwirft` (ohne Angabe jetzt `gruendlichNichtDa`).
5. **`auftragFehlgeschlagen` neutral:** „Der Auftrag in WLO ist fehlgeschlagen (FLOW_FAILED).“ /
   „The job in WLO failed (FLOW_FAILED).“ — `test_ablauf_auftrag` liest den Satz über `bot_text`.
6. **`test_ablauf_pg::test_verdraengte_vorgaenge_nehmen_ihre_auftraege_mit`** erzwingt jetzt, dass
   ein Vorgang mit Auftrag wirklich verdrängt wurde (Vorgänge mit Auftrag nach jedem `lesen` aus
   `vorgang_auftraege` gemerkt, am Ende mindestens einer nicht mehr in `vorgaenge`). pg-Test, nicht
   während der Suite gelaufen.
7. **NIT — abgelehnt.** Den Satz `metadatenOhneText` schon an `metadaten_frage` zu nennen geht
   ohne neuen Schritt nicht: Platzhalter setzen immer einen Wert ein (ein fehlender wird „—“), es
   gibt keinen bedingten Text; `bereit` entsteht beim Start, vor dem Upload, kennt die Ablage also
   nicht; eine Verzweigung vor der Frage wäre der 41. Schritt. Der Satz steht weiter vor dem
   Ersatzweg, sobald „Ja“ gewählt ist.
8. **NIT:** `<progress>` trägt `aria-valuetext` = der Standtext (Spec in
   `ui-fortschritt.element.spec.ts`).
9. **NIT:** Eine Prüfung der Zahlen für Chat und API: `client.fortschritt_zahlen` (vorher
   `ui_auftrag._zahlen`); der Chat-Satz nennt `fehlgeschlagen` nur, wenn fertig + fehlgeschlagen
   ≤ gesamt, und ohne gültige Zahlen den Satz ohne Zahlen.

**Deploy:** wie oben; die Seed-Fassung ändert sich erneut (Text `ohne_metadaten`).

## Offen

- Freigabe-Box mit der Vorschau des MCP (Entscheid 1).
- Weg „Dokument“ mit Übertragung nach WLO ohne Metadaten-Flow (Abweichung 2).
- Ein Teil eines Stapels, dessen Start „nicht verfügbar“ meldet, zählt wie bisher als nicht
  gestartet. Nur der erste Teil führt zurück an die Rückfrage.
- Ticket-Anmeldungen am Proxy sind ungemessen. Beim Durchtest mit einem Ticket-Block prüfen.

## Durchtest gegen Staging (19.11.)

Lokales Backend (Staging-Kopie) auf Port 8107 gegen die Wegwerf-DB `boerdi_durchtest_k`, LLM nativ
`gpt-6-luna`, Master-Skill lokal (`vorgehen-knapp.md`), Staging-MCP `wlo-mcp…nip.io` (1.4.0, führt
`wlo_start_flow`/`wlo_flow_status`/`wlo_cancel_flow`/`wlo_list_flows`), Repository Staging,
Testkonto über Sitzungs-Tausch (`WLO-Access-Block`). API-Ebene wie das Widget, nicht im Browser.
Skripte `*_k.py`, Protokolle `lauf_k_*.log` und `backend_k.log` im Scratchpad unter `tg7/`.

| Fall | Ergebnis | Beleg |
|---|---|---|
| 1 Dateien → gründlich/WLO, 2 md-Inhalte + md-Lehrplan (Rolle `struktur`) | **fehlgeschlagen (außerhalb des Chatbots)** | Ablage 3 × `stored` (14 s), Rückfrage, Start über den MCP (3,6 s), Sperre + „Stand prüfen“/„Später weitermachen“/„Auftrag abbrechen“, `ui_fortschritt` mit Kürzel. Der Flow endet nach ~3 s `FAILED`, `errorCode FLOW_FAILED`, `progress` 3/3 gelungen, keine `outputs`; `/stand` → `{"stand":"fehler","fertig":3,"gesamt":3}`. Metadaten an den 3 Knoten unverändert. Ursache vermutlich: `textContent` der md-Knoten bleibt `null` (der MCP liest den Text über `get_wlo_content_text`, der Flow nicht). |
| 1c Kontrolle: 1 Text-PDF, gleicher Weg | ok | Flow 16 s: `/stand` `laeuft` → `fertig` 1/1; „Stand prüfen“ → „1 Materialien erschlossen, 0 nicht.“; `metadaten_lesen`: Titel „Der Aufbau des Laubblatts …“, Beschreibung, 8 Schlagworte, Fach Biologie, Sek I; Knoten lesend geprüft: Titel, Beschreibung, Schlagworte, Fach, Stufe, Sprache, Typ, Zielgruppe geändert (neue Version). Entwurf: Fach Biologie, Stufe Sek I, 2 Punkte; Thema Platzhalter (r2-1 besteht). |
| 1 Vorbelegung aus dem Strukturdokument (K5) | nicht prüfbar | Der md-Lehrplan bekam wegen FLOW_FAILED keine Metadaten; `_aus_strukturdokumenten` → `{}`. |
| 2 Später weitermachen, Rückkehr | ok | „Später“: Sperre fällt, Satz mit Frist „bis 26.11.2026“, nur „Stand prüfen“, Lauf bleibt `wartet_auftrag`. Start-Knopf `ablauf_starten` → Rückfrage „Neu starten / Stand prüfen“, Lauf unverändert. „Stand prüfen“ holte ab (Flow schon gescheitert) → `ohne_metadaten`. Sperre nach „Stand prüfen“ bei laufendem Job nicht beobachtbar (Job war nach 5 s beendet). |
| 3 Abbruch (1 Text-PDF) | ok | 5,4 s nach dem Start „Auftrag abbrechen“ → Rückfrage → „Der Auftrag ist abgebrochen, der Ablauf endet hier.“, Chips „Neues Vorhaben“/„Arbeitsstand löschen“. Beim MCP `cancelled`; `/stand` danach 409 `kein_auftrag`; Knoten 60 s später unverändert. |
| 4 Ohne Anmeldung | teilweise | Kein „Gründlich“, Schalter `ablage_in_wlo: false`, `ablage_nach_anmeldung: true`; Ablage anonym 403 `nur_angemeldet`, `/stand` 403, 0 Aufträge. Der Chat-Satz nennt die Anmeldung als Grund nicht. |
| 5 Log und DB | ok | `backend_k.log`: 0 × jobId (roh), 0 × `confirmToken`, 0 × Block/Passwort/Cookie/Schlüssel, 0 × `Bearer`. Im DB-Abzug steht die jobId nur in `vorgang_auftraege.job_id`. |

**Befunde:**
- **MAJOR (Flow/Repository, nicht Chatbot):** `node-metadata-write` scheitert für Markdown (FLOW_FAILED,
  nichts geschrieben); PDFs gehen. Damit fallen md-Strukturdokumente (E14/K5) und md-Inhalte aus.
  An Flow-Autor bzw. MCP melden (Text über `/content` wie `get_wlo_content_text`, oder Status je Knoten
  `NO_TEXT` statt FLOW_FAILED liefern).
- **MINOR:** Ein gescheiterter Flow führt ohne eigenen Satz zu `ohne_metadaten` („nicht eingerichtet …
  Anmeldung abgelaufen“) — falsch, der Flow lief. `Stand.fehlercode` wird nicht genutzt
  (`services/ablauf/auftrag_zug.py:500`, `services/ablauf/treiber.py:986`).
- **MINOR:** `/api/ui/auftrag/stand` meldet bei `fehler` „3 von 3 fertig“ (`services/auftraege/mcp_starter.py:257`
  zählt `failed` mit, `progress` zählt Iterationen); das Modul zeigt Zahlen neben dem Fehler.
- **MINOR:** Angemeldet, neue Sitzung: die getippte Wendung „Themenbaum aus meinen Dateien“ landete als
  Freitext-Antwort `zweck` im offenen Lauf einer anderen Sitzung (Frage `wofuer`), statt neu zu starten
  (nachgestellt mit `fall1b_k.py`, danach eine neue Sitzung mit der Wendung).
- **MINOR:** Plan E16 sieht nach „Abbrechen“ `ohne_metadaten` vor; der Code beendet den Lauf
  (`auftrag_zug.abbrechen`). Entscheid bestätigen oder Plan angleichen.
- **MINOR:** Ohne Anmeldung sagt `schnell` (`seeds/06-ablaeufe/themenbaum.yaml:213`) nicht, dass der
  gründliche Weg eine Anmeldung braucht.
- **NIT:** Leiste: `von` steigt beim Sprung nach `ohne_metadaten` (14 → 15, `services/ablauf/fortschritt.py:279`).
- **NIT:** r2-1 besteht live: Thema „Themen aus den bereitgestellten eigenen Dateien“.

**Aufgeräumt:** 8 eigene Knoten (5 Dateien `boerdi-durchtest-1911-*` — 3 md, 2 PDF — und 3
`vorgang*.json`; kein Vorgangsordner, Layout `flach`) in den Papierkorb des Testkontos
(`DELETE …?recycle=true`, je 200); persönlicher Bereich wieder 13 Knoten wie vorher. Server gestoppt,
Wegwerf-DB gelöscht, andere Container und Dev-DB unberührt. Abweichung: 8 statt etwa 6 Knoten — die
PDF-Kontrolle (1c) war nötig, um den md-Fehlschlag einzuordnen.
