# Mehrere Suchen in einem Aufruf; MCP-Stand „15.11.“ (2026-11-14)

Plan [`2026-11-14-mcp-stand-8cbc051.md`](../plans/2026-11-14-mcp-stand-8cbc051.md), Paket N4, und
die Rückmeldung des MCP-Entwicklers zu „Sammlung per Titel“. Er datiert seinen Stand auf den
15.11.; so heißt er auch hier.

## N4: `search_wlo_content_many`

Für einen Lernpfad, eine Stunde oder eine Reihe sucht die KI je Schritt ein Material. Bisher waren
das vier bis sechs Einzelsuchen. Der MCP kennt ab dem Stand vom 14.11. eine Mehrfachsuche: bis zu
acht Anfragen in einem Aufruf, je bis zu fünf Treffer in Kurzform.

- **Angebot** (`services/mcp/suche_mehrfach.py`): Die KI bekommt das Werkzeug nur, wenn der
  bereitgestellte Server es führt. Es steht bewusst nicht im Katalog der Lesewerkzeuge: Den reicht
  der Muster-Weg als Ganzes weiter, und ein Server ohne das Werkzeug wiese dort jeden Aufruf ab.
  Der Agent bekommt es, ein Muster nur, wenn es das Werkzeug beim Namen nennt.
- **Argumente** (`api/schemas_mcp.py`): Kennung und Suchtext je Anfrage in den Schranken des
  Servers, sechs Filter gemeinsam oder je Anfrage, 1 bis 5 Treffer. Eine Anfrage oder ein Filter,
  die keine sein können (mehrere Werte als Liste, eine Zahl), fallen nicht still weg; der Server
  lehnt den Aufruf dann ab und sagt es. Eine Liste mit genau einem Wert ist dieser Wert, `null`
  und eine leere Liste heißen „nicht angegeben“, die alten Filternamen (`educationalLevel`,
  `resourceType`, `subject`) werden übersetzt.
- **Der Client lehnt selbst mit einem Satz ab:** keine Liste, keine Anfrage, mehr als acht, und
  einen unbekannten Filternamen in einer Anfrage (den ließe der Server still weg, und die Suche
  liefe ungefiltert). Still kürzen hieße, dass Schritte ohne Suche bleiben und wie „keine
  Treffer“ aussehen.
- **Sperren:** Persönliche Daten in der Nachricht oder eine erkannte Krise sperren das Werkzeug
  wie jede Volltext- und Materialsuche (`services/safety/regex_gate.py`). Die zwei im Studio
  gepflegten Listen nennen es ebenfalls: die Regel `pol-no-personal-data-search`
  (`seeds/01-base/policy.yaml`) und `crisis_blocked_tools` (`seeds/01-base/safety-config.yaml`).
- **Antwort:** Der Server antwortet in Markdown und legt die Treffer zusätzlich strukturiert bei.
  Der Client stellt den strukturierten Teil als Umschlag vor den Text
  (`suche_mehrfach.mit_umschlag`).
  - Aus dem Umschlag werden **Karten** unter der Antwort, wie bei der Einzelsuche
    (`parsers.parse_search_many_cards`): reihum je Anfrage, jedes Material einmal.
  - Die Materialien-Box ist gedeckelt. Ein Zug mit diesem Werkzeug nimmt den Deckel des
    Lernpfads (`display_rules.groups.materialien_max_lernpfad`, Vorgabe 5, höchstens 8) statt des
    Standards (3). Mit „reihum“ trägt so jeder Teil eine Karte, solange der Deckel reicht.
  - Die KI nennt je Teil Titel und Link. Im Chat bleiben die Titel stehen, die Links nimmt die
    Endverarbeitung heraus (wie beim Lernpfad). Was über den Deckel hinausgeht, hat im Chat
    danach einen Titel, aber keinen Link; vollständig mit Links steht es in einem Dokument.
  - Am Endpunkt `/api/agent` gibt es keine Karten; dort bleibt der Text mit Titel und Link.
  - Die KI bekommt nur den Text des Servers, ganz (rund 6 kB für 15 Treffer, nachgerechnet
    höchstens rund 20 kB). Was der Server nicht beantworten konnte, steht dort am Ende unter
    „Nicht beantwortet — KEIN Befund ‚keine Treffer‘“. Nur ein Ausreißer über 32 000 Zeichen
    wird gekürzt; Anfang und Ende bleiben.
  - Eine Teilantwort (`missing`) hält der Cache nicht, eine unvollständige Teilsuche
    (`results[id].incomplete`) nur für Sekunden.
- **Studio:** Die Seite „Werkzeuge“ zeigt das Werkzeug als Zeile. Solange der Server es nicht
  führt, steht dort der Grund (`server_lacks`). Am MCP-Server trägt es einen Schalter wie jedes
  Lesewerkzeug. Die Warnung „fehlt am Server“ der Seite „MCP-Server“ gilt für dieses Werkzeug
  nicht: Ohne den Server wird es gar nicht angeboten.
- **Master-Skill** (M09): „Ist ein Werkzeug für mehrere Suchen in einem Aufruf angeboten, alle
  Schritte damit zugleich suchen.“ Ohne Werkzeugnamen, wie bei N2 und N3.

### Gemessen

Am neuen Stand des Servers, lokal gestartet gegen das Staging-Repository (anonym, lesend):

| | ein Aufruf mit fünf Suchen | fünf Einzelsuchen nacheinander | fünf zugleich |
|---|---|---|---|
| Wartezeit | 0,6 bis 1,1 s | 4,0 bis 4,9 s | 2,6 bis 3,1 s |

Mit `gpt-6-luna` und der Bitte um einen Lernpfad zur Optik (fünf Schritte), je drei Läufe:

| | ohne das Werkzeug | mit |
|---|---|---|
| Werkzeugaufrufe | 5, 6, 17 | 2, 6, 8 |
| Zeit bis zur Antwort | 14,5 s, 16,9 s, kein Ende nach 8 Runden | 9,3 s, 21,8 s, kein Ende nach 8 Runden |

Die Streuung ist groß und die Probe klein. Der beste Fall ist deutlich kürzer (zwei Aufrufe statt
fünf), der schlechteste gleich schlecht: Dort wich das Modell auf Sammlungen und Skills aus, mit
und ohne das neue Werkzeug. Gemessen wurde vor den Korrekturen aus den Reviews. Seither hat sich
ein Satz der Werkzeugbeschreibung geändert (Titel und Link nennen, Karten kommen dazu). Zwei
Läufe damit: 2 und 5 Werkzeugaufrufe (10,7 s und 17,8 s); die Antwort nennt je Schritt Titel
und Link.

### Bewusst gelassen

- Das Muster M09 (Muster-Weg) nennt das Werkzeug nicht; es sucht weiter einzeln. Im Studio lässt
  es sich einem Muster hinzufügen.
- Die Gold-Erwartungen `tools_any: [search_wlo_all, search_wlo_content]` kennen die Mehrfachsuche
  nicht. Das sind Fälle mit einem Thema; dort wäre sie das falsche Werkzeug. In `tools_none` der
  beiden Krisenfälle steht sie.
- Die Zählung der Treffer im Qualitätslog (`outcome_service`) bleibt für dieses Werkzeug bei
  „Erfolg, ein Treffer“, wie bei `search_wlo_all`.
- Im Muster-Weg schiebt der Chatbot Fach und Stufe aus der Klassifikation nur bei
  `search_wlo_content` nach, und der Filter gegen themenfremde Karten kann Karten zu Unterthemen
  entfernen, die kein Wort mit der Nachricht teilen. Wer das Werkzeug einem Muster gibt, prüft
  das mit.
- Unbekannte Argumente außerhalb von `filters` fallen wie bei jedem Werkzeug weg. Kennung,
  Suchtext und Filtertext werden auf 40, 200 und 200 Zeichen gekürzt.
- Die Zeichenzahl im Log (`mcp_aufruf`) zählt Umschlag und Text, also gut das Doppelte dessen,
  was die KI bekommt.

## MCP-Stand „15.11.“: Sammlungen ohne Fachangabe

Der Entwickler hat beide Befunde aus unserer Messung behoben. Nachgemessen an seinem Stand:

| Aufruf | Stand 14.11. | Stand „15.11.“ |
|---|---|---|
| „Mechanik“ + Physik | abgelehnt | aufgelöst, die Community-Sammlung steht daneben (`alsoFound`) |
| „Klimawandel“ + Geografie | Community-Sammlung genommen | abgelehnt (`disciplineUnverified`) |
| „Saeuren und Basen“ + Chemie | „nichts Ähnliches“ | gefunden, als lose Übereinstimmung gesagt |

Im Chatbot (`services/mcp/sammlung_per_name.py`, `ui_module/datenquelle.py`):

- **`disciplineUnverified`:** Das Themenbaum-Modul sagt der KI, dass es eine gleichnamige Sammlung
  ohne Fachangabe gibt, dass ein neuer Aufruf mit dem Titel nichts ändert und dass sie die
  Kennung nehmen oder nachfragen soll. War die Suche zugleich unvollständig, entfällt „nicht noch
  einmal“: Dann kann ein späterer Versuch anders ausgehen.
- **`alsoFound`:** Die KI bekommt die nicht gewählten Namensvettern als Zeilen (höchstens drei,
  mit Kennung, „3 von 5“) und den Hinweis, das Werkzeug mit einer dieser Kennungen zu rufen, wenn
  eine davon gemeint ist.
- Die neue Form der Zeilen des Servers betrifft den Chatbot nicht: Er liest die Felder.

Die Antwort an den Entwickler steht in `docs/mcp-antwort-2026-11-14.md`, Abschnitt 9. Sie nennt
die Zeilen, die der Chatbot wörtlich auswertet (seine Frage), und einen Befund: Die Mehrfachsuche
meldete bei null Treffern „es gibt weitere Treffer“. Der Entwickler hat ihn in seiner Arbeitskopie
behoben und zugleich weitere Zeilen auf „Kennung vorn“ umgestellt (Skill-Zeilen, Baumzeile,
Dublettenprüfung, Sammlungsübersicht). Nachgeprüft: Die Kürzung der Sammlungsübersicht greift wie
zuvor. An einer Form hängt der Chatbot noch (siehe Review, Befund 4).

## Review

Ein unabhängiges Review fand 4 schwere, 6 mittlere und 6 kleine Punkte. Behoben:

1. **Treffer kamen im Chat nicht an (schwer).** Die Beschreibung verlangte „nenne Titel und Link
   selbst“; die Endverarbeitung nimmt Links aus dem Antworttext, und Karten gab es keine. Jetzt
   werden die Treffer Karten (oben, „Antwort“).
2. **Abgeschnitten im Muster-Weg (schwer).** Dort griff der blinde Deckel von 4 000 Zeichen;
   „Nicht beantwortet“ steht am Ende und fiel zuerst. Beide Wege bekommen den Text jetzt ganz.
3. **Filter fiel still weg (schwer).** Ein Filter je Anfrage als Liste oder Zahl verschwand, und
   gesucht wurde ungefiltert. Er bleibt jetzt stehen; der Server lehnt ab.
4. **Tabelle an den MCP-Entwickler unvollständig (schwer).** Fünf Formen fehlten, darunter die
   Fehlzeile von `get_skill` als ganze Zeile: Stellt der Server sie um, gälte sie im Chatbot als
   geladene Anleitung. Die Tabelle ist ergänzt; die Erkennung über das Feld `found` ist als
   offener Punkt notiert.
5. **Mittlere:** Zeile und Schalter im Studio; unvollständige Teilsuche im Cache; die zwei
   gepflegten Sperrlisten; Tests für Karten, den ganzen Text, den Schalter, den Modus, Listen als
   Filter; `tools_none` der Gold-Fälle.
6. **Kleine:** lokaler Satz bei leerer Liste; „3 von 5 gleichnamigen“; der Fall „Fach ungeprüft
   und Suche unvollständig“; das Datum (die Arbeit ist vom 14.11.).

Weil die Korrektur zu 1 ein Umbau war, las ein zweites unabhängiges Review den neuen Stand: 1
schwerer, 6 mittlere und 5 kleine Punkte. Behoben:

1. **Karten nur zur ersten Anfrage (schwer).** Nach dem Deckel der Materialien-Box (3) blieben
   drei Karten, alle zur ersten Anfrage, und die Beschreibung verbot der KI, Titel zu nennen.
   Jetzt stehen die Karten reihum, der Zug nimmt den Deckel des Lernpfads, die Titel bleiben im
   Text, und die Beschreibung verspricht nur, was geschieht.
2. **Mittlere:** Die Beschreibung stimmt auch an `/api/agent`; keine falsche Warnung auf der
   Seite „MCP-Server“; ein unbekannter Filtername wird abgelehnt statt still verworfen; `null`
   im gemeinsamen Filter; Tests für den Deckel, einen Lauf durch die Agent-Schleife und die
   Warnung.
3. **Kleine:** ein weiter Sicherheitsdeckel für Ausreißer; eine Angabe in der Tabelle an den
   MCP-Entwickler.

Nicht geändert: Scheitert die Prüfung der Argumente an einem gemeinsamen Filter, gehen sie roh zum
Server, auch `outputFormat`. Der Server lehnt dann ohnehin ab; käme JSON zurück, bleibt es JSON.
Kennungen, die durch Kürzen auf 40 Zeichen gleich werden, meldet der Server. Steht eine Wendung
wie „war nur teilweise erreichbar“ in der Beschreibung eines Treffers, gilt die Antwort als
unvollständig; die Folge ist nur eine kürzere Cache-Frist.

## Geprüft

- Backend: volle Suite 10 429 Tests grün (5 übersprungen); neu `tests/test_mcp_suche_mehrfach.py`, ergänzt
  `tests/test_mcp_sammlung_per_name.py`.
- Studio: 2 156 Tests bestanden (`ng test studio`).
- Client des Chatbots gegen den lokalen neuen MCP, nach den Korrekturen: vier Anfragen in einem
  Aufruf ergeben 9 Karten, reihum je Anfrage, und 3 959 Zeichen Text für die KI (ohne Umschlag);
  aus dem Cache dieselben Karten; ein Filter mit zwei Werten kommt als Ablehnung des Servers
  zurück („expected string, received array“); eine leere Liste lehnt der Client selbst ab. Vor
  den Korrekturen: neun Anfragen, `OER`, die drei Fälle der Tabelle oben im Themenbaum-Modul.

Nicht geprüft: ein Zug im Chat mit Datenbank und Widget gegen den neuen MCP (erst nach dessen
Deploy auf Staging); die neue Zeile im Studio im Browser (Text und Daten sind durch Tests belegt).

## Deploy

- Keine Migration, keine neue Variable, keine Reihenfolge zum MCP. Image neu bauen.
- `import-config --werksabgleich` (Werkzeugliste des MCP-Servers, Regelwerk, Schutz-Einstellungen)
  und Master-Skill-Knoten in WLO mit `docs/skills/vorgehen-knapp.md` ersetzen.
- Wer Regelwerk oder Schutz-Einstellungen im Studio als eigene Fassung führt, trägt
  `search_wlo_content_many` dort selbst nach (Regel `pol-no-personal-data-search`, Liste
  „Werkzeuge bei Krise sperren“). Die festen Sperren wirken auch ohne das.
