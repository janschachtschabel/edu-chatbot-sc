# Paket AS-7a — Führungen in Abläufen, Backend (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5m. Die Entscheide F-1 bis F-8 sind dort
festgehalten.

## Was ein Ablauf jetzt kann

- **Schritt `seite`** (F-1, F-2): Er zeigt einen Text und einen Chip, der zu einer Seite führt
  (`url`: Pfad mit `/` oder `https://`; `label` je Sprache).
  - Mit `ankunft` (Pfadmuster) wartet der Lauf (`wartet_seite`), bis die Person auf einer
    passenden Seite ist. Steht sie schon dort, geht es gleich weiter.
  - Ohne `ankunft` steht der Chip unter der Antwort, und der Lauf geht sofort weiter.
- **Bedingung `wenn_seite`** (F-6): Eine Regel der Verzweigung prüft die Seite des Zugs gegen
  Pfadmuster. Sie steht allein in ihrer Regel, wie `wenn_wert`.
- **Auslöser `seite`** (F-7): Modell und Prüfung (Muster sind Pflicht). Das Angebot unter der
  Begrüßung kommt mit AS-7b.
- **Pfadmuster** (F-3, `domain/seiten_muster.py`):
  - `*` als einziger Platzhalter, sonst wörtlich, ohne reguläre Ausdrücke;
  - verglichen wird der normalisierte Pfad wie bei der Tour (ohne Host, Anfrage und Anker, klein,
    ohne Schrägstrich am Ende);
  - höchstens 10 je Liste, je 200 Zeichen.

## Wie die Ankunft ankommt

- **Seiten-Ping** (F-4): `page_event: ablauf_seite`, ein Hintergrund-Zug wie Tour-Tick und
  Kontext-Ping (`domain/hintergrund_zug.ist_seiten_ping`).
  - Der neue frühe Knoten `graph/nodes/ablauf_seite` (nach `tour`) beantwortet ihn immer selbst.
    Dabei wird keine Nutzernachricht gespeichert, und weder Sicherheitsprüfung noch Modell laufen.
  - Passt die Seite, geht der Lauf weiter (`services/ablauf/seite_zug.angekommen`). Sonst ist die
    Antwort leer.
  - Das Widget schickt den Ping ab AS-7b.
- **Chip** `__fuehrung__|Label|URL` (F-2), mit eigenem Präfix: Der Widget-Nachlauf macht
  `__guide__`-Chips außerhalb der Tour zu Links oder entfernt sie. Wie die Chips einer Wahl
  übersteht er jede Höchstzahl (`domain/wahl_knopf.ist_wahl_knopf`).
- **Unter jeder Antwort** (F-5): Solange ein `seite`-Schritt wartet, steht sein Chip auch unter
  Antworten der KI (`turn_assembly`, `seite_zug.aktueller_knopf`).

## Prüfung, Simulation, Studio

- **Prüfung** (`pruefung._seite`, `url_ok`, `muster_befunde`):
  - `url` als Pfad mit `/` (nicht `//`) oder als `https://`-Adresse ohne Zugangsdaten, ohne `|`
    und ohne Leerraum;
  - `label` auf Deutsch;
  - die Muster;
  - `url`, `label` und `ankunft` nur bei `seite`;
  - der Auslöser `seite` braucht Muster.
- **Simulation:** Testfall `seite` (Seite beim Start, für `wenn_seite`) und Eingabe `seite` an einem
  wartenden `seite`-Schritt. Eine Seite, die nicht passt, ist eine Abweichung.
- **Studio:** Die Felder erscheinen über `NurBei` nur bei `seite`. Feldtexte de/en sind da.
  Regel-Editor und Ablaufbild folgen mit AS-7b.

## Tests

- `test_ablauf_seite.py`: Muster, Prüfung, Treiber, `wenn_seite`, Simulation.
- `test_ablauf_seite_zug.py`: Chip, Hintergrund-Zug, Start, Ping mit und ohne Treffer, Chip
  unter jeder Antwort, ohne `ankunft`.
- Nach dem Review sind es zusammen 72 Tests.
- Angepasst wurden der Schema-Wächter `test_ablauf_studio_k2c1.py` und die Knotenfolge in
  `test_graph_build.py`.
- `openapi-v1.json` ist neu erzeugt; `openapi-public.json` ist unverändert.

## Review AS-7a (10.11., unabhängig)

1 kritischer, 1 schwerer, 6 mittlere Befunde und eine Kleinigkeit; alle am Code geprüft und behoben.
Wegen des kritischen Befunds folgt ein zweites, unabhängiges Review.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | kritisch | `*` wurde zu `.*` in Pythons `re`. Mit mehreren `*` und einer langen, fast passenden Seite des Clients brauchte der Vergleich O(nᵏ), etwa beim Seiten-Ping oder bei `wenn_seite`. Das blockierte die Event-Loop. Nachgestellt: Der Test hing. | Glob in linearer Zeit (`_passt_eins`: Anfang und Ende fest, Mittelstücke mit `str.find`); die Seite wird auf 1000 Zeichen gekappt. | 50 000 Zeichen gegen `/*a*a*a*b` in < 0,5 s; zehn Fälle für die Richtigkeit; Kappung |
| 2 | schwer | `zug.lauf_wartet` kannte `wartet_seite` nicht. Eine Wendung oder Modul-Antwort ersetzte den wartenden Lauf ohne Rückfrage. | Eine gemeinsame Liste `treiber.WARTEND` für `zug`, `zug_basis`, `simulation` und `arbeitsstand_verweis`. | `lauf_wartet` bei `wartet_seite`; der Status steht in der Liste |
| 3 | mittel | Bei laufender Tour beendete der Ping die Tour oder galt als Gruppenantwort. In `setup` war er dann kein Hintergrund-Zug. | Die Tour lässt den Ping durch; `setup` behandelt ihn immer als Hintergrund-Zug. | Ping bei aktiver Tour |
| 4 | mittel | `seite` mit `ankunft` zählte in der Prüfung als Halt, läuft aber durch, wenn die Person schon dort ist. | `seite` ist kein Halt; ein Kreis über ihn ist ein Befund. | Kreis `seite → nachricht → seite` |
| 5 | mittel | `/\host` wurde angenommen (Browser machen daraus eine fremde Adresse). Geprüft wurde die getrimmte URL, in den Chip kam die ungetrimmte. | `\` und Steuerzeichen werden abgewiesen; das Modell trimmt `url`. | `//`, `/\`, Leerraum, Tab, NUL, Trennstrich, Trimmen |
| 6 | mittel | Ein `seite`-Schritt ohne Text gab nach dem Ping eine leere, unsichtbare Antwort. | `text.de` ist bei `seite` Pflicht. | Befund ohne Text |
| 7 | mittel | `wenn_seite: []` galt als Bedingung, die nie greift, und blieb ohne Befund. | Eine leere Liste ist nicht gesetzt, die Regel bekommt dann den Befund ohne Bedingung. | leere Liste |
| 8 | mittel | Die Kennzeile an die KI nannte einen Lauf bei `wartet_seite` nicht. | Gemeinsame Liste (wie Befund 2). | Kennzeile |
| 9 | klein | Ohne Nachfolger endete `weiter_seite` mit `fertig`, `_rechne` mit `fehler`. Ein veralteter Kommentar. Zwei `seite`-Schritte in einem Zug zeigten nur einen Chip. | `fehler` wie `_rechne`; `navigation` ist eine Liste; Kommentar angepasst. | zwei Wege in einem Zug |

## Zweites Review (10.11., unabhängig)

Alle 9 Behebungen sind vollständig und korrekt. Neu gefunden: 0 kritisch, 1 schwer, 2 mittel,
2 klein. Alle sind behoben.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | schwer | Der Pfad wird ohne Schrägstrich am Ende verglichen. Das naheliegende Muster `/mitmachen/*` passte deshalb nicht auf die Einstiegsseite `/mitmachen/`, der Lauf hätte still gewartet. | Ein Muster auf `/*` passt auch auf seinen Stamm. Die Prüfung meldet `seite_unerreichbar`, wenn das eigene Ziel (`url`) keine Ankunft erreicht. Tests mit Stamm, Unterseite und Nachbarseite (`/mitmachen-xyz` passt nicht). |
| 2 | mittel | Der Ping glich Vorgang und Verweis nicht ab. Ein anderswo bewegter Lauf ließ den Verweis auf `wartet_seite` stehen (weitere Pings, toter Chip), ein abgeschalteter Ablauf lief weiter. | Wie `wahl_zug`: Der Verweis folgt dem Vorgang, still festgeschrieben. Ein abgeschalteter oder geänderter Ablauf wird abgebrochen und mit „unbekannt“ beantwortet. Tests für beides. |
| 3 | mittel | `ist_hintergrund_anfrage` prüfte die Tour-Aktion vor dem Seiten-Ping, Graph und `setup` umgekehrt. | Der Seiten-Ping geht überall vor. Test. |
| 4 | klein | Ungültige Escape-Sequenz im Test (SyntaxWarning). | Raw-Strings; die Tests laufen mit `-W error::SyntaxWarning`. |
| 5 | klein | Doppelte Lambda für „leere Liste = nicht gesetzt“. | Eine Funktion an beiden Stellen. |

**Prüfung:** `test_ablauf_seite*.py` und `test_graph_build.py`: 108 grün; ruff sauber.

## Deploy

Backend und Studio neu bauen. Keine Migration, keine neue Variable. Bestehende Abläufe behalten
ihre Fassung, denn alle neuen Felder haben die Vorgabe `None`.
