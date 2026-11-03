# Master-Skill und Werkzeugbeschreibungen: UI-Module richtig nutzen (2026-11-03)

**Warum:** Golden-Lauf 2026-11-03 (Agent, gpt-6-luna; Reports
`evals/reports/golden-20261103-112633-u1-ui-agent.json` und `…-113227-u1-seed-agent.json`):

- Das Auswahlfeld (`ui_entscheidung`) wählte der Agent nie (GV-UI-3/4/5). „Zuerst handeln“
  ließ für eine Rückfrage nach den Ergebnissen keinen Platz, und der Master-Skill nannte das
  Modul nicht.
- „Optik eine Ebene tiefer“ (GV-UI-1) zeigte keinen Baum. Der Agent rief zweimal das rohe
  `browse_collection_tree` und tippte die Themen ab, weil er für das Unterthema keine
  Sammlungs-Kennung hatte.
- Zweimal duzte die Antwort eine Lehrkraft (GV-UI-1, GV-LEH-1).

Auftrag des Nutzers: Werkzeugbeschreibungen verbessern, solange sie allgemein bleiben, sonst im
Master-Skill; die kompakte Fassung (`docs/skills/vorgehen-knapp.md`, die live steht) anpassen.

## Werkzeugbeschreibungen (Manifeste, allgemein)

| Modul | Änderung |
|---|---|
| `ui_entscheidung` | Ergebnisse dieses Zuges stehen vor dem Auswahlfeld; Frage nicht im Text wiederholen, keine Schnellantworten dazu, ein Feld je Zug; nach der Antwort weiterarbeiten statt erneut fragen. Neues „wann“: nach einer Suche oder Erklärung ist genau eine Angabe offen, die den nächsten Schritt bestimmt. Nennt kein WLO-Werkzeug. |
| `ui_themenbaum` | Unterthema eines Fachs: Sammlung zuerst mit `search_wlo_collections` finden, dann `nodeId`. „nicht wann“ geschärft: `browse_collection_tree` nur zum Auswerten, zum Zeigen immer der Themenbaum. Das Modul ist über seine Datenquelle ohnehin an WLO gebunden. |

Register neu erzeugt (`npm run module:register`), Backend-Kopie `manifeste.json` mit.

## Master-Skill (`docs/skills/vorgehen-knapp.md`)

Grundlage ist die live stehende Fassung. Sie war im Repo nur bei den Schnellantworten älter: Die
Regel „du lieferst sie selbst über `respond_to_user`“ ist jetzt übernommen.

- **Zuerst handeln:** Eine Rückfrage im Auswahlfeld ist kein Vertagen. Erst kommen die Ergebnisse
  dieses Zuges, dann höchstens eine Frage.
- **Zielgruppen:**
  - Lernende: nach der Erklärung höchstens eine Frage (Klasse, Vorwissen), als Auswahlfeld.
  - Lehrkräfte: Sie (wie `persona_formality.P-LEH`).
- **Suchen und Gliederung:**
  - Breit suchen (M06): Bleibt danach eine Angabe offen, die die Auswahl ändert, höchstens eine
    Frage als Auswahlfeld, mit Möglichkeiten aus den Treffern.
  - Eine Ebene tiefer (M08): Themen zeigen → `ui_themenbaum`. Für ein Unterthema die Sammlung per
    `search_wlo_collections` finden, dann `nodeId`. `browse_collection_tree` nur zum Auswerten
    oder ohne Themenbaum.
- **Zusammenstellen (M09):** Fragt die Person nur nach Bausteinen, suchen, die Bausteine
  einordnen und als Auswahlfeld anbieten (mehrfach, mit Freitext); im nächsten Zug den Plan.
- **Nachfragen (M03):** die Frage als Auswahlfeld; ohne Auswahlfeld als Text mit Schnellantworten.
- **Oberfläche ansteuern:**
  - neue Punkte „Themenbaum“, „Auswahlfeld“ und „Nicht angeboten“;
  - „Kacheln“ nennt Trefferliste und Webseiten-Box;
  - „Form“ unter „Immer gültig“ um Themenbaum und Auswahlfeld ergänzt.

Die lange Vorlage `vorgehen.md` und `vorgehen-kompakt.md` sind **nicht** angepasst; live steht
die Kurzfassung.

## Prüfung

- `tests/test_master_skill_vorlage.py`: Der Namens-Wächter kennt jetzt `respond_to_user`,
  `quick_replies` und die Modul-Werkzeuge aus den Manifesten. Vier neue Wächter für die
  Kurzfassung (Auswahlfeld, Themenbaum, Schnellantworten, Anrede der Lehrkräfte), je in den
  Fassungen Vorlage, Editor und Fett. Zusammen mit `test_mcp_tool_defs.py`: 215 bestanden.
- UI-Modul-Tests (`tests/test_ui_*.py`, `test_inhaltsrahmen_werkzeug.py`): 375 bestanden.
- Der Container holt den Master-Skill aus dem WLO-Knoten (`get_skill`,
  `MASTER_SKILL_NODE_ID`); die Wirkung zeigt erst ein Golden-Lauf, nachdem die Fassung im Knoten
  steht — siehe „Messung nach dem Upload“.

## Messung nach dem Upload

Golden-Lauf 2026-11-03 (Agent) nach der Übertragung in den Knoten — Reports
`evals/reports/golden-20261103-122516-ms-ui-agent.json` (UI-Abläufe) und
`…-123158-ms-seed-agent.json` (Seed-Suite):

| Satz | vorher (11:26/11:32) | nachher (12:25/12:31) |
|---|---|---|
| UI-Abläufe, hart | 28/32 (87,5 %) | 27/31 (87,1 %) |
| Seed-Suite, hart | 90/91 (98,9 %) | 89/91 (97,8 %) |

- **Auswahlfeld:** GV-UI-4 Zug 1 zeigt jetzt `ui_entscheidung` (samt Trefferliste). GV-UI-3 Zug 1
  (sucht und fragt nicht) und GV-UI-5 Zug 1 (erklärt, kein Block) weiter ohne.
- **Begleittext schwach:** neben dem Auswahlfeld nur „Bitte wähle unten aus.“ — geduzt gegenüber
  einer Lehrkraft, ohne Einordnung der Treffer.
- **`qr` falsch gezählt:** GV-UI-4 Zug 1 fiel bei `qr` durch, obwohl unter einer offenen Frage
  absichtlich keine Schnellantworten stehen — ein Fehler des Runners, nicht der Antwort.
- **Themenbaum zum Unterthema:** GV-UI-1 Zug 2 zeigt einen Themenbaum (`ui` besteht), aber
  wieder den des Fachs (Aufruf mit `subject`, Antwort aus dem Werkzeug-Cache) und bittet, „Optik“
  selbst aufzuklappen; der Optik-Zweig mit eigener Kennung kam nicht.
- **Anrede:** GV-ELT-1 Zug 2 und 3 duzen eine Elternperson (Erwartung Sie). GV-UI-5 Zug 2 ist ein
  Messfehler der Heuristik („Sie zählt …“ meint die Zahl).

Folgen im Gesamt-Review ([`2026-11-03-review-u1-gesamt.md`](2026-11-03-review-u1-gesamt.md)):
Begleittext-Regel und M03-Ausnahme in der Kurzfassung und der Beschreibung von
`ui_entscheidung`, `qr` unter einer offenen Frage nicht gestellt. Die Kurzfassung ist damit
erneut geändert und muss wieder in den Knoten.
