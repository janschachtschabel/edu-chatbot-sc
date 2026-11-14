# Antwort an den MCP-Entwickler: Sammlungsstrukturen (2026-11-14)

Zu deiner Antwort vom 14.11. auf unsere Wünsche S1 bis S10
([`mcp-werkzeug-wuensche-2026-11-14.md`](mcp-werkzeug-wuensche-2026-11-14.md)).

## Kurzfassung

Danke, das deckt den Weg „Lehrplan → Sammlungsbaum → Inhalte einsortieren → einreichen“ ab. Wir
haben deinen Stand lokal gestartet (anonym, nur lesend, gegen das Staging-Repository) und im
Chatbot alles angebunden, was du gebaut hast. Es hängt an deiner Werkzeugliste; bis du
bereitstellst, ändert sich bei uns im Chat nichts.

- **Nachgemessen:** `tools/list` nennt 60 Werkzeuge. `list_collection_tree` am Fachportal Physik:
  144 Sammlungen in 4,7 s, in der Reihenfolge des Repositorys. `order: "stored"` an
  `browse_collection_tree` liefert dieselbe Reihenfolge, `"title"` die alphabetische.
- **Nicht nachmessbar ohne Anmeldung:** jede Vorschau und jedes Schreiben. Das prüfen wir im Chat,
  sobald dein Stand auf Staging läuft.
- **Zwei kleine Funde** für dich (unten), **drei Wünsche** aus dem Einbau und eine Sache, die
  bei uns liegt.

## Was wir angebunden haben

| Bei dir | Bei uns |
|---|---|
| `list_collection_tree` | die KI bekommt es, wenn du es führst; die Liste geht ganz an sie und kommt nie aus unserem Cache. Unser Abgleich „Entwurf gegen Sammlung“ liest damit alle vier Ebenen statt zwei |
| `order` an Baum und Übersicht | angeboten je Werkzeug, wenn du den Parameter dort führst |
| `discipline`, `educationalContext`, `keywords`, `shared` im Baum | angeboten, wenn du `shared` führst; für einen älteren Stand nehmen wir die Felder vor dem Senden heraus und sagen es |
| `wlo_submit_contents`, `wlo_remove_from_collections`, `wlo_delete_collections` | als Pläne: eine Bestätigung, „Plan fortsetzen“ |
| `wlo_move_collection`, `wlo_order_collection`, `wlo_decide_collection_proposal` | zweistufig wie die übrigen Schreibwerkzeuge |
| `wlo_list_collection_proposals` | liest nur; im Lesemodus einer Einbettung erlaubt |
| `removeFrom` an `wlo_add_to_collections` | angeboten, wenn du `wlo_remove_from_collections` führst |
| „vorgeschlagen statt aufgenommen“ | die Beschreibung sagt der KI: Vorgeschlagen ist nicht aufgenommen |

## Woran wir deinen Stand erkennen

Wir lesen aus `tools/list` den Werkzeugnamen und die Parameter der obersten Ebene. Bitte halte
diese stabil:

- `list_collection_tree` mit `depth`;
- `order` an `browse_collection_tree` und `get_collection_overview`;
- `shared` an `wlo_create_collection_tree`;
- je neues Kuratier-Werkzeug ein Pflichtparameter: `items`, `pairs`, `nodeIds`, `newParentId`,
  `order`, `collectionId`, `decision`;
- `removeFrom` steht eine Ebene tiefer, die sehen wir nicht. Dafür nehmen wir
  `wlo_remove_from_collections` als Zeichen desselben Stands. Lieferst du die beiden je getrennt
  aus, sag es bitte.

Die Plan-Werkzeuge treiben wir mit derselben Schleife wie `wlo_add_to_collections`: `complete`,
`continuationToken`, `expiresAt` im strukturierten Teil, dazu `plan_expired`, `plan_mismatch`,
`too_many_plans`.

## Zwei Funde

1. **`more.nextSkipCount` über der eigenen Grenze** (in deiner Arbeitskopie vom 14.11. abends
   schon behoben: dort steht jetzt `skipLimitReached`). `list_collection_tree` nimmt `skipCount`
   bis 500. Bei Seiten zu 250 nannte die dritte Seite 750 als nächsten Wert; der Aufruf damit
   wurde abgelehnt. Wir lesen `skipLimitReached` wie `walkCapped`.
2. **Ein Fachportal löst sich über `collection` nicht auf.** „Physik“ ergibt
   `ambiguous_collection` mit Kandidaten wie „Physikalische Konstanten“. Für uns in Ordnung, die
   KI nimmt dort die Kennung; unsere Beschreibung sagt es ihr. Falls du es anders willst: Das
   Fachportal selbst fehlt unter den Kandidaten.

## Drei Wünsche aus dem Einbau

1. **Reihenfolge „gesetzte Position, sonst Titel“ (S11).** Unser Themenbaum-Modul braucht eine
   Reihenfolge, die immer passt. `stored` ist bei dir: die gesetzte Position, sonst die
   Reihenfolge des Anlegens. Für einen angelegten Lehrplan ist das richtig, für ein Fachportal
   beliebig, und die Antwort sagt uns nicht, welcher Fall vorliegt. Zwei Wege, such dir einen
   aus:
   - ein dritter Wert an `order` (etwa `position`): je Elternknoten die gesetzten Positionen,
     und wo keine gesetzt ist, alphabetisch; oder
   - je Knoten ein Merkmal, ob an seinen Untersammlungen Positionen gesetzt sind. Dann sortieren
     wir selbst.

   Gebraucht an `browse_collection_tree` (das liest das Modul) und `list_collection_tree`. Bis
   dahin bleibt das Modul alphabetisch.
2. **Inhaltszahlen in der Baumliste schneller (S12).** Gemessen am Fachportal Physik
   (144 Sammlungen), je dreimal:

   | Aufruf | Dauer |
   |---|---|
   | `list_collection_tree`, Tiefe 4, ohne `includeContentCounts` | 5,0 bis 6,4 s |
   | `list_collection_tree`, Tiefe 4, mit `includeContentCounts` | 10,5 bis 12,8 s |
   | `browse_collection_tree`, Tiefe 2, mit Zahlen | 3,6 bis 5,0 s |

   Als erster Aufruf eines frischen Prozesses dauerte die Liste mit Zahlen einmal 19 und einmal
   38 s. Unser Abgleich zeigt die Zahlen je Sammlung und braucht sie deshalb. Kein Muss: Dauert
   eine Seite länger als 30 s oder reicht die Zeit eines Zugs nicht, lesen wir zwei Ebenen wie
   bisher.

3. **Sag, wo die Baumliste nicht lesen konnte (S13).** `incomplete` und `restricted` gelten für
   den ganzen Lauf, `childrenUnread` und `childrenRefused` stehen nur an Einträgen der
   gelieferten Seite. Zwei Fälle sehen wir deshalb nicht:
   - die Auflistung der Startsammlung selbst fällt teilweise aus (dafür gibt es keinen Eintrag);
   - die betroffene Sammlung steht auf einer anderen Seite als der, die wir gerade lesen.

   Bis dahin behandeln wir jeden gemeldeten Ausfall so, als könnte er überall gewesen sein, und
   zeigen jeden neuen Punkt als „nicht gefunden“. Mit den Kennungen aller nicht gelesenen
   Eltern eines Aufrufs im Kopf der Antwort (die Startsammlung eingeschlossen) könnten wir das
   wieder auf den betroffenen Zweig begrenzen.

## Was bei uns liegt

- Ein Strukturentwurf darf bei uns 30 Punkte auf oberster Ebene haben, du nimmst 15. Das war schon
  vorher so und steht bei uns als offener Punkt.
- Das Fach aus einem Entwurf schicken wir nur mit, wenn dein Vokabular es kennt (Name oder
  Alias). Ein frei geschriebenes Fach ließe sonst den ganzen Baum scheitern, und die Person kann
  es im Entwurf nicht ändern.
- Der Themenbaum in unserem Widget bleibt vorerst alphabetisch (siehe Wunsch 1 oben).
- Der Abgleich liest die Baumliste so tief, wie der Entwurf reicht (zwei bis vier Ebenen), und
  höchstens drei Seiten zu 250 Einträgen. Was du nicht lesen konntest, zeigen wir als „nicht
  gefunden“ statt als „neu“:
  - `walkCapped`, `skipLimitReached` oder mehr Seiten, als wir lesen: ab der tiefsten gelesenen
    Ebene. Wir verlassen uns darauf, dass du Ebene für Ebene liest und die Liste so ordnest;
  - `incomplete` oder `restricted`: an jedem neuen Punkt (siehe Wunsch 3).

## Offen bei dir

- Der Deploy-Termin für Staging. Danach prüfen wir die Schreibwege im Chat mit Anmeldung.
- Zeigt die WLO-Oberfläche Vorschläge an eine Sammlung, und in welcher Reihenfolge zeigt sie
  Untersammlungen? Beides hast du als nicht gemessen genannt; wir können es auch nicht.
