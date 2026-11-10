# Paket TB-E1: Ein anonym gelesenes Dokument geht an die Person, die sich anmeldet (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md` §4, Gruppe E. Grundlage sind die
Nutzer-Entscheide N1 und N2 vom 10.11.

**Vorher:** Ein anonym gelesenes Dokument gehörte `aufrufer=None`. Meldete sich die Person danach in
derselben Sitzung an, fand der Entwurf es nicht mehr (`kein_dokument`). Sie musste es noch einmal
lesen lassen.

**Jetzt:**
- `services/dokumente/ablage.zuschreiben(s, session_id, aufrufer)` übernimmt das noch lesbare
  Dokument **ohne Besitzerin** derselben Sitzung für die angemeldete Person. Das ist ein einziges
  `UPDATE … RETURNING`, ohne Lücke zwischen Lesen und Schreiben.
- `ablage.fuer_aufrufer(s, session_id, aufrufer)` ist der **eine Leseweg des Zuges**. Er gilt
  für den Lader (`stand.laden`) und für die Prüfung des Teils `document` im Arbeitsstand
  (`arbeitsstand._dokument_bestaetigt`). Hat die angemeldete Person kein eigenes Dokument,
  übernimmt sie das anonyme.
- **Zeitpunkt:** beim ersten Lesen nach der Anmeldung, also spätestens mit der ersten Arbeit am
  Dokument (Entwurf, Auswahlfeld, Ablauf). Der Plan (§4) deckt das. Der Nutzer-Entscheid N2 nennt
  „Anmeldung und Schreiboperation“; ein Lesen geht dem immer voraus.
- Festgeschrieben wird die Übernahme mit dem Commit des Aufrufers, auch wenn die Gliederung danach
  unlesbar ist. Das schadet nicht: Das Dokument gehört dann der Person, wird aber nicht genutzt.

**Grenzen:**
- Nur dieselbe Sitzung.
- Nur ein Dokument ohne Besitzerin: Eines, das schon einer Person gehört, bleibt bei ihr.
- Ein abgelaufenes Dokument wird nicht übernommen.
- Abmelden gibt das Dokument **nicht** wieder frei, denn anonym liest nur `aufrufer IS NULL`.
- **Bewusst nicht geschützt** (Review TB-E1, Befund 4): Löschen. Wer die Sitzung hält, kann das
  Dokument der Sitzung auch nach dem Abmelden löschen (`/api/ui/dokumente` löschen, „Arbeitsstand
  löschen“, neues Hochladen ersetzt). So war es schon vorher. Der Schutz gilt fürs Lesen; Löschen
  gibt nichts preis.

**Schon vorhanden und nicht geändert (N1):** Ablegen in WLO (`/api/ui/ablage/*`) und Aufträge
(`/api/ui/auftrag/stand`) antworten ohne bestätigte Anmeldung mit 403 `nur_angemeldet`, abgedeckt
durch `test_ui_ablage_api.py` und `test_ui_auftrag_api.py`. Schreibende MCP-Werkzeuge laufen nur mit
`has_personal_auth()`. Das Lesen und der Entwurf bleiben anonym möglich (`dokument_ohne_anmeldung`).

**Nicht im Paket:** Ein Vorgang, den die Person anonym begonnen hat, gehört weiter der Sitzung
(`sitzung:<id>`). Nach der Anmeldung sieht sie ihn nicht als ihren. Das ist eine eigene Frage, für
`offene-befunde-und-todo.md` §1 vermerkt.

**Review** (unabhängig, nach dem Paket): 1 MAJOR, 3 MINOR, 2 NIT, alle behoben.
- **MAJOR:** Der zweite Leseweg (`arbeitsstand._dokument_bestaetigt`) übernahm nicht. Ein anonym
  hochgeladenes Dokument wäre nach der Anmeldung im Teil `document` still verworfen worden.
  Jetzt läuft auch er über `fuer_aufrufer`.
- **MINOR:** Zwei Züge derselben Person zugleich: Der zweite liest nach der Übernahme des ersten noch
  einmal.
- **MINOR:** Ein Postgres-Test über `fuer_aufrufer`.
- **MINOR:** Löschen als bewusste Grenze vermerkt.

**Prüfung:**
- 8 neue Tests (3 gegen Postgres), zuerst rot.
- Danach `test_dokument_stand`, `test_dokument_ablage`, `test_ui_dokumente_api`,
  `test_strukturentwurf_dokument`, `test_ablauf_dokumente*`, `test_arbeitsstand`,
  `test_persist_node`, `test_preflight_node`: 182 grün, nach dem Review dazu der Postgres-Test.
- ruff ist sauber.
