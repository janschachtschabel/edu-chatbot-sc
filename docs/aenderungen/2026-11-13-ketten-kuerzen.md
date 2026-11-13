# Werkzeug-Ketten kürzen (2026-11-13)

Anlass: Prüfung, wo der Chatbot KI-Runden und MCP-Aufrufe spart. Wünsche an den MCP stehen in
[`mcp-werkzeug-wuensche-2026-11-13.md`](../mcp-werkzeug-wuensche-2026-11-13.md).

## Was sich ändert

- **Themenseiten-Suche ohne Aufwärm-Aufruf** (`services/topic_pages.py`, `services/prefetch.py`).
  - Vor jeder Themenseiten-Suche des Vorabrufs lief ein `search_wlo_collections`, dessen Ergebnis
    verworfen wurde. Der alte Server füllte seinen Themenseiten-Index je Sitzung.
  - Der heutige MCP ist zustandslos (je Anfrage ein neuer Server), und seine Themenseiten-Suche
    sucht die Sammlungen selbst.
  - Die Funktion heißt jetzt `_topic_pages_with_fallback`. Der Rückfall über die globale Liste
    bleibt unverändert.
  - Die Kappung der Sammlungssuche im Vorabruf auf fünf Treffer bleibt, wie sie ist. Sie stammt
    aus derselben Zeit; ohne sie hat niemand gemessen.
- **Metadaten direkt ändern** (Werkzeugbeschreibungen, Master-Skill, Muster M18).
  - `wlo_update_content` nimmt Bezeichnungen (Fach, Stufe, Typ, Zielgruppe).
  - `get_node_details` davor nur noch, wenn die Kennung nicht aus dem Gespräch stammt oder die
    Änderung auf dem bisherigen Wert aufbaut (Text ergänzen, korrigieren).
  - `lookup_wlo_vocabulary` erst nach einer Ablehnung, oder wenn die KI Werte selbst aus einem
    Text ableitet (Erschließen). Beim Inhaltstyp nimmt sie stattdessen einen Vorschlag aus der
    Ablehnung.
- **Die Vorschau nennt den Datensatz** (`domain/write_anzeige.ziel_zeile`, `services/mcp/client.py`).
  - Der Vorschautext des MCP besteht bei einer Metadaten-Änderung nur aus den Feldzeilen. Titel und
    Kennung stehen nur im strukturierten Teil der Antwort.
  - Der Client setzt daraus „Geändert wird (Kennung): ‚Titel‘“ vor den Vorschautext, für die
    Person (Kasten) und für die KI.
  - Keine Zeile, wenn der Server das Ziel selbst als „Titel“ (Kennung) benennt (Einreichen,
    Vorschlagen), beim Löschen und beim Anlegen.
  - Die Zeile sagt nicht „Datensatz“ oder „Sammlung“: Der MCP meldet eine Sammlung, die über
    `wlo_update_content` geändert wird, als Inhalt. Ihr Titel kann dann ein Altwert sein
    (Wunsch Z2).
  - Der Titel ist fremder Text. Die Kennung steht deshalb davor, Anführungszeichen im Titel
    werden ersetzt, er ist auf 120 Zeichen gedeckelt.
- **Neu in den Beschreibungen**, weil es bisher nirgends stand:
  - Schlagwörter werden ergänzt; Fach, Stufe, Typ und Zielgruppe ersetzt, alle bisherigen Werte
    fallen weg. Soll ein Wert hinzukommen, bietet die KI einen Vorschlag an.
  - Der Server gleicht Bezeichnungen auch über Teilwörter ab („Wirtschaft“ wird
    „Agrarwirtschaft“). Weicht ein Wert der Vorschau vom genannten ab, sagt die KI das.
- **Erschließen (M20) bündelt** (Master-Skill, Muster M20, Beschreibung von `find_content_by_url`).
  - Erster Schritt zusammen: `get_url_text`, `find_content_by_url` und die Vokabulare für Fach und
    Stufe. Alle brauchen nur die Adresse.
  - Zweiter Schritt zusammen: die Titelsuche und `lookup_wlo_publishers`.

## Was bewusst bleibt

- **`find_content_by_url` vor dem Anlegen.** Meine erste Empfehlung, den Aufruf zu streichen, war
  falsch. Die Vorschau von `wlo_create_content` prüft nur die genaue Schreibweise der Adresse
  (`duplicates.ts` im MCP). Bereinigte Schreibweisen findet allein `find_content_by_url`. Ohne den
  Aufruf entstünden Dubletten.
- **Aufrufe einer Runde laufen weiter nacheinander.** Die parallele Ausführung in beiden Schleifen
  ist nicht gebaut (Entscheid vom 04.07. gilt weiter: reihenfolgeabhängige Nachverarbeitung,
  Spitzenlast am MCP). Für den Hauptfall, mehrere Suchen im Lernpfad, ist eine Stapel-Suche im MCP
  der bessere Weg (Wunsch Z4). Wie oft eine Runde mehrere MCP-Aufrufe trägt, steht je Zug in der
  Zugakte.
- **Rückfall der Themenseiten-Suche über die globale Liste.** Er kostet bei leerem Ergebnis einen
  Aufruf (3,5 s in der Probe). Ob er trifft, zeigt die Logzeile `topic_pages query-fallback`.

## Gemessen

Alle Messungen am 13.11.

- **Aufwärmen** (Staging-MCP, nur lesend, ohne Cache): acht Themen, je einmal ohne und mit
  Aufwärm-Aufruf. Achtmal dasselbe Ergebnis (Optik 3, Klimawandel 1, Photosynthese 1,
  Programmieren 1, vier Themen ohne Treffer). Eine Messung vom 30.07. hatte dasselbe schon für das
  Themenseiten-Muster gezeigt.
- **KI-Runden je Kette:** Das Modell (gpt-6-luna) bekam die echten Werkzeugdefinitionen und den
  Master-Skill; die Werkzeugantworten waren Attrappen in der Form des MCP. Kein MCP, kein Schreiben.

| Fall | vorher | nachher |
|---|---|---|
| Fach und Stufe ändern | 2, 1, 2 Runden | 1, 1, 1 |
| Schlagwörter ergänzen | 1, 1, 2 | 1, 1, 1 |
| Beschreibung ergänzen (liest zuerst, gewollt) | 2, 3, 3 | 3, 2, 3 |
| Seite erschließen | 3, 8, 4 | 3, 4, 3, 4, 3 |
| Unbekanntes Fach | 3, 4, 3 | 3, 3, 3 |

- **Verhalten nach dem Review** (Attrappe mit dem echten Vorschautext, je drei Läufe):
  - Nur eine Kennung genannt: Die KI ändert direkt; den Titel kennt sie aus der neuen Zeile des
    Clients (in zwei von drei Läufen nennt sie ihn im Begleitsatz).
  - „Fach: Wirtschaft“: In drei von drei Läufen nennt die KI, dass daraus „Agrarwirtschaft“ wurde.
  - „Fach Mathematik hinzufügen“: Die KI ruft das Werkzeug trotz Regel auf (drei von drei) und
    sagt dann, dass ersetzt würde; in zwei Läufen bietet sie den Vorschlag an.

Grenzen der Messung: drei bis fünf Läufe je Fall, ein vereinfachter Systemtext (Master-Skill ohne
Persona und Leitplanken), keine Anmeldung. Die langen Läufe „vorher“ beim Erschließen gehen zum
Teil auf die Attrappe zurück (kleine Fächerliste). Im Chat mit Anmeldung ist die geänderte Kette
nicht gelaufen.

## Bekannte Grenzen

- **„Wert hinzufügen“ öffnet eine Ersetzen-Vorschau.** Der Begleitsatz warnt, der Kasten mit dem
  Ausführen-Knopf steht trotzdem da. Sauber lösen lässt es sich nur im MCP (Beobachtung B1).
- **Teilwort-Treffer beim Schreiben.** Der MCP setzt für „Wirtschaft“ still „Agrarwirtschaft“. Die
  KI soll die Abweichung nennen; eine Sicherung ist das nicht (Wunsch Z1).
- **Inhaltstyp in der Vorschau als Adresse.** Alt und neu sind dort nicht lesbar (Wunsch Z2).
- **Golden-Folge GV-RED-1:** Der zweite Zug erwartet `lookup_wlo_vocabulary` oder
  `lookup_wlo_publishers`. Bündelt die KI die Vokabulare schon im ersten Zug, bleibt
  `lookup_wlo_publishers`. Nicht gelaufen; beim nächsten Golden-Lauf ansehen.

## Geprüft

- Neue Tests:
  - `tests/test_vorschau_nennt_datensatz.py`: die Zeile, auch über den Client mit einer Antwort in
    der Form des MCP; Schlüssel und Abnahme bleiben unberührt.
  - `tests/test_werkzeug_ketten_kurz.py`: Kernsätze der Beschreibungen.
  - `tests/test_topic_pages.py`: genau ein Aufruf bei einem Treffer.
- Zwei unabhängige Reviews sind eingearbeitet.
  - Das erste (2 schwere, 9 mittlere Befunde): Die Vorschau nannte den Datensatz nicht, und „der
    Server lehnt Unbekanntes ab“ stimmte nur für den Inhaltstyp.
  - Das zweite (1 schwerer, 7 mittlere Befunde): Die neue Zeile fiel weg, sobald der Titel
    irgendwo im Vorschautext vorkam, etwa als Schlagwort.
- Abläufe (`seeds/06-ablaeufe`) nennen keinen der gekürzten Schritte; nichts anzupassen.

## Deploy

- Keine Migration, keine neue Variable.
- Image neu bauen, danach `boerdi import-config --werksabgleich` (M18, M20 und die Domänenregeln
  geändert).
- Master-Skill-Knoten in WLO mit `docs/skills/vorgehen-knapp.md` ersetzen (Abschnitte M18 und M20).

## Worauf der Chatbot sich jetzt am MCP verlässt

- Die Schreibwerkzeuge nehmen Bezeichnungen und schreiben nichts vor der Bestätigung.
- Die Vorschau zeigt je Feld den bisherigen und den neuen Wert; der strukturierte Teil trägt Titel
  und Kennung.
- Bei `wlo_update_content` werden Schlagwörter ergänzt; Fach, Stufe, Typ und Zielgruppe ersetzt.
- Der Server ist zustandslos; die Themenseiten-Suche braucht keine vorherige Sammlungssuche.
