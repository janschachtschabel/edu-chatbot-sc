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
| `verzweigung` | Regeln unter `weiter`: `wenn_teil` (ein Teil ist da), `wenn_gewaehlt` (eine Wahl), `wenn_wert` (eine Stelle eines Teils vergleichen: gleich, enthält, vorhanden, leer, größer, kleiner) und `wenn_seite` (Führungen). Die erste passende gilt, `sonst` am Ende. |
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
  Upload). Sonst bleibt es ein Vorschlag, und „Ablauf prüfen“ meldet es.
- Die KI bietet nur **eingeschaltete** Abläufe an. Einen ausgeschalteten Ablauf mit `direkt` kann man
  in der Studio-Vorschau also nicht über die KI ausprobieren, nur über „Ablauf ausprobieren“.

## Beispiel: Sammlung aus Ordnern

`06-ablaeufe/sammlungsstruktur` („Themenbaum · aus Ordnern“) ist der kürzeste vollständige Ablauf:

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

## Beispiele: Themenbaum mit Kernfragen

Die vier Themenbaum-Abläufe heißen im Studio einheitlich „Themenbaum · aus …“: aus Ordnern, aus
einem Thema, aus eigenen Inhalten und aus einem Dokument. Im Werkszustand an sind „aus Ordnern“,
„aus einem Thema“ und „aus einem Dokument“ (sie schreiben nichts); „aus eigenen Inhalten“ ist aus,
bis der Flow freigeschaltet ist. Ohne Anmeldung startet „aus eigenen Inhalten“ nicht: passt die
Wendung, sagt die KI das in einem Satz und hilft ohne ihn weiter.
„Aus einem Thema“ und „aus einem Dokument“ beginnen mit der Wahl „mit Fragen / gleich entwerfen /
ohne Ablauf“, „aus eigenen Inhalten“ mit „Ja, los geht's / ohne Ablauf“.
„Themenbaum · aus einem Dokument“ startet auch aus dem Auswahlfeld, mit „Themenbaum aus dem
Strukturdokument erstellen“ (Modul-Auslöser).

**Kernfragen als Teile.** Die Fragen kommen aus dem Gestaltungsleitfaden: wofür, für wen, welches
Thema, wie tief.

- Eine Nachricht mit Schnellantworten und `schreibt: zweck` legt das Label der gewählten Antwort
  als Teil `zweck` ab. In der Zeile für die KI steht dann „Wahl: Unterricht planen“.
- Getippter Text geht wie bisher über `freitext.schreibt` in einen Teil. Tragen beide denselben
  Namen (etwa `stufe`), ergeben Wahl und Tippen denselben Teil.
- Der Hinweis an die KI setzt nichts ein. Die KI sieht eine Wahl in der Arbeitsstands-Zeile
  („Wahl: …“). Getippten Text sieht sie im Verlauf; in der Zeile steht davon nur der Name des
  Teils.

**`06-ablaeufe/themenbaum_aus_thema`** („Themenbaum · aus einem Thema“):

1. `wofuer`, `stufe`, `thema` (Freitext) und `tiefe`.
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

Damit der Auftrag im Betrieb läuft, muss der Flow in `B_API_JOBS_FLOWS` stehen, und der
B-API-Schlüssel muss ihn starten dürfen. Solange der Ablauf aus ist, ist eine fehlende
Freischaltung nur ein Hinweis.

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
- Ein Flow, den der Betrieb nicht in `B_API_JOBS_FLOWS` freischaltet, sperrt nur einen
  **eingeschalteten** Ablauf. Bei einem ausgeschalteten erscheint er als Hinweis.

