# Paket TB-F1: Flow im Namen der Person, Vermerk „schreibt“ (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md`, Gruppe F. Grundlage sind die Nutzer-Entscheide
N13 (Identität vorläufig) und N15:

> „TB-1 so erweitern, dass auch schreibende Flows möglich sind … ein Vermerk, dass es schreibende
> Vorgänge enthält, damit man weiß, dass ein WLO-Login notwendig ist — das muss der Nutzer festlegen
> können.“

## Umsetzung

- **Benutzername nur im Zug:**
  - `anmeldung._aus_stand` übernimmt `authority` aus `/auth/status` in `Befund.benutzer`, mit
    `repr=False`, damit er nie in einem Log auftaucht.
  - `auth.setze_bestaetigung(..., benutzer=…)` legt ihn neben die Kennung in die ContextVar des
    Zuges.
  - `auth.benutzername()` gibt ihn nur zurück, wenn diese Bestätigung zum Block des Zuges gehört
    und persönlich ist. Er liegt nur im Prozessspeicher: in der Bestätigung des Zuges und im
    Zwischenspeicher der Anmeldungen (`anmeldung._cache`, je Fingerabdruck des Blocks, bis er
    verdrängt wird). Nie in Datenbank, Log, Trace oder Zugakte. Der Streuwert für den Besitz bleibt.
  - Nur druckbares ASCII taugt als Kopfwert, nach dem Review TB-F1. Ein Name mit Umlaut oder
    Steuerzeichen ergibt keinen Kopf; der Start scheitert dann sauber zu `bei_fehler`.
- **`X-Edu-User-Id` beim Start:** `client.starten` schickt den Kopf, wenn `benutzername()` gesetzt
  ist (B-API-Leitfaden §9.1, Weg A). Ohne bestätigte Anmeldung fehlt er. Die Abfrage des Stands
  bekommt ihn nicht (nicht gemessen, ob sie ihn braucht; siehe Grenzen).
- **Vermerk `repo_schreibt`:**
  - Am Schritt `auftrag` gibt es neu den Studio-Schalter „Flow schreibt ins Repositorium“
    (Vorgabe `None`, wegen `treiber.fassung`).
  - Er ist ein Vermerk für Redaktion und Handbuch. Der Chatbot sieht nicht in den Flow.
  - Ein Auftrag braucht ohnehin die WLO-Anmeldung (Prüfung `auftrag_anmeldung`) und startet nie
    direkt.
  - Die Texte „nur lesende Flows“ in `client.py` und `settings.py` sind entfernt.
- **Freischaltung:** Der Befund `auftrag_frei` (Flow nicht in `B_API_JOBS_FLOWS`) sperrt nur einen
  **eingeschalteten** Ablauf. Bei einem ausgeschalteten steht er unter den Hinweisen (`warnungen`).
  Sonst bräche ein Seed mit Auftrag den Werksabgleich in jedem Betrieb, der den Flow nicht
  freischaltet.
- **Doku:**
  - `ablaeufe.md`, Abschnitt „Aufträge, die schreiben“;
  - Studio-Texte de/en;
  - Bereichsschema neu exportiert.

## Review (unabhängig) und Behebung

2 MAJOR, 3 MINOR, 2 NIT.

- **MAJOR 1:** Ein Name mit Umlaut brach httpx mit `UnicodeEncodeError` ab, und zwar am Fang
  vorbei, also brach der ganze Zug ab. Auch ein Name, der kein Text ist, und eine Kürzung wären
  durchgegangen. Jetzt gilt nur druckbares ASCII mit 1 bis 200 Zeichen, sonst gibt es keinen Kopf.
- **MAJOR 2:** Der Plan verlangt eine Rückfrage vor einem schreibenden Flow, geprüft wurde sie
  nicht. Neu ist der Befund `auftrag_rueckfrage`: Vor einem `auftrag` mit `repo_schreibt` muss eine
  Wahl, ein Freitext, ein Modul oder eine Freigabe stehen.
- **MINOR:** Der Name liegt auch im Zwischenspeicher der Anmeldungen. Die Notiz ist ehrlich gefasst
  (siehe oben).
- **MINOR:** Weitere Tests: Umlaut, Zeilenumbruch, kein Text, zu lang, nicht persönlicher Block;
  `_bestaetigung` wird nach dem Test zurückgesetzt.
- **MINOR:** Ob die B-API für die Statusabfrage `X-Edu-User-Id` braucht, ist nicht gemessen. Das
  steht unter „Grenzen“.
- **NIT:** Der Eintrag K18 in den offenen Befunden ist nachgezogen.

## Prüfung

- `test_tb_f1_flow_identitaet.py`: 6 Fälle, zuerst rot.
- Mit `test_auftraege_client`, `test_mcp_anmeldung`, `test_ablauf_auftrag`, `test_ablauf_pruefung`,
  `test_ablauf_beispiele` und `test_seed_waechter`: 134 grün.
- Die Config- und Settings-Tests: 484 grün.
- ruff sauber, OpenAPI ohne Abweichung.

## Grenzen

- `X-Edu-User-Id` ist der Benutzername (`authority`). Ob die B-API die interne ID erwartet, ist
  offen; gemessen ist der Benutzername, lesend 200.
- Ob die Statusabfrage (`GET …/jobs/{id}`) `X-Edu-User-Id` braucht, ist nicht gemessen. Bei einer
  400 dort käme „Stand prüfen“ immer wieder; das klärt die Staging-Probe.
- Kein Limit je Job. Der Nutzer hält es für sinnvoll (N14); es kommt mit TB-F2 bzw. später.
