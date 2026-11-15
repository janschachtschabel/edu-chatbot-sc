# Themenbaum in gesetzter Reihenfolge; Ausfall nur am betroffenen Zweig (2026-11-15)

Plan [`2026-11-14-sammlungsstruktur-werkzeuge.md`](../plans/2026-11-14-sammlungsstruktur-werkzeuge.md),
Paket SW-5. Der MCP-Entwickler hat unsere Wünsche S11 bis S13 gebaut (seine Notiz vom 15.11.);
dieses Paket nutzt S11 und S13. Sein Stand ist nicht bereitgestellt: Bis er es ist, ändert sich
im Chat nichts.

## Themenbaum: gesetzte Position, sonst Titel (S11)

Das Modul `ui_themenbaum` las die Untersammlungen bisher alphabetisch. Die Abfolge eines
angelegten Lehrplans ging dabei verloren.

- **Jetzt** liest das Modul mit `order: "position"`, wenn der Server den Wert führt: je
  Elternknoten erst die Untersammlungen mit gesetzter Position in dieser Reihenfolge, sonst nach
  Titel. Das gilt auch für das Aufklappen eines Zweigs und für „Als Entwurf bearbeiten“.
- **Wo keine Position unterscheidet, sortiert der Chatbot selbst nach Titel** (SE-12), im Baum
  und im Entwurf, der aus dem Baum entsteht. Der Server meldet das je Ebene
  (`childrenPositioned: false`). Ohne diesen Schritt stünden dort zwei Alphabete hintereinander:
  erst die Sammlungen mit (gleicher) Position, dann die ohne. Gemessen an „Optik“: Farben,
  Geometrische Optik, Menschliches Auge, Wellenoptik, dann die zwei Kompendium-Sammlungen.
- **Ohne das Merkmal** (älterer Server, gekürzte Liste) bleibt die Reihenfolge des Servers.
- **Für die KI:** `order` trägt den dritten Wert `position` an `browse_collection_tree` und
  `get_collection_overview`, und `list_collection_tree` nimmt `order` jetzt auch. Angeboten wird
  beides nur, wenn der Server es führt; verlangt die KI `position` an einem Server ohne den
  Wert oder `order` an einer Baumliste ohne den Parameter, lehnt der Client mit einem Satz ab.

## Strukturabgleich: Ausfall nur am betroffenen Zweig (S13)

Meldete die Baumliste einen Ausfall (`incomplete`, `restricted`), stand bisher an jedem neuen
Punkt „Nicht gefunden“: Die Antwort sagte nicht verlässlich, wo es war. Der neue Stand nennt die
betroffenen Sammlungen im Kopf der Antwort (`unreadParents`, `refusedParents`), für den ganzen
Lauf und die Start-Sammlung eingeschlossen.

- **Jetzt** steht „Nicht gefunden“ nur an Punkten, die unter einer genannten Sammlung liegen
  können. Alles andere bleibt verbindlich „Neu“.
- **Weiter an jedem neuen Punkt** in diesen Fällen:
  - Die Antwort sagt es nicht (Stand ohne die Listen, mehr als 50 Kennungen, fremde Form).
  - Die Start-Sammlung selbst ist betroffen, oder eine genannte Sammlung ist nicht unter den
    gelesenen.
  - Der Ausfall kommt erst auf einer Folgeseite. Jede Seite ist ein eigener Lauf des Servers;
    fällt eine Unterliste erst im zweiten aus, rücken dort alle späteren Positionen vor, und
    zwischen den Seiten fehlen Einträge, die nicht unter der genannten Sammlung liegen. Eine
    Ablehnung (`restricted`) ist in jedem Lauf gleich und bleibt eingegrenzt.

## Gemessen

Am lokal gestarteten Stand vom 15.11. (anonym, nur lesend, gegen Staging):

- `tools/list` nennt `position` in der Aufzählung von `order` an allen drei Werkzeugen.
- Physik, erste Ebene: `title` beginnt Akustik, Astronomie, Atomphysik; `stored` beginnt Optik,
  Methoden, Astronomie; `position` beginnt Optik, Akustik, Astronomie. Das Merkmal ist `true`:
  An „Optik“ ist dort eine eigene Position gesetzt.
- Optik, erste Ebene: Merkmal `false`; `position` liefert die zwei Alphabete, das Modul zeigt
  nach dem eigenen Sortieren dieselbe Reihenfolge wie bisher.
- Baumliste Physik mit Inhaltszahlen: 6,8 und 8,3 s (vorher 10,5 bis 12,8 s).

Nicht gemessen: ein Ausfall mit `unreadParents` (ließ sich nicht herbeiführen; die Tests folgen
der Notiz des Entwicklers und seinem Quelltext).

## Bekannte Folge

Die Vorschau der zweiten Ebene zeigt je Sammlung nur einige Untersammlungen. Der Server holt
dafür die ersten in der Reihenfolge des Repositorys und sortiert danach, das war laut seinem
Quelltext auch mit `title` schon so. Neu mit `position`: Untersammlungen mit gesetzter Position
stehen in der Vorschau vorn. Aufgeklappt kommt der Zweig ganz.

## Review

Ein unabhängiges Review fand 1 schweren, 4 mittlere und 3 kleine Punkte. Behoben:

1. **Ein Ausfall erst auf einer Folgeseite ließ sich nicht eingrenzen (schwer).** Ein Punkt, den
   es in WLO gibt, konnte verbindlich „neu“ heißen (siehe oben). Jetzt gilt dann wieder jeder
   neue Punkt als „nicht gefunden“.
2. **Mittlere:**
   - „Als Entwurf bearbeiten“ las mit `position`, sortierte aber nicht selbst: Im Entwurf standen
     die zwei Alphabete, die der Baum gerade nicht zeigt. Die Regel gilt jetzt einmal am Rohbaum.
   - Der Test zum neuen Wert im Argumentmodell hätte auch ohne die Änderung bestanden.
   - `order: "title"` an einer Baumliste ohne den Parameter ging hinaus; der Server hätte es
     still verworfen.
   - Der Gegenfall zum schweren Punkt fehlte in den Tests.
3. **Kleine:** Ø, Æ, Ł sortierten hinter Z; eine Vorgabe des Manifests geht jetzt vor; die
   „Bekannte Folge“ war ungenau beschrieben.

## Geprüft

- Backend: volle Suite 10 590 Tests grün (5 übersprungen); neu `tests/test_sammlungen_sw5.py` (28 Tests).
- Frontend: nur die Beschreibung im Manifest des Themenbaums; `npm run module:register` neu
  erzeugt.

## Deploy

- Keine Migration, keine neue Variable, kein `import-config`. Image neu bauen.
