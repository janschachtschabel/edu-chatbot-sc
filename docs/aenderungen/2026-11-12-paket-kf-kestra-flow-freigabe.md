# Paket KF: Kestra-Flows im Studio freigeben (2026-11-12)

Plan [`plans/2026-11-12-kestra-flow-freigabe.md`](../plans/2026-11-12-kestra-flow-freigabe.md).
Nutzer-Entscheid 11.11.: Die Freigabe über Umgebungsvariablen war unpraktisch. Sie gehört in die
Abläufe-Oberfläche und ist dort klar als Kestra-Flow-Freigabe erkennbar.

## Was

- **Neuer Bereich `01-base/kestra-flows`** (`kestra.flows`, Liste von `namespace/flowId`):
  - Modell `domain/config_models/kestra_flows.py`, Lader `config_loader/kestra_flows.py`, Seed
    (leer), Wirkung `voll/voll`.
  - Höchstens 50 Flows, Doppelte und Leerraum fallen weg.
- **Studio:** Auf der Seite „Abläufe“ steht unter der Liste der Abschnitt **„Kestra-Flows
  freigeben“**, mit Datenschutzhinweis (30 Tage Klartext bei Kestra). Wirkt ohne Neustart.
- **Regel** (`services/auftraege/client.py`):
  - Im Studio freigegeben: diese Flows. `B_API_JOBS_FLOWS` ist dann optionale Obergrenze.
  - Im Studio nichts freigegeben: `B_API_JOBS_FLOWS` wie bisher. Bestehende Anlagen bleiben
    unverändert.
  - Start-Pfad leer heißt Vorgabe `/api/v1/jobs/flows/{flow}`.
  - „Eingerichtet“ heißt: gültiger Pfad und mindestens ein wirksam freigegebener Flow.
- **Vorschläge** (`services/auftraege/flow_katalog.py`, Katalog `kestra_flows`):
  - Die aktiven Flows, die `GET /api/v1/jobs/flows` für `B_API_KEY` meldet, innerhalb der
    Obergrenze, dazu die schon freigegebenen.
  - 5 Minuten zwischengespeichert, nach einem Fehlschlag 1 Minute.
  - Die Antwort ist am 12.11. gemessen: eine Liste mit `namespace`, `flowId`, `description`,
    `active` …
- **Prüftext** `auftrag_frei`: „Flow … ist nicht freigegeben (Abläufe → Kestra-Flows
  freigeben)“ statt des Verweises auf die Umgebung. Der Hinweis am Flow-Feld zeigt auf den
  Abschnitt.

## Sicherheit

- **Härtung:** Eine Flow-Kennung mit einem Abschnitt nur aus Punkten (`../etc`, `wlo/..`) bestand
  bisher die Prüfung des Clients. Aus `/api/v1/jobs/flows/{flow}` wäre so ein anderer Pfad der
  b-api geworden. Bisher konnte nur der Betrieb Flows setzen, jetzt auch das Studio.
  `kestra_flows.ist_flow` weist solche Kennungen ab, im Modell wie beim Start.
- Die Beschreibung der b-api ist Text Dritter: nur die erste Zeile, höchstens 80 Zeichen, als
  Beschriftung in einer Vorschlagsliste.

## Geändertes Verhalten

- Ein leerer `B_API_JOBS_START_PATH` schaltet Aufträge nicht mehr aus, es gilt die Vorgabe. Aus
  sind Aufträge ohne freigegebenen Flow oder mit unsicherem Pfad. Der Test
  `test_der_flow_katalog_ist_leer_ohne_eingerichtete_auftraege` ist darauf umgestellt.
- **Achtung beim Deploy:** Eine Anlage mit gesetztem `B_API_JOBS_FLOWS`, aber leerem
  `B_API_JOBS_START_PATH` hatte bisher keine Aufträge. Jetzt sind sie an. Wer sie aus haben will,
  setzt `B_API_JOBS_START_PATH=aus`.

## Review (unabhängig) und Behebung

0 CRITICAL, 2 MAJOR, 5 MINOR, 3 NIT, alle behoben:

- **MAJOR 1:** Der Abruf lief mit dem Zeitlimit des Clients (20 s). Jetzt sind es 5 s, wie im
  Plan.
- **MAJOR 2:**
  - Der Katalog rief die b-api auch ohne `B_API_KEY`, aus einer Anlage ohne b-api und in der CI
    echt ins Netz. Jetzt kein Abruf ohne Schlüssel.
  - Eine Fixture in `conftest` sperrt das Netz des Auftrags-Clients in allen Tests und leert den
    Zwischenspeicher je Test.
- **MINOR 3:**
  - Ein unlesbarer Bestand öffnete die Freigabe auf die ganze Obergrenze. Jetzt schließt er: Es
    gelten nur seine gültigen Kennungen, sonst keine.
  - Nur ein fehlender oder leerer Bereich fällt auf die Umgebung zurück (Lader liefert `None`).
- **MINOR 4:** Flows außerhalb von `B_API_JOBS_FLOWS` weist das Speichern ab (`config_guards`).
  Die Meldung nennt die erlaubten Flows. Vorher wirkten sie still nicht.
- **MINOR 5:** Der Ausschalter `B_API_JOBS_START_PATH=aus` steht jetzt in `.env.example`, mit
  Test und der Warnung oben.
- **MINOR 6:** Nach dem Speichern eines Bereichs lädt das Studio die Vorschlagslisten neu. Ein
  freigegebener Flow steht so gleich im Feld „Flow“.
- **NIT 7:** Höchstens 200 Einträge der b-api; Steuerzeichen (Cf, etwa Bidi) fallen aus der
  Beschreibung.
- **NIT 8:** Nur ausdrücklich aktive Flows (`active: true`).
- **NIT 9:** Docstring und Testnamen zum leeren Start-Pfad sind nachgezogen.

## Prüfung

- **Backend:**
  - neu `test_kf_kestra_flows` (19, davon 6 aus dem Review);
  - angepasst `test_ablauf_studio_k2c1`, `test_ablauf_auftrag` (Prüftext) und `test_config_models`
    (neuer Bereich);
  - breiter Satz zu Ablauf, Auftrag, Konfiguration, Wächtern und Seeds: 1670 grün.
  - Nur `test_health_nennt_das_repositorium` lief in eine Zeitüberschreitung, weil lokal keine
    Datenbank lief (Docker aus). Die CI prüft ihn.
- **Studio:**
  - Tests angepasst: 36 Bereiche, Abschnitte der Seite „Abläufe“; neu: Kataloge nach dem
    Speichern;
  - Studio 2149 grün;
  - Schema-Fixture neu erzeugt;
  - Lint und `check:*` sauber.

## Deploy

1. Keine Migration. Image neu bauen.
2. `boerdi import-config --werksabgleich` bringt den leeren Bereich.
3. Im Studio unter Abläufe → „Kestra-Flows freigeben“ den Flow eintragen, etwa
   `edusharing.chatbot/node-metadata-write`.
4. Danach lässt sich „Themenbaum · aus eigenen Inhalten“ einschalten.

`B_API_JOBS_FLOWS` und `B_API_JOBS_START_PATH` sind nicht mehr nötig.
