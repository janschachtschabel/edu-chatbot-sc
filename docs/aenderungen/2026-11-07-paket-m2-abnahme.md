# Paket M2: Schreib-Abnahme nach dem neuen MCP-Vertrag (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M2), aufbauend auf M1
(`McpAntwort`, `error.code`).

## Was sich ändert

- **Schlüssel aus `structuredContent.confirm`.** Muster- und Agent-Zug nehmen den Schlüssel, den der
  Server für GENAU diesen Aufruf geprägt hat. Zugeordnet wird über Werkzeug und Fingerabdruck der
  Angaben. Der Vorschautext ist nur noch Rückfall für ältere Server, und aus einer Fehlermeldung wird
  nie ein Schlüssel gelesen (ein fremder Titel darin wäre ein Köder).
- **Einlösen über `error.code`:**
  - `confirm_expired/unknown/mismatch` und `plan_expired/mismatch`: Geschrieben wurde nichts. Die Abnahme
    legt dieselben Angaben **ohne** Schlüssel neu vor (eine Vorschau, die nichts schreibt) und zeigt sie
    mit Bestätigungs-Chip („Die Freigabe war nicht mehr gültig …“). Gebunden an dieselbe Person und
    dieselben Angaben.
  - Kommt auf diese neue Vorschau keine Antwort, sagt die Abnahme „Freigabe war nicht mehr gültig“, nicht
    „vielleicht angekommen“. Meldet der Server `unchanged`, kommt „Da gibt es nichts zu ändern“.
  - `login_required`/`login_rejected` ergeben „Dafür braucht WLO deine eigene Anmeldung“.
  - `exists` nennt den vorhandenen Datensatz samt Kennung.
  - Andere Ablehnungen nennen den Grund des Servers, aber nur fachliche (`refused`, `invalid_input`,
    `not_found`, `not_a_collection`, `not_checked`) und nur auf Deutsch (der Servertext ist deutsch).
    Repository-Interna (`upstream_error`, `forbidden`) bleiben im Protokoll.
  - Ein offener Ausgang (M1) bleibt „bitte in WLO nachsehen“.

## Bewusst anders als geplant

- Der Vorschau-Kasten bleibt die Textfassung des Servers (`preview_for_display`) und wird nicht aus
  `preview.fields` gebaut. Die Textfassung trägt die ⚠-Hinweise, und ihr Fehlverhalten ist sicher: sie
  zeigt eher zu viel als zu wenig.

## Beim Deploy

Nichts Besonderes. Neue Bot-Texte: `write.confirmRenewed`, `write.confirmExpired`, `write.loginNeeded`,
`write.rejectedReason`, `write.existsHint`, `write.nothingToChange` (DE/EN).

## Review

Unabhängiges Review: Die Sicherheitsregel hält (die neue Vorschau schreibt nie, nichts wird ohne
Abnahme frei). Es gab 1 MAJOR, 8 MINOR und 2 NIT, alle behoben:
- Server-Interna wurden ungefiltert gezeigt.
- Eine ausbleibende neue Vorschau wurde als „vielleicht angekommen“ gemeldet.
- Der Kasten zeigte nur eine gekürzte Kopie.
- Der Schlüssel wurde nur über den Werkzeugnamen zugeordnet.
- Für `unchanged` fehlte ein eigener Satz.
- Bei einer Dublette fehlte die Kennung.
- Ein Köder aus einer Fehlermeldung wurde als Schlüssel gelesen.
- Dazu Testlücken und Doku.

Vor M2 da: `_zustimmung_unklar` zeigt die gekürzte Kopie (bis 4000 Zeichen), so belassen.

## Tests

- `tests/test_mcp_vertrag_m2.py` (neu, 22)
- Attrappen in `tests/test_write_approval.py` und `tests/test_preflight_node.py` auf
  `call_mcp_tool_antwort` umgestellt (`als_antwort`)
- Die neuen Tests liefen vor dem Code rot.
