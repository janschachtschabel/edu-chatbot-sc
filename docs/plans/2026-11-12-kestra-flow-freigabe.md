# Plan: Kestra-Flows im Studio freigeben (Paket KF, 2026-11-12)

## Anlass

- Ein Ablauf darf einen Kestra-Flow nur starten, wenn er in `B_API_JOBS_FLOWS` steht, und nur,
  wenn `B_API_JOBS_START_PATH` gesetzt ist. Beides sind Variablen der Server-Umgebung.
- Der Nutzer (11.11.): „über Umgebungsvariablen ist ziemlich unpraktisch“.
- **Entscheid:** Die Freigabe gehört in die Abläufe-Oberfläche des Studios und ist dort klar als
  Kestra-Flow-Freigabe erkennbar.

## Entscheide

- **K-E1 Bereich:** `01-base/kestra-flows`, Feld `kestra.flows`, eine Liste von
  `namespace/flowId`.
  - Abschnitt „Kestra-Flows freigeben“ auf der Seite „Abläufe“, unter der Liste der Abläufe.
  - Wirkt ohne Neustart (Lader mit Zwischenspeicher wie jeder Bereich).
- **K-E2 Regel der Freigabe:**
  - Im Studio freigegeben: Es gelten diese Flows. Ist `B_API_JOBS_FLOWS` gesetzt, ist sie die
    Obergrenze, es gilt also die Schnittmenge.
  - Im Studio nichts freigegeben: Es gelten die Flows aus `B_API_JOBS_FLOWS` wie bisher. Bestehende
    Anlagen bleiben unverändert.
- **K-E3 Start-Pfad:**
  - Leer heißt jetzt Vorgabe `/api/v1/jobs/flows/{flow}` (B-API-Handbuch, am Staging gemessen).
  - Ein gesetzter, unsicherer Pfad schaltet weiter aus.
  - „Aufträge eingerichtet“ heißt: gültiger Pfad und mindestens ein wirksam freigegebener Flow.
- **K-E4 Auswahl:** Das Feld schlägt die Flows vor, die die b-api für `B_API_KEY` meldet
  (`GET /api/v1/jobs/flows`, gemessen 12.11.: Liste mit `namespace`, `flowId`, `description`,
  `active` …).
  - Zeitlimit 5 s, Zwischenspeicher 5 min, im Fehlerfall leer.
  - Nur aktive Flows, innerhalb der Obergrenze.
  - Freitext bleibt möglich (`datalist`). Die Form prüft das Modell.
- **K-E5 Kein „schreibt“-Vermerk in der Freigabe:** Den trägt der Auftragsschritt
  (`repo_schreibt`, TB-F1). Der Datenschutzhinweis (30 Tage Klartext bei Kestra) steht am Abschnitt.

## Pakete

| Teil | Inhalt |
|---|---|
| KF-1 | Backend: Modell, Lader, Seed, Wirkung (`area_effects`), Client-Regel (K-E2/K-E3), Katalog `kestra_flows` (K-E4), Tests |
| KF-2 | Studio: Abschnitt auf „Abläufe“, Texte de/en, Schema-Fixture, Tests |
| KF-3 | Doku (`ablaeufe.md`, `.env.example`, offene Befunde, Notiz) und Review mit Behebung |

## Nicht im Umfang

- Eingaben eines Flows aus dem `inputSchema` als Vorschlag für `argumente`, ein eigenes späteres
  Paket.
