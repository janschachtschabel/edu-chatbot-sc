# MCP-Antwort, zweite Runde: der Chatbot am Stand vom 14.11.2026 abends (2026-11-15)

Anlass: die Antwort des MCP-Entwicklers „Sammlungsstrukturen, zweite Runde“ (14.11.2026). Sie
nennt neben seinen Antworten auf unsere zwei Funde alles, was sich durch sein Audit für einen
Client sichtbar geändert hat. Der Stand ist nicht bereitgestellt; er liegt als Arbeitskopie vor.

## Vorgehen

1. Jede Aussage am Quelltext des MCP geprüft und, wo es ohne Anmeldung geht, am lokal
   gestarteten Server gemessen (gegen das Staging-Repository, nur lesend).
2. Je Aussage die betroffene Stelle im Chatbot gesucht und eingeordnet.
3. Behoben, wo der Chatbot mit dem neuen Stand falsch reagierte (MR-1 bis MR-4).

## Einordnung

| Punkt der Antwort | Chatbot | Paket |
|---|---|---|
| Ablehnung des Repositorys bei den Schreib-Einzelwerkzeugen: `forbidden`, `not_found`, `refused` mit `outcomeOpen: false` | **falsch:** neue Vorschau mit „die Freigabe war nicht mehr gültig“, bei jedem Ja wieder | MR-1 |
| `not_in_collection`, `forbidden` in der Vorschau | kein Satz für die Person | MR-1 |
| `wlo_create_collection` mit `recordExists` | Satz sprach von „Datensatz“ und „Datei“ | MR-1 |
| `get_wlo_content_text`: `text_unreadable` | kein Satz, fünf Minuten im Cache | MR-2 |
| `internal_error` | Themenseiten hielten ihn für „noch leer“; der Themenbaum wiederholte ihn | MR-2 |
| `get_related_content`: `siblingsUnread` | fünf Minuten im Cache | MR-2 |
| Neue Grenz-Felder und -Sätze beim Lesen (`scanCapped`, `totalIsUpperBound`, `truncated` …) | fielen in der Kürzung für die KI weg | MR-3 |
| Fachportal über `collection` | Beschreibung der Baumliste schickte die KI zur Kennung | MR-3 |
| `wlo_store_batch_manifest`: `not_checked` | als „abgewiesen“ gemeldet | MR-4 |
| `upstream_busy` für 429/503, offen nach der Einlösung | passt | – |
| `unchanged` ohne Schlüssel, 409 als Erfolg, `confirm_expired` wiederholt, `preview.action: delete` | passt | – |
| Pläne: `pending`, später `added`; Baumknoten `pending`; „offen — Ausgang unbekannt“ | passt (gelesen werden `complete`, `continuationToken`, `expiresAt`) | – |
| `proposal_not_marked` mit `error.mark` | der Satz stimmt für beide Werte | – |
| Hinweiszeile vor Fremdtext (`get_url_text`, `get_wlo_content_text`) | deterministisch nicht betroffen (M17 liest das Feld `text` im JSON) | nach Deploy prüfen |
| `list_collection_tree`: `nextSkipCount` höchstens 500, `skipLimitReached` | passt (SW-4) | – |
| `get_compendium_text` im JSON-Format, Skill-Katalog, `search`, REST `/api/*` | nutzt der Chatbot nicht oder nicht in dieser Form | – |

## Entscheide

| Nr. | Frage | Entscheid |
|---|---|---|
| ME-1 | Wann legt der Chatbot nach einem Fehler beim Einlösen von selbst neu vor? | **Nur, wenn der Schlüssel nicht (mehr) gilt:** `confirm_expired`, `confirm_mismatch` vor der Einlösung, `changed_since_preview` (der Datensatz hat sich seit der Vorschau geändert). Jede andere Antwort mit „nichts geschrieben“ ist eine Ablehnung, die mit Grund gezeigt wird; die Person bittet selbst noch einmal. Das gilt auch, wenn WLO nur nicht gelesen werden konnte (`not_checked`, `unreadable`, `upstream_error`): Hinter denselben Codes stehen beim MCP dauerhafte Gründe (ein abgelehnter Upload beim Volltext, eine Sammlung mit mehr Einträgen, als er durchsucht), und „neu vorlegen“ lief dort in eine Schleife. Ein offener Ausgang heißt „bitte nachsehen“; bei einem Plan-Werkzeug „Plan fortsetzen“, auch nach einem Unfall im Server ohne `outcomeOpen`. |
| ME-2 | Welchen Grund liest die Person? | Den Satz des Chatbots zum Code. Den Text des Servers nur auf Deutsch und nur, wenn er weder die Antwort des Repositorys trägt („HTTP 400: …“) noch den Namen eines internen Abrufs („getCollectionContents failed: 503“). Erkannt wird das am Wortlaut; ein Feld dafür wäre besser (Wunsch an den Entwickler). Bei `upstream_error` entscheidet der Status im Text: 4xx außer 429 ist „so nicht angenommen“, alles andere „ließ sich gerade nicht prüfen“. |
| ME-3 | `text_unreadable` und `siblingsUnread` im Cache | Nur kurz, wie jeder Ausfall. Bei diesen zwei Werkzeugen zählt nur das Feld, nie eine Wendung im Text: Ein Volltext ist Fremdtext. |
| ME-4 | Grenz-Hinweise des Servers | Jede Zeile, die hinter dem JSON-Umschlag am Zeilenanfang mit „Hinweis: “ beginnt, reist mit zur KI (mit den Ausfall-Sätzen zusammen höchstens fünf, Ausfall zuerst). Nicht: eingerückte Zeilen (dort steht der Skill-Katalog einer Sammlung mit fremden Titeln), Markdown-Antworten ohne Umschlag (dort stehen Beschreibungen der Treffer im selben Text) und die Mehrfachsuche. Für den Cache sind Grenzen kein Ausfall. |
| ME-5 | `internal_error` | Bei den Themenseiten ein Ausfall („hat gerade nicht geantwortet“). Der Themenbaum wiederholt ihn nicht. Sonst wie bisher: keine Wiederholung im Client, nach einer Einlösung „bitte nachsehen“. |
| ME-6 | Ablage `not_checked` | „Später noch einmal“ (503) statt „abgewiesen“ (422). Das Widget zeigt beides gleich („Vorgang fehlt“) und versucht den Abschluss nicht erneut; das bleibt offen. |

## Bewusst nicht gebaut

- `outcomeOpen` je Eintrag eines Plans im Ablauf (`freigabe_ergebnis`): Sind alle Einträge mit
  offenem Ausgang gescheitert, geht der Lauf zu `bei_fehler`, als sei sicher nichts geschehen.
- `error.upload` am Datei-Upload: Der Code genügt für den Satz.
- Der Ausfall-Satz von `get_compendium_text` landet im Seitenkontext der Sitzung als Text.
- Die Lizenz-Zeile der Suche („ⓘ 4 von 25 geprüften Treffern …“) geht im Muster-Weg weiter am
  Deckel verloren.
- `portalsUnread`: Über `incomplete` zählt es schon als „unvollständig“.

## Prüfung

- Gezielte Tests je Paket (`tests/test_mcp_antwort_runde2.py`), vor dem Upload die volle Suite.
- Live nur lesend gegen den lokal gestarteten Stand.
- Nicht prüfbar vor dem Deploy: jeder Schreibweg (braucht eine Anmeldung am neuen Stand) und ob
  die KI die Hinweiszeile vor Fremdtext in einen Volltext oder ein Material übernimmt.

## Fortschritt

- MR-1 bis MR-4: umgesetzt 15.11. (Notiz `aenderungen/2026-11-15-mcp-antwort-runde-2.md`)
