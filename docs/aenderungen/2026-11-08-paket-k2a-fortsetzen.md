# Paket K2a — Gespräch fortsetzen über die Anmeldung, Frist eines wartenden Auftrags (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2a,
Entscheid F2 (über die Anmeldung, keine Gesprächs-ID zum Eintippen).

## Was die Person sieht

- Ist sie angemeldet und wartet ein Ablauf von ihr in einem **anderen** Gespräch, zeigt das Widget über der
  Eingabe einen Hinweis: „In einem früheren Gespräch wartet noch „Lesen“ (zuletzt 7. Nov., 09:30).“ mit
  **Fortsetzen** und ×.
  - Gefragt wird beim Öffnen (wenn schon angemeldet), nach der Anmeldung, nach einem neuen Block (Ticket) und
    nach einem Neustart — einmal je Gespräch und Block.
  - „Wartet“ heißt: auf einen b-api-Auftrag (`wartet_auftrag`) oder auf ihre Antwort (`wartet_person`).
  - Angeboten wird nur der jüngste, und nie der Vorgang, den das aktuelle Gespräch schon führt.
- **Fortsetzen** wechselt auf jenes Gespräch und lädt dessen Verlauf; bis er da ist, nimmt die Eingabe
  nichts an. Wartet dort ein Auftrag, fragt das Widget gleich „Stand prüfen“:
  - fertig → das Ergebnis wird abgeholt, und der Ablauf geht weiter;
  - läuft noch → „Der Auftrag läuft noch“ mit „Stand prüfen“ und „Auftrag abbrechen“.
- Nach dem Abmelden oder einer abgewiesenen Anmeldung ist der Hinweis weg.
- Ein Vorgang mit wartendem Auftrag **verfällt nicht mehr nach 3 Tagen**: Er hält mindestens 8 Tage
  (Job bis 24 h bei der b-api, danach 7 Tage Ein- und Ausgaben dort), höchstens 30. Ist das Ergebnis
  abgeholt, gilt wieder die gewöhnliche Frist.
- Beim Verdrängen (höchstens 3 Vorgänge je Person) weicht ein Vorgang mit wartendem Auftrag nie.

## Geändert

- **Backend**
  - `services/vorgaenge.py`:
    - `WARTET_AUFTRAG`, `WARTEND`, `WARTET_AUFTRAG_TAGE = 8`, `HOECHSTENS_TAGE = 30`;
    - die Frist hängt am Status: `lauf_setzen` nach dem neuen Status, `teil_setzen` und `beruehren` per SQL
      nach dem Status der Zeile (ein Lesen verkürzt die Frist eines wartenden Auftrags nicht);
    - `anlegen` verdrängt keinen Vorgang mit wartendem Auftrag (warten mehr als drei, liegt die Zahl
      darüber; die b-api begrenzt die offenen Jobs selbst);
    - neu `offene(s, aufrufer, ohne=…)` und `sitzung_setzen(s, vorgang_id, session_id)`.
  - `services/ablauf/zug_basis.py`: `festhalten(…, session_id=…)` merkt das Gespräch am Vorgang, sobald der
    Lauf darin zu warten beginnt — auf einen Auftrag oder auf die Person (dorthin führt „Fortsetzen“);
    `STATUS` nutzt `vorgaenge.WARTET_AUFTRAG`. Die Aufrufer in
    `zug.py` und `auftrag_zug.py` reichen `req.session_id` durch.
  - neu `api/ui_vorgaenge.py`: `POST /api/ui/vorgaenge/offen` `{session_id}` →
    `{vorgaenge: [{titel, ablauf, status, session_id, geaendert}]}`.
    - Nur mit bestätigter Anmeldung (403 `nur_angemeldet`); Besitzerin ist die Kennung der Anmeldung, nie eine
      mitgeschickte ID; das aktuelle Gespräch und sein Vorgang fehlen; höchstens ein Eintrag.
    - `Cache-Control: private, no-store`: die Kennung eines Gesprächs ist dessen Geheimnis.
    - Schreibt nichts, kein Zug, IP-Drossel wie die übrigen Modul-Abrufe.
  - `main.py`: Router eingehängt. Vertrag neu erzeugt; Eintrag in `api/bewusste-vertragszusaetze.md`.
- **Widget**
  - neu `stream/offene-vorgaenge.ts`: Form und Prüfung der Antwort (nur wohlgeformte Einträge, nur
    Widget-Kennungen `bb-…`).
  - `stream/chat-api.ts`: `offeneVorgaenge(sessionId)`.
  - neu `shell/fortsetzen.ts`: `FortsetzenController` (einmal je Gespräch und Block fragen; eine Antwort nach
    einem Wechsel von Gespräch oder Block verwerfen; das Angebot gilt nur für den Block, mit dem gefragt wurde,
    `gueltiges()`; still bei Fehlern; `vergessen`) und `fortsetzenDatum`.
  - `shell/lifecycle.ts`: `wechseln(id)` — wie `restart()`, aber mit der fremden Kennung und ihrem Verlauf; das
    Laden hält, bis der Verlauf da ist.
  - `shell/chat-shell.component.{ts,html}`, `_chat-footer.scss`: Hinweis über der Eingabe in einer Live-Region,
    die immer im DOM steht (`role="status"`); Effekt „fragen, sobald angemeldet und kein Zug läuft“ samt Anlass
    (neuer Block, Neustart); `onFortsetzen()` und `onFortsetzenSchliessen()` geben den Fokus an die Eingabe.
  - i18n de/en: `fortsetzen.hinweis`, `fortsetzen.knopf`, `fortsetzen.schliessen`, `fortsetzen.pruefen`.

## Bewusst so

- **Statt `GET /api/vorgaenge/offen`** (Plan) ein `POST /api/ui/vorgaenge/offen` wie die übrigen Abrufe des
  Widgets: der Zugangsblock reist dort schon mit, und die Kennung des aktuellen Gesprächs gehört nicht in eine
  URL.
- **„Ergebnis liegt bereit“** ist kein eigener Text: Nach dem Wechsel fragt das Widget „Stand prüfen“, und
  dessen Antwort holt das fertige Ergebnis ab oder sagt, dass der Auftrag noch läuft. Das Backend kennt den
  Stand ohnehin nur über diese Abfrage mit dem Schlüssel der Person.
- **Die Frist ist ein fester Wert** (8 Tage) statt `deadlineAt` je Job (`simplify:` in `vorgaenge.py`): die
  b-api setzt bisher immer Start + 24 h. Hält sie Flows einmal länger, gehört `deadlineAt` in
  `vorgang_auftraege` (Migration).
- **Nur das jüngste** wartende Gespräch wird angeboten; mehr als drei Vorgänge hat eine Person selten.
- Ein anonymes Gespräch kann keinen Auftrag starten und braucht also kein Fortsetzen über die Anmeldung
  (Plan §1).

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 2 hoch, 4 mittel, 4 Kleinigkeiten. Sicherheit des Endpunkts ohne Befund (nur
bestätigte Person, `no-store`, keine Kennung im Log, Drossel).

| Befund | Behebung |
|---|---|
| **Hoch:** Das Gespräch am Vorgang folgte nur dem Start eines Auftrags. Führte ein Gespräch B den Lauf aus A weiter, bot B bei jedem Neuladen „Fortsetzen“ nach A an — mit veraltetem Verlauf. | `festhalten` merkt das Gespräch bei jedem Beginn eines Wartens; der Endpunkt lässt den Vorgang des aktuellen Gesprächs aus. |
| **Hoch:** Meldete die Gastseite ohne Neuladen eine andere Person an (neues Ticket), blieb das Angebot der ersten stehen — ein Klick hätte deren Gespräch geöffnet. | Das Angebot gilt nur für den Block, mit dem gefragt wurde (`gueltiges()`); jeder neue Block, jede Anmeldung, Neustart und `resetSession` vergessen es und fragen neu. |
| Nach einer Abweisung (abgelaufener Block, 403) fragte das Gespräch nie wieder, auch nicht nach dem stillen Ticket-Tausch. | Der Tausch ist ein Anlass, neu zu fragen. |
| Während der Verlauf lud, nahm die Eingabe Text an; danach fiel „Stand prüfen“ still aus. | `wechseln` hält das Laden bis zum Ende des Verlaufs. |
| Die Live-Region kam schon gefüllt ins DOM (oft nicht angesagt); nach dem Klick fiel der Fokus auf `body`. | Leere Live-Region steht immer im DOM; Fokus zurück in die Eingabe. |
| Kleinigkeiten | Nur der jüngste Vorgang geht hinaus; Neustart fragt sofort; Wortlaut „zuletzt {datum}“ statt „Gespräch vom“; Tests ergänzt (ohne `persist-session`, kein Fragen während eines Zugs, Blockwechsel, Neustart). |

Offen und dokumentiert:
- **Aufbewahrung unter 8 Tagen** (`retention_days` der Gesprächsverläufe): Verlauf und Verweis des alten Gesprächs
  können vor dem Vorgang gehen. Nach „Fortsetzen“ ist der Verlauf dann leer, und „Stand prüfen“ findet den Vorgang
  nur, wenn er der jüngste offene ist. Empfehlung: Aufbewahrung mindestens 8 Tage, solange Aufträge freigeschaltet
  sind.
- Wie `restart()` setzt `wechseln` die Tour und wartende Aufträge der Gastseite nicht zurück (älter als K2a).
- Gemeinsames Gerät: Abmelden räumt nur den Block, nicht das Gespräch. Was danach jemand anderes im selben
  Gespräch schreibt, kann die angemeldete Person später über „Fortsetzen“ lesen. Folge von F2 und „Abmelden räumt
  nur den Block“; dafür gibt es den Neustart-Knopf.
- Eine neue Sitzung übernimmt den wartenden Vorgang ohnehin (`juengster`) und zeigt im gesperrten Lauf (K2b) den
  Sperr-Hinweis, während das Banner auf das alte Gespräch zeigt — beides führt zum selben Lauf.

## Tests

- Backend:
  - neu `tests/test_ui_vorgaenge_api.py` (Liste, 403 ohne Anmeldung, ohne Lauf kein Ablauf, unbrauchbare
    Kennung, `no-store`, `ohne` = aktuelles Gespräch);
  - neu `tests/test_vorgaenge_fortsetzen_pg.py` gegen Postgres (Frist beim Warten, auch nach Lesen und neuem
    Teil; zurück nach dem Abholen; Obergrenze; Verdrängen lässt Wartende aus; `offene` nennt das Gespräch des
    Auftrags, nicht das aktuelle, nicht fremde);
  - `tests/test_ablauf_auftrag.py` (`festhalten` merkt das Gespräch bei jedem Warten, nicht bei einem beendeten
    Lauf); im Endpunkt-Test zusätzlich: nur der jüngste, nicht der Vorgang des aktuellen Gesprächs;
  - `tests/test_i18n_messages.py`: Code `nur_angemeldet` als bewusst einsprachig eingetragen;
  - Attrappen in `test_ablauf_zug.py`/`test_ablauf_auftrag.py` um `sitzung_setzen` ergänzt;
    `test_openapi_contract.py` (Routen-Inventar).
- Widget: neu `shell/fortsetzen.spec.ts` (auch Blockwechsel), `shell/chat-shell-fortsetzen.spec.ts`
  (Live-Region, kein Fragen während eines Zugs, Neustart); `shell/lifecycle.spec.ts` (`wechseln` mit und ohne
  `persist-session`, Laden bis zum Verlauf).

## Betrieb

Keine Migration und keine neue Variable. Das Widget-Bündel muss neu gebaut werden.
