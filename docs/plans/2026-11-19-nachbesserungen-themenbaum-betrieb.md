# Plan 2026-11-19: Nachbesserungen Themenbaum und Betrieb (Paket N)

Auftrag des Nutzers (19.11.) nach den Paketen D, K, U. Entscheide unten sind abgestimmt.

## N1 — Betriebsanzeige (Studio und Health)

- `B_API_KEY_MODE` ist ohne Variable `auto` (so im Code; Test pinnt es).
- Der Chatbot merkt sich je Prozess (und über die DB für alle Kopien, wenn einfach möglich), welche
  Betriebsart er zuletzt gesehen hat: **hinter dem b-api-Proxy mit Delegation** (`bdt_`), **mit
  durchgereichtem Schlüssel**, **direkt** (ohne Kopf, `B_API_KEY`), jeweils mit Zeitpunkt. Nie Werte.
- Anzeige: Health-Endpunkt (nur Art und Zeit, keine Geheimnisse) und Studio (Betrieb/Übersicht).
  Warnung, wenn `B_API_KEY_MODE=forward` gesetzt ist, aber seit Start kein Token kam, und wenn
  Delegation gesehen wird, die Admin-Liste aber offensichtlich fehlt (z. B. Zugangsblock kommt nie an).

## N2 — Fach und Stufe aus dem Vokabular

- Die Kurzangaben (`services/dokumente/inhalt_angaben.py`) bekommen die Labels der WLO-Vokabulare
  (Fach, Bildungsstufe) als geschlossene Liste in den Prompt.
- Danach wird jedes Ergebnis auf das Vokabular abgebildet (vorhandene Abbildung über
  `lookup_wlo_vocabulary`, 24 h gepuffert, `services/mcp/arg_resolvers.py`); kein Treffer → leer.
- Dasselbe für Fach/Stufe im Entwurf und in der Vorbelegung, wo sie aus Angaben stammen.

## N3 — Zuordnung Datei → Punkt

- Der Entwurf `aus_inhalten` verlangt schon je Punkt die Kennungen der Materialien (`abschnitte`).
  Diese werden als `inhalte` je Knoten übernommen — mit **`node_id`, wo es eine gibt** (WLO-Weg,
  Ablage), sonst `upload_id`/`i` (Chat-Weg). `node_id` geht immer vor, damit Inhalte in edu-sharing
  wiederzufinden sind.
- **Nachziehen über Einbettungen:** Materialien, die das Modell keinem Punkt zuordnet (oder
  offensichtlich falsch), werden per Einbettung (Titel, Beschreibung, Schlagworte gegen Titel und
  Beschreibung der Punkte) dem nächsten Punkt zugeordnet, oberhalb einer Schwelle; darunter
  „nicht zugeordnet“. Ein Aufruf für alle, Kosten gebucht.
- **Test der Güte:** ein fester Satz echter Beispiele (z. B. 12 Materialien zu 4 Themen) mit
  erwarteter Zuordnung; die Einbettung muss mindestens 80 % richtig zuordnen (Messlauf mit
  echtem Modell lokal, Ergebnis in der Notiz; im CI eine Attrappe mit festen Vektoren).
- Die Oberfläche zeigt je Punkt die zugeordneten Materialien (Zahl, aufklappbar mit Titeln).

## N4 — Freigabe-Box für den Kestra-Start

- Nach „Ja“ an der Rückfrage holt der Server die Vorschau des MCP (`wlo_start_flow` ohne
  `confirmToken`) und zeigt sie als **kompakte Box**: Kopfzeile „N Materialien werden in WLO
  erschlossen – überschreibt Titel, Beschreibung, Schlagworte, Fach, Stufe, Zielgruppe, Typ,
  Sprache“, die Liste **eingeklappt** (aufklappbar, gruppiert nach Ordner, bei vielen Einträgen mit
  Suche bzw. seitenweise), Probleme des MCP (`problems`) getrennt sichtbar; Knöpfe „Freigeben“ und
  „Abbrechen“. Ein Stapel über 50 Dateien: **eine** Box für alle Teile.
- Erst „Freigeben“ bestätigt (`confirmToken` bleibt auf dem Server, gebunden an Lauf und Person).
- Baut auf dem Freigabe-Weg aus Paket S auf (Box + Chip, `_pending_write`-Muster), erweitert auf
  Auftrags-Schritte.

## N5 — Wunsch an den Flow-Autor (extern)

`edusharing.chatbot/node-metadata-write`: je Node nach MIME-Typ verzweigen — `text/markdown` und
`text/plain` → Inhalt direkt lesen (`GET …/edu-sharing/repo/nodes/{id}/content`, Scope
`edu-sharing-repo`), sonst wie bisher `textContent`. Danach nimmt der Chatbot den Ausschluss
(`auftrag_teile.METADATEN_FLOW_OHNE`) heraus.

## Offen, später

- Ticket-Anmeldung (eingebettet in edu-sharing) gegen den Repository-Proxy testen, sobald eine Seite
  mit Ticket verfügbar ist.

## Vorgehen

Je Paket Test zuerst, unabhängiges Review mit Behebung (bei vielen MAJOR ein zweites), volle Suite,
Durchtest gegen Wegwerf-DB, PR, Merge bei grüner CI. Reihenfolge: N1 + N2 (parallel zu N3), dann N4.
