# Plan: Werkzeuge für Sammlungsstrukturen anbinden (2026-11-14)

Der MCP-Entwickler hat auf unsere Wünsche
([`mcp-werkzeug-wuensche-2026-11-14.md`](../mcp-werkzeug-wuensche-2026-11-14.md)) am selben Tag
geantwortet: Neun von zehn sind gebaut (S10, Teilbaum kopieren, nicht). Der bereitgestellte Server
läuft weiter auf dem alten Stand.

## Stand des MCP, nachgemessen

Seine Arbeitskopie lokal gestartet (anonym, nur lesend, gegen das Staging-Repository):

- `tools/list` nennt 60 Werkzeuge. Neu gegenüber unserem Katalog: `list_collection_tree`,
  `wlo_order_collection`, `wlo_submit_contents`, `wlo_move_collection`,
  `wlo_remove_from_collections`, `wlo_delete_collections`, `wlo_list_collection_proposals`,
  `wlo_decide_collection_proposal`.
- Erweitert: `order` an `browse_collection_tree` und `get_collection_overview`; `shared` und
  `discipline`/`educationalContext`/`keywords` je Knoten an `wlo_create_collection_tree`;
  `removeFrom` je Paar an `wlo_add_to_collections`.
- `list_collection_tree` am Fachportal Physik: 144 Sammlungen über drei Ebenen in 4,7 s, in der
  Reihenfolge des Repositorys (Optik, Methoden, Astronomie …; alphabetisch wäre Akustik zuerst).
  Der Text ist Markdown (16,7 kB), die Daten stehen im strukturierten Teil.
- Die Schreibwerkzeuge lassen sich ohne Anmeldung nicht prüfen. Das geht erst nach seinem Deploy
  auf Staging.

## Regeln für alle Pakete

- Alles hängt an der Werkzeugliste des Servers (`services/mcp/faehigkeiten.py`): Bis er die neuen
  Werkzeuge führt, ändert sich im Chat nichts. Es gibt keine Reihenfolge beim Deploy.
- Der Master-Skill nennt kein Werkzeug und keinen Parameter beim Namen, die nur der neue Server
  führt (gemessen bei N3: Sonst nimmt das Modell sie auch ohne Angebot und gibt auf).
- Tests schreiben wir gegen die Drahtform aus dem Quelltext und den Tests des MCP.
- Kleine Pakete, je mit Änderungsnotiz; Review nach SW-2 und nach SW-3.

## Pakete

| Paket | Inhalt | Wünsche |
|---|---|---|
| SW-1 | Lesen: `list_collection_tree` für die KI; `order` an Baum und Übersicht | S1 (lesen), S2 |
| SW-2 | Baum anlegen mit Fach, Stufe, Schlagworten; der Ablauf-Dienst reicht sie aus dem Entwurf durch | S3, S1 (setzen im Baum) |
| SW-3 | Sieben Kuratier-Werkzeuge: Stapel-Einreichen, Stapel-Entfernen, Umsortieren, leere Sammlungen löschen, Umhängen, Reihenfolge setzen, Vorschläge lesen und entscheiden | S4 bis S9 |
| SW-4 | Anzeige: Strukturabgleich bis Tiefe 4 (umgesetzt); Themenbaum in gespeicherter Reihenfolge (wartet auf den Server, SE-4) | S1, S2 |

SW-4 ist abgetrennt, weil es ein Modul und seinen Dienst ändert. Der Abgleich ist umgesetzt, der
Themenbaum nicht (siehe SE-4, SE-5, SE-9, SE-10).

## Entscheide

| Nr. | Frage | Entscheid |
|---|---|---|
| SE-1 | `list_collection_tree`: in den Katalog? | **Nein**, bedingt angeboten wie die Mehrfachsuche. Der Muster-Weg reicht den Lese-Katalog als Ganzes weiter; ein Server ohne das Werkzeug wiese dort jeden Aufruf ab. |
| SE-2 | Die sieben Kuratier-Werkzeuge: in den Katalog? | **Ja.** Nur so greifen Bestätigung, Pläne, Argumentmodelle, Cache-Sperre und die Wächter-Tests von selbst. Angeboten werden sie trotzdem nur, wenn der Server sie führt (ein Filter in `angebot`). |
| SE-3 | `wlo_delete_collections` in Abläufen? | **Nein**, wie jedes Löschen. Im Chat mit Bestätigung erlaubt; es löscht nur leere Sammlungen. |
| SE-4 | Themenbaum-Modul in gespeicherter Reihenfolge? | **Nein, bis der Server eine passende Reihenfolge kennt.** `order: "stored"` heißt: die gesetzte Position, sonst die Reihenfolge des Anlegens. Für einen angelegten Lehrplan ist das richtig, für ein Fachportal beliebig, und die Antwort sagt nicht, welcher Fall vorliegt. Gebraucht wird „gesetzte Position, sonst Titel“; das steht als Wunsch in `mcp-antwort-2026-11-14-sammlungsstrukturen.md`. Kein Code auf Verdacht. Bis dahin entscheidet die KI je Aufruf über `order` an den Werkzeugen. |
| SE-5 | Strukturabgleich bis Tiefe 4? | **Ja, wenn der Server `list_collection_tree` führt** (SW-4, 14.11.); sonst zwei Ebenen wie bisher. Je Ebene gilt die Regel der Ebene 2: erst unter der zugeordneten Sammlung des Elternpunkts, sonst gegen die übrigen Sammlungen der Ebene. Maßgeblich ist der Stand des Servers, nicht das Angebot des Zugs: Ein KI-Schritt eines Ablaufs engt das Angebot ein, und gerade dort wird tief abgeglichen. Lesen darf der Dienst über `dienst.braucht` (`browse_collection_tree`). Den Studio-Schalter der Baumliste beachtet er; eine Sperre je Lauf, die nur die Baumliste nennt, erreicht ihn nicht. Bricht die Liste ab (Grenze des Servers, zu viele Seiten, keine Zeit), wird „neu“ ab der tiefsten gelesenen Ebene zu „nicht gefunden“; meldet der Server einen Ausfall (`incomplete`, `restricted`), an jedem neuen Punkt, denn wo es war, sagt die Antwort nicht verlässlich. |
| SE-6 | Fach, Stufe, Schlagworte aus dem Strukturentwurf? | Der Ablauf-Dienst `baum_aus_entwurf` reicht Stufe und Schlagworte durch, das Fach nur, wenn das Vokabular es kennt (im Entwurf ist es Freitext; der Server lehnte sonst den ganzen Baum ab). Die Werte stehen an jedem Knoten, nicht in `shared`. Ein Server, der die Felder nicht annimmt, bekommt sie nicht. |
| SE-7 | Vorschlag an eine Sammlung: eigener Weg im Chatbot? | **Nein.** Der Server schlägt von selbst vor, wo nur Leserecht besteht, und sagt es je Paar (`proposed`). Der Master-Skill hält fest: Vorgeschlagen ist nicht aufgenommen. |
| SE-8 | Vorschläge lesen (`wlo_list_collection_proposals`) | Wie `wlo_list_suggestions`: bei den Kuratier-Werkzeugen, ohne Bestätigung, im Lesemodus erlaubt. |
| SE-9 | Abdeckung (Treffer in ganz WLO) auch für Ebene 3 und 4? | **Nein.** Gezählt wird weiter für Ebene 1 und 2, höchstens 60 Punkte. Tiefere Punkte tragen keine Zahl und zählen nicht als „ungezählt“; Modul und KI lesen einmal „Gezählt wird nur für Ebene 1 bis 2“. Mehr Punkte hieße mehr Suchanfragen je Abgleich. |
| SE-10 | Die Baumliste eines Fachportals dauert länger als der alte Weg | Gemessen: Physik (144 Sammlungen) mit Inhaltszahlen 10,5 bis 12,8 s, als erster Aufruf eines Prozesses 19 und 38 s; bisher 3,6 bis 5,0 s. Die Zahlen bleiben, das Modul zeigt sie. Eine Seite der Liste darf 30 s dauern; bleiben dem Lauf dafür keine 40 s (30 s und 10 s für den alten Weg, nach 15 s Reserve), dauert die erste Seite länger oder fällt sie aus, liest der Dienst zwei Ebenen. Nach 30 s insgesamt beginnt keine weitere Seite. Schnelleres Zählen steht als Wunsch beim MCP-Entwickler. |
| SE-11 | Wie tief wird die Baumliste gelesen? | **So tief wie der Entwurf, mindestens zwei, höchstens vier Ebenen.** Tiefer kostete je Sammlung eine Abfrage und stieße früher an die Grenze des Servers (400 Auflistungen je Aufruf), ohne dass ein Punkt dazu passte. „Nur in WLO“ zeigt deshalb nichts unterhalb der Tiefe des Entwurfs. |

## Prüfung

- Je Paket gezielte Tests, vor dem Upload die volle Backend-Suite.
- Live nur lesend gegen die lokal gestartete Arbeitskopie des MCP.
- Nicht prüfbar vor dem Deploy des MCP: jede Vorschau und jedes Schreiben, also SW-2 und SW-3 im
  Zusammenspiel mit dem Server. Das steht danach als offener Punkt in
  `offene-befunde-und-todo.md`.

## Fortschritt

- SW-1: umgesetzt 14.11. (Notiz `aenderungen/2026-11-14-sammlungsbaum-lesen-und-metadaten.md`)
- SW-2: umgesetzt 14.11. (dieselbe Notiz)
- SW-3: umgesetzt 14.11. (Notiz `aenderungen/2026-11-14-sammlungen-pflegen.md`)
- SW-4: Abgleich bis Ebene 4 umgesetzt 14.11. (Notiz
  `aenderungen/2026-11-14-strukturabgleich-vier-ebenen.md`); Themenbaum in gespeicherter
  Reihenfolge wartet auf den Server (SE-4)
- SW-5 (offen): Der MCP-Entwickler hat S11 bis S13 am 15.11. zugesagt und baut sie. Danach:
  Themenbaum-Modul mit `order: "position"`, wenn der Server den Wert führt; im Abgleich einen
  gemeldeten Ausfall auf den betroffenen Zweig begrenzen (die Kennungen der nicht gelesenen
  Eltern stehen dann im Kopf der Antwort)
