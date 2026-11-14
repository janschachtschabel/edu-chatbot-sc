# Strukturabgleich bis Ebene 4 (2026-11-14)

Plan [`2026-11-14-sammlungsstruktur-werkzeuge.md`](../plans/2026-11-14-sammlungsstruktur-werkzeuge.md),
Paket SW-4. Baut auf SW-1 auf ([Notiz](2026-11-14-sammlungsbaum-lesen-und-metadaten.md)).

Der MCP-Server kennt `list_collection_tree` ab dem Stand „Sammlungsstrukturen“ (14.11.2026); der
bereitgestellte führt es nicht. Bis er es tut, liest der Abgleich wie bisher zwei Ebenen. Zwei
kleine Änderungen gelten sofort, siehe „Was sich am alten Weg ändert“.

## Was sich ändert

Das Modul `ui_strukturabgleich` vergleicht einen Strukturentwurf mit einer WLO-Sammlung. Bisher
ging das für Ebene 1 und 2. Ein Entwurf und ein angelegter Sammlungsbaum haben aber bis zu vier
Ebenen.

- **Mit dem neuen Server** liest der Dienst den Baum als Liste (`list_collection_tree`, mit
  Inhaltszahlen) und gleicht alle Ebenen des Entwurfs ab, bis zu vier. Gelesen wird so tief, wie
  der Entwurf reicht, mindestens zwei Ebenen (SE-11).
- **Ohne ihn** bleibt es bei `browse_collection_tree` und zwei Ebenen. Dasselbe gilt, wenn die
  Redaktion die Baumliste am MCP-Server abgeschaltet hat, wenn die Zeit nicht reicht oder wenn
  die Liste ausfällt.
- **Die Regel je Ebene ist dieselbe wie bisher für Ebene 2:** Ein Punkt wird zuerst unter der
  Sammlung gesucht, die seinem Elternpunkt zugeordnet ist. Hat der Elternpunkt keine, wird er mit
  den übrigen Sammlungen derselben Ebene verglichen.
- **Im Modul** stehen tiefere Punkte eingerückt unter ihrem Punkt. „Nur in WLO“ nennt Ebene 1
  bis 4 und die Elternsammlung.
- **Gefunden ohne Elternpunkt:** Wurde ein Punkt nicht unter der Sammlung seines Elternpunkts
  gefunden, sondern irgendwo auf seiner Ebene, steht dabei, unter welcher Sammlung („in WLO:
  Grundlagen · unter Mechanik“). Titel wie „Grundlagen“ gibt es in vielen Zweigen.

## Entscheide

- **Maßgeblich ist der Stand des Servers, nicht das Angebot des Zugs** (SE-5). Ein KI-Schritt
  eines Ablaufs engt das Angebot auf seine Werkzeuge ein; die Baumliste stünde dort nie darin,
  und gerade dort wird tief abgeglichen. Lesen darf der Dienst die Sammlung über
  `browse_collection_tree` (`dienst.braucht`): Ist das gesperrt, wird das Modul nicht angeboten.
  Den Studio-Schalter der Baumliste (je MCP-Server) beachtet der Dienst. Eine Sperre je Lauf
  (Policy), die nur die Baumliste nennt, erreicht ihn nicht.
- **Zeit** (SE-10). Ein ganzes Fachportal mit Inhaltszahlen dauert länger als der alte Weg
  (Zahlen unten). Eine Seite der Liste darf 30 s dauern. Begonnen wird sie nur, wenn dem Lauf
  dafür 40 s bleiben (30 s und 10 s für den alten Weg, nach 15 s Reserve). Dauert die erste
  Seite länger, liest der Dienst zwei Ebenen. Nach 30 s insgesamt beginnt keine weitere Seite.
- **Vollständigkeit.** Der Server liest Ebene für Ebene und sagt, wenn die Liste nicht
  vollständig ist.
  - Bricht sie ab (Grenze des Servers, mehr als drei Seiten zu 250 Einträgen, keine Zeit mehr,
    eine Folgeseite fällt aus), steht ab der tiefsten gelesenen Ebene „Nicht gefunden“ statt
    „Neu“. „Neu“ auf den Ebenen darüber bleibt verbindlich.
  - Konnte er irgendwo nicht lesen (ein Zweig ohne Antwort oder verweigert), steht an jedem
    neuen Punkt „Nicht gefunden“. Wo es war, sagt die Antwort nicht verlässlich; dazu steht ein
    Wunsch beim MCP-Entwickler.
  - Das Modul und die Textfassung sagen dann „nicht vollständig gelesen“ statt „größer als
    gezeigt“. Die Textfassung führt „Neu“ und „Nicht gefunden“ getrennt.
- **„Größer als gezeigt“ nur, wenn es stimmt.** Ist der Baum ganz gelesen, sagt das Modul das
  nicht mehr, auch wenn die Liste „Nur in WLO“ bei 100 gedeckelt ist. Deren Überschrift nennt
  die Zahl („100 von 138“).
- **Titel der Sammlung** kommt bei der Baumliste vom Server, nicht aus dem Argument der KI.
- **Abdeckung bleibt bei zwei Ebenen** (SE-9). Mit `abdeckung: true` zählt der Dienst weiter für
  Ebene 1 und 2 (höchstens 60 Punkte). Tiefere Punkte tragen keine Zahl und zählen nicht als
  „ungezählt“; der Abschnitt „Lücken“ und der Text an die KI sagen einmal: „Gezählt wird nur für
  Ebene 1 bis 2.“
- **Modulversion bleibt 1.** Das Schema wird nur weiter (`ebene` bis 4, drei neue freiwillige
  Felder); alte Daten passen. Ein Widget mit älterem Bündel im Cache zeigt Zeilen der Ebene 3
  und 4 uneingerückt und nennt tiefe Sammlungen „Ebene 1“. Widget und Backend kommen aus einem
  Image, das betrifft also nur offene Seiten bis zum Neuladen.

## Was sich am alten Weg ändert

Für gültige Entwürfe bleibt der Abgleich über zwei Ebenen gleich. Geändert ist:

- **Ein Punkt ohne Titel fällt mit allem darunter weg**, im Abgleich und in der Zählung der
  Abdeckung. Bisher hingen seine Kinder am Geschwister davor und wurden unter dessen Sammlung
  gesucht. Die Prüfung des Entwurfs lässt Punkte ohne Titel ohnehin nicht zu.
- **Die Textfassung** führt „Neu“ und „Nicht gefunden“ getrennt.
- **Gefunden ohne Elternpunkt** nennt auch hier die Sammlung darüber.
- **Mit dem neuen Server** entfällt auf dem neuen Weg die Selbstheilung einer falschen Kennung
  über das Fach; sie hängt an `browse_collection_tree`. Fällt die Liste deshalb aus, liest der
  alte Weg, und die Selbstheilung greift dort.

## Gemessen

Am neuen Stand des Servers (lokal gestartet, anonym, nur lesend, gegen Staging), Fachportal
Physik mit 144 Sammlungen auf drei Ebenen, sechs Läufe:

| Aufruf | Dauer |
|---|---|
| `list_collection_tree`, Tiefe 4, ohne Inhaltszahlen | 5,0 bis 6,4 s |
| `list_collection_tree`, Tiefe 4, mit Inhaltszahlen | 10,5 bis 12,8 s |
| `browse_collection_tree`, Tiefe 2, mit Inhaltszahlen (bisher) | 3,6 bis 5,0 s |

Als erster Aufruf eines frischen Prozesses dauerte die Liste mit Zahlen einmal 19 und einmal
38 s. Die Sammlung Optik (16 Sammlungen) dauerte mit Zahlen 2,2 s. Ein Entwurf mit drei Ebenen
wurde gegen Physik richtig zugeordnet (Optik › Geometrische Optik › Reflexion und Brechung
vorhanden, erfundene Punkte neu).

## Nicht umgesetzt: Themenbaum in gespeicherter Reihenfolge

Das Modul `ui_themenbaum` bleibt alphabetisch (SE-4). `order: "stored"` heißt am Server: die
gesetzte Position, sonst die Reihenfolge des Anlegens. Für einen angelegten Lehrplan ist das
richtig, für ein Fachportal beliebig, und die Antwort sagt nicht, welcher Fall vorliegt. Dafür
steht ein Wunsch an den MCP-Entwickler in
[`mcp-antwort-2026-11-14-sammlungsstrukturen.md`](../mcp-antwort-2026-11-14-sammlungsstrukturen.md)
(„gesetzte Position, sonst Titel“). Die KI kann `order` je Aufruf weiter selbst wählen.

## Review

Zwei unabhängige Reviews. Der Kern (Elternzuordnung, Abgleich je Ebene, Blättern, Schema,
Fremdtext, Abbruch eines laufenden Aufrufs) war beide Male richtig.

**Erstes Review:** 1 schwerer, 10 mittlere, 3 kleine Punkte. Behoben:

1. **Die Studio-Sperre der Baumliste wirkte am Dienst nicht (schwer).** Wer das Werkzeug am
   MCP-Server abschaltet, etwa wegen der Last, stoppte den teuersten Aufrufer nicht. Der Dienst
   fragt den Schalter jetzt ab.
2. **Mittlere:**
   - „Unvollständig“ war ein Schalter für den ganzen Baum: Ab etwa 400 Sammlungen hätte der
     Abgleich nie mehr „Neu“ gesagt, auch nicht auf Ebene 1. Jetzt je Ebene.
   - Die Zeit wurde nur einmal vorab geprüft, die Liste hatte keine eigene Frist, und ein Ausfall
     kostete den ganzen Abgleich. Jetzt: Prüfung vor jeder Seite, 30 s je Seite, Rückfall auf
     zwei Ebenen.
   - Ein `more` in fremder Form galt als „vollständig“. Jetzt gilt es als „es gäbe mehr“.
   - Eine Sammlung auf zwei Seiten stand doppelt unter „Nur in WLO“ und zählte doppelt.
   - Mit Abdeckung lasen KI und Person „3 von 5 Punkten gezählt“ ohne Grund; eine tiefe Zeile
     mit der Kennung eines Punkts bekam dessen Treffer.
   - Ein Punkt, der in einem fremden Zweig gefunden wurde, stand als „Vorhanden“ da, ohne zu
     sagen, wo.
   - Kinder eines Punkts ohne Titel standen in der Anzeige unter dem Geschwister davor.
   - Bei einem Ausfall hieß es „größer als gezeigt“.
3. **Kleine:** Listen tragen ihre Rolle ausdrücklich (VoiceOver); nur Kennungen in UUID-Form
   werden zur Adresse; ein Titel, der nur die Kennung wiederholt, gilt nicht; höchstens 250
   Einträge je Seite.

**Zweites Review** (nach dem Umbau): 1 schwerer, 6 mittlere, 3 kleine Punkte. Behoben:

1. **Bei zwei Ausfällen im selben Lesevorgang konnte ein Punkt verbindlich „Neu“ heißen
   (schwer).** Die Marke je Sammlung steht nur an Einträgen der gelieferten Seite, und für die
   gelesene Sammlung selbst gibt es keine. Sobald eine Marke sichtbar war, galt jeder andere
   Ausfall als nicht geschehen. Jetzt macht jeder gemeldete Ausfall alle neuen Punkte zu „Nicht
   gefunden“.
2. **Mittlere:**
   - Eine Antwort ohne `items` galt als Sammlung ohne Untersammlungen; jetzt ist sie keine
     Baumliste, und der alte Weg liest.
   - Die Textfassung führte „nicht gefunden“ unter „Neu“.
   - Die Zählung der Abdeckung stieg in Punkte ohne Titel ab, der Abgleich nicht.
   - Lief die erste Seite in ihre Frist, las der alte Weg aus der Reserve des Laufs.
   - Gelesen wurde immer Tiefe 4, auch für einen Entwurf mit zwei Ebenen. Das kostete je
     Sammlung eine Abfrage und stieß früher an die Grenze des Servers.
   - Vier Testfälle fehlten.
3. **Kleine:** eine unbenutzte Konstante; ein ungenauer Satz in den offenen Punkten.

Bewusst so gelassen:

- Die Modulversion bleibt 1 (siehe oben).
- Eine Sperre je Lauf nur für die Baumliste erreicht den Dienst nicht; wer das Lesen der
  Sammlung sperren will, sperrt `browse_collection_tree`.
- Hat der Entwurf mehr als 250 Punkte, heißt es weiter „größer als gezeigt“ (wie vor SW-4).

## Geprüft

- Backend: volle Suite 10 518 Tests grün (5 übersprungen); neu `tests/test_strukturabgleich_sw4.py` (30 Tests).
- Frontend: `ng test ui-module` 380 Tests grün; `npm run module:register` neu erzeugt; das
  Bündel des Moduls liegt bei 4,3 kB gzip (Grenze 20).

Nicht geprüft: der Abgleich im Chat mit dem neuen Server (braucht dessen Deploy auf Staging) und
ein Portal mit mehr als 400 Sammlungen (dort greift die Grenze des Servers).

## Deploy

- Keine Migration, keine neue Variable. Image neu bauen (Backend und Widget-Bündel).
- Kein `import-config` nötig.
