# Paket K2d-3 — MCP W1–W3 angebunden: Volltexte und Metadaten vieler Datensätze (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2d,
Teil K2d-3 (Nutzer-Entscheid 2026-11-08: „W4 jetzt, Rest mit K2d“). Grundlage ist der MCP-Stand vom 08.11.:
`src/tools/curation-fulltext*.ts` und `curation-update-many.ts` im Klon `wlo-mcp-server-sc`, nur gelesen.

## Was sich ändert

Drei neue kuratierende Werkzeuge stehen im Agent-Modus und im Muster M18 bereit. Sie arbeiten nur mit Anmeldung
und hinter derselben Abnahme wie jede Änderung.

| Werkzeug | Was | Art |
|---|---|---|
| `wlo_attach_fulltext` (W1) | Ein Volltext (Markdown) im `textContent` eines Datensatzes; `replace` ersetzt einen vorhandenen | zweistufig: Vorschau → „ja“ → der Chat löst ein |
| `wlo_attach_fulltexts` (W2) | Bis zu 200 Volltexte unter **einer** Bestätigung | **Plan** wie M5: der Vorlauf löst ein, „Weiter anlegen“ setzt fort |
| `wlo_update_contents` (W3) | Metadaten von bis zu 200 Datensätzen unter **einer** Bestätigung | **Plan**; der Server schreibt manche Felder direkt und hinterlegt die redaktionellen als Vorschlag (`reason`) |

- **`would_replace_file` ist kein Fehler** (Nutzer-Entscheid). Ein Datensatz, der schon Inhalt trägt (Datei oder
  Text), bekommt vom Server vorerst keinen Volltext, bis das MCP-Team gemessen hat, dass die Datei erhalten bleibt.
  - Die Beschreibungen von W1/W2 und die Tabelle in M18 sagen dem Modell, das als „hier noch nicht möglich, beim
    MCP-Team vorgemerkt“ zu nennen, nicht als Fehlschlag. Ein Nachtragen versprechen sie nicht, denn gemerkt
    wird der Text nirgends (Review, Befund 3).
  - Technisch bleibt es eine Ablehnung des Servers. Es geht kein Alarm los, nichts wird geschrieben, und nach dem
    „ja“ steht der Grund des Servers in der Antwort.
  - `link_record` (verlinkter Datensatz, dessen Text das Repository von der Webseite liest) ordnen die
    Beschreibungen ebenso ein.
- **Argumente:** Nur die Felder, die der Server kennt, gehen zu ihm, und keine leeren Werte. Ein leeres Feld
  weist bei W3 sonst den ganzen Aufruf ab; unbekannte Felder entfernt der Server still.
  - W2: `nodeId`, `markdown`, `source` (`binary`, `website`, `manual`), `sourceUrl`, `language` je Eintrag.
  - W3: `nodeId`, `reason` und die 13 Metadatenfelder wie bei `wlo_update_content`, ohne Inhalt und Datei.
  - Einen `confirmToken` oder `continuationToken` setzt nie das Modell (wie M5).
- Die übrigen Codes (`changed_since_preview`, `upstream_busy` mit `retryAfter`, `outcomeOpen`) laufen über die
  vorhandene Einordnung (Pakete M1, S2, S3).

## Geändert

- `domain/write_confirm.py`: die drei in `CURATION_TOOLS`, W2/W3 in `PLAN_TOOLS`.
- `api/schemas_mcp_curation.py` (Fassade `api/schemas.py`): `FulltextAttachArgs`, `FulltextsAttachArgs`,
  `ContentsUpdateArgs`; Felder je Eintrag gefiltert.
- `services/mcp/tool_defs_curation.py`: die drei Definitionen, `_VORGEMERKT`.
- Seeds:
  - `05-knowledge/mcp-servers.yaml`: Freigabe der drei Werkzeuge;
  - `03-patterns/m18-kuration.md`: Werkzeugliste, Ausnahme „Pläne“, zwei Zeilen in der Reihenfolge-Tabelle.
- Doku: `architektur.md`, `mcp-und-anmeldung.md`.

## Bewusst so

- **Nicht als Ablaufschritt.** Ein `werkzeug`-Schritt ruft heute nur lesende MCP-Werkzeuge
  (`werkzeuge.LESENDE_MCP`). Schreibende Schritte mit Freigabe sind Paket S. Bis dahin hängt ein Ablauf die
  Volltexte über Kestra an (Flow 1) oder übergibt an den Agent-Modus.
- **Große Mengen:** Ein Plan, dessen Angaben 256 KB übersteigen (`MAX_REMEMBERED_ARGS_BYTES`), ist im Chat nicht
  bestätigbar („in kleineren Teilen“, `write.planTooLarge`, seit M5). Bei Volltexten ist das schnell erreicht; der
  Server selbst nimmt mehr.
- **Kein Feld `mode`** bei W3. Der Server entscheidet je Feld, ob er schreibt oder vorschlägt (MCP-Stand), anders
  als im Auftrag (F5) gefragt.
- **Am Staging** schreibt der Server derzeit keinen Inhalt (500 seit 06.11., MCP-Hinweis). Live wirkt W1/W2 erst
  nach dem Repository-Fix und dem MCP-Deploy.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 4 mittel, 6 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Leere Werte (`""`, `[]`) in Einträgen gingen zum Server; bei W3 weist ein leeres Feld den ganzen Aufruf ab. | `_nur` lässt leere Werte weg. |
| Ein zu großer Plan (> 256 KB, etwa fünf Volltexte) fiel erst nach dem „ja“ auf. | Schon bei der Vorschau: keine Box, kein Merkposten; das Modell liest „in kleinere Aufrufe aufteilen“ (`PLAN_ZU_GROSS_TEXT`, Werkzeug- und Agent-Schleife). |
| „vorgemerkt und wird nachgetragen“ versprach etwas, das niemand merkt; `would_replace_file` kommt auch bei vorhandenem Text. | Ehrlich formuliert: hier noch nicht möglich, beim MCP-Team vorgemerkt, kein Nachtragen versprechen; „trägt schon Inhalt“. |
| Zugakte speicherte je Volltext 1000 Zeichen, das Protokoll (mit `LOG_CONTENT`) volle Texte in Einträgen. | `markdown` nur als Länge; `_args_for_log` kürzt auch in Listen und Einträgen. |
| `link_record` ohne Einordnung; `replace` ist unter der Sperre nie möglich. | Beschreibungen ergänzt. |
| Nach dem „ja“ las die Person bei `would_replace_file` nur „WLO hat abgelehnt“ ohne Grund. | Der Grund des Servers steht da (`would_replace_file`, `link_record`, `exists`). |
| `write.planExpired`/`planTooLarge` sprachen von Sammlungen bzw. „anlegen“. | Werkzeugneutral. |
| Veraltete Zählungen in Kommentaren; „der Server prüft streng“ stimmt für W2/W3 nicht. | Korrigiert. |
| Testlücken | Tests für leere Werte, zu großen Plan, Zugakte/Protokoll, Grund, Beschreibung. |

Offen und in `offene-befunde-und-todo.md`: Der Knopf heißt auch bei Metadaten „Weiter anlegen“ (die Beschriftung
steht in Seeds und Doku). `write.busy` nennt das `retryAfter` des Servers nicht (W2 mit vollem Server-Speicher:
60 s). Ein Durchlauf von W2/W3 durch Vorlauf und „Weiter anlegen“ ist nur über den generischen Plan-Weg (M5-Tests)
abgedeckt.

## Zweites Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 4 klein, 2 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Der Hinweis „zu großer Plan“ lud zu mehreren Vorschauen in einem Zug ein — nur die letzte überlebt, die anderen verfielen still. | Der Text verlangt, nur den ersten Teil vorzulegen und den nächsten nach dessen Abschluss; M18 sagt es auch. |
| M18 empfahl bei W3 `get_node_details` je Datensatz (bis 200 Aufrufe). | `get_nodes_details` in M18 freigegeben, die Zeile liest alle in einem Aufruf. |
| `_nur` ließ `"  "` und `[""]` durch — der Server kürzt sie zu „kein Wert“ und weist bei W3 den ganzen Aufruf ab. | Leer ist auch nur Leerzeichen; leere Listeneinträge fallen weg, eine dann leere Liste ganz. |
| Der Weg „zu großer Plan“ in der Werkzeug-Schleife war ungetestet. | Test: kein Merkposten, keine Vorschau, das Modell liest den Hinweis ohne Schlüssel. |
| Die Grenze `reason` ≤ 500 Zeichen (sonst kippt der ganze Aufruf) stand nicht in der Beschreibung. | Ergänzt. |
| „256 KB“ zählt Zeichen, nicht Bytes. | Text sagt „rund 256 000 Zeichen“. |

Bewusst nicht: die übrigen Längengrenzen von W2 je Eintrag (`nodeId` 200, `sourceUrl` 2000, `language` 10)
— sie trifft ein Modell praktisch nie, und der Server meldet sie.

## Tests

- neu `backend/tests/test_mcp_volltext_k2d3.py` (11, davon 5 aus dem Review):
  - kuratierend und zweistufig, W2/W3 als Pläne;
  - Beschreibungen (Pflichtfelder, `source`-Auswahl, „vorgemerkt“, Plan-Satz, kein Schlüssel-Feld);
  - Argumente je Werkzeug;
  - Seeds.
- angepasst:
  - `test_curation_tools.py`: Beispielwerte `source` und `items`;
  - `test_untrusted_text.py`: die drei als Änderungs-Vorschau eingeordnet.
- grün: die Wächter der Kataloge und Seeds (`test_mcp_tool_defs`, `test_config_seed_tree`, `test_seed_*`,
  `test_mcp_vertrag_m1…m6`, `test_write_confirm`, `test_agent_tools`).

- Volle Suiten nach dem zweiten Review K2d-1…3: Backend ohne Fehler (Lauf mit `-x`), Studio 2040 grün, eslint und ruff sauber.

## Betrieb

- Seeds geändert: `boerdi import-config --werksabgleich` übernimmt `m18-kuration.md` und `mcp-servers.yaml`.
- MCP-Stand 08.11.2026 vorausgesetzt, denn vorher gibt es die drei Werkzeuge nicht. Ein älterer MCP meldet sie
  als unbekannt.
