# Sammlungsbaum ganz lesen; Fach, Stufe, Schlagworte beim Anlegen (2026-11-14)

Plan [`2026-11-14-sammlungsstruktur-werkzeuge.md`](../plans/2026-11-14-sammlungsstruktur-werkzeuge.md),
Pakete SW-1 und SW-2. Der MCP-Entwickler hat neun unserer zehn Wünsche
([`mcp-werkzeug-wuensche-2026-11-14.md`](../mcp-werkzeug-wuensche-2026-11-14.md)) gebaut; der
bereitgestellte Server läuft weiter auf dem alten Stand.

Beide Pakete hängen an der Werkzeugliste des Servers. Bis er den neuen Stand führt, ändert sich im
Chat nichts.

## SW-1: lesen

- **`list_collection_tree`** (`services/mcp/baum_lesen.py`): der Teilbaum unter einer Sammlung als
  flache Liste, je Untersammlung Kennung, Titel, Pfad, Tiefe und Elternknoten. Bis vier Ebenen, in
  Seiten zu höchstens 250, in der Reihenfolge des Repositorys.
  - Das ist die Tiefe und Menge, die das Anlegen eines Baums erlaubt. `browse_collection_tree`
    reicht nur bis Ebene 3 und kürzt je Elternknoten.
  - Die KI bekommt es nur, wenn der Server es führt; im Katalog der Lesewerkzeuge steht es nicht
    (wie die Mehrfachsuche).
  - Die Antwort geht ganz an die KI, auch im Muster-Weg (dort schnitte sonst ein Deckel bei
    4 000 Zeichen ab). Eine volle Seite mit langen Titeln hat rund 50 kB; ein Sicherheitsdeckel
    liegt bei 120 000 Zeichen und kürzt nur an einer Zeilengrenze, mit einem Satz dazu.
    Karten entstehen keine: Die Liste ist zum Rechnen gedacht.
  - Aus dem Cache kommt sie nie, weil sie dem Zurücklesen nach dem Anlegen dient.
- **`order`** an `browse_collection_tree` und `get_collection_overview`: `"stored"` liefert die
  Reihenfolge des Repositorys statt der alphabetischen. Angeboten je Werkzeug, wenn der Server den
  Parameter dort kennt. Verlangt die KI die gespeicherte Reihenfolge an einem Server ohne den
  Parameter, lehnt der Client das mit einem Satz ab; der Server lieferte sonst still
  alphabetisch.
- **Studio:** Die Seite „Werkzeuge“ zeigt das neue Lesewerkzeug als Zeile, mit dem Grund, solange
  der Server es nicht führt. Am MCP-Server trägt es einen Schalter.
- **Master-Skill** (M08), ohne Werkzeugnamen: „Ist ein Werkzeug angeboten, das einen ganzen
  Sammlungsbaum als Liste liefert, nimm es zum Rechnen … Wo die Abfolge etwas bedeutet
  (Lehrplan), in der gespeicherten Reihenfolge lesen, wenn das Werkzeug das anbietet.“

## SW-2: Baum anlegen mit Fach, Stufe, Schlagworten

- **`wlo_create_collection_tree`** bekommt je Knoten `discipline`, `educationalContext`,
  `keywords` und gemeinsame Werte für den ganzen Baum als `shared`
  (`services/mcp/baum_metadaten.py`). Vorher brauchte das einen zweiten Aufruf mit einer zweiten
  Bestätigung.
- **Zwei Stellen sichern den älteren Server ab.** Er prüft jede Ebene streng; ein fremdes Feld
  ließe den ganzen Baum scheitern.
  - Die KI bekommt die Felder nur angeboten, wenn der Server sie führt (Agent und Muster M18).
  - Vor dem Senden nimmt der Client sie für einen Server ohne diese Felder wieder heraus und
    stellt einen Satz vor die Antwort („… wurden NICHT mitgesendet …“), den KI und Person lesen.
- **Der Ablauf-Dienst `baum_aus_entwurf`** reicht Stufe und Schlagworte aus dem Strukturentwurf
  durch, das Fach nur, wenn das Vokabular es kennt (Name oder Alias, kein Teilwort). Fach und
  Stufe des Entwurfs gelten für jeden Punkt, der keine eigenen nennt.
- **Reihenfolge:** Der neue Server setzt beim Anlegen die Reihenfolge der Eingabe. Im Chatbot
  ist dafür nichts zu tun.

### Warum das Fach geprüft wird

Der Server prüft Fach und Stufe streng gegen das Vokabular und lehnt mit einem unbekannten Wert
den ganzen Baum ab. Im Entwurf ist das Fach Freitext, und die Person kann es dort nicht ändern
(bearbeitbar sind Titel, Beschreibung, Schlagworte). Ein Ablauf liefe damit in eine Sackgasse.
Deshalb reist ein Fach, das das Vokabular nicht kennt, nicht mit; die Vorschau des Servers nennt
je Knoten, was gesetzt wird. Die Stufe kommt aus einer festen Liste und ist unkritisch. Im Chat
nennt die KI Fach und Stufe selbst und korrigiert nach einer Ablehnung.

## Gemessen

Am neuen Stand des Servers, lokal gestartet gegen das Staging-Repository (anonym, nur lesend):

- `tools/list` nennt 60 Werkzeuge, darunter die acht neuen.
- `list_collection_tree` am Fachportal Physik: 144 Sammlungen über drei Ebenen in 4,7 s, 16,7 kB
  Text. Die Optik-Sammlung: 16 Einträge, 1,7 kB.
- `browse_collection_tree` mit `order: "stored"`: Optik, Methoden, Astronomie …; mit `"title"`:
  Akustik, Astronomie, Atomphysik …
- Das angebotene Schema des Baum-Werkzeugs (vier Ebenen, `shared`) deckt sich mit dem des
  Servers; kein angebotener Parameter ist ihm unbekannt.

## Bewusst gelassen

- Das Themenbaum-Modul bleibt alphabetisch, der Strukturabgleich bei zwei Ebenen (SW-4, Entscheide
  SE-4 und SE-5 im Plan).
- Der Fachportal-Name löst sich über `collection` nicht auf („Physik“ → Kandidaten). Für ein
  Fachportal nimmt die KI die Kennung; die Beschreibung sagt das.
- `shared` nutzt der Ablauf-Dienst nicht: Er schreibt die Werte an jeden Knoten. Für neue Knoten
  ist das gleichwertig.

## Geprüft

- Backend: volle Suite 10 456 Tests grün (5 übersprungen); neu `tests/test_mcp_baum_lesen.py`, `tests/test_mcp_baum_metadaten.py`.
- Client des Chatbots gegen den lokalen neuen MCP: Angebot, gespeicherte Reihenfolge, Baumliste
  (ganz, geklemmte Grenzen, per Titel, Seiten), Sicht der KI.

Nicht geprüft: jede Vorschau und jedes Schreiben mit den neuen Feldern (braucht eine Anmeldung am
neuen Stand, also dessen Deploy auf Staging).

## Review

Ein unabhängiges Review fand 2 schwere, 7 mittlere und 3 kleine Punkte. Behoben:

1. **Baumliste in der Mitte gekürzt (schwer).** Sie erbte den Deckel der Mehrfachsuche (32 000
   Zeichen); eine volle Seite ist größer, und bis zu 100 Zeilen fehlten ohne Hinweis. Jetzt
   eigener Deckel weit über einer Seite, Schnitt nur an Zeilengrenzen, mit Satz.
2. **Freies Fach im Entwurf (schwer).** Der Dienst schrieb das Fach ungeprüft an jeden Knoten;
   der neue Server hätte den ganzen Baum abgelehnt. Jetzt nur noch Fächer aus dem Vokabular.
3. **Mittlere:** `[""]` am Knoten schaltete das gemeinsame Fach ab; das Herausnehmen der Felder
   für einen älteren Server war stumm; die Baumliste kam nach dem Anlegen aus dem Cache; die
   Beschreibung nannte Feldnamen, die die KI nicht sieht; `order` an einem älteren Server;
   Tests für Rohfall, Deckel und Muster-Weg.

Nicht geändert: Kippt die Fähigkeitsabfrage zwischen Vorschau und Bestätigung (Neustart, drei
Fehlabfragen), gehen andere Felder hinaus als in der Vorschau. Der Server antwortet dann mit
`confirm_mismatch` bzw. `plan_mismatch`, und der Chat legt neu vor; es wird nie still etwas
anderes geschrieben.

## An den MCP-Entwickler

- `list_collection_tree` nennt `more.nextSkipCount` auch über seiner eigenen Grenze
  (`skipCount` höchstens 500): Die dritte Seite nennt 750, der nächste Aufruf wird abgelehnt
  (am Quelltext gelesen, nicht gemessen; Staging hat keinen Baum dieser Größe).
- Ein Fachportal löst sich über `collection` nicht auf („Physik“ → Kandidaten). Für uns in
  Ordnung, die KI nimmt die Kennung.

## Außerhalb des Pakets (Bestand)

Ein Strukturentwurf darf 30 Punkte auf oberster Ebene haben, der Server nimmt 15. Entwürfe mit 16
bis 30 Punkten scheitern an der Vorschau (steht in `offene-befunde-und-todo.md`).

## Deploy

- Keine Migration, keine neue Variable, keine Reihenfolge zum MCP. Image neu bauen.
- `import-config --werksabgleich` (Werkzeugliste des MCP-Servers); Master-Skill-Knoten in WLO mit
  `docs/skills/vorgehen-knapp.md` ersetzen.
