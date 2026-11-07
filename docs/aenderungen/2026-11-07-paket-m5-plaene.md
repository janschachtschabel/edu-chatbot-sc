# Paket M5: Pläne — Sammlungsbaum und Massen-Aufnahme (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M5). Der MCP (Stand 07.11.)
führt zwei Schreibwerkzeuge als **Plan**: eine Vorschau für das Ganze, nach dem „ja“ Abschnitte von etwa 40 s.

## Was sich ändert

- **`wlo_create_collection_tree`** (neu): ein ganzer Baum von Untersammlungen unter einer Sammlung — höchstens
  250 Knoten, Tiefe 4, 15 Kinder je Knoten (prüft der Server). Gleichnamige vorhandene werden übernommen
  (`onExisting: merge`, Vorgabe) oder abgelehnt (`fail`).
- **`wlo_add_to_collections`** (neu): bis zu 200 Paare `{nodeId, collectionId}` auf einmal. Ein schon vorhandenes
  Paar zählt als erledigt, ein gescheitertes hält die anderen nicht auf.
- Beide stehen hinter **derselben Abnahme** wie jede Änderung (Vorschau → „ja“ → der Chat löst ein), nur mit
  Anmeldung, im Agent-Modus und im Muster M18 (Kuration, zwei neue Tabellenzeilen).
- **Fortsetzen ohne neue Bestätigung:** Ist nach einem Abschnitt noch etwas offen (`complete: false`), zeigt der Chat
  den Stand („3 von 12 Schritten erledigt“, je Schritt eine Zeile) und den Knopf **„Weiter anlegen“**. Der setzt den
  Plan mit seinem `continuationToken` fort — nur für dieselbe Person, nur mit Schreibrecht, höchstens 30 Minuten nach
  der Freigabe. Den Schlüssel sieht die Person nicht; er steht im Sitzungszustand (`_offener_plan`).
- **Fehlerfälle:**
  - `plan_expired` / `plan_mismatch` beim Fortsetzen → „Der Plan ist abgelaufen …“, der Merkposten fällt weg; was
    schon angelegt ist, bleibt, ein neuer Anlauf übernimmt vorhandene Sammlungen.
  - `too_many_plans` beim Einlösen (fünf unfertige Pläne unter dieser Anmeldung) → nichts geschrieben; der Chat sagt,
    dass er die Vorschau danach neu vorlegt, und zeigt „Weiter anlegen“, wenn ein eigener Plan offen ist.
  - Keine Antwort beim Einlösen (Zeitüberschreitung, Netz) → der Plan wird mit dem Bestätigungsschlüssel gemerkt (der
    Server nimmt ihn auch zum Fortsetzen), Knopf „Weiter anlegen“; kennt der Server keinen Plan, kommt `plan_expired`.
  - Zeitüberschreitung oder Transportfehler beim Fortsetzen → der Plan bleibt gemerkt, der Knopf kommt wieder
    (derselbe Schlüssel ist gefahrlos wiederholbar).
  - `inProgress` (ein anderer Aufruf arbeitet gerade daran) → der Stand des Servers wird gezeigt, der Knopf bleibt.
- Neue Texte DE/EN: `write.planOpen`, `write.planExpired`, `write.planNone`, `write.planUnclear`,
  `write.tooManyPlans`, `write.planBlocked`, `write.planUnclearStart`, `write.planTooLarge`, `action.plan.weiterKnopf`.

## Bewusst anders als im Plan

- **Kein selbsttätiges Fortsetzen im Zug.** Ein Abschnitt dauert bis ~40 s; zwei hintereinander lägen über der
  Zugfrist. Fortgesetzt wird über den Knopf.
- Das **Modell** setzt nie selbst fort: ein `continuationToken` aus einem Modellaufruf wird wie ein `confirmToken`
  entfernt, die Werkzeugbeschreibung verweist auf den Knopf.
- Einen Plan **löst nur der Vorlauf ein** (`services/write_approval` — er merkt den Plan und bietet „Weiter anlegen“
  an). Werkzeug-Schleife (Fingerabdruck-Weg) und Agent-Schleife setzen für Pläne nie einen Schlüssel ein; ihr Aufruf
  bleibt eine Vorschau. Folge: über `/api/agent` mit `write_mode=execute` lassen sich Bäume und Massen-Aufnahmen nur
  vorschlagen, nicht anlegen.
- Ein Baum, dessen Angaben über 256 KB liegen (`MAX_REMEMBERED_ARGS_BYTES`), wird nicht gemerkt und ist im Chat nicht
  bestätigbar (der Chat sagt es: „in kleineren Teilen“) — an der Servergrenze denkbar (250 Knoten × 2000 Zeichen),
  von einem Modell praktisch nicht erzeugt.
- Der Eingang „In WLO anlegen“ aus dem Strukturentwurf bleibt ein eigener Schritt.

## Review

Unabhängiges Review: 3 MAJOR, 6 MINOR, 3 NIT. Behoben:

- „Weiter anlegen“ prüft wie das Einlösen auch ein im Studio verborgenes Werkzeug und die nur lesende Einbettung
  (MAJOR; Text `write.planBlocked`).
- `too_many_plans`: ehrlicher Text, Knopf für einen eigenen offenen Plan (MAJOR; der Merkposten wird nicht mehr
  zurückgelegt — jeder Folgezug, auch „Weiter anlegen“, verwürfe ihn).
- Keine Antwort beim Einlösen → Plan mit dem Bestätigungsschlüssel gemerkt (MAJOR).
- Ein fertiger Plan räumt keinen anderen offenen ab; die Frist kommt aus `expiresAt` des Servers.
- `continuationToken` vom Modell entfernt (`strip_confirm_token`), Beschreibungen angepasst.
- Studio-Sitzungsansicht maskiert auch den Plan-Schlüssel.
- Abgelaufene Pläne fallen zu Zugbeginn weg, „Arbeitsstand löschen“ räumt den Plan ab.
- `tools_called` nennt das Werkzeug nur, wenn es gerufen wurde.

Bewusst gelassen: „fünf“ steht fest im Text (Grenze des Servers, `PLANS_PER_IDENTITY`).

Nachprüfung der Korrekturen: 1 MAJOR, 2 MINOR, 3 NIT. Behoben:
- Pläne löst nur der Vorlauf ein (MAJOR — nach dem Entfernen des `continuationToken` hätte ein in der Schleife
  eingelöster Plan sonst weder Merkposten noch Knopf gehabt).
- Eigener Text, wenn beim ersten Einlösen keine Antwort kam (`write.planUnclearStart`: ob der Plan angelaufen ist,
  ist offen).
- Ein abgelaufener Plan fällt vor der Abnahme-Prüfung weg und wird so mit festgeschrieben.
- Testname, Weiche über `verborgene_werkzeuge()` statt Wortlaut.
Aus dem Review von M6 (zum M5-Nachtrag): ein Plan, dessen Angaben zu groß zum Merken sind, wird nicht mehr
wortlos neu vorgelegt (`write.planTooLarge`); ein abgelaufener Plan wird zu Zugbeginn sofort festgeschrieben; Test für
den Werkzeug-Loop (setzt für Pläne keinen Schlüssel ein, Gegenprobe mit einem gewöhnlichen Werkzeug); die
Beschreibungen sagen, dass ein erneuter Aufruf nur eine neue Vorschau ergibt.
Offen (selten): Drückt die Person „Weiter“, bevor ein langsamer erster Abschnitt den Plan auf dem Server angelegt hat,
kommt `plan_expired`; der später anlaufende Plan bleibt bis zu seiner Frist ohne Knopf.

## Beim Deploy

- MCP-Stand 07.11.2026 vorausgesetzt (die beiden Werkzeuge gibt es vorher nicht).
- Seeds geändert: `03-patterns/m18-kuration.md`, `05-knowledge/mcp-servers.yaml`. Übernehmen mit
  `boerdi import-config --werksabgleich`.

## Tests

- `tests/test_mcp_vertrag_m5.py` (neu, 9): Werkzeuge kuratierend und zweistufig, Argumente, unfertiger und fertiger
  Plan beim Einlösen, `too_many_plans` schreibt nichts, Fortsetzen mit dem Schlüssel, nur dieselbe Person,
  nur mit Schreibrecht, abgelaufener Plan, Direktaktion hinter der Prüfung. Liefen vor dem Code rot.
- Aus dem Review (+12): verborgenes Werkzeug, Knopf bei `too_many_plans`, keine Antwort beim Einlösen (Zeit/Netz),
  keine Antwort beim Fortsetzen, `inProgress`, Frist, anderer Plan bleibt, Frist vom Server, Modell setzt nicht fort,
  Studio-Ansicht, Aufräumen zu Zugbeginn; aus der Nachprüfung: die Agent-Schleife löst keinen Plan ein.
- `tests/test_curation_tools.py`: Beispielwerte für die Listen-Pflichtfelder `tree`/`pairs`.
- `tests/test_untrusted_text.py`: die beiden Werkzeuge eingeordnet (Änderungs-Vorschau).
