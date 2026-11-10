# Paket TB-F2: Bericht und Metadaten als Teile (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md`, Gruppe F.

## Was es schon gab

- Der `report` des Flows `node-metadata-write` steht nach dem Abholen im Teil des Auftrags unter
  `outputs.report`, zum Beispiel `{$teil: metadatenlauf, pfad: outputs.report}`.
- Ein `FAILED` ohne Ausgabe führt zu `bei_fehler`, sonst endet der Lauf mit `fehler`.
- Laut B-API-Leitfaden gibt es `outputs` erst bei `SUCCEEDED`. Der Muster-Flow bricht ab, wenn kein
  Node geschrieben wurde. Ein Ablauf führt `bei_fehler` deshalb zu einem Satz wie „Für keine Datei
  konnten Metadaten geschrieben werden“.

## Neu

**Ablauf-Werkzeug `metadaten_lesen`** (`services/ablauf/metadaten.py`). Der Bericht nennt nur, welche
Felder geschrieben wurden, nicht ihre Werte; der Themenbaum aus Inhalten braucht sie.

- **Eingabe:** der ganze Teil `ablage` (`wlo.ablage@1`, vom Ablage-Endpunkt geschrieben, nie vom
  Modell). Das Werkzeug nimmt nur abgelegte Einträge (`stand: stored`) und die früheren eines
  ersetzten Stapels, ohne Doppel, nur gültige UUIDs, höchstens 50.
- **Aufruf:** `get_nodes_details` nur unter der persönlichen Anmeldung des Zuges. Er liest nicht
  aus dem Cache, damit die Werte frisch sind, gleich nachdem Kestra sie geschrieben hat. Der Cache
  hängt an der Person, die frische Antwort wird wieder abgelegt.
- **Ausgabe:** Teil `wlo.metadaten@1`, also `{titel, inhalte: [{node_id, rolle, titel,
  beschreibung (≤300), schlagworte (≤10), faecher, stufen, arten}], fehlend: [nodeId…]}`.
  - Der ganze Teil bleibt unter 60 000 Byte (`teil_verweise.MAX_BYTES` = 64 000). Bei Bedarf
    kürzt der Dienst zuerst die Beschreibungen, dann die Schlagworte, zuletzt Inhalte vom Ende.
  - Kein Teil, dann `bei_fehler`, gibt es in diesen Fällen: ohne Anmeldung, bei einem Fehler des
    Servers, bei einer Antwort, die kein JSON ist, und wenn kein Node lesbar war.
- **Angemeldet** in `DIENSTE`, `DIENST_MCP` (die Sicherheitsprüfung sperrt mit
  `get_nodes_details` auch den Dienst), `DIENST_EINGABE`, `DIENST_AUSGABE` und `LISTEN`. Die
  Werkzeugauswahl im Studio übernimmt es von selbst.

## Prüfung

- `test_tb_f2_metadaten_lesen.py`: 5 Fälle, zuerst rot; nach dem Review 13. Sie decken Auswahl, Kürzung, „ohne
  Cache“, die Grenze von 50, Fehler, Registrierung und einen Ablauf ohne Befund ab.
- Mit `test_ablauf_werkzeuge_ki`, `test_ablauf_pruefung`, `test_ablauf_beispiele`,
  `test_ablauf_datenfluss`, `test_ablauf_datensicht`, `test_ablauf_simulation` und
  `test_ablauf_studio_k2c1`: 154 grün.
- ruff ist sauber.

## Review (unabhängig) und Behebung

1 MAJOR, 4 MINOR, 2 NIT.

- **MAJOR 1:** Der Server meldet unlesbare Nodes in `failed` und schickt `results: {}`. Daraus
  entstand ein leerer Teil, und der Ablauf lief still weiter. Jetzt entsteht kein Teil, also
  `bei_fehler`.
- **MINOR 2:**
  - Ohne `has_personal_auth()` gibt es keinen Aufruf, sonst läse der Server anonym oder mit dem
    Dienstkonto.
  - Neuer Prüfbefund `metadaten_anmeldung`: das Werkzeug braucht die Voraussetzung `anmeldung`.
- **MINOR 3:** Die Begründung für „ohne Cache“ war falsch. Der Cache hängt an der Person, der
  Grund ist Frische. Doku und Docstring sind korrigiert.
- **MINOR 4:** Bei 50 Nodes konnte der Teil bis ~185 KB groß werden, über der Grenze für
  Folgeschritte. Jetzt wird er auf 60 000 Byte eingepasst.
- **MINOR 7:** Weitere Tests:
  - nichts lesbar,
  - kein JSON,
  - `results` als Liste,
  - ohne Anmeldung,
  - der Prüfbefund,
  - die Größe,
  - der Vorrang der abgelegten Einträge vor den früheren an der Grenze.
- **NIT 5/6:** Der Teil trägt `titel` („Metadaten zu N Inhalten“) für Akte und KI-Verweis.
  `fehlend` steht in `LISTEN`. Der Modulkopf von `werkzeuge.py` nennt Dienste mit Netz.

Nicht übernommen: Den Weg über den Treiber (gesperrtes Werkzeug → `bei_fehler`) deckt schon
`test_abdeckung_m1` (Zeile ~231) für `abdeckung_zaehlen` ab. Es ist derselbe Code (`DIENST_MCP`).

## Offen (bewusst)

- Das Limit je Job (N14) ist noch nicht umgesetzt. Ein Stapel hat bis zu 200 Dateien.
  `metadaten_lesen` liest 50, der Rest steht seit dem Querschnitts-Review F/T in `fehlend`.
- Seit dem Querschnitts-Review F/T liest der Dienst nur den jetzigen Stapel, nicht `frueher`.
  Das sind dieselben Dateien, die der Flow bekommt.
