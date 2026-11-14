# Werte hinzufügen statt ersetzen (2026-11-14)

Plan [`2026-11-14-mcp-stand-8cbc051.md`](../plans/2026-11-14-mcp-stand-8cbc051.md), Paket N2.

Bisher ersetzte `wlo_update_content` Fach, Bildungsstufe, Inhaltstyp und Zielgruppe und nahm je
Feld genau eine Bezeichnung. „Füge das Fach Mathematik hinzu“ ging nicht: Die KI sollte das
Werkzeug dafür nicht aufrufen und einen Vorschlag anbieten. In der Messung vom 13.11. öffnete sie
stattdessen eine Ersetzen-Vorschau mit Warnsatz.

Der MCP kennt ab dem Stand vom 14.11.:

- `addDiscipline`, `addEducationalContext`, `addUserRole` an `wlo_update_content` und je Eintrag
  von `wlo_update_contents`: fügt hinzu, die bisherigen Werte bleiben.
- Eine Liste statt einer Bezeichnung an den vier ersetzenden Feldern, auch beim Anlegen.
- `lookup_wlo_vocabulary` mit `contentType`: die Inhaltstypen, wie das Schreiben sie annimmt.

## Was sich im Chatbot ändert

- **Angebot an die KI** (`services/mcp/werte_hinzufuegen.py`): die drei Hinzufügen-Parameter, die
  vier Felder als Liste, der Wert `contentType` beim Nachschlagen. Angeboten wird das nur, wenn der
  bereitgestellte Server es führt; der Chatbot liest es aus dessen Werkzeugliste. Kein Schalter,
  keine Reihenfolge beim Deploy.
- **Beschreibung von `wlo_update_content`:** Statt „nur ersetzen, sonst Vorschlag anbieten“ steht
  dann „zum Hinzufügen `add…` nehmen; nie dasselbe Feld zugleich ersetzen und ergänzen; der
  Inhaltstyp lässt sich nur ersetzen“.
- **Argumentmodelle** (`api/schemas_mcp_curation.py`): Die vier Felder und die drei neuen nehmen
  Text oder Liste; Leerraum am Rand und leere Einträge fallen weg. Eine einzelne Bezeichnung in
  einer Liste geht als Text an den Server; so nimmt sie auch der alte. Das gilt im Einzelaufruf
  und je Eintrag des Stapel-Werkzeugs.
- **Kein stilles Verwerfen:** Nennt die KI `add…`, obwohl der bereitgestellte Server es
  nachweislich nicht kennt, schickt der Client den Aufruf nicht hinaus und sagt es ihr. Der Server
  ließe das Feld sonst wortlos weg und schriebe nur, was daneben steht.
- **Agent und Muster** bekommen dasselbe Angebot (`agent_tools`, `response_tool_selection`): Das
  Kuratieren läuft auch über das Muster M18.
- **Feste Texte** (Muster M18, drei Fassungen des Master-Skills): „Soll ein Wert hinzukommen:
  Bietet das Werkzeug dafür einen eigenen Parameter, ihn nehmen; sonst … Vorschlag anbieten.“ Ohne
  Parameternamen, damit der Text mit beiden Server-Ständen stimmt.
- **Fähigkeitsabfrage** (`services/mcp/faehigkeiten.py`): merkt sich je Parameter auch die
  Aufzählungswerte (`kennt_wert`). `vocabulary` gab es immer, `contentType` als sein Wert ist neu.
- **Ein Ort für alles, was vom Server-Stand abhängt:** `services/mcp/angebot.py` legt N3 (Sammlung
  per Titel) und N2 auf die Kataloge.

## Entscheide

- **Woran das Angebot hängt:** an `addDiscipline` in der Werkzeugliste von `wlo_update_content`.
  Listen und die Einträge des Stapel-Werkzeugs zeigt die Werkzeugliste nur verschachtelt; sie
  kamen mit demselben Stand und hängen an derselben Marke.
- **Listen als `array`, kein „Text oder Liste“ im Schema für die KI.** Ein Schema mit zwei Typen
  (`anyOf`) verstehen nicht alle Modell-Anbieter gleich. Die Argumentmodelle nehmen beides.
- **Beides zugleich entscheidet der Server.** Nennt die KI `discipline` und `addDiscipline`, lehnt
  er ab und sagt es. Der Client wählt nicht aus; sonst schriebe er etwas anderes, als verlangt war.
- **Nachschlagen bleibt der zweite Weg.** Lehnt der Server einen Inhaltstyp ab, nimmt die KI zuerst
  seine Vorschläge und schlägt erst sonst unter `contentType` nach. Das sagen jetzt alle Stellen
  gleich: die Beschreibung des Nachschlagens, die des Felds `contentType`, Muster M18 und der
  Master-Skill.
- **Mehr als 20 Bezeichnungen lehnt der Server ab.** Der Client schneidet nicht ab; bei einem
  ersetzenden Feld fehlten sonst Werte, ohne dass es jemand merkt.
- **Abläufe unverändert.** Die Prüfung eines Ablaufs kennt die vier Felder weiter als einzelnen
  Wert; eine Auswahl (Liste) an einem solchen Schritt bleibt dort ein Befund.

## Gemessen mit dem echten Modell

`gpt-6-luna`, echte Werkzeugdefinitionen und Kurzfassung des Master-Skills. Die Schreibwerkzeuge
antworteten aus einer Attrappe in der Form des neuen Servers; ohne Anmeldung gibt der echte keine
Vorschau.

| Auftrag | ohne Angebot (alter Server) | mit Angebot |
|---|---|---|
| „Füge das Fach Mathematik hinzu.“ | Ersetzen-Vorschau mit Warnsatz (3 von 3) | `addDiscipline: ["Mathematik"]`, eine Runde (3 von 3) |
| „Passt auch für Sekundarstufe I und Hochschule, bitte ergänzen.“ | nicht gemessen | `addEducationalContext` mit beiden Werten (3 von 3) |
| „Setze die Fächer auf Mathematik und Informatik.“ | ein Text „Mathematik, Informatik“ oder nur ein Fach | `discipline` als Liste (3 von 3) |
| „Ändere das Fach auf Mathematik.“ | `discipline` | `discipline` (3 von 3) |

## Review

Ein unabhängiges Review fand nichts Kritisches oder Schweres, 5 kleinere Befunde und 9
Randnotizen. Behoben sind alle fünf und sieben Randnotizen: widersprüchliche Texte zum
Nachschlagen des Inhaltstyps, `query: null` beim Nachschlagen, der Stapel wurde anders
normalisiert als der Einzelaufruf, `add…` an einem alten Server fiel still weg, fehlende Tests
(Bestätigungsweg, Muster ohne Schreibrecht, Rückbau des Servers).

Bewusst gelassen:
- Der Schlüssel einer Bestätigung unterscheidet `["Physik"]` und `"Physik"`. Das betrifft nur
  einen Rückfallweg; der Regelweg führt die gemerkten Argumente aus.
- Die Studio-Übersicht der Werkzeuge zeigt die Beschreibungen ohne die Zusätze (wie bei N3).

## Geprüft

- Backend: volle Suite 10 377 Tests grün (5 übersprungen); neu `tests/test_mcp_werte_hinzufuegen.py`. Die Schemata darin stammen aus
  den Werkzeuglisten beider Stände (neu: lokal gestartet; alt: der bereitgestellte Staging-MCP).

Nicht geprüft: eine echte Vorschau und ein echtes Schreiben mit `add…`. Dafür braucht es eine
Anmeldung am neuen Stand, also dessen Deploy auf Staging.

## Deploy

- Keine Migration, keine neue Variable, keine Reihenfolge zum MCP. Image neu bauen.
- `import-config --werksabgleich` (Muster M18 geändert) und Master-Skill-Knoten in WLO mit
  `docs/skills/vorgehen-knapp.md` ersetzen.
- Nach dem Deploy des MCP: „Füge beim Material … das Fach Mathematik hinzu“ zeigt eine Vorschau
  der Form `Fach: „Physik, Chemie“ + „Mathematik“`.
