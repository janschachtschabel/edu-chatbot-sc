# Paket Q2: Abläufe — Befunde des Querschnitts-Reviews (2026-11-06)

Grundlage: [`../audits/2026-11-06-querschnitts-review.md`](../audits/2026-11-06-querschnitts-review.md),
Plan [`../plans/2026-11-06-querschnitts-befunde.md`](../plans/2026-11-06-querschnitts-befunde.md) (Q2).

## Was sich ändert

- **M4 — Wendung prüft die ganze Nachricht.** Löst eine Wendung einen Ablauf aus, liest die
  Sicherheitsprüfung die ganze Nachricht (`sicherheits_text`) statt der ersten 500 Zeichen einer
  Direktaktion. Eine Krise weiter hinten führt wieder zu M01.
- **M5 — kein veralteter Lauf in der Sitzung.** Frühe Antworten (`nur_text`) schreiben die Entities fest;
  in den „unbekannt“-Zweigen (`weiter_nach_ki`, `pruefen`) und in `wartet_auf` folgt der Verweis dem
  Vorgang — eine zweite Sitzung derselben Person kann den Lauf weitergeschoben haben.
- **M7 — keine offene Lese-Transaktion über Netzaufrufe.** Vor jedem Treiber-Aufruf (`basis.rechne`), vor
  der b-api-Abfrage in `pruefen` und nach dem Lesen in `wartet_auf` (vor der Moderation) geht die
  Verbindung frei (`commit`, Objekte bleiben gültig).
- **Aufträge:** `unbekannt`/`aus` gelten als gescheitert (`bei_fehler`), `abgewiesen` beendet den Lauf mit
  Hinweis (kein Endlos-Knopf, kein gesperrter Neustart); ein neuer Lauf schließt den Auftrag des alten; die
  Größengrenze der Ausgabe zählt Bytes.
- **Wendung** startet nur mit erfüllten Voraussetzungen (eine anonyme Frage bleibt eine Frage).
- **Katalog:** Längengrenzen für `titel` (120), `wann`/`nicht_wann` (höchstens 5 zu je 200 Zeichen); je
  Speicherstand einmal geprüft (Streuwert des Inhalts).
- **KI-Budget** eines Agent-Schritts wird erst nach einem gelungenen Neustart zurückgesetzt.

## Beim Deploy

- **Wartende Läufe brechen einmal ab.** `fassung` lässt jetzt `None`-Felder weg — die Fassung jedes
  Ablaufs ändert sich dadurch genau einmal, wartende Läufe gelten beim ersten Zug danach als „geändert“
  und werden abgebrochen. Heute gibt es keine im Betrieb (Abläufe sind noch nicht live).
- **Längengrenzen:** ein gespeicherter Katalog mit längerem Titel oder mehr als fünf `wann` fällt zur
  Laufzeit still weg und lässt sich im Studio erst nach dem Kürzen speichern (422). Der mitgelieferte Seed
  hält die Grenzen (Titel 22/23 Zeichen, ein `wann` mit 64).

## Bewusst anders als geplant

- `wartet_auf` bricht einen nicht mehr fortsetzbaren Lauf weiter **vor** der Sicherheitsprüfung ab — es
  ist nur Aufräumen von Zustand, nichts erreicht die Person oder ein Modell; der Docstring sagt es jetzt.
- Der Katalog-Schlüssel ist ein Streuwert des Inhalts, nicht die Version des Store-Cache (bei der heutigen
  Größe vernachlässigbar; Review Q2, Befund 9).

## Tests

`test_querschnitt_ablaeufe.py` (neu: M5 zwei Wege, M7 Reihenfolge, endgültige Gründe, abgewiesen,
vorübergehend, neuer Lauf, Wendung ohne Voraussetzung, Fassung, Längen, Zwischenspeicher, Review Q2),
`test_preflight_node.py` (M4 lange Nachricht, „Stand prüfen“ durch die Sicherheitsprüfung),
`test_auftraege_client.py` (Bytes), `test_ablauf_ki_schritt.py` (längster erlaubter Titel). Studio-Fixture
der Bereichs-Schemata neu erzeugt (`maxLength`/`maxItems`).

## Review Q2 (unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 0 MAJOR, 3 MINOR, 6 NIT. Gehalten: M4 ohne Wirkung auf den gewöhnlichen Weg; Freigabe
lässt ORM-Objekte gültig und schreibt nichts Unbeabsichtigtes; kein Doppelschreiben (Sitzungssperre,
frühe Antworten enden ohne `persist`); Zusammenspiel mit dem automatischen Abholen; Zwischenspeicher ohne
geteilte Veränderung; `exclude_none` ohne Bedeutungswechsel; `ENDGUELTIG` passt zum Client.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | MINOR | `abgewiesen` ließ den Lauf warten (Neustart gesperrt, Knopf kam wieder) | Lauf wird abgebrochen — Test |
| 2 | MINOR | `wartet_auf` frischte einen weitergeschobenen Lauf nicht auf | Verweis folgt dem Vorgang — Test |
| 3 | MINOR | Deploy-Notiz zu `fassung` fehlte, Kommentar ungenau | diese Notiz, Kommentar präzisiert |
| 4 | NIT | KI-Budget vor dem Neustart zurückgesetzt | erst nach dem Festhalten — Test |
| 5 | NIT | Zwischenspeicher-Test hing an der Reihenfolge | Fixture setzt ihn zurück |
| 6 | NIT | Testlücken (`weiter_nach_ki`, Fehlerzweige) | ergänzt; Postgres-Tests folgen in Q4 |
| 7 | NIT | `wartet_auf` vor dem Tor nur dokumentiert | hier als bewusste Abweichung vermerkt |
| 8 | NIT | Kommentar zum Abholen und der Abnahme veraltet | angeglichen |
| 9 | NIT | Katalog wird je Aufruf serialisiert | bewusst so (siehe oben) |
