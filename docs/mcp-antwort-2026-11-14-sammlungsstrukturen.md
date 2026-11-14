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
- **Zwei kleine Funde** für dich (unten) und eine Sache, die bei uns liegt.

## Was wir angebunden haben

| Bei dir | Bei uns |
|---|---|
| `list_collection_tree` | die KI bekommt es, wenn du es führst; die Liste geht ganz an sie und kommt nie aus unserem Cache |
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

1. **`more.nextSkipCount` über der eigenen Grenze.** `list_collection_tree` nimmt `skipCount` bis
   500. Bei Seiten zu 250 nennt die dritte Seite 750 als nächsten Wert; der Aufruf damit wird
   abgelehnt. Am Quelltext gelesen (`collection-tree-flat.ts`, `collection-tree-list.ts`), nicht
   gemessen: Staging hat keinen Baum dieser Größe.
2. **Ein Fachportal löst sich über `collection` nicht auf.** „Physik“ ergibt
   `ambiguous_collection` mit Kandidaten wie „Physikalische Konstanten“. Für uns in Ordnung, die
   KI nimmt dort die Kennung; unsere Beschreibung sagt es ihr. Falls du es anders willst: Das
   Fachportal selbst fehlt unter den Kandidaten.

## Was bei uns liegt

- Ein Strukturentwurf darf bei uns 30 Punkte auf oberster Ebene haben, du nimmst 15. Das war schon
  vorher so und steht bei uns als offener Punkt.
- Das Fach aus einem Entwurf schicken wir nur mit, wenn dein Vokabular es kennt (Name oder
  Alias). Ein frei geschriebenes Fach ließe sonst den ganzen Baum scheitern, und die Person kann
  es im Entwurf nicht ändern.
- Der Themenbaum in unserem Widget bleibt vorerst alphabetisch. „Gespeichert“ heißt ohne gesetzte
  Position „Reihenfolge des Anlegens“, und für ein Fachportal ist die beliebig. Wir stellen um,
  sobald klar ist, welche Reihenfolge die WLO-Oberfläche zeigt.

## Offen bei dir

- Der Deploy-Termin für Staging. Danach prüfen wir die Schreibwege im Chat mit Anmeldung.
- Zeigt die WLO-Oberfläche Vorschläge an eine Sammlung, und in welcher Reihenfolge zeigt sie
  Untersammlungen? Beides hast du als nicht gemessen genannt; wir können es auch nicht.
