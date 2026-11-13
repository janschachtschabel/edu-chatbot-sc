# Werkzeug-Wünsche an den MCP: weniger Runden, weniger Wartezeit (2026-11-13)

Nachtrag zur [Rückmeldung vom 13.11.](mcp-rueckmeldung-2026-11-13.md). Dort geht es um Fehlerfälle
und den Diensteleitfaden, hier um Tempo und um das, was beim Kürzen aufgefallen ist.

## Kurzfassung

Wir haben geprüft, wo der Chatbot KI-Runden und Wartezeit verliert. Eine KI-Runde ist ein Aufruf
des Sprachmodells; jedes Werkzeug-Ergebnis, auf das die KI erst reagieren muss, kostet eine weitere.

- Einen Teil haben wir auf unserer Seite gekürzt (vorletzter Abschnitt). Dafür verlassen wir uns
  jetzt auf einige Eigenschaften deines Servers. Bitte halte sie stabil.
- Beim Kürzen ist ein Fehlerrisiko im Schreibpfad aufgefallen (Z1). Das ist der wichtigste Punkt.
- Fünf Wünsche und zwei Beobachtungen bleiben. Alle sind additiv oder verschärfen nur eine
  Prüfung; keiner braucht ein Sprachmodell im MCP.

| Nr. | Wunsch | Nutzen | Aufwand bei dir |
|---|---|---|---|
| Z1 | Schreiben nimmt keine Teilwort-Treffer still an, sondern nennt Kandidaten | verhindert falsche Fächer und Stufen im Bestand | klein: Trefferart und `suggestVocab` gibt es schon |
| Z2 | Vorschautext nennt den Datensatz und zeigt den Inhaltstyp lesbar | die Person sieht, woran sie etwas ändert | klein |
| Z3 | Sammlung per Name, zusätzlich zur `nodeId` | spart in etwa der Hälfte der Fälle eine KI-Runde | mittel |
| Z4 | Mehrere Suchen in einem Aufruf | Lernpfad: ein Aufruf statt 4–6 | mittel |
| Z5 | Vorschau des Anlegens nennt ähnliche Adressen | spart einen Aufruf je Erschließung | klein |

Beobachtungen: B1 (ein Wert je Fach, Stufe, Typ, Zielgruppe) und B2 (das Nachschlage-Werkzeug
listet für den Inhaltstyp ein anderes Vokabular, als das Schreiben prüft).

Alle Messungen stammen vom 13.11. Suchen und Zeiten: gegen den Staging-MCP, nur lesend, ohne
unseren Cache. Vokabular-Beispiele: am gebauten Stand deiner Arbeitskopie (`dist/`) nachgerechnet,
ohne Netz.

## Z1 Schreiben: Teilwort-Treffer nicht still annehmen

**Heute.** `vocabularyUris` (`services/write/fields.ts`) löst Fach, Bildungsstufe und Zielgruppe
mit `resolveVocab` auf. Das nimmt nach gleichem Namen und Alias auch einen Teilwort-Treffer ab vier
Zeichen; der erste Eintrag der Tabelle gewinnt (`vocabs.ts`). Für die Suche ist das richtig, ein
Filter ohne Treffer schadet nicht. Beim Schreiben setzt es still einen anderen Wert:

| Eingabe | wird geschrieben als | `suggestVocab` nennt |
|---|---|---|
| Wirtschaft | Agrarwirtschaft | Landwirtschaft, Hauswirtschaft, Wirtschaftskunde |
| Technik | Arbeitslehre | Bautechnik, Polytechnik, Holztechnik |
| Kunstgeschichte | Geschichte | Geschichte, Kunst |
| Mathematik und Physik | Mathematik | Mathematik, Physik |
| Gesamtschule | Schule | Schule |
| Sekundarstufe | Sekundarstufe I | Sekundarstufe1, Sekundarstufe 2 |
| Eltern und Lehrer | Eltern | Eltern, Lehrer |

Abgelehnt werden nur Wörter ohne jeden Teilwort-Treffer, etwa „Naturlehre“ oder „Lehrkräfte“.

**Warum es jetzt drängt.** Fach, Stufe und Zielgruppe ersetzen beim Ändern alle bisherigen Werte
(B1). Ein Datensatz mit Physik und Chemie trägt nach „Fach: Wirtschaft“ nur noch Agrarwirtschaft.
Die Vorschau zeigt den neuen Wert, die Person muss den Unterschied aber selbst bemerken. Der
Chatbot weist die KI inzwischen an, eine Abweichung zu nennen; in unserer Messung tat sie das in
drei von drei Läufen. Das ist eine Hilfe, keine Sicherung.

**Vorschlag.**

- Im Schreibpfad nur die Trefferarten `exact` und `alias` annehmen. `resolveVocabMatch` liefert die
  Art schon.
- Ein `fuzzy`-Treffer wird abgelehnt wie ein unbekanntes Wort, mit Kandidaten: der Teilwort-Treffer
  selbst und was `suggestVocab(wert, vokabular)` nennt (`vocab-suggest.ts`, Editierabstand und
  Teilwort über Bezeichnungen und Aliasse).
- Im Text, wie heute schon beim Inhaltstyp: „‚Wirtschaft‘ kommt im Vokabular für ‚Fach‘ nicht vor.
  Meintest du: Agrarwirtschaft, Wirtschaftskunde, Hauswirtschaft?“
- Im strukturierten Teil, damit ein Programm es lesen kann:
  `candidates: [{ field: "discipline", value: "Wirtschaft", suggestions: ["Agrarwirtschaft", …] }]`.
  `rejectionReply(reasons, extra)` nimmt das zweite Argument schon.
- Die Suche bleibt, wie sie ist.

Falls du das Annehmen behalten willst: dann wenigstens im Vorschautext und im strukturierten Teil
sagen, dass der Wert abgeglichen wurde („Agrarwirtschaft, aus ‚Wirtschaft‘“).

**Nutzen für das Tempo.** Nach einer Ablehnung mit Kandidaten wählt die KI ohne
`lookup_wlo_vocabulary`. Ohne Kandidaten brauchte sie in unserer Messung drei Runden statt zwei
(Änderung, Nachschlagen, Antwort an die Person).

**Ohne Sprachmodell möglich?** Ja. Dein Server nennt nur die nächsten Einträge; die Wahl trifft die
KI des Clients oder die Person.

## Z2 Vorschautext nennt den Datensatz und zeigt den Inhaltstyp lesbar

**Heute.** Der Vorschautext einer Metadaten-Änderung besteht nur aus den Feldzeilen
(`renderChangeSet`), zum Beispiel:

```
Fach: „Physik, Chemie“ → „Mathematik“
Schlagwörter: + Linsen
```

- Titel und Kennung des Datensatzes stehen nur im strukturierten Teil
  (`confirm.preview.target`). Im Text steht der Titel nur beim Löschen; bei einer Verknüpfung
  steht dort die Kennung des Originals, ohne Titel.
- Eine Sammlung, die über `wlo_update_content` geändert wird, meldet der strukturierte Teil als
  `kind: "content"`, und ihr Titel kommt aus `cclom:title`. Nach `collection-fields.ts` kann das
  auf einer Sammlung ein Altwert sein, den ihre Ansicht nicht zeigt.
- Der Inhaltstyp steht alt und neu als Adresse (`http://w3id.org/…/new_lrt/…`), weil
  `PREVIEW_VOCAB` das Feld `ccm:oeh_lrt` nicht kennt.

**Folge.** Wer die Vorschau liest, sieht nicht, an welchem Datensatz sich etwas ändert, und kann
beim Inhaltstyp alt und neu nicht lesen. `wlo_update_content` ändert auch Sammlungen; auch das
sieht man nicht.

**Was wir getan haben.** Der Chatbot setzt seit heute „Geändert wird (Kennung): ‚Titel‘“ aus dem
strukturierten Teil vor den Vorschautext. Ob es ein Datensatz oder eine Sammlung ist, sagt die
Zeile nicht, weil `kind` das nicht verlässlich trägt. Andere Clients haben die Zeile nicht.

**Vorschlag.**

- Eine erste Zeile im Text mit Art, Titel und Kennung.
- `target.kind` und `target.title` für Sammlungen aus dem Sammlungsfeld setzen (wie `titleOn`
  es beim Vorschlagen schon tut).
- Beim Inhaltstyp die Bezeichnung statt der Adresse.

Nennt dein Text das Ziel in der Form `„Titel“ (Kennung)`, wie es Einreichen und Vorschlagen
schon tun, lässt unser Client seine Zeile von selbst weg.

## Z3 Sammlung per Name, zusätzlich zur `nodeId`

**Heute.** Diese Werkzeuge brauchen die Kennung der Sammlung: `get_collection_overview`
(`collectionId`), `get_collection_contents`, `get_compendium_text`,
`search_wlo_within_collection` und `browse_collection_tree` (dort gibt es schon `subject` für ein
Fachportal, aber nichts für eine Sammlung darunter). Für „Was gibt es unter Optik?“ ruft die KI
erst `search_wlo_collections` auf, liest das Ergebnis und ruft dann das eigentliche Werkzeug. Das
sind zwei KI-Runden vor der Antwort.

**Vorschlag.**

- Ein zusätzlicher, optionaler Parameter `collection` (Titel der Sammlung) an diesen fünf
  Werkzeugen, dazu optional das Fach zum Eingrenzen. Der Name dafür ist dein Entscheid;
  `discipline` geht nicht überall, weil `search_wlo_within_collection` ihn schon als
  Inhaltsfilter führt. Denkbar ist `collectionSubject`.
- Die Kennung bleibt und hat Vorrang. Wer sie hat, ändert nichts.
- Die Schreibwerkzeuge bleiben bei der Kennung.

**Geht die Auswahl ohne Sprachmodell?** Für einen klar abgegrenzten Teil ja. Die Regel:

1. Mit Titel und Fach die vorhandene Sammlungssuche fragen, so wie `search_wlo_collections` es
   tut (`searchCollectionsResult`, der Fachfilter sitzt heute im Werkzeug).
2. Titel bereinigen: Groß- und Kleinschreibung, „ß“ wie „ss“, Leerzeichen und Bindestriche.
3. Trägt **genau ein** Treffer denselben Titel, ist er gemeint. Das Werkzeug läuft damit weiter.
4. In jedem anderen Fall läuft das Werkzeug **nicht**. Die Antwort trägt den Code
   `ambiguous_collection` und bis zu fünf Kandidaten. Die KI des Clients wählt dann, wie heute.
5. Kein Raten über Wortanfang oder Teilwort. Bei den Fachportalen (`matchSubjectPortal`) trägt das,
   weil es eine geschlossene, kurze Liste ist. Bei Tausenden Sammlungen träfe es zu oft die
   falsche; Z1 zeigt, wohin das führt.

**Was die Regel leistet (24 Namen, je mit und ohne Fach).**

| | genau ein gleicher Titel | mehrere gleiche Titel | kein gleicher Titel |
|---|---|---|---|
| mit Fach | 13 | 0 | 11 |
| ohne Fach | 8 | 4 | 12 |

- Stand ein gleicher Titel im Ergebnis, dann immer auf Platz 1.
- Er steht aber nicht immer im Ergebnis. „Evolution“, „Mittelalter“ und „Weimarer Republik“ fand
  die Suche nur mit Fach; ohne Fach fehlte der gleiche Titel unter den zehn Treffern. „Grammatik“
  und „Klimawandel“ fand sie nur ohne Fach, also nicht unter dem Fach, das wir angaben (Deutsch,
  Geografie). „Kein gleicher Titel im Ergebnis“ heißt deshalb nicht „gibt es nicht“; auch dafür
  ist die Kandidaten-Antwort da.
- Mit Fach gab es keine Mehrdeutigkeit. Ohne Fach viermal: „Mechanik“ ×2, „Grammatik“ ×2,
  „Rechtschreibung“ ×3, „Klimawandel“ ×2. Deshalb gehört das Fach dazu, und mehrere gleiche Titel
  dürfen nie still entschieden werden.
- Ohne gleichen Titel blieben Namen wie „Genetik“ (vorhanden: „Genetik und Vererbung“,
  „Molekulargenetik“, „Klassische Genetik“) oder „Demokratie“ („Demokratie in Deutschland“, „Krise
  der Demokratie“). Hier braucht es Sprachverständnis; das bleibt beim Client.
- Die Stichprobe ist klein und von Hand gewählt, und auf Staging liegen Testsammlungen.

In rund der Hälfte der Fälle spart der Parameter also eine KI-Runde. In der anderen Hälfte kostet
er nichts, wenn die Kandidaten-Antwort so viel trägt wie heute ein Suchergebnis.

**Was die Antwort braucht.**

- Bei Erfolg, vor dem eigentlichen Ergebnis: welche Sammlung gewählt wurde, im Text („Sammlung:
  Optik, unter Physik“) und strukturiert (`resolvedCollection: { nodeId, title, path }`). Sonst
  sieht niemand, wenn die falsche getroffen wurde.
- Bei `ambiguous_collection`: je Kandidat `nodeId`, `title`, `path` und `contentsCount`. Der Pfad
  fehlt heute im Ergebnis von `search_wlo_collections`; zwei Sammlungen „Mechanik“ sind dort nicht
  zu unterscheiden.

**Kosten.** Die Sammlungssuche läuft dann in deinem Server statt als eigener Aufruf von uns
(gemessen 1,3–3,2 s). Die Auflösung lässt sich kurz zwischenspeichern (`short-cache.ts`).

**Offen auf unserer Seite.** Wie der Chatbot den Parameter nutzt, entscheiden wir, wenn er da ist
(Master-Skill, Modul `ui_themenbaum`). Du musst darauf nicht warten.

## Z4 Mehrere Suchen in einem Aufruf

**Heute.** Für einen Lernpfad sucht die KI je Schritt ein Material, also 4–6 Mal
`search_wlo_content`. Der Chatbot arbeitet die Aufrufe einer Runde nacheinander ab.
`count_wlo_content_matches` nimmt zwar viele Anfragen, sucht aber ohne Varianten und Umsortierung
und liefert je Treffer nur Kennung, Titel und Adresse.

**Gemessen (fünf Suchen zu Optik, Fach Physik, je fünf Treffer).**

| | je Suche | zusammen |
|---|---|---|
| nacheinander | 4,2 · 2,5 · 2,2 · 1,8 · 2,1 s | 12,8 s |
| gleichzeitig vom Client | 6,1 · 5,4 · 4,6 · 3,6 · 2,9 s | 6,1 s |

Gleichzeitig halbiert die Zeit, mehr nicht: jede einzelne Suche wird langsamer. Nach dem Quelltext
liegt das nahe, denn fünf Suchen mit bis zu fünf Varianten (`query-expand.ts`) sind bis zu 25
Anfragen ans Repositorium, die Schranke lässt 24 zugleich durch (`upstream-gate.ts`). Ob die
Schranke oder das Repositorium bremst, haben wir nicht gemessen.

**Vorschlag.** Ein eigenes Werkzeug in der Form von `count_wlo_content_matches`, etwa
`search_wlo_content_many`:

- Eingabe: `queries: [{ id, query, filters? }]` (höchstens 8), gemeinsame Filter daneben,
  `maxResults` je Anfrage (höchstens 5).
- Ausgabe je Anfrage unter ihrer `id`: die Treffer in Kurzform, dazu `missing` wie beim Zählen.
- Ein eigenes Werkzeug statt eines neuen Parameters an `search_wlo_content`, weil das
  Ausgabeschema ein anderes ist.

**Auf Zeit gebaut.** Das war die Bitte des Nutzers; diese Stellschrauben sehen wir im Quelltext:

- Gemeinsame Filter einmal auflösen, nicht je Anfrage.
- Weniger Varianten je Anfrage als bei der Einzelsuche, zum Beispiel drei. Für die besten drei bis
  fünf Treffer genügt auch ein kleineres Fenster als 25 je Variante.
- Alle Anfragen ans Repositorium in einem gemeinsamen Vorrat durch die Schranke, mit einem
  Höchstanteil. So verdrängt ein Stapel die anderen Nutzer nicht.
- Eine Frist je Anfrage und eine für den ganzen Aufruf. Was nicht fertig wird, steht in `missing`
  (`timeout`); der Aufruf scheitert nicht als Ganzes.
- Kein Nachfüllen über weitere Fenster, kein Volltext.
- Treffer in Kurzform: `nodeId`, `title`, `url`, Beschreibung bis 200 Zeichen, Inhaltstyp, Lizenz,
  Bildungsstufe.
- Wahlweise `distinct: true`: Ein Material erscheint nur bei der Anfrage, zu der es am besten
  passt. Für einen Lernpfad ist das die gewünschte Form.

Als Ziel schlagen wir vor: fünf Anfragen deutlich unter den 6,1 s, die fünf gleichzeitige
Einzelsuchen heute brauchen. Das ist ein Messziel, keine Zusage von uns.

**Ohne Sprachmodell möglich?** Ja, es ist dieselbe Suche, nur gebündelt.

## Z5 Vorschau des Anlegens nennt ähnliche Adressen

**Heute.** Die Vorschau von `wlo_create_content` lehnt ab, wenn es die Adresse in genau dieser
Schreibweise schon gibt (`findByUrl`); mit `addToCollectionId` bietet sie stattdessen an, den
vorhandenen Datensatz einzusortieren. Bereinigte Schreibweisen findet nur `find_content_by_url`.
Deshalb rufen wir beide auf.

**Vorschlag.** Findet die Vorschau einen Datensatz unter einer bereinigten Schreibweise, steht er
als Hinweis in der Vorschau, so wie heute der gleiche Titel am Ablageort („Möglicherweise eine
Dublette“). Er blockiert nicht. Die Person entscheidet mit ihrem Ja.

**Nutzen.** `find_content_by_url` vor dem Anlegen entfällt. Das spart einen Aufruf, keine Runde,
denn wir bündeln ihn schon mit `get_url_text`. Kleiner Wunsch.

## B1 Beobachtung: ein Wert je Fach, Stufe, Typ und Zielgruppe

- `discipline`, `educationalContext`, `contentType` und `userRole` sind im Schema ein einzelner
  Text. Bei `wlo_update_content` ersetzt er alle bisherigen Werte; nur Schlagwörter werden ergänzt
  (`MERGED_PROPERTIES`).
- Ein Datensatz mit Physik und Chemie lässt sich so nicht um Mathematik ergänzen. Er trägt danach
  nur Mathematik.
- Die Feldprüfung nimmt schon eine Liste an (`fields.ts`, `Array.isArray(input)`); nur das Schema
  lässt sie nicht durch.
- Vorschlag: `string | string[]` im Schema (additiv) und ein Satz in der Beschreibung, dass diese
  Felder ersetzt werden. Ob es zusätzlich ein Ergänzen geben soll, ist eine fachliche Frage an
  die Redaktion.
- Der Chatbot sagt der KI seit heute, dass diese Felder ersetzt werden. Bittet jemand um
  „Mathematik hinzufügen“, öffnet die KI in unserer Messung trotzdem die Ersetzen-Vorschau und
  warnt im Begleitsatz. Sauber lösen lässt sich das nur bei dir.

## B2 Beobachtung: Inhaltstyp, zwei Vokabulare

- Der Schreibpfad prüft den Inhaltstyp gegen `new_lrt` und verlangt den genauen Namen. „Video“
  wird abgelehnt (dort heißt es „Video (Material)“), „Arbeitsblatt“ und „Audio“ gehen. Die
  Ablehnung nennt Kandidaten; das ist gut.
- `lookup_wlo_vocabulary` mit `lrt` listet das zusammengefasste Vokabular. Dessen Adressen lehnt
  der Schreibpfad ab. Wer nach einer Ablehnung nachschlägt, bekommt also Werte, die wieder
  abgelehnt werden.
- Bei einer doppeldeutigen Bezeichnung (etwa „Stationenlernen“) verlangt die Ablehnung „als URI
  angeben“, nennt die Adressen aber nicht (`fields-lrt.ts`). Dort gibt es für einen Client keinen
  Ausweg.
- Das Beispiel „Video“ steht in der Beschreibung des Feldes `contentType` (`curation-fields.ts`).
- Der Chatbot sagt der KI seit heute, beim Inhaltstyp einen Kandidaten aus der Ablehnung zu nehmen
  und nicht nachzuschlagen.
- Vorschlag: das Beispiel ändern, bei Doppeldeutigkeit die Adressen in der Ablehnung nennen, und
  `lookup_wlo_vocabulary` einen Eintrag für das Vokabular geben, das das Schreiben prüft.

## Was wir nicht wünschen

- **Ein Kombi-Werkzeug für das Browser-Plugin** (Seitentext, Dublette, Skill-Katalog und Anleitung
  in einem). Der Katalog liegt auf Sammlungsseiten schon vorab in unserer Kette, den Rest bündeln
  wir in einer Runde. Übrig bliebe wenig, erkauft mit vier gekoppelten Fehlerquellen.
- **Namensauflösung in Schreibwerkzeugen.** Dort bleibt die Kennung Pflicht.
- **Ein Sprachmodell im MCP.** Keiner der Wünsche braucht eines.

## Was der Chatbot selbst gekürzt hat, und worauf er sich dabei verlässt

| Kürzung bei uns | Eigenschaft deines Servers, auf die wir uns verlassen |
|---|---|
| Kein Aufwärm-Aufruf mehr vor der Themenseiten-Suche | Der Server ist zustandslos; `search_wlo_topic_pages` mit `query` sucht die Sammlungen selbst. Acht Themen, achtmal dasselbe Ergebnis mit und ohne Aufwärmen. |
| Metadaten ändern ohne `lookup_wlo_vocabulary` davor | Die Schreibwerkzeuge nehmen Bezeichnungen und schreiben nichts, bevor die Person die Vorschau bestätigt hat. |
| Metadaten ändern ohne `get_node_details` davor | Die Vorschau zeigt je Feld den bisherigen und den neuen Wert; der strukturierte Teil trägt Titel und Kennung (`confirm.preview.target`). |
| Die KI sagt, was ersetzt und was ergänzt wird | Bei `wlo_update_content` werden Schlagwörter ergänzt, Fach, Stufe, Typ und Zielgruppe ersetzt. |

Ändert sich eine dieser Eigenschaften, brauchen wir vorher Bescheid. Z1 und Z2 ändern sie in
unserem Sinn, und unser Client läuft damit ohne Anpassung weiter. Nach Z1 ziehen wir aber unsere
Texte nach: Sie sagen der KI heute, dass dein Server auch über Teilwörter abgleicht.

## Vorschlag für die Reihenfolge

1. Z1, weil es falsche Werte im Bestand verhindert und die Bausteine schon da sind.
2. Z2, klein und für jeden Client nützlich.
3. Z3, weil es die meisten Anwendungsfälle trifft (Sammlung zeigen, Lernpfad auf einer Sammlung,
   Prüfen).
4. Z4, sobald Z3 steht. Vorher lohnt eine Messung bei dir, wo die Zeit der Einzelsuche bleibt.
5. Z5, B1 und B2 nach Gelegenheit.

Direkt umsetzbar ohne Entscheidung des Nutzers: Z1, Z2, Z5 und B2. Bei Z3 und Z4 sind die Namen der
Parameter und des Werkzeugs dein Entscheid. Für B1 braucht das Ergänzen eine Antwort der Redaktion.
