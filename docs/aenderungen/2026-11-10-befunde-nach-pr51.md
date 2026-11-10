# Offene Befunde nach PR #51 behoben (2026-11-10)

Aus `offene-befunde-und-todo.md`, auf Auftrag des Nutzers („Befunde beheben“).

| Befund | Ursache | Behebung |
|---|---|---|
| Wartet ein Lauf an einer Wahl mit vier oder mehr Chips, fiel der Knopf eines vorgeschlagenen Ablaufs weg (offen seit AS-5b). | `vorschlag.anhaengen(alle=True)` hält die Chips der Wahl ganz und kürzt dahinter. Die KI hatte den Knopf aber schon angekündigt. | `wahl_zug.platz_fuer_vorschlag`: Füllen die Chips den Platz (`vorschlag.grenze`, 4 oder die Höchstzahl des Gastgebers), bietet der Zug keinen Ablauf an. Gilt im Agent-Modus (`respond_agent`) und im Muster-Modus (`respond` → `ohne_ablaeufe`). Test `test_ablauf_wahl_platz.py`, zuerst rot. |
| `test_usage_analytics::…_zeitraum` kippte im vollen Lauf und am 10.11. auch allein. | Zeilen ohne `created_at` bekommen `now()`. `_JAN` + 300 Tage war genau der 10.11.2026, also lag das Testfenster auf „heute“, und Nachbartests drängten die eigene Sitzung aus der Liste der teuersten. | Das Fenster liegt jetzt vor `_JAN` (`now()` erreicht es nie). Ebenso das Fenster `_JAN` + 500 Tage, sonst die nächste Zeitbombe im Mai 2027. |
| `test_anmeldung_status::…_bis_zur_frist` (`60.0000002 <= 60`) | Testuhr und Uhr im Dienst laufen unter Windows um Bruchteile auseinander. | Toleranz von 1 ms. |
| Widget: `anmelde-frist.spec` kippte einmal im vollen Lauf. | Die Specs teilen sich `sessionStorage`; ein Abmelde-Merker einer anderen Spec stand noch. | Den Merker auch **vor** dem Test löschen. |

**Nicht behoben, als Entscheidung offen:** Sitzungen der Studio-Vorschau und der Probe zählen in der
Auswertung als Betrieb. Die Herkunft hängt allein am Präfix der Sitzungskennung; ein eigenes Präfix
oder eine Verknüpfung mit `entities._probe` in jeder Auswertung ist eine Entscheidung.

**Prüfung:**
- `test_ablauf_wahl_platz` mit den Wahl- und Ablauf-Tests: 212 grün.
- `test_usage_analytics` und `test_anmeldung_status`: 50 grün.
- `ng test ui`: 1384 grün.
- ruff ist sauber.
