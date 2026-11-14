# Werkzeug-Wünsche an den MCP: Sammlungsstrukturen anlegen und pflegen (2026-11-14)

Folge zu den [Wünschen vom 13.11.](mcp-werkzeug-wuensche-2026-11-13.md). Dort ging es um Tempo,
hier um das, was für den Weg „Lehrplan → Sammlungsbaum → Inhalte einsortieren → einreichen“ noch
fehlt.

## Kurzfassung

Wir haben dein Werkzeug-Inventar (33 lesend, 23 schreibend) gegen diesen Weg gelegt und das
Repository dort gemessen, wo du noch kein Werkzeug hast. Ergebnis:

- Für das **Anlegen** fehlen vier Dinge (S1 bis S4). S1 ist das wichtigste: Ein Lehrplan hat eine
  Abfolge, und die geht heute beim Lesen verloren.
- Für das **Pflegen** bestehender Bäume fehlen drei (S5 bis S7).
- Zwei Punkte betreffen Personen ohne Schreibrecht (S8, S9), einer ist nachrangig (S10).
- Das Repository kann alles, was wir wünschen: Reihenfolge, Umhängen, Kopieren und der Vorschlag
  an eine Sammlung antworten auf Staging richtig (Abschnitt „Gemessen“).
- Eine gute Nachricht nebenbei: Einsortieren (`PUT …/references`) antwortet auf Staging wieder
  mit 200. Der Live-Nachweis für `wlo_add_to_collections` ist damit möglich.

| Nr. | Wunsch | Nutzen | Aufwand bei dir |
|---|---|---|---|
| S1 | Reihenfolge der Untersammlungen lesen und setzen | der Baum steht so da, wie der Lehrplan ihn ordnet | klein (lesen), mittel (setzen) |
| S2 | Baum in der Tiefe lesen, in der er angelegt wird | Abgleich und Folgeschritte sehen den ganzen Baum | klein bis mittel |
| S3 | Fach, Stufe, Schlagworte je Knoten im Baum-Werkzeug | eine Bestätigung statt zwei | mittel |
| S4 | Einreichen im Stapel | nach einem Upload nicht 200 Bestätigungen | klein: Plan-Muster gibt es |
| S5 | Sammlung umhängen | bestehende Bäume umbauen | mittel |
| S6 | Inhalte im Stapel entfernen und umsortieren | bestehende Bäume umbauen | klein bis mittel |
| S7 | Leere Sammlungen im Stapel löschen | gefahrloses Rückgängig nach einem falschen Baum | klein |
| S8 | Vorschlag an eine Sammlung | Einsortieren ohne Schreibrecht, wie bei Metadaten | mittel, Rechte ungemessen |
| S9 | Vorschau sagt, ob ein Material öffentlich ist | „eingeordnet, aber noch nicht sichtbar“ | klein |
| S10 | Teilbaum kopieren | Vorlage für ähnliche Bäume | nachrangig |

Alle Wünsche sind additiv. Wir binden jeden an deine Werkzeugliste (`tools/list`), wie bei
`collection`, `add…` und der Mehrfachsuche: Es gibt keine Reihenfolge beim Deploy.

## Gemessen

Am 14.11.2026 gegen `repository.staging.openeduhub.net`, mit unserem Testkonto, nur an eigenen
Wegwerf-Knoten (eine private Sammlung mit Untersammlungen, fünf Testmaterialien im Eingang).
Danach alles gelöscht und das Löschen nachgeprüft (jeder Knoten antwortet mit 404).

| Was | Aufruf | Ergebnis |
|---|---|---|
| Vorgabe-Reihenfolge der Untersammlungen | `GET …/{id}/children/collections` ohne Sortierung | Reihenfolge des Anlegens (zwei Läufe: C, A, B und M, Z, A, K). Eine spätere Änderung an einem Kind ändert sie nicht. |
| Reihenfolge setzen (Untersammlungen) | `POST …/{id}/order`, Rumpf: Liste der Kennungen | 200. Jedes Kind bekommt `ccm:collection_ordered_position` (0, 1, 2 …). |
| Gesetzte Reihenfolge lesen | wie oben, mit `sortProperties=ccm:collection_ordered_position&sortAscending=true` | die gesetzte Reihenfolge. **Ohne** diesen Parameter bleibt es bei der Anlege-Reihenfolge. `orderMode` der Elternsammlung bleibt `null`. |
| Unvollständige Liste | `POST …/order` mit einem von drei Kindern | 200. Das genannte Kind bekommt 0, die anderen behalten ihre alten Werte: zwei Kinder standen danach beide auf 0. |
| Reihenfolge setzen (Inhalte) | `POST …/order` mit den Kennungen der **Verweise** | 200, Positionen gesetzt, lesbar mit demselben `sortProperties` an `children/references`. |
| dasselbe mit Original-Kennungen | | **400** `Node id … is not a children of the collection`. |
| Sammlung umhängen | `POST /node/v1/nodes/-home-/{neue Eltern}/children/_move?source={Sammlung}` | 200. Kennung bleibt, Titel bleibt, die Untersammlung darunter zieht mit, `level0` ist `false`. |
| Zähler nach dem Umhängen | `childCollectionsCount` der neuen Elternsammlung | sofort 0, nach 8 s 1. Die Zähler hinken nach. |
| Teilbaum kopieren | `POST …/{Quelle}/copy?targetCollection=…&copyChildCollections=true` | 200. Die Sammlung samt zwei Ebenen darunter steht als Kopie unter dem Ziel. |
| Vorschlag an eine Sammlung | `PUT …/{Sammlung}/references/{Material}?asProposal=true` | 200. Es entsteht ein Knoten `ccm:collection_proposal` mit `ccm:collection_proposal_status: PENDING`. Kein Verweis: `children/references` und `childReferencesCount` bleiben leer. |
| Vorschläge lesen | `GET …/{Sammlung}/children/proposals?status=PENDING` | Liste der vorgeschlagenen Materialien, je mit `proposal` (dem Vorschlags-Knoten) und `status`. |
| Rückwärtssuche zu einem vorgeschlagenen Material | `GET /usage/v1/usages/node/{id}/collections` | ein Eintrag mit `collectionUsageType: PROPOSAL_PENDING`. Dein Filter auf `ACTIVE` in `node-collections.ts` fängt das schon ab. |
| Vorschlag annehmen | gewöhnliches `PUT …/references/{Material}` | 200, der Verweis entsteht. Der Vorschlag bleibt aber **PENDING**. |
| Vorschlag ablehnen | `POST /node/…/{Vorschlags-Knoten}/property?property=ccm:collection_proposal_status`, Rumpf `["DECLINED"]` | 200. Der Vorschlag steht danach unter `status=DECLINED` und nicht mehr unter `PENDING`. |
| Einsortieren (gewöhnlich) | `PUT …/references/{Material}` | viermal 200. Der 500er (`InvalidTypeException`) aus deinen Unterlagen trat nicht mehr auf. |
| Zähler nach dem Einsortieren | `childReferencesCount` | direkt danach 0, nach 2 s 3. Die Wurzel-Sammlung zeigte 4, obwohl sie selbst keinen Verweis hält: Der Zähler scheint den Teilbaum zu zählen. |

Nicht gemessen, weil wir dafür ein zweites Konto oder fremde Daten bräuchten:

- ob eine Person **ohne** Schreibrecht an einer Sammlung dort vorschlagen darf (der eigentliche
  Zweck von S8);
- welche Reihenfolge die WLO-Oberfläche zeigt, solange `orderMode` leer ist;
- was `_move` mit lokal gesetzten Rechten macht (nach unseren älteren Notizen wechselt die
  Vererbung auf die neue Elternsammlung);
- `GET …/children/proposals/collections` (Sammlungen mit offenen Vorschlägen, über den Suchindex)
  gab direkt nach dem Vorschlagen eine leere Liste; ob das nur der Index-Verzug war, ist offen.

## S1 Reihenfolge der Untersammlungen

**Heute.** `browse_collection_tree` sortiert jede Ebene nach Titel (`sortByTitle` in
`collection-traversal.ts`). `wlo_create_collection_tree` legt Geschwister nacheinander an, also in
der Reihenfolge, in der wir sie nennen. Das Repository behält diese Reihenfolge (Tabelle oben).
Beim Lesen über dich ist sie weg: „3 Optik“ steht vor „1 Mechanik“ nur dann richtig, wenn die
Titel zufällig sortierbar sind.

**Wunsch.**

1. **Lesen:** `browse_collection_tree` und `get_collection_overview` geben die Untersammlungen in
   der Reihenfolge des Repositorys zurück (Position, wenn gesetzt, sonst Anlege-Reihenfolge), oder
   bekommen dafür einen Parameter (`order: "stored" | "title"`). Für uns reicht das schon für den
   ersten Schritt.
2. **Schreiben im Baum:** Nach dem Anlegen einer Ebene `POST …/order` mit allen Kindern in der
   genannten Reihenfolge. Dann steht die Abfolge ausdrücklich da und hängt nicht am
   Anlege-Zeitpunkt. Bei `merge` mit vorhandenen Geschwistern: die vorhandenen behalten ihren
   Platz, neue kommen dahinter, oder die Vorschau fragt.
3. **Eigenes Werkzeug** `wlo_order_collection {collectionId, order: [nodeId …]}` für
   Untersammlungen und Inhalte. Zwei Dinge aus der Messung gehören hinein: Die Liste muss alle
   Kinder nennen (sonst doppelte Positionen), und bei Inhalten braucht das Repository die
   Kennung des Verweises. Das Werkzeug sollte Original-Kennungen annehmen und selbst auflösen.

**Bei uns.** Der Strukturentwurf trägt die Reihenfolge schon. Der Themenbaum und der
Strukturabgleich zeigen sie, sobald du sie lieferst.

## S2 Baum in der Tiefe lesen, in der er angelegt wird

**Heute.** Anlegen: Tiefe 4, 250 Knoten. Lesen: `browse_collection_tree` bis Tiefe 3, 300 Knoten.
Unser Abgleich „Entwurf gegen Bestand“ arbeitet deshalb nur mit zwei Ebenen, und nach dem Anlegen
können wir den Baum nicht in einem Aufruf zurücklesen.

**Wunsch.** `depth` bis 4, oder ein Auszug des Teilbaums als flache Liste mit Pfad und Kennung
(`[{nodeId, path: ["Physik", "Optik", "Linsen"], contentsCount?}]`), in Seiten. Die flache Form
wäre uns lieber: Sie ist kleiner, und genau so rechnet der Abgleich.

## S3 Fach, Stufe, Schlagworte je Knoten im Baum-Werkzeug

**Heute.** Ein Knoten im Baum trägt Titel und Beschreibung. Fach, Stufe und Schlagworte an einer
Sammlung gehen seit dem 13.11. über `wlo_update_contents`, also mit einem zweiten Aufruf und einer
zweiten Bestätigung, und erst, wenn die Kennungen aus dem ersten zurück sind.

**Wunsch.** `discipline`, `educationalContext`, `keywords` je Knoten, dazu gemeinsame Werte für
den ganzen Baum (wie die gemeinsamen Filter der Mehrfachsuche), die ein Knoten überschreiben kann.
Vokabular streng wie beim Schreiben (kein Teilwort-Treffer). Bei `merge`: Die Vorschau sagt
weiter, dass ein vorhandener Knoten unverändert bleibt; ein Schalter „vorhandene ergänzen“ wäre
der zweite Schritt.

## S4 Einreichen im Stapel

**Heute.** `wlo_submit_content` nimmt einen Datensatz. Der Weg „Ordner hochladen → Metadaten →
einsortieren → zur Prüfung einreichen“ endet bei 200 Dateien mit 200 Bestätigungen.

**Wunsch.** `wlo_submit_contents {items: [{nodeId}], comment?}`, bis 200, als Plan wie
`wlo_add_to_collections`: eine Bestätigung, `already_submitted` zählt als erledigt, ein
gescheiterter Eintrag hält die anderen nicht auf.

## S5 Sammlung umhängen

**Heute.** Kein Werkzeug. Ein Punkt, der im Bestand an der falschen Stelle hängt, lässt sich nur
löschen und neu anlegen; die Verweise darin gingen dabei verloren.

**Gemessen.** `_move` hängt eine Sammlung samt Untersammlungen um, die Kennung bleibt (Tabelle).

**Wunsch.** `wlo_move_collection {nodeId, newParentId}`, später als Liste. Die Vorschau sollte
nennen: alte und neue Elternsammlung mit Pfad, wie viele Untersammlungen mitziehen, und dass die
Rechte danach von der neuen Elternsammlung kommen. Ablehnen, wenn das Ziel im eigenen Teilbaum
liegt oder dort schon eine Sammlung gleichen Titels steht.

## S6 Inhalte im Stapel entfernen und umsortieren

**Heute.** `wlo_remove_from_collection` nimmt ein Paar. Ein Material von einer Sammlung in eine
andere zu legen heißt: hinzufügen (Stapel möglich), dann je Material einzeln entfernen.

**Wunsch.** `wlo_remove_from_collections {pairs}` als Plan, und in `wlo_add_to_collections` je
Paar ein optionales `removeFrom` (Kennung der Quell-Sammlung). Reihenfolge je Paar: erst
hinzufügen, zurücklesen, dann entfernen. Scheitert das Entfernen, liegt das Material in beiden,
und die Antwort sagt es.

## S7 Leere Sammlungen im Stapel löschen

**Heute.** `wlo_delete_collection` löscht eine Sammlung samt Untersammlungen und den Originalen,
die direkt darin liegen. Für „der Baum war falsch, bitte zurück“ ist das zu grob, sobald mit
`merge` in einen bestehenden Baum angelegt wurde.

**Wunsch.** `wlo_delete_collections {nodeIds}`, das **nur leere** Sammlungen löscht (keine
Untersammlung, kein Verweis, kein Original; direkt gelesen, nicht über die Zähler, die hinken).
Alles andere kommt als `not_empty` zurück. Noch besser: Die Antwort von
`wlo_create_collection_tree` trägt eine Kennung des Plans, und das Löschen nimmt sie an
(„was dieser Plan angelegt hat und noch leer ist“).

## S8 Vorschlag an eine Sammlung

**Heute.** Wer an einer Sammlung nicht schreiben darf, bekommt `forbidden`. Für Metadaten gehst du
in dem Fall den Weg über Vorschläge (`wlo_suggest_metadata`, `wlo_update_contents`).

**Gemessen.** Das Repository kennt dasselbe für Sammlungen (Tabelle): vorschlagen, auflisten,
ablehnen. Annehmen ist zweiteilig: Verweis anlegen **und** den Status am Vorschlags-Knoten auf
`ACCEPTED` setzen. Das ist dieselbe Falle wie bei den Metadaten-Vorschlägen, wo „angenommen“
allein nichts schreibt.

**Wunsch.**

- `wlo_add_to_collection(s)`: bei fehlendem Schreibrecht statt `forbidden` einen Vorschlag
  anlegen und das je Paar sagen (`proposed`), wie `wlo_update_contents` es je Feld tut.
- `wlo_list_collection_proposals {collectionId, status}` und
  `wlo_decide_collection_proposal {collectionId, nodeId, decision}`.

**Vorher zu klären (bei dir, mit zwei Konten):** Darf eine Person ohne Schreibrecht überhaupt
vorschlagen, und sieht die Redaktion den Vorschlag in der WLO-Oberfläche?

## S9 Vorschau sagt, ob ein Material öffentlich ist

**Heute.** Einsortieren in eine öffentliche Sammlung macht ein Material nicht öffentlich (in der
Python-Bibliothek gemessen und dokumentiert). Deine Antworten sagen dazu nichts; lesend gibt es
nur `accessInfo` (Login, Kosten).

**Wunsch.** In der Vorschau von `wlo_add_to_collection(s)` je Material ein Feld `public: false`
und ein Satz („3 der 12 Materialien sind noch nicht öffentlich; sichtbar werden sie nach der
Prüfung“). Kein Werkzeug zum Setzen von Rechten: Das bleibt der Redaktion über das Einreichen.

## S10 Teilbaum kopieren

`POST …/{Quelle}/copy` kopiert eine Sammlung samt Untersammlungen (gemessen). Als Vorlage für
ähnliche Bäume (derselbe Aufbau für ein anderes Bundesland oder eine andere Stufe) wäre das
nützlich. Nachrangig: Mit `wlo_create_collection_tree` und einem gelesenen Baum (S2) geht es
auch.

## Beobachtungen

- **B1 Einsortieren auf Staging geht wieder.** Viermal 200 mit eigenem Material aus dem Eingang.
  Der Live-Test für `wlo_add_to_collections` und `addToCollectionId` ist damit möglich.
- **B2 Zähler hinken und zählen wohl den Teilbaum.** `childReferencesCount` und
  `childCollectionsCount` stimmen erst Sekunden nach einer Änderung, und an der Wurzel standen die
  Verweise der Untersammlungen mit drin. Wo du diese Zähler ausgibst (Inhaltszahlen im Baum),
  wäre ein Satz dazu gut; zum Zurücklesen nach einem Schreibvorgang taugen sie nicht.
- **B3 Nicht bewusst weggelassen, aber auch nicht gewünscht:** Icon, Farbe, Anheften, Kommentare,
  Bewertungen, Rechte setzen. Das brauchen wir für diesen Weg nicht.

## Reihenfolge, die wir vorschlagen

1. S1 (Lesen in der Reihenfolge des Repositorys) und S2: beide nur lesend, sofort nützlich.
2. S4 und S3: sie schließen den Weg vom Upload bis zum Einreichen.
3. S1 (Setzen), S6, S7.
4. S5 und S8, wenn der Umbau bestehender Bäume und das Einsortieren ohne Schreibrecht anstehen.
