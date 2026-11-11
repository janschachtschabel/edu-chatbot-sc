# Paket TW-4: Themenbaum-Abläufe mit Einstieg, Vorgaben und Dokument-Weg (2026-11-11)

Plan `plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`, Entscheide E2, E3, E5 und E6, nach
den Vorgaben des Nutzers (N16).

> Stand nach Review und Querschnitts-Review. Was die Reviews geändert haben, steht in den
> Abschnitten dazu. Hier steht der Endstand.

## „Themenbaum · aus einem Thema“ (`themenbaum_aus_thema`)

- **Einstieg** mit drei Wahlen:
  - „Ja, mit Fragen“;
  - „Gleich entwerfen“: direkt zum KI-Schritt;
  - „Ohne Ablauf“: Ausstieg, siehe unten.
- **Zuerst angeboten:**
  - Der Auslöser `agent` steht auf `modus: direkt`. Der Ablauf schreibt nichts, also startet die
    KI ihn ohne Klick, wenn die Bitte passt, auch „einen Themenbaum zu Karate erstellen“.
  - Als Wendung nur die eindeutige „themenbaum aus einem thema“. Alle anderen Bitten entscheidet
    die KI, die `nicht_wann` sieht (zweites Review TW, Befund 2).
  - `wann` nennt auch Gliederung und Sammlungsstruktur. `nicht_wann` schließt eigene Dateien,
    Dokumente sowie Texte und Referate aus.
- **KI-Schritt:**
  - Startknopf „Entwurf erstellen“.
  - Der Hinweis übergibt Thema, Fach, Stufe und Tiefe, sonst aus dem Verlauf. Fehlt das Thema,
    fragt die KI einmal nach.
  - Vorgaben aus dem Leitfaden:
    - Zweck → Baumart: Planungsbaum, Fachsystematik mit 6 bis 12 Punkten oben, oder Themenwelt
      (Fragen als Titel nur, wenn alle Geschwister Fragen sind);
    - die Stufe ist nie ein Punkt;
    - in der Beruflichen Bildung ordnen Lernfelder bzw. Handlungen die obere Ebene;
    - Kompetenzen, Methoden und Formate stehen nur in den Schlagworten.

## „Themenbaum · aus eigenen Inhalten“ (`themenbaum_aus_inhalten`)

- **Einstieg:** „Ich führe dich in wenigen Schritten durch … Einverstanden?“ mit den Antworten
  „Ja, los geht's“ oder „Ohne Ablauf“ (Ausstieg).
- **Wendungen** auch in natürlicher Satzstellung, z. B. „aus meinen dateien einen themenbaum“.
  `nicht_wann` schließt ein einzelnes Dokument (Lehrplan) aus.
- **Ein gelesenes Dokument** im Upload-Schritt führt zu einem Hinweis auf den Dokument-Ablauf
  (`nach_dokument`).
- **KI-Schritt:** Startknopf und Vorgaben zum Bau von unten:
  - nach Themen, nicht nach Ordnern, Jahren, Klassen oder Formaten;
  - mindestens zwei Materialien je Punkt;
  - Zweck → Baumart.

## Neu: „Themenbaum · aus einem Dokument“ (`themenbaum_aus_dokument`)

- **Auslöser:**
  - `modul` auf `ui_upload` mit `wenn_teil: document`. Das ist genau „Themenbaum aus dem
    Strukturdokument erstellen“, denn `aktion: dokument` heißt laut Manifest immer `ziel:
    themenbaum`.
  - Dazu Knopf, KI (Vorschlag, wegen des Uploads nie direkt) und Lehrplan-Wendungen.
- **Schritte:**
  1. `hochladen` (`ui_upload`, mit dem Hinweis „falls nötig als Strukturdokument markieren“).
  2. `gelesen`: Verzweigung auf `document`. Ohne Dokument folgt die Frage „Nochmal wählen /
     Beenden“. Hier setzt der Modul-Auslöser ein.
  3. `einstieg`: mit Fragen, gleich entwerfen oder ohne Ablauf.
  4. `ordnung`: „Wonach soll die erste Ebene geordnet sein?“
  5. `wofuer`.
  6. `entwurf`: KI mit `aus_dokument`, Startknopf und Vorgaben.
  7. `ende`.
- **Vorgaben** aus dem Leitfaden und der Lehrplan-Doppelseite:
  - **Ebene 1** folgt der Ordnung, in der Reihenfolge des Dokuments, ohne Nummern.
  - **Ebene 2** sind Fachbegriffe und Inhalte; in der Berufsschule die Inhalte bzw.
    Handlungsschritte, Lernsituationen nur, wenn das Dokument sie nennt.
  - **Keine Punkte** werden Kompetenzerwartungen, Basiskonzepte, Kontexte, Differenzierung,
    Leistungsbewertung, Hinweise, Stundentafeln und Zeitrichtwerte.
  - Was der Zweck bewirkt.
  - **Ohne Fragen** gilt die Ordnung: Lernfelder vor Themenfeldern vor Kapiteln.

## Ausstieg (alle drei)

„Ohne Ablauf“ endet an einem `ende` mit `ausstieg: true`. „Abbrechen“ in der Ablauf-Leiste wirkt
genauso.

- **Sperre:** Drei Züge mit der KI lang (Direktaktionen, Ablauf-Schritte und Kontext-Pings
  zählen nicht) startet derselbe Ablauf nicht von selbst, weder per Wendung noch
  per Modul-Antwort noch als KI-Werkzeug (Agent- und Muster-Weg).
- **Weg zurück:** Die Antwort bietet „Doch mit Ablauf“.

## Prüfung

- Alle drei Seeds sind aus. `pruefe()` ergibt keinen Befund.
- **Simulation:** zuerst 13 Testfälle, nach dem Review 16, alle grün.
  - aus einem Thema: 5 (alle Fragen, ohne Ablauf, gleich entwerfen, getippte Zielgruppe, ohne
    Entwurf);
  - aus Inhalten: 7 (die bisherigen 6 mit dem Einstieg, dazu „ohne Ablauf“);
  - aus einem Dokument: 4 (vom Auswahlfeld bis zum Entwurf, ohne Ablauf, gleich entwerfen ohne
    Entwurf, nur erfasst).

## Review (unabhängig) und Behebung

2 MAJOR, 11 MINOR, 4 NIT.

- **MAJOR 1:** Die Wendungen waren zu breit. „Themenbaum überarbeiten“ oder „Was ist ein
  Themenbaum für …“ starteten den Ablauf, und Sätze wie „aus meinen Dateien einen Themenbaum
  erstellen“ landeten im falschen Ablauf.
  - **Neuanlage:** Die Wendungen heißen jetzt „einen themenbaum zu“, „einen themenbaum für“,
    „einen themenbaum erstellen“, „einen themenbaum anlegen“ und „neuen themenbaum“.
  - **Natürliche Satzstellung** für die beiden anderen Abläufe: „aus meinen dateien einen
    themenbaum“, „aus meinem lehrplan einen themenbaum“, „themenbaum aus dem rahmenlehrplan“ und
    weitere.
  - **Neuer Test** `test_tw4_seeds.py` gegen die echten Seeds: Wendungen, Modul-Auslöser,
    Direktstart.
- **MAJOR 2:** „Ohne Fragen“ beendete den Lauf, und die nächste Nachricht startete ihn wieder
  (Schleife). Jetzt gilt:
  - **Drei Wahlen:** „Ja, mit Fragen“, „Gleich entwerfen“ (zum KI-Schritt mit Startknopf und
    Vorgaben) und „Ohne Ablauf“ (Ausstieg).
  - **Neues Feld `ausstieg`** am `ende` (Studio „Ausstieg aus dem Ablauf“). Endet der letzte Lauf
    dort, startet derselbe Ablauf nicht wieder von selbst, weder per Wendung noch per
    Modul-Antwort noch als Werkzeug der KI (`zug.abgelehnt`). Ein Knopf startet ihn weiter. Tests
    stehen in `test_tw4_ausstieg.py`.
  - Die Vorgabe „ohne Fragen: wähle selbst die Ordnung“ wirkt jetzt, denn „Gleich entwerfen“
    führt zum KI-Schritt.
- **MINOR 3, bewusst so:** Beim Dokument-Ablauf kommt die Wahl nach dem Lesen, weil der
  Modul-Auslöser dort beginnt. Vor dem Upload bietet die Ablauf-Leiste „Abbrechen“.
- **MINOR 4:**
  - Der Text des Upload-Schritts sagt „markiere es falls nötig als Strukturdokument“.
  - `ohne_dokument` ist eine Nachricht mit „Nochmal wählen“ und „Beenden“.
- **MINOR 5:** Die Vorgaben des Dokument-Ablaufs sagen jetzt, was der Zweck bewirkt.
- **MINOR 6:** In der Berufsschule kommen die Inhalte bzw. Handlungsschritte des Lernfelds;
  Lernsituationen nur, wenn das Dokument sie nennt.
- **MINOR 7:** Die Zeile „ein Strukturdokument darf die obere Ebene vorgeben“ ist gestrichen,
  denn der Generator sieht die Rolle nicht.
- **MINOR 8:** Fragen als Titel nur, wenn alle Geschwister Fragen sind. Die Ebenen folgen der
  gewählten Tiefe, und ohne Antworten nimmt die KI Thema und Wünsche aus dem Verlauf.
- **MINOR 9:**
  - `nicht_wann` bei „aus Inhalten“.
  - Ein gelesenes Dokument im Upload-Schritt führt zu einem Hinweis auf den Dokument-Ablauf
    (`nach_dokument`).
- **MINOR 10, Grenze:** Ist im Studio „Dokument im Chat“ aus, bietet der Dokument-Ablauf keinen
  Lese-Knopf. Eine Voraussetzung „Dokument lesen“ gibt es noch nicht.
- **MINOR 12:** Der Knopf „Senden“ heißt für Screenreader „Auswahl an den Chat senden“
  (`aria-label`), denn der Chat hat selbst einen Knopf „Senden“.
- **MINOR 13:** `nicht_wann` bei „aus einem Thema“ nennt Texte, Referate und Arbeiten.
- **NITs:** Zählung korrigiert; README des Upload-Moduls; die Frage heißt „Wonach soll die erste
  Ebene geordnet sein?“ mit der Option „Lernfelder (Berufsschule)“.

## Grenzen

- **Wendungen** sind zusammenhängende Teilzeichenketten. Bei „Aus meinem Lehrplan **bitte**
  einen Themenbaum“ trennt „bitte“ die Wörter, das übernimmt der KI-Weg. Bei gleicher Länge
  entscheidet die Kennung.
- Die Vorgaben sind Text an den Generator, ob er sie befolgt, zeigt erst ein Lauf. Den Weg prüft
  der Chat-Smoke.
- Der Modul-Auslöser greift nur, wenn der Ablauf eingeschaltet ist. Ausgeschaltet geht die
  Upload-Antwort wie bisher direkt an die KI.
