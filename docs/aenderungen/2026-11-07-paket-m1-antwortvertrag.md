# Paket M1: Antwortvertrag des MCP im Client (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M1). Anlass: Der WLO-MCP
läuft seit 07.11. mit dem neuen Vertrag. Jeder Fehler trägt `structuredContent.error = {code, message, …}`,
eine unbekannte Lizenz liefert keine Materialien, und `excludeNodeIds` wirkt auch in der Sammlung.

## Was sich ändert

- **Fehler mit Code.** `client.call_mcp_tool_antwort` liefert eine `McpAntwort` mit Text, Art, Code,
  Zusatzfeldern (`outcomeOpen`, `reasons`, `existing` …) und dem strukturierten Teil eines Erfolgs.
  `call_mcp_tool_status` und `call_mcp_tool` bleiben, wie sie waren. Das Modell liest den Code mit:
  `MCP error [not_found]: …` (der Präfix bleibt, `client.fehlercode()` liest ihn).
- **Ausgang offen heißt nicht abgelehnt.** `timeout` mit offenem Ausgang, `not_visible` und `unverified`
  gelten wie „keine Antwort“ (Art `timeout`). Die Schreib-Abnahme sagt dann „in WLO nachsehen“ statt „es
  wurde nichts geändert“. Damit entsteht keine Dublette durch einen zweiten Versuch.
- **Anmeldung.** `login_rejected` gilt immer wie ein abgewiesener Zugang, `login_required` nur mit einem
  persönlichen Block. Ohne einen solchen Block (anonym oder Block der Anlage) bleibt es eine Ablehnung:
  niemand, der nie angemeldet war, liest „deine Anmeldung gilt nicht mehr“.
- **Stapel-Ablage.** Sie kennt die Gründe `batch_unknown`, `batch_expired` und `batch_mismatch` (die alten
  Namen bleiben als Rückfall). Jeder andere Fehler wird ein Code: Anmeldung → `kein_recht`/`nur_angemeldet`,
  offener Timeout → `zu_langsam` (die Datei kann abgelegt sein), sonst `abgewiesen`. Bisher wurde daraus
  ein endgültiger Stand „unverified“.
- **`search_wlo_within_collection`:** `excludeNodeIds` geht an den Server. Die Umrechnung in `skipCount`
  übersprang beliebige Treffer statt der gezeigten.
- **Lizenz.**
  - Eine Lizenz, die wir nicht abbilden, geht unverändert an den Server. Der antwortet mit keinen
    Materialien und Vorschlägen.
  - Sammelwerte („OER-Lizenz“, „freie Lizenzen“) gehen als `OER` hinaus.
  - Der Hinweis sagt jetzt die Wahrheit: „Die Lizenz „CC BY NC“ kenne ich nicht — mit ihr finde ich
    keine Materialien. Meintest du „CC BY-NC“?“. Andere Filter behalten den Satz „allgemeiner gesucht“.
  - Meldet der Server eine unbekannte Lizenz, wird die gemerkte Entität `lizenz` verworfen. Sonst bliebe
    jede Folgesuche leer.
  - `unresolvedFilters` und `facets` werden auch aus `structuredContent` gelesen, falls ein Server den
    Meta-Textblock nicht schickt.
- **`search_skill` fehlt:** erkannt über `unknown_tool`, der Text bleibt Rückfall.

## Beim Deploy

Nichts Besonderes. Neue Bot-Texte: `facets.unresolvedLicense`, `facets.licenseSuggestion`.

## Review

Unabhängiges Review: 3 MAJOR, 6 MINOR, 3 NIT. Alle sind behoben:
- Der Meta-Eintrag aus dem strukturierten Teil ging in eigenen Aufgaben verloren.
- Die Stapel-Ablage behandelte den neuen Fehlervertrag als Ergebnis.
- Ein offener Timeout wurde als „abgelehnt“ gemeldet.
- `login_required` wurde ohne persönlichen Block weggeworfen.
- Sammelwerte gingen roh hinaus.
- Die Lizenz-Entität blieb hängen.
- Das fehlende Werkzeug wurde über den Text erkannt.
- Dazu: Code im Text, Docstrings, Wortlaut.

## Tests

- `tests/test_mcp_vertrag_m1.py` (neu, 16)
- `tests/test_ablage_mcp.py` (+6)
- Bewusst geändert: `test_mcp_tool_defs.py` (`excludeNodeIds` in der Sammlung) und `test_lizenz_abgleich.py`
  (unbekannte Lizenz geht hin, Sammelwert wird `OER`).
- Die neuen Tests liefen vor dem Code rot.
