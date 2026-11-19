# Doku und Architekturgrafiken auf dem Stand der Pakete D, K und U (2026-11-19)

Quellen: Plan `docs/plans/2026-11-17-b-api-delegation-und-upload.md`, MCP-Plan
`docs/plans/2026-11-17-mcp-wuensche-b-api-flows.md`, Änderungsnotizen
`2026-11-18-paket-d-b-api-delegation.md`, `2026-11-18-paket-k-kestra-ueber-mcp.md`,
`2026-11-19-paket-u-ein-upload-weg.md` und der Code am Commit `81d66f6` (Branch `ein-upload-weg`).
Kein Produktivcode geändert.

## Texte

| Datei | Was |
|---|---|
| `README.md` | Neue Zeilen „b-api-Betrieb“, „Kestra über den MCP“, „Ein Upload-Weg“; MCP-Zeile nennt die Flow-Werkzeuge (Stand 18.11.); „Betrieb in Kürze“ verweist auf `b-api-betrieb.md` (`forward` mit Delegation); Grafik-Zeile nennt den Datenstrom. |
| `docs/architektur.md` | Vertiefungstabelle (b-api-Betrieb, Abläufe); §4.4 `faehigkeiten.py` und die zwei Aufrufwege ohne Modell (Stapel-Ablage, Flows); §5 Bild mit Repository-Proxy und Kestra; §5.4 „Der Weg der Bytes“ mit den drei Orten; §5.5 Absatz zur Person bei der b-api; §5.6 Absatz „Delegations-Token (Paket D)“, Länge 8–8192; **neu §5.8** Kestra-Flows über den MCP und **§5.9** ein Upload-Weg, ein Datenstrom aus Teilen (Tabelle je Ort mit Teilen und Herkunft). |
| `docs/uebergabe-betrieb.md` | Header-Tabelle (`bdt_`), Content-Types (Upload-Feld); §5 Variante A mit `forwardDelegation`, kein Rückfall, Admin-Liste, freigegebene Köpfe; neuer Block „Kestra über den MCP“ (`WLO_BAPI_VIA_REPOSITORY`, `WLO_BAPI_FLOWS`, Erkennung beim Start, Neustart des MCP, Rechte bei der b-api); Variante B (Direktweg nur ohne `repo_schreibt`); §11 Studio-Grenzen `lokal_max_dateien`/`lokal_max_mb_gesamt`; §13 MCP-Stand und Kestra; §15 Deploy der Pakete D, K, U. |
| `docs/ablaeufe.md` | Baustein `auftrag`; „Themenbaum erstellen“ ohne Wegfrage (E12, 38 Schritte, `dateien_weg` nach den Teilen der Auswahl), Kestra im Ablauf (E14, md/txt-Ausschluss); `themenbaum_aus_inhalten` mit `orte: [wlo]`; Grenzen des Flows (`FLOW_FAILED`-Satz, md/txt); „Aufträge, die schreiben“ neu: MCP statt `X-Edu-User-Id`, `repo_schreibt` Pflicht für schreibende Flows, Start in zwei Schritten, `outcomeOpen`; **neu** „Warten auf den Flow“ (`warten: gesperrt`, drei Knöpfe, Frist, `unknown_job`); KF-Abschnitt: Freigabe über den MCP; `dokument_lesen` liest auch Inhalte. |
| `docs/mcp-und-anmeldung.md` | **Neu §1a** die Kette bis zur b-api (LLM mit Delegation; Jobs Widget → Backend → MCP → Repository-Proxy → b-api → Kestra, Assertion des Repositorys), Risiko jobId. |
| `docs/b-api-betrieb.md` | Stand 19.11.; Rückfall-Regeln nach K (Abbruch im Zug über den MCP, Direktweg nur ohne Delegation); Kestra-Weg „gilt seit Paket K“; Fehlerzeile `EDU_USER_REQUIRED` mit den Sätzen von heute; **neu §5** Kestra-Flows über den MCP (Weg, Träger je Schritt, Start, `outcomeOpen`, Stand, jobId, md/txt, Fehler des MCP, Einstellungen am MCP). |
| `docs/steckbrief-uebergabe.md` | Köpfe und virtueller Key: `forwardDelegation`, Delegations-Token, Kestra über den Repository-Proxy, Verweis auf den b-api-Betrieb; Buchung auf das Token. |
| `docs/einbindung-kurzanleitung.md` | geprüft, beschreibt weder Upload noch b-api — unverändert. |
| `docs/ui-module.md` | §6 war schon auf dem Stand von U — unverändert. |

## Grafiken (`docs/architektur-grafiken/`)

Alle drei gegen `81d66f6` im Klon `edu-chatbot-sc` verankert (`--repo-root`, nur gelesen). Die Belege
der beiden vorhandenen Grafiken (bisher `2a589a6` bzw. `e7f10c0`) sind auf die Zeilen von `81d66f6`
nachgezogen: wo der Block unverändert war, verschoben; sonst von Hand geprüft.

- **`architektur.html` (aktualisiert):** neue oberste Zeile mit dem Bereich „b-api (Bildungs-API)“
  (LLM und Kestra-Jobs); b-api-Proxy mit Delegation `bdt_`; WLO-MCP mit Stapel-Ablage und Flows;
  neu „Repository-Proxy“ (`/rest/bapi/**`, Assertion) und „Kestra-Jobs der b-api“
  (`node-metadata-write`, schreibt Metadaten nach edu-sharing); Karte „Kestra über den MCP“.
- **`ui-module-einbindung.html` (aktualisiert):** neuer Knoten „Hochladen (ui_upload)“ an der
  Fähigkeit `hochladen (rolle)` des Hosts (`/api/ui/dokumente`, `/api/ui/ablage`, Orte), Karte
  „Upload-Feld (Paket U)“ mit der Antwort `bereitgestellt` und den Teilen.
- **`datenstrom-upload-kestra.html` (neu, Workflow, 5 Lanes, 1232 px breit):** Dateien wählen →
  „Wo verarbeiten?“; Zweig „Hier im Chat“ (`/api/ui/dokumente` → `metadaten` (chatbot) und
  `strukturdokument`); Zweig „In WLO“ (Stapel-Ablage → `wlo_start_flow` → Repository-Proxy →
  Kestra-Job → `wlo_flow_status` → `metadaten_lesen` → `metadaten` (aus WLO gelesen)); Teil `struktur` immer;
  am Ende Abläufe, freier Chat (`dokument_lesen`) und Werkzeuge.
- `index.html` und `README.md` des Ordners: acht Grafiken, neue Karte bzw. Zeile, Quellstände,
  Befehl zum Neu-Erzeugen, Hinweis zum Windows-Abbruch der Browser-Prüfung.
- PNGs (hell) neu: `png/architektur.png`, `png/ui-module-einbindung.png`,
  `png/datenstrom-upload-kestra.png`.
- Quellen: `quellen/architektur.json`, `quellen/ui-module-einbindung.json`,
  `quellen/datenstrom-upload-kestra.json`. Prüfbelege (`*.delivery*.json` u. a.) liegen unter
  `.archify/doku-1911/`, nicht im Grafik-Ordner.

## Geprüft

- `archify finalize --quality showcase` für alle drei: validate, deliver, check und browser-check
  bestanden. Die Browser-Prüfung brach unter Windows zunächst mit `viewer/temp-cleanup-incomplete`
  ab (Chrome gab sein Profil zu spät frei); mit einem Vorspann, der das Aufräumen länger wiederholt,
  lief sie durch. Hinweise ohne Befund: 3 unbekannte deutsche Übersetzungsschlüssel (wie bisher),
  in den UI-Modulen ein Umweg mit drei Knicken (`host → uiantwort`, wie bisher).
- PNGs angesehen: keine Überlappungen; im Datenstrom läuft „In WLO“ links um die erste Lane herum
  (eine festere Führung brach die Prüfung, darum automatisch).
- `npm run check:docs`: 39 Host-Attribute, alle in der Laufzeit-Tabelle eingeordnet.
- Nach dem Review (19.11.) nachgezogen: `X-Boerdi-Engine` in der Admin-Liste; Werksvorgabe des
  Flows nutzt ab Werk „Themenbaum erstellen“; Freigabe im Studio bzw. `B_API_JOBS_FLOWS` für
  schreibende Flows; Deploy-Hinweise (Werksabgleich über `migrate`, angepasste Bereiche, Proxy erst
  nach dem Backend, `forward` nur hinter dem Proxy, Rechte bei der b-api); acht Grafiken in der
  Übergabe; Studio-Name „UI-Module → Hochladen“; Anmerkung „überholt“ in W1 des MCP-Plans; Etikett
  „metadaten (aus WLO gelesen)“ in der Datenstrom-Grafik.

## Offen

- `deploy/README.md` und `deploy/.env.example` nicht angefasst (Paket D hat `.env.example` schon
  kommentiert).
- `docs/architektur.md` §8 (Datenmodell) zählt die Tabellen noch nach Paket 18; nicht Teil dieser
  Pakete.
- Die Zahl der Schritte in „Themenbaum erstellen“ (38) und die Frist-Regel stammen aus dem Seed bzw.
  der Änderungsnotiz K; bei einer weiteren Seed-Fassung mitziehen.
