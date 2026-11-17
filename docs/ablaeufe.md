# Abläufe bauen — Handbuch für die Redaktion

Ein **Ablauf** führt die Person Schritt für Schritt durch eine Aufgabe, etwa vom Ordner zum
Themenbaum oder durch die Webseite. Er wird im Studio unter **Abläufe** gebaut, geprüft und
getestet. Jeder Ablauf ist ein eigenes Dokument (`06-ablaeufe/<kennung>`).

Dieses Handbuch gehört zum Plan `plans/2026-11-09-ablaeufe-im-studio.md`. Es erklärt die Bausteine,
drei Beispiele aus dem Werkszustand (alle ausgeschaltet, bis die Redaktion sie einschaltet) sowie
Testen und Ausprobieren.

## Bausteine

**Schritte** laufen in der Reihenfolge der Liste. Ein Schritt springt woandershin, wenn er es sagt
(`weiter`, `bei_fehler`, das Ziel einer Schnellantwort).

| Typ | Was er tut |
|---|---|
| `nachricht` | Ein Text, auf Wunsch mit Schnellantworten (`optionen`) oder Freitext (`freitext`). |
| `modul` | Ein UI-Modul im Chat, etwa `ui_upload` oder `ui_strukturentwurf`; der Lauf wartet auf die Antwort darin. Auch hier gehen `optionen` und `freitext`. |
| `werkzeug` | Ein Dienst ohne Sprachmodell oder ein lesendes WLO-Werkzeug; das Ergebnis wird ein Teil (`schreibt`). Ein schreibendes WLO-Werkzeug nur mit `freigabe`: Der Schritt legt die Änderung vor, und die Person gibt sie frei. |
| `verzweigung` | Regeln unter `weiter`: `wenn_teil` (ein Teil ist da), `wenn_gewaehlt` (eine Wahl), `wenn_wert` (eine Stelle eines Teils vergleichen: gleich, enthält, vorhanden, leer, größer, kleiner; der Wert darf selbst eine Stelle sein, `"{teil.struktur.block_id}"` — fehlt sie, greift die Regel nicht) und `wenn_seite` (Führungen). Die erste passende gilt, `sonst` am Ende. |
| `agent` | Ein Abschnitt, in dem die KI mit genau den genannten Werkzeugen arbeitet (`agent.werkzeuge`, höchstens `agent.zuege` Züge). |
| `auftrag` | Ein Auftrag bei der b-api (Kestra), etwa für lange Umwandlungen. |
| `seite` | Führt auf eine Seite der Webseite (Kapitel Führungen). |
| `ende` | Schlusssatz; der Lauf ist fertig. |

**Teile** sind die Daten eines Laufs. Ein Schritt liest sie mit `{$teil: <name>}` und schreibt sie
mit `schreibt: <name>`. In Texten setzt `{teil.<name>.<pfad>}` einen Wert ein, `{start.<feld>}` ein
Feld der Startdaten. Die Sicht **Daten** im Studio zeigt, welcher Schritt welchen Teil schreibt
und liest.

**Auslöser** sagen, wie ein Ablauf startet: `knopf` (Direktaktion), `text` (eine Wendung in der
Nachricht), `agent` (die KI schlägt ihn vor), `modul` (die Antwort eines Moduls), `extern` (die
Gastseite, mit Startdaten) und `seite` (Angebot unter der Begrüßung).

Bei `agent` legt `modus` fest, wie der Ablauf startet:
- `vorschlagen` (Vorgabe): Unter der Antwort erscheint ein Knopf, und die Person startet.
- `direkt`: Der Ablauf startet nach der Antwort von selbst. Das Widget drückt denselben Knopf, deshalb
  laufen Prüfung, Bremse („läuft schon“) und die Herkunft `ki` der Angaben wie bei einem Klick.
- `direkt` gilt nur für Abläufe, die nichts schreiben (kein schreibendes Werkzeug, kein Auftrag, kein
  Upload). Sonst bleibt es ein Vorschlag, und „Ablauf prüfen“ meldet es. Seit Plan 2026-11-16 (TG-6)
  zählt ein Auftrag nicht, vor dem auf jedem Weg direkt eine echte Rückfrage steht: eine Wahl mit
  mindestens einer Option, die nicht zum Auftrag führt, und ohne Freitext dorthin (wie „Ja,
  Metadaten erzeugen“ / „Nein, so lassen“), oder eine Freigabe. Geschrieben wird erst nach dem Klick
  der Person.
- Die KI bietet nur **eingeschaltete** Abläufe an. Einen ausgeschalteten Ablauf mit `direkt` kann man
  in der Studio-Vorschau also nicht über die KI ausprobieren, nur über „Ablauf ausprobieren“.

## Beispiel: Sammlung aus Ordnern

`06-ablaeufe/sammlungsstruktur` („Themenbaum · aus Ordnern“) ist der kürzeste vollständige Ablauf.
Davor stehen seit dem zweiten Review TG-2 `bereit`, `vorhanden` und eine von zwei Fassungen des
Einstiegs (siehe „Bereitgestelltes übernehmen“ unten).

1. `erfassen` (`modul ui_upload`, Zweck `sammlungsstruktur`): Die Person wählt einen Ordner. Die
   Ordnerstruktur wird der Teil `structure`.
2. `entwurf` (`werkzeug strukturentwurf_aus_ordnern`): Ein Dienst ohne Sprachmodell macht daraus
   einen Themenbaum-Entwurf, Teil `draft`. Ohne Unterordner geht es zu `ohne_ordner`.
3. `bearbeiten` (`modul ui_strukturentwurf` mit `daten: {$teil: draft}`): Die Person sieht und
   bearbeitet den Entwurf.
4. `ende`.

Er zeigt das Grundmuster: Modul erfasst → Dienst rechnet → Modul zeigt, mit einem eigenen Ende für
den Fehlerweg.

## Beispiel: Sammlung prüfen

`06-ablaeufe/sammlung_pruefen` gleicht einen Entwurf aus den Ordnern der Person mit WLO ab. Er
schreibt nichts in WLO.

1. `erfassen` und `entwurf` wie oben.
2. `luecken` (`werkzeug abdeckung_zaehlen`): zählt je Punkt des Entwurfs die WLO-Inhalte, Teil
   `abdeckung` (`gezaehlt`, `luecken`).
3. `gezaehlt` (`verzweigung` mit `wenn_wert`): Ist `teil.abdeckung.gezaehlt` größer 0, geht es zu
   `zeigen`, sonst zu `ohne_zahlen`. **Wichtig:** Der Dienst liefert auch bei einem Ausfall (WLO
   nicht erreichbar) ein Ergebnis, dann mit `gezaehlt: 0`. `bei_fehler` greift nur, wenn das
   Werkzeug gar nichts liefert (etwa gesperrt). Darum prüft der Ablauf den Wert.
4. `zeigen` (`modul ui_strukturentwurf`): Der Text nennt die Lücken mit Platzhaltern —
   „Bei {teil.abdeckung.luecken} von {teil.abdeckung.gezaehlt} Punkten …“.
5. `weiter_zum_abgleich` (`verzweigung` nur mit `sonst`): springt über `ohne_zahlen` hinweg. So
   bleibt der Fehlerweg in der Liste, ohne dass der normale Weg hineinläuft.
6. `abgleich` (`agent` mit `werkzeuge: [search_wlo_all, ui_strukturabgleich]`): Die KI fragt
   nach der Sammlung. Nennt die Person einen Namen, sucht sie die Sammlung und nimmt ihre Kennung;
   dann zeigt sie den Abgleich im Modul. Den Abgleich kann kein Werkzeug-Schritt liefern; er
   braucht die Sammlung, die erst im Gespräch feststeht. Ein KI-Schritt bekommt nur lesende
   WLO-Werkzeuge und UI-Module mit Agent-Freigabe.
7. `ende`.

Fünf Testfälle decken ab:
- den Weg mit Zahlen;
- den Weg ohne Unterordner;
- eine Zählung ohne Ergebnis (`gezaehlt: 0`, so sieht ein Ausfall aus);
- ein gesperrtes Werkzeug (`null`);
- den ganzen Weg bis zum Ende.

Der Entwurf entsteht in den Tests echt aus der Ordnerstruktur; nur die Zählung ist
nachgestellt. **Regel für eigene Testfälle:** Stelle ein Werkzeug so nach, wie es im Betrieb
antwortet, sonst prüft der Test einen Weg, den es nicht gibt.

## Abläufe zuerst, Startknopf, Vorgaben, Ausstieg (Plan 2026-11-11)

- **Abläufe zuerst:** Jedes Ablauf-Werkzeug sagt der KI, dass es einzelnen Modulen und Werkzeugen
  vorgeht, wenn es passt. Im Angebot stehen die Abläufe vor den Modulen. Der Master-Skill sagt
  dasselbe.
- **Wendungen:** Die längste passende Wendung gewinnt, bei gleicher Länge die kleinste Kennung.
  Eine Wendung ist eine zusammenhängende Teilzeichenkette, ohne reguläre Ausdrücke.
- **Startknopf** (`agent.startknopf`): eine Schnellantwort beim Eintritt in den KI-Schritt, und
  nach einem zu frühen „Weiter“. Ihr Text geht als Nachricht an die KI, die dann loslegt. Kein
  `|`, nicht mit `__` am Anfang, höchstens 60 Zeichen.
- **Vorgaben** (`agent.vorgaben`): Wissen der Redaktion für die Module des KI-Schritts, je
  Sprache bis 2000 Zeichen. `ui_strukturentwurf` setzt es in den Systemteil seines Generators.
- **Ausstieg** (`ausstieg` am `ende`, ebenso „Abbrechen“ in der Leiste):
  - Die Person arbeitet ohne den Ablauf weiter.
  - Drei Züge mit der KI lang startet derselbe Ablauf nicht wieder von selbst, weder per Wendung
    noch per Modul-Antwort noch als Werkzeug der KI. Direktaktionen, Ablauf-Schritte und
    Kontext-Pings zählen nicht.
  - Die Antwort bietet „Doch mit Ablauf“ (Knopf). Er startet den Ablauf von vorn, beim
    Dokument-Ablauf also mit dem Upload; das Dokument wird noch einmal gewählt.
- **Vorgaben** gehen an den Generator des Moduls. Sie gelten vor seinen allgemeinen Regeln, nicht
  vor dem Antwortformat. Er sieht nur, was die KI übergibt, Anweisungen an die KI gehören in den
  Hinweis.
- **Muster-Maschine:** Am KI-Schritt bietet sie die UI-Module des Schritts an, auch wenn das
  Muster sie nicht nennt.
- **„Weiter im Ablauf“** (Durchtest TG-7, M1a) ist ein Steuerchip des Ablaufs: Er steht unter jeder
  Antwort eines wartenden KI-Schritts, auch wenn das Muster keine Schnellantworten zeigt (Agent:
  `mode=none`) und neben Chips des Gastgebers. Die Knöpfe einer Frage und „Stand prüfen“ bleiben an
  diese Grenzen gebunden.
- **Übernehmen setzt fort** (M1b): Übernimmt die Person mit einem Modul des Schritts genau dessen
  `ausgabe` (`uebernommen: true`, etwa „Übernehmen“ im `ui_strukturentwurf` bei `ausgabe: draft`),
  geht der Lauf ohne weiteren KI-Zug zum nächsten Schritt (`ki_schritt.uebernimmt`,
  `zug.nach_uebernahme`). Nur mitgeschickt (ohne Übernehmen) bleibt es ein gewöhnlicher Zug.
- **`dokument_lesen`** (M2): Hat die Person im Chat ein Dokument lesen lassen, liest die KI es selbst
  — Gliederung, dann Abschnitte, höchstens 6000 Zeichen je Aufruf, nach der Moderation, gerahmt.
  Im freien Chat und am KI-Schritt (virtuell, wie `wissen_suchen`); nur die Dokumente der Sitzung
  bzw. Person. Nur in der Agent-Schleife; im Muster-Weg sagt der Rahmen, dass sie es dort nicht kann.

## Beispiel: Themenbaum erstellen (Plan 2026-11-16, TG-6)

`06-ablaeufe/themenbaum` („Themenbaum erstellen“) ist **der** Themenbaum-Ablauf ab Werk. Er löst
die vier Abläufe „Themenbaum · aus …“ ab; sie liegen weiter als Werksfassung vor, ab Werk aus
(Beschreibung unten). Er hat keine Voraussetzung: Thema, Dokument, Ordner und der schnelle Weg
gehen anonym, der WLO-Weg nur angemeldet.

Seit dem Review TG-4–6 gilt: erst die Grundlage und ihre Daten, dann die Fragen, die dort wirken,
dann der Entwurf.

1. **Bereitgestelltes zuerst:** `bereit` (Dienst `bereitgestellt`) meldet auch `art` (`dokument`,
   `ordner` oder `dateien` — was ein Ablauf übernehmen kann, in dieser Reihenfolge), `name` (für den
   Text, etwa „die Ordner „Physik““), `wlo_ablage` (das Upload-Feld kann ablegen: Studio-Schalter,
   MCP, Anmeldung) und `wlo_erschliessen` (dazu lässt sich der Metadaten-Auftrag starten, sein Flow
   ist freigegeben). Liegt etwas bereit, fragt `einstieg_mit` („Ja, verwenden“ / „Anderes wählen“ /
   „Ohne Führung“), sonst `einstieg`.
2. **Grundlage:** Getippt ist es das Thema. Sonst „Ein Dokument mit Gliederung, etwa ein
   Lehrplan“, „Meine Ordner“ oder „Meine Dateien“. An Fragen mit Freitext trifft getippter Text ein
   Synonym nur, wenn er ihm **ganz** gleicht (Wörter ohne Satzzeichen: „nein, danke“ = „Nein
   danke“, aber nicht „Keine Atomphysik“); ohne Freitext, wie bei der Führung, weiter Teilwörter.
   Ausnahme `synonyme_im_satz: true` (nur die Grundlage): ganze Wörter im Satz („meine Lehrpläne“),
   nicht verneint im selben Satzteil — davor („keinen Lehrplan“) oder direkt dahinter („Lehrplan
   nicht, Ordner“ → Ordner); „nicht nur“ bejaht. Treffen mehrere Optionen („Dateien aus meinem
   Ordner“), ist der Text weder Wahl noch Thema: Der Hinweis `kein_treffer` fragt nach (jedes Mal),
   der Schritt wartet weiter. `kein_treffer` neben Freitext ist nur mit `synonyme_im_satz` erlaubt.
3. **Daten:**
   - Dokument → Upload-Feld mit `einzeldatei_als_struktur` → gelesen?
   - Ordner → Upload-Feld → `strukturentwurf_aus_ordnern` → Prüfpunkt `ui_strukturentwurf` („Ordner
     sind dein Ausgangspunkt …“) → „So lassen“ (fertig, die Dateien sind je Punkt gemerkt) oder „Mit
     deinen Angaben verfeinern“. Ohne Unterordner der Weg Dateien. Überträgt die Person die Dateien
     im Feld nach WLO, folgen erst Rückfrage, Kestra-Metadaten und `metadaten_lesen`, dann der
     Entwurf mit den node_ids.
   - Dateien → „Gründlich über WLO“ / „Nur die Dateinamen“ nur bei `wlo_erschliessen`; sonst ein Satz
     („Ich nehme nur die Dateinamen …“) und `inhalte_aus_dateien`.
4. **Fragen**: wofür, für wen bzw. welche Stufe (eine Frage), Umfang, Hinweise, dann Soll oder Ist
   (nur bei Dateien — die Metadaten liegen dann vor; gefragt in `zum_entwurf`). Unter 5 Inhalten
   (kein fünfter Eintrag in `metadaten.inhalte`) statt dessen „Mit so wenigen Dateien wird der Baum
   sehr klein. Lieber nach Stoff (Soll) aufbauen?“ (`soll_wenig`: „Nach Stoff (Soll)“ / „Trotzdem
   nur meine Dateien“, Durchtest TG-7, m4). Auf dem Ordner-Weg nur nach „verfeinern“.
   Freitext nur, wo die Antwort frei ist (Grundlage, wofür, Stufe, Umfang, Hinweise).
   **Knopf-Fragen** (Ja/Nein, Entweder-oder: Einstieg, „So lassen“/„verfeinern“, „Gründlich“/„Nur
   die Dateinamen“, Soll oder Ist, die Rückfrage vor Kestra, die Auswege) nehmen keinen Freitext und
   tragen keine Synonyme — „Passt so“ oder „Ja, gründlich“ träfen sonst den falschen Knopf. Ohne
   Treffer erscheint einmal „Bitte wähle einen der Knöpfe.“ mit denselben Chips (`kein_treffer`).
5. **Entwurf** im KI-Schritt der Grundlage; auf dem Ordner-Weg mit `vorlage: true` (der geprüfte
   Entwurf wird verfeinert).
6. **Ende:** Der Entwurf ist gespeichert, nächste Schritte als Text. Jeder Fehlerweg bietet
   „Nochmal“ (zurück zu `daten`, Auswahl verworfen), „Andere Grundlage“ bzw. „Frei weiter“.

Die KI-Schritte tragen `agent.vorbelegen: true` (TG-5): Die Antworten belegen die Argumente von
`ui_strukturentwurf` vor — `umfang` wird `tiefe`/`anzahl_oben` (1/6, 2/10, 3/12; ein verneintes
Wort zählt nicht), `stufe` die `bildungsstufe` (nur bekannte Labels, sonst eine Zeile), eine
getippte Grundlage das Thema — ohne sie (Durchtest TG-7, m1) auf dem Ordner-Weg der Name des
Wurzelordners, auf dem Dokument-Weg der Name des ersten Strukturdokuments ohne Endung, auf dem
Datei-Weg keins (die KI leitet es aus den Inhalten ab, nie den Zweck); Zweck, für wen, Soll/Ist und
Hinweise gehen als Zeilen in `hinweise` (Vorsatz in der Sprache des Zugs, die Hinweise der Person
bekommen den übrigen Platz). Ein Argument, das die KI selbst setzt, geht vor; `tiefe` und
`anzahl_oben` nur zusammen, `""` löscht `bildungsstufe` bzw. `hinweise`. Die KI sieht in
`[VORBELEGT — …]`, was der Ablauf setzt.

**Freie Arbeit bleibt (Review TG-4–6, MAJOR 2):** Ein Ablauf mit Auftrag beginnt nur dann in einem
frischen Vorgang, wenn im aktuellen eine Ablage, ein Metadaten-Lauf oder ein offener Lauf liegt
(N14). Sonst übernimmt er die freie Arbeit samt Entwurf. Darum prüft keine Regel des Ablaufs
`draft`, sondern Teile, die nur er schreibt (`ordnerweg`, `metadaten`).

**Leiste (Review TG-4–6, Befund 10):** Ein Lauf zählt seine Halte selbst (`lauf.halte`): jede Stelle,
an der er auf die Person wartet. Werkzeuge, Dienste, Verzweigungen und Nachrichten ohne Wahl zählen
nicht; eine Frage, die nur eine andere wiederholt, auch nicht. „Schritt n von m“: `n` = die Halte,
`m` = `n` − 1 + die meisten Halte, die ab hier noch kommen können. Ein „Nochmal“ ist ein weiterer
Halt. Läufe aus der Zeit davor rechnen weiter über den längsten Weg. Für `m` zählen Kanten **zurück**
(von einer anderen Frage oder einem Fehlerschritt zu einem früheren Schritt) nicht — nur die des
Schritts, an dem der Lauf steht: An „Damit komme ich nicht weiter“ zählt der Weg nach „Nochmal“, auf
dem Hauptweg steigt `m` nie (zweites Review, B).

**Synonyme vor einem schreibenden Auftrag:** Eine Antwort, die direkt zu einem Flow führt, der ins
Repositorium schreibt, trägt keine `synonyme` — ohne Freitext träfe „Nein, nicht erzeugen“ über
„erzeugen“ die Zustimmung. Die Prüfung meldet das (`auftrag_synonym`), und für den Direktstart zählt
eine solche Frage nicht als Rückfrage.

**Simulation und Hinweis:** Bekommt getippter Text den Hinweis `kein_treffer`, wartet der Lauf auch
im Selbsttest weiter; die nächste Eingabe gilt demselben Schritt. Ohne Freitext einmal je Besuch
(ein zweiter Fehlversuch ginge im Betrieb an die KI und bleibt hier eine Abweichung), ein
mehrdeutiger Satz jedes Mal.

**Simulation und Upload:** Ein simuliertes Upload-Feld hat eine feste `block_id`
(`simulation` + Modulname ohne Unterstriche, etwa `simulationuiupload`); Testfälle, die eine Ablage
desselben Felds vorgeben, tragen sie in `teile.ablage.block_id`. So prüft die Simulation die Regel
„Ablage gehört zur jetzigen Auswahl“ (`teil.ablage.block_id` gleich `{teil.struktur.block_id}`).

**Kein stummes Ende:** Die Prüfung meldet als Hinweis ein `ende` ohne `ausstieg`, das ein Lauf
ohne Ergebnis und ohne Wahl der Person erreichen kann — etwa direkt nach `bei_fehler` oder nach
einem Upload, der nichts Brauchbares brachte (`services/ablauf/stumme_enden`). Ergebnis heißt: ein
KI-Schritt, ein Auftrag, eine Freigabe, eine Ankunft auf einer Seite oder ein Modul, dessen Antwort
mehr als Bereitstellung schreibt (etwa `draft`). Alle Seeds sind frei davon.

## Beispiele: Themenbaum mit Kernfragen (abgelöst)

Die vier Themenbaum-Abläufe heißen im Studio einheitlich „Themenbaum · aus …“: aus Ordnern, aus
einem Thema, aus eigenen Inhalten und aus einem Dokument. Seit Plan 2026-11-16 (TG-6) sind sie ab
Werk aus und durch „Themenbaum erstellen“ abgelöst; die Beschreibung bleibt für eigene Fassungen.
Vorher waren „aus Ordnern“, „aus einem Thema“ und „aus einem Dokument“ an (sie schreiben nichts),
„aus eigenen Inhalten“ war aus, bis der Flow freigeschaltet war. Ohne Anmeldung startet „aus eigenen Inhalten“ nicht: passt die
Wendung, sagt die KI das in einem Satz und hilft ohne ihn weiter.
„Aus einem Thema“ und „aus einem Dokument“ beginnen mit der Wahl „mit Fragen / gleich entwerfen /
ohne Ablauf“, „aus eigenen Inhalten“ mit „Ja, los geht's / ohne Ablauf“.
Seit Plan 2026-11-16 (TG-2, G-E6) ist das Auswahlfeld zielneutral: Ein gelesenes Dokument
startet nichts von selbst (der Modul-Auslöser von „aus einem Dokument“ ist entfallen); die KI
fragt und schlägt den Ablauf vor.

**Bereitgestelltes übernehmen** (zweites Review TG-2). „Aus einem Dokument“ und „aus Ordnern“
beginnen mit dem Werkzeug-Schritt `bereit` (Dienst `bereitgestellt`, ohne Sprachmodell). Er
schreibt den Teil `bereit` in der Form `{"dokument": {"name", "lesbar"} | null, "ordner": {"name",
"unterordner"} | null, "dateien": n, "inhaltsdateien": n}`:

- ein Dokument nur, wenn es das lesbare Dokument dieser Sitzung ist (aus einer anderen Sitzung oder
  nach Ablauf der Frist ist es das nicht);
- Ordner mit der Zahl der Unterordner (ohne sie gibt es keinen Entwurf);
- seit Plan 2026-11-16, TG-3a die Zahl der Dateien, deren Namen im Teil `struktur` bereitliegen
  (`dateien`: nicht ignoriert; `inhaltsdateien`: Rolle `inhalt`) — 0 ohne `struktur`;
- seit TG-3e die Strukturdokumente des Vorgangs (`strukturdokumente: [{name, lesbar}]` aus dem Teil
  `strukturdokument` und den Knoten mit Rolle `struktur` in `ablage`) und ihre lesbare Zahl
  (`lesbare_strukturdokumente`, für `wenn_wert`). `dokument.lesbar` gilt für jedes der bis zu fünf
  lesbaren Dokumente der Sitzung, nicht nur das jüngste.

Die Verzweigung `vorhanden` prüft mit `wenn_wert` (`teil.bereit.dokument.lesbar` gleich `ja` bzw.
`teil.bereit.ordner.unterordner` größer `0`) und wählt eine von zwei Fassungen des Einstiegs:
`einstieg` wie bisher oder `einstieg_mit` („Ja, … verwenden“ / „Andere wählen“ / „Ohne Führung“),
deren Text den Namen über `{teil.bereit.dokument.name}` bzw. `{teil.bereit.ordner.name}` nennt.
So steht der Einstieg in der Leiste immer an derselben Stelle. Die Form von `bereit` ist
erweiterbar (TG-3d: Strukturdokumente).

**Teile verwerfen.** Eine Schnellantwort kann mit `verwirft: [teilname, …]` Teile aus dem Vorgang
entfernen, bevor es weitergeht — auch für die Schritte desselben Zugs. „Andere wählen“ verwirft so
das bereitgestellte `document` bzw. `structure` und `struktur`: Schickt die Person danach nur „Senden“, kommt die
Rückfrage statt still des Entwurfs aus dem abgelehnten Dokument. Die Prüfung meldet Namen, die der
Ablauf nicht kennt, und `start`. Die Simulation verwirft genauso.

**Bereitgestelltes geht beim Start mit.** Freie Arbeit landet im aktuellen Vorgang. Schließt ein
Start ihn (sein Lauf ist beendet oder gehört einem anderen Ablauf), übernimmt der neue Vorgang die
Bereitstellungs-Teile (`arbeitsstand_teile.BEREITSTELLUNG`: `structure`, `struktur`, `document`) mit Inhalt
bzw. Verweis — kein Entwurf, kein Lauf, keine Antworten. Das gilt für jeden Start.

**Nicht verwerfbar** sind Teile mit Verweisen ins Repositorium (`typen.NICHT_VERWERFBAR`, heute
`ablage`). `verwirft: [document]` nimmt nur den Teil; das Sitzungsdokument selbst bleibt lesbar.

**Kernfragen als Teile.** Die Fragen kommen aus dem Gestaltungsleitfaden. „Aus einem Thema“ fragt
seit 13.11. zuerst das Thema, dann wofür, für wen und wie tief: Das Thema trägt den Baum.

- **Jede Frage nimmt auch getippten Text** (`freitext` mit demselben Teil wie `schreibt`). Ohne
  ihn geht eine getippte Antwort an die KI, und die kann den Ablauf nicht weiterschalten: Er
  bleibt stehen. Ausgenommen sind Steuerfragen mit Ausstieg („Ohne Ablauf“). Ein Test wacht über
  die Seeds (`tests/test_ablauf_frageschritte_freitext.py`).

- Eine Nachricht mit Schnellantworten und `schreibt: zweck` legt das Label der gewählten Antwort
  als Teil `zweck` ab. In der Zeile für die KI steht dann „Wahl: Unterricht planen“.
- Getippter Text geht wie bisher über `freitext.schreibt` in einen Teil. Tragen beide denselben
  Namen (etwa `stufe`), ergeben Wahl und Tippen denselben Teil.
- Der Hinweis an die KI setzt nichts ein. Die KI sieht eine Wahl in der Arbeitsstands-Zeile
  („Wahl: …“); von getipptem Text steht dort nur der Name des Teils.
- **Am KI-Schritt bekommt die KI die Antworten als Daten** (seit 13.11.): Die Zeile
  `[ABLAUFDATEN — …]` nennt, was die Person auf die Fragen dieses Ablaufs geantwortet hat, gewählt
  oder getippt (`services/ablauf/ki_schritt.daten_zeile`). Vorher stand getippter Text nur im
  Verlauf. Die KI sieht davon die letzten 10 Nachrichten, bei einem längeren Dialog ging das
  Thema verloren.
  - Die Zeile gilt dem **Lauf**: Er merkt sich, welche Fragen in ihm beantwortet wurden
    (`lauf.antworten`, nur Namen). Nach einem Neustart im selben Vorgang stehen dort keine
    Antworten des vorigen Laufs.
  - Keine Antwort ist die Wahl an einer Steuerfrage mit Ausstieg („Gleich entwerfen“) und ein
    Teil, den auch ein Werkzeug, ein Auftrag, die KI oder ein Modul schreibt.
  - Jede Antwort ist auf höchstens 200 Zeichen gekürzt, als Daten gerahmt und entschärft (keine
    Anführungszeichen, eckigen Klammern, Steuerzeichen).
  - Das ist eine bewusste Ausnahme von „keine Eingaben der Person in KI-Zeilen“ (Review AS-3a,
    Befund 11). Die Zeile `[ARBEITSSTAND — …]` bleibt ohne Inhalt.
- **Der Stand des Ablaufs steht in `[ARBEITSSTAND — …]` vor den Teilen** (seit 13.11.). Am Ende
  der auf 300 Zeichen gedeckelten Zeile fiel er bei vielen Teilen weg.
- **Zusammenfassung vor dem Entwurf:** Eine `nachricht` ohne Schnellantworten wartet nicht, ihr
  Satz steht über dem des nächsten Schritts. So zeigt `notiert` mit Platzhaltern
  (`{teil.thema}` …), was der Ablauf verstanden hat.

**`06-ablaeufe/themenbaum_aus_thema`** („Themenbaum · aus einem Thema“):

1. `thema` (Freitext), `wofuer`, `stufe` und `tiefe`, dann `notiert` (Zusammenfassung).
2. `entwurf` (`agent` mit `ui_strukturentwurf`, `ausgabe: draft`): Der Schritt fragt nach
   Schwerpunkten. Ein KI-Schritt antwortet erst auf den nächsten getippten Zug, darum diese
   Frage („oder einfach ‚Los‘“). Dann erzeugt die KI den Entwurf nach den Antworten und zeigt ihn.
3. „Weiter“ führt zu `ende`. Ohne Entwurf geht es zu `ohne_entwurf`.

**`06-ablaeufe/themenbaum_aus_inhalten`** („Themenbaum · aus eigenen Inhalten“, Voraussetzung
Anmeldung):

1. `wofuer`, `stufe`, `thema`.
2. `hochladen` (`ui_upload`): Die Person überträgt Dateien in ihren Bereich in WLO; daraus wird
   der Teil `ablage`. Dafür muss im Studio unter „Datei-Upload“ die Ablage in WLO an sein.
3. `uebertragen` (`verzweigung` mit `wenn_teil: ablage`): Ohne Übertragung geht es zu
   `ohne_ablage`.
4. `metadaten_frage`: die Rückfrage vor dem schreibenden Flow.
5. `metadaten` (`auftrag` `edusharing.chatbot/node-metadata-write`, `repo_schreibt: true`). Die
   nodeIds nimmt der Schritt nur aus der Ablage desselben Vorgangs, als Auswahl
   `{$teil: ablage, liste: inhalte, wo: {stand: stored}, feld: node_id}`. Scheitert der Flow, sagt
   `metadaten_fehlt` das, und es geht mit den vorhandenen Angaben weiter.
6. `lesen` (`werkzeug metadaten_lesen`, `schreibt: metadaten`): Titel, Beschreibung, Schlagworte …
   der Dateien, unter der Anmeldung der Person.
7. `entwurf` (`agent`): Die KI ruft `ui_strukturentwurf` mit `aus_inhalten: true`. Der Dienst
   liest den Teil `metadaten` selbst und gruppiert die Materialien zu Themen.
8. `ende`. Sammlungen daraus anzulegen, kommt später.

Damit der Auftrag im Betrieb läuft, muss der Flow im Studio freigegeben sein (Abläufe →
„Kestra-Flows freigeben“, siehe unten), und der B-API-Schlüssel muss ihn starten dürfen. Solange
der Ablauf aus ist, ist eine fehlende Freigabe nur ein Hinweis.

**Grenzen des Flows `node-metadata-write`** (Plan §5b):

- Er ersetzt acht Felder je Datei: Titel, Beschreibung, Schlagworte, Sprache, Fach,
  Bildungsstufe, Zielgruppe, Ressourcentyp. Jede Änderung wird eine neue Version. Die Rückfrage
  nennt sie alle.
- **Nur Dateien dieses Laufs:**
  - Ein schreibender Ablauf beginnt immer in einem frischen Vorgang, damit keine alte Ablage
    hineinrutscht.
  - Die nodeIds sind die abgelegten des jetzigen Stapels.
  - Eine leere Auswahl startet keinen Auftrag, es geht weiter mit `bei_fehler`.
- **Kein Limit je Job:**
  - Ein Stapel hat bis zu 200 Dateien.
  - `metadaten_lesen` liest davon 50, der Rest steht in `fehlend`.
- **`FAILED`:** Scheitert der Flow, gibt es vermutlich keinen Bericht (F7). Der Ablauf geht mit
  den vorhandenen Angaben weiter.
- **In der Studio-Probe** („Ablauf ausprobieren“) legt der Upload nichts in WLO ab (Trockenlauf).
  Der Ablauf endet dort also in `ohne_ablage`.
- **Vor der Antwort:** „Weiter im Ablauf“ am KI-Schritt, bevor die Person etwas getippt hat,
  führt zu `ohne_entwurf`. Das ist Absicht, so bleibt die Person am Steuer.

## Führungen: durch die Webseite leiten

Eine Führung zeigt der Person den Weg zu einer Seite und kann warten, bis sie dort ist. Drei
Bausteine gibt es dafür.

### Schritt „Seite“ (`typ: seite`)

| Feld | Bedeutung |
|---|---|
| `text` | Was der Chat dazu sagt (Pflicht, Deutsch). |
| `url` | Wohin der Chip führt: ein Pfad mit `/` (etwa `/mitmachen/`) oder eine `https://`-Adresse. |
| `label` | Aufschrift des Chips je Sprache, etwa „Zur Mitmach-Seite“ (Pflicht, Deutsch). |
| `ankunft` | Pfadmuster. Gesetzt: Der Ablauf wartet, bis die Person auf einer passenden Seite ist. Leer: Der Chip steht da, und es geht sofort weiter. |

- Der Chip öffnet die Seite im selben Fenster. Das Gespräch geht dort weiter, wenn das Widget auf
  der Zielseite eingebunden ist und die Sitzung behält (`persist-session`, oder die Übergabe zu
  einer vertrauten Domain). **Ohne `persist-session` beginnt auf der neuen Seite ein neues
  Gespräch**; eine Führung mit `ankunft` kommt dort nie an. Für solche Einbindungen nur
  Seitenschritte ohne `ankunft` nehmen.
- Kommt die Person an, meldet das Widget es von selbst, und der nächste Schritt erscheint.
- Solange der Ablauf wartet, zeigt die Ablauf-Leiste den Weg als Knopf, auch nach einem Neuladen
  oder einem anderen Link.
- Steht die Person schon auf der Seite, zeigt der Schritt keinen Chip und geht gleich weiter.
- Schreibe den Text als Ankündigung („Als Nächstes …“): Er erscheint vor dem Wechsel.
- Tippt sie zwischendurch etwas, antwortet die KI. Der Ablauf wartet weiter, und der Chip steht
  wieder unter der Antwort.
- Die Prüfung meldet, wenn das eigene Ziel (`url`) zu keinem Muster der `ankunft` passt. Der
  Ablauf wartete sonst für immer.

### Bedingung „Seite passt“ (`wenn_seite`)

In einer **Verzweigung** prüft eine Regel, auf welcher Seite die Person gerade ist. Im
Regel-Editor ist es die Bedingung „Seite passt“; mehrere Muster werden mit Komma getrennt.

### Auslöser „Seite“ (`art: seite`)

Passt die Seite beim Öffnen des Chats, bietet das Widget den Ablauf als Chip unter der Begrüßung
an, höchstens zwei solche Angebote. Von selbst startet nichts. Hat die Einbindung eigene
Start-Chips (`start-replies`), gelten diese. Auf Seiten mit eigenem Kontext-Gruß (Sammlung,
Inhalt, Themenseite) entfällt die Begrüßung und damit das Angebot. Abläufe mit der Voraussetzung
„Anmeldung“ werden nicht angeboten.

### Pfadmuster

- Ein Muster beginnt mit `/`. `*` steht für beliebig viele Zeichen, auch für `/`; sonst zählt jedes
  Zeichen wörtlich. Groß- und Kleinschreibung, Anfrage (`?…`), Anker (`#…`) und ein `/` am Ende
  zählen nicht.
- `/mitmachen/*` passt auf `/mitmachen/` und auf jede Seite darunter, aber nicht auf
  `/mitmachen-xyz`. `/mitmachen*` passt auf alle drei.
- Höchstens 10 Muster je Liste, je 200 Zeichen. Reguläre Ausdrücke gibt es nicht.

### Testen

Ein Testfall nennt die Seite beim Start (`seite`) und an einem wartenden Seitenschritt die Seite,
auf der die Person ankommt (Eingabe `seite`). „Tests ausführen“ spielt den Ablauf ohne Browser durch
(siehe auch das Kapitel „Testen“ unten).

### Beispiel

Im Werkszustand liegt `06-ablaeufe/fuehrung` („Kurze Führung durch WLO“), ausgeschaltet. Er prüft
zuerst mit `wenn_seite`, ob die Person schon auf der Mitmach-Seite ist. Dann führt er über
Startseite und Bildungsinhalte dorthin, mit drei Testfällen. Die bestehende Webseiten-Tour bleibt
davon unberührt.

## Testen

- **Prüfen** meldet, was der Treiber nicht sicher ausführen könnte (fehlende Ziele, Teile, die nie
  entstehen, schreibende Werkzeuge ohne Freigabe …). Gespeichert wird nur ein Ablauf ohne Befund.
- **Tests ausführen** spielt jeden Testfall mit dem echten Treiber durch, ohne Sprachmodell, WLO
  oder b-api. Das kostet nichts und kommt jedes Mal gleich heraus.

Ein Testfall (`tests`) nennt:

| Feld | Bedeutung |
|---|---|
| `ab` | Bei welchem Schritt er beginnt (sonst beim ersten). |
| `teile` | Teile vor dem Start, etwa die Ordnerstruktur eines Uploads. |
| `start` | Startdaten wie von der Gastseite. |
| `quelle` | Woher die Startdaten kommen: `gastseite` (Vorgabe) oder `ki`. |
| `angemeldet` | `true` (Vorgabe) oder `false`. Ohne Anmeldung startet ein Ablauf mit der Voraussetzung „Anmeldung“ nicht, Aufträge und Freigaben gehen zu `bei_fehler`. |
| `gewaehlt` | Die Wahl eines Modul-Auslösers, mit `ab` zusammen. |
| `seite` | Die Seite beim Start (Führungen, `wenn_seite`). |
| `werkzeuge` | Ergebnis je Werkzeug-Schritt (Schritt-Kennung → Wert, `null` = liefert nichts). Dienste ohne Netz rechnet die Simulation selbst. |
| `eingaben` | Antworten an wartenden Schritten, je mit `bei` (der wartende Schritt): `antwort` für ein Modul, `option`/`text` für eine Wahl, `ergebnis`/`fehler` für Auftrag und Freigabe, `freigabe: ja`/`nein`, `teile` für einen KI-Schritt, `seite` für eine Führung. |
| `erwartet` | `weg` (die Schritte), `status`, `ende`, `teile`. |

Die Antwort an ein Modul muss so aussehen wie im Betrieb; bei `ui_strukturentwurf` also mit
`titel`, `quelle`, `knoten`, `uebernommen`, `bearbeitet`. Sonst meldet der Test „passt nicht zur
Frage“.

## Im Widget ausprobieren

Am Ablauf steht **„Im Widget ausprobieren“**. Der Knopf öffnet die Vorschau mit diesem Ablauf; dort
lassen sich Startdaten (JSON) mitgeben, und **„Ablauf starten“** startet ihn im echten Widget.

- Es gilt die **gespeicherte** Fassung. Erst speichern, dann ausprobieren.
- Auch ein ausgeschalteter Ablauf startet hier, und Startdaten gehen auch ohne Auslöser „Gastseite“,
  solange sein Startschema passt.
- Es ist ein **Trockenlauf**:
  - Schreibende WLO-Werkzeuge laufen nicht. Die Vorschau einer Änderung ist echt, nach der Freigabe
    steht „Trockenlauf: … geschrieben wurde nichts“. Was ein Schreibschritt anlegen würde, gibt es
    in der Probe nicht: Sein Teil enthält nur `{trockenlauf, werkzeug}`. Folgeschritte, die auf
    Kennungen des Angelegten bauen, prüft ein Testfall mit `eingaben.ergebnis`.
  - Aufträge starten nicht; sie sind sofort fertig, ohne Ergebnis. Wer Ergebnisse durchspielen
    will, nimmt einen Testfall. Wie im Betrieb braucht ein Auftrag die WLO-Anmeldung.
  - Dateien werden nicht in WLO abgelegt.
  - „Meine Vorgänge“ gibt es in der Probe nicht; sie berührt keine echten Vorgänge.
- Anmeldung und Freigaben bleiben wie im Betrieb: Die Probe zeigt, was die Person sieht.
- Das Widget trägt dabei das Etikett „Probe · Trockenlauf“. Ohne gültige Studio-Anmeldung läuft
  keine Probe, das Widget meldet dann einen Fehler.

## Aufträge, die schreiben (Plan 2026-11-10, TB-F1)

Ein `auftrag` startet einen Kestra-Flow über die B-API **im Namen der angemeldeten Person**. Der
Chatbot schickt `X-Edu-User-Id` mit ihrem Benutzernamen, also arbeitet der Flow im Repositorium mit
ihren Rechten. Ohne WLO-Anmeldung startet kein Auftrag.

- Ob ein Flow schreibt, sieht der Chatbot nicht. Die Redaktion kreuzt am Schritt **„Flow schreibt
  ins Repositorium“** an (`repo_schreibt: true`). Der Vermerk steht im Studio, ein Ablauf mit Auftrag
  startet nie direkt.
- Vor einem schreibenden Auftrag gehört eine Wahl, die sagt, was geschieht. Zum Beispiel: „Ich
  erzeuge jetzt Metadaten für deine N Dateien und schreibe sie hinein. Weiter?“
- Ein Flow, der nicht freigegeben ist, sperrt nur einen **eingeschalteten** Ablauf, und nur, wenn
  sein Auftragsschritt keinen Ersatzweg (`bei_fehler`) hat. Bei einem ausgeschalteten Ablauf oder
  mit Ersatzweg erscheint er als Hinweis (Rückmeldung 16.11.). Zur Laufzeit startet der Auftrag
  dann nicht, und der Schritt nimmt `bei_fehler`. Dasselbe gilt beim Entziehen einer Freigabe.

### Kestra-Flows freigeben (Paket KF)

Auf der Seite „Abläufe“ steht unter der Liste der Abschnitt **„Kestra-Flows freigeben“**
(`01-base/kestra-flows`). Dort trägt die Redaktion die Flows ein, die ein Auftragsschritt starten
darf (`namespace/flowId`). Die Änderung wirkt ohne Neustart.

- **Vorschläge:** die aktiven Flows, die die b-api für den Schlüssel der Anlage meldet
  (`GET /api/v1/jobs/flows`, `B_API_KEY`, 5 Minuten zwischengespeichert). Freitext geht auch.
- **Obergrenze:** Ist `B_API_JOBS_FLOWS` gesetzt, wirken nur Flows aus dieser Liste. Ist im Studio
  nichts freigegeben, gelten ihre Flows wie vor dem Paket.
- **Werksvorgabe (16.11.):** Ist weder im Studio etwas freigegeben noch `B_API_JOBS_FLOWS`
  gesetzt, gilt `edusharing.chatbot/node-metadata-write`. Das ist der Metadaten-Flow des Ablaufs
  „Themenbaum · aus eigenen Inhalten“, ab Werk an.
  - Sie steht im Code (`auftraege/client.WERKSVORGABE`), nicht im Seed. Ein Seed-Eintrag wirkte
    als Studio-Liste und nähme einer Anlage mit gesetzter Variable alle anderen Flows.
  - Wer die Variable setzt und den Ablauf nutzen will, nimmt den Flow dort auf.
- **Start-Pfad:** Leer heißt Vorgabe `/api/v1/jobs/flows/{flow}`. Aufträge sind an, sobald
  ein Flow wirksam freigegeben ist.
- **Datenschutz:** Eingaben und Ausgaben liegen bei Kestra 30 Tage im Klartext. Nur Flows
  freigeben, deren Eingaben dort liegen dürfen. Das gilt auch für die Werksvorgabe: Die
  erzeugten Metadaten privater Dateien liegen 30 Tage bei Kestra.

