# Paket AS-8a — Probe der Studio-Vorschau mit Trockenlauf (Backend, 2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5n (Entscheide P-1 … P-8).

## Was sich ändert

- **Erkennung (P-1):** `ChatRequest.probe` (Vorgabe `false`). Es gilt nur mit gültigem
  Studio-Cookie (`api/probe_anfrage.probe_erlaubt`, über `studio_auth.authorize_request`, ein
  falsches Cookie zählt als Fehlversuch). Ohne Recht weist der Endpunkt den Zug ab (403 `probe_ohne_recht`, Review Befund 3).
- **Zug-Merker (P-2):** neues Modul `services/probe.py`.
  - Der Endpunkt baut den Zug über `chat.turn_kontext` (`TurnContext.probe`).
  - `begin_turn` bindet den Merker als geteiltes Objekt, samt Sprache.
  - `setup` gleicht ihn mit der Sitzung ab: Eine erkannte Probe kommt als `entities._probe` an die
    Sitzung und wird sofort festgeschrieben, eine gemerkte hebt den Merker. Die Probe klebt also.
- **MCP (P-3):** `call_mcp_tool_antwort` ruft in der Probe kein schreibendes Werkzeug.
  - Schreibend heißt: `wlo_…` außer den lesenden; erlaubt bleibt nur die Vorschau eines
    bestätigbaren Werkzeugs ohne Schlüssel.
  - Die Antwort lautet „Trockenlauf: Hier wäre jetzt … gelaufen — geschrieben wurde nichts.“ (de/en),
    strukturiert `{trockenlauf, werkzeug, complete: true}`, damit kein „Plan fortsetzen“ folgt.
  - Ohne Aufruf entsteht kein `preparedRequest`.
- **Ablage (P-4):** `api/ui_ablage` antwortet in einer Probe-Sitzung vor jedem Aufruf mit 409
  `trockenlauf`.
- **Aufträge (P-5):**
  - `auftrag_zug.starter()` gibt in der Probe einen Trocken-Starter zurück; er braucht weder b-api
    noch Schlüssel, die WLO-Anmeldung aber wie im Betrieb (Querschnitts-Review AS-8, Befund 3).
  - Die Kennung lautet `trocken-<16 hex>`.
  - `client.stand` meldet sie sofort `fertig` ohne Ausgaben, `abbrechen` meldet `abgebrochen`,
    `datei` und der Hintergrund-Abbruch fassen die b-api nicht an.
- **Ausgeschaltete Abläufe (P-6):**
  - `treiber.gilt(ablauf, lauf)` ersetzt fünfzehn gleiche Bedingungen („Ablauf da, aktiv, Fassung
    gleich“) in `services/ablauf/*` und `api/ui_auftrag.py`.
  - Ein Lauf mit `probe: true` (gesetzt aus `Umgebung.probe`) gilt auch bei `aktiv: false`.
- **Start (P-7):** In der Probe startet `ablauf_starten` jeden Ablauf des Katalogs, wie von der
  Gastseite und mit Startdaten nach dessen Startschema. Die Prüfung der Daten bleibt.
- **Anmeldung (P-8):** Voraussetzung `anmeldung` und Freigaben bleiben wie im Betrieb.

## Tests

- Neu `tests/test_probe.py` (35 Fälle):
  - Erkennung mit und ohne Cookie;
  - Merker und klebende Sitzung;
  - welche Aufrufe trocken laufen, und dass dabei kein Transport stattfindet;
  - Trocken-Aufträge ohne b-api;
  - `gilt`, die Marke am Lauf, der Start ausgeschalteter Abläufe mit Startdaten;
  - die Verdrahtung Endpunkt → `begin_turn` → `setup`.
- `tests/test_ui_ablage_api.py`: Probe-Sitzung → 409 `trockenlauf` an allen drei Endpunkten,
  ohne MCP-Aufruf.

**Volle Backend-Suite:** 9709 grün, 3 rot.
- Zwei gingen auf dieses Paket zurück und sind behoben:
  - Der neue Code `trockenlauf` fehlte in der Liste von `test_i18n_messages`.
  - Ein Test band über `begin_turn` die Zugakte im Testkontext, er läuft jetzt in einer Kopie.
- Der dritte (`test_anmeldung_status::…_bis_zur_frist`, `60,0000002 <= 60`) ist eine vorbestehende
  Uhren-Ungenauigkeit, eingetragen in `offene-befunde-und-todo.md`.
- Danach liefen die betroffenen Dateien erneut: 107 grün. ruff ist sauber.

## Review und Behebung

Das unabhängige Review fand 0 kritische, 4 schwere, 3 mittlere und 1 kleinen Befund. Alle wurden am
Code bestätigt und behoben, je mit einem Test, der vorher rot war (außer Befund 4a und 7, siehe
dort).

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | schwer | Probe- und echte Vorgänge vermischten sich bei angemeldeten Personen: Dieselbe Kennung holte in der Probe den jüngsten echten Vorgang (und führte ihn trocken weiter oder brach seinen Auftrag ab); ein Probe-Lauf eines ausgeschalteten Ablaufs tauchte in echten Sitzungen auf. | `arbeitsstand.aufrufer_fuer` gibt in der Probe `probe:<Sitzung>` zurück; die Endpunkte außerhalb des Graphen geben ihre Entities mit (`chat._ablauf_stand`, `sessions`, `ui_auftrag`). „Meine Vorgänge“ (`ui_vorgaenge`: offen, liste, wiederkehr, loeschen) antwortet in einer Probe-Sitzung 409 `trockenlauf`, damit „Fortsetzen“ kein echtes Gespräch zur Probe macht. Tests in beide Richtungen. |
| 2 | schwer | Ein Trocken-Auftrag ohne durchgereichten Schlüssel hing: „Stand prüfen“ und `/api/ui/auftrag/stand` verlangten Schlüssel und Anmeldung, bevor der Client antworten konnte. | Für `trocken-…` entfallen beide Bedingungen; echte Kennungen brauchen sie weiter. Tests über `auftrag_zug.pruefen` und den Endpunkt. |
| 3 | schwer | Eine Probe ohne Recht (abgelaufenes Cookie, gedrehtes Passwort, Sperre) lief still als echter Zug — mit echten Freigaben und Aufträgen. | `probe_anfrage.pruefe_probe` im Vorspann beider Chat-Endpunkte: 403 `probe_ohne_recht`, nie ein echter Zug. |
| 4 | schwer | `entities._probe` ließ sich über die Ausgabe des Klassifikators setzen (`merge` übernahm `_`-Schlüssel) — ohne Cookie gab das die erweiterten Rechte der Probe. | (a) `merge` verwirft `_`-Schlüssel aus der Klassifikator-Ausgabe (schützt auch die übrigen Merkposten, vorbestehend). (b) Der Merker trennt `aktiv` (schränkt ein, auch aus der Marke) von `recht` (erweitert, nur mit dem Cookie dieses Zuges); Start ausgeschalteter Abläufe und Startdaten ohne Auslöser hängen an `recht`. Der Test zu (a) entstand nach der Behebung (TDD-Fehler, ehrlich vermerkt). |
| 5 | mittel | Der Trocken-Starter übersprang die Freischaltung des Flows. | Ist die b-api eingerichtet, scheitert ein nicht freigeschalteter Flow wie im Betrieb (`bei_fehler`); ohne Einrichtung bleibt die Probe möglich. |
| 6 | mittel | Abbrechen eines Trocken-Auftrags ohne Schlüssel sagte „läuft bei der b-api weiter“. | Für `trocken-…` der Text „abgebrochen“. |
| 7 | mittel | Testlücken auf den tragenden Wegen. | Ergänzt: Einlösen einer Plan-Freigabe in der Probe Ende zu Ende (kein Transport, kein „Plan fortsetzen“, kein `preparedRequest`), Stand-Abruf, Vorgangs-Übertrag, Fail-closed. Ein Endpunkt-Test gegen die echte DB fehlt weiter; die Verdrahtung prüfen `turn_kontext`, `begin_turn`, `setup` und die Reihenfolge im Vorspann. |
| 8 | klein | Plan nannte „zehn Prüfungen“ und `ui_auftrag` ohne Marke. | Plan §5n nachgezogen. |

## Zweites Review

Wegen vier schwerer Befunde lief ein zweites, unabhängiges Review. Es bestätigte die Behebungen 1–8
am Code und fand 0 kritische, 2 schwere, 2 mittlere und 1 kleinen Befund. Alle sind behoben, je
mit einem Test, der vorher rot war.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| Z1 | schwer | Der Verweis in der Sitzung trug die Marke `probe` nicht. Sechs Stellen lesen den Lauf aus dem Verweis (Leiste, „Stand prüfen“-Knöpfe, KI-Schritt, Ankunft an einem Seitenschritt, getippte Wahl) — für einen ausgeschalteten Ablauf in der Probe galt der Lauf dort nicht mehr. | `verweis_fuer` übernimmt `probe: true` als Wahrheitswert (nicht über `zeile`, das machte Text daraus). Test: ausgeschalteter Ablauf in der Probe, danach `fortschritt.stand` und `seite_zug.wartend`. |
| Z2 | schwer | `persoenlich` war für `probe:<Sitzung>` wahr; das Widget blendet dann die Leiste ohne Zugangsblock aus. | `arbeitsstand.ist_persoenlich` (neben `aufrufer_fuer`): `sitzung:` und `probe:` sind nicht persönlich. |
| Z3 | mittel | Das Recht wurde zweimal geprüft (Vorspann und `turn_kontext`); dazwischen liegen Handschlag und Sitzungssperre — ging das Recht verloren, lief der Zug still echt. | Einmal entscheiden: `pruefe_probe` gibt die Entscheidung zurück, `turn_kontext(req, probe)` und `_stream_turn(…, probe=…)` übernehmen sie. |
| Z4 | mittel | Vorgänge `probe:<Sitzung>` überlebten das Löschen der Sitzung, „Alles löschen“ und den Waisen-Lauf. | Alle drei Löschregeln nehmen `probe:` mit. Test gegen Postgres. |
| Z5 | klein | Notiz und Docstring sagten noch „ohne Cookie wirkungslos“. | Angeglichen. |

**Nach dem zweiten Review:** Regression über alle berührten Bereiche (`test_ablauf_*`,
`test_vorgaeng*`, `test_chat*`, `test_sessions*`, `test_kanarienvogel_logs`, SSE/Strom,
`test_arbeitsstand*`, `test_ui_*`, Probe, Merge, Setup, Graph, i18n, OpenAPI-Vertrag): 1708 grün.
Davor die volle Suite nach dem ersten Review: 9733 grün, 2 rot, beide allein grün und ohne Bezug zur
Probe (Kippler, eingetragen in `offene-befunde-und-todo.md`). ruff ist sauber.

## Vertrag

- In `openapi-v1.json` und `openapi-public.json` steht das Feld `ChatRequest.probe`.
- Eingetragen in `docs/api/bewusste-vertragszusaetze.md`.

**Deploy:** Backend neu bauen. Keine Migration.
