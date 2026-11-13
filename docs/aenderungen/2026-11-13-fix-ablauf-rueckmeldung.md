# Fix: Rückmeldung zum Ablauf „Themenbaum · aus einem Thema“ (2026-11-13)

Beim Test des Ablaufs fielen vier Dinge auf. Drei davon hatten eine gemeinsame Ursache oder lagen
am Abbrechen; das vierte war kein Fehler.

## 1 Der Ablauf blieb bei „Schritt 2 von 6“ stehen

**Beobachtet:** Auf „Wofür soll der Themenbaum sein?“ tippte die Person „für eine Webseite über
Karate“. Die KI antwortete, der Ablauf frage „jetzt die weiteren Angaben ab“. Er blieb aber
stehen, und die Knöpfe kamen wieder. In einer zweiten Sitzung stellte die KI die Frage sogar
selbst noch einmal als Auswahlfeld.

**Ursache:** Der Schritt `wofuer` hatte nur Schnellantworten, kein `freitext`
(`services/ablauf/wahl_zug.nimmt_getippt`). Ein getippter Text, der keinem Knopf entspricht, ging
an die KI. Die KI kann einen Ablauf aber nicht weiterschalten. Dieselbe Lücke hatten `tiefe` und
in den Geschwister-Abläufen `wofuer` („aus einem Dokument“, „aus eigenen Inhalten“) und `ordnung`
(„aus einem Dokument“).

**Behoben:**
- Jede Frage, deren Antwort ein Teil wird (`schreibt`), nimmt jetzt auch getippten Text an.
  Ausgenommen sind Steuerfragen mit Ausstieg („Ohne Ablauf“): dort ist Getipptes ein Gespräch mit
  der KI.
- Ein Wächter-Test hält die Regel für alle Seeds fest
  (`tests/test_ablauf_frageschritte_freitext.py`).
- Masterskill (`docs/skills/vorgehen-knapp.md`, Abschnitt „Abläufe“): Wartet ein Ablauf auf eine
  Wahl, stellt die KI seine Frage nicht selbst und kündigt keine Fragen an.

## 2 Das Thema „Karate“ ging verloren, der Baum hieß „Sport“

**Beobachtet:** Der Entwurf galt dem ganzen Fach Sport (Sportspiele, Leichtathletik, Turnen …).

**Ursache:** „Karate“ stand nur in der getippten Antwort auf `wofuer`, die nach Punkt 1 kein Teil
wurde. Die spätere Frage „Zu welchem **Fach und** Thema?“ lud zur Antwort „Sport“ ein. Der
KI-Schritt nimmt die Antworten vor dem Verlauf, also ging „Sport“ als Thema an den Generator.

**Nachgestellt:** Der Generator selbst ist in Ordnung. Mit `thema: "Karate"` (mit oder ohne Fach
„Sport“, mit oder ohne die Vorgaben des Ablaufs) hieß der Baum in 8 von 8 Aufrufen „Karate“
(Kata, Kumite, Etikette …).

**Behoben (Entscheid 13.11.):**
- Das Thema wird zuerst gefragt: „Zu welchem Thema soll der Baum sein? … gern mit Fach, zum
  Beispiel „Optik (Physik)“ oder „Karate“.“ Die Reihenfolge ist jetzt Thema, Zweck, Zielgruppe,
  Tiefe. Das Thema trägt den Baum, darum steht es vorn.
- Der Hinweis an die KI sagt: `thema` ist der Gegenstand, nie nur das Fach.
- Die Vorgaben für den Generator sagen: Der Baum gilt immer dem Thema, nie dem ganzen Fach.
- Neue Optionen: „Überblick, etwa für eine Webseite“ (Zweck) und „Alle, ohne Bildungsstufe“
  (Zielgruppe). Die Vorgaben haben dazu je eine Regel, ebenso für einen eigenen, getippten Zweck.

## 3 „Ablauf abbrechen“ fragte noch einmal nach

**Beobachtet:** Nach „Ablauf abbrechen“ und dem Start eines anderen Ablaufs kam die Frage, ob der
laufende beendet werden soll.

**Ursache:** Der Knopf in der Leiste brach nicht ab, er stellte erst die Rückfrage „Den Ablauf
wirklich abbrechen?“. Wer sie überging, hatte weiter einen laufenden Ablauf. Der nächste Start
fragte deshalb „neu starten?“.

**Behoben (Entscheid 13.11.):**
- Der Knopf bricht sofort ab (`services/ablauf/abbruch_zug.py`). Was gesammelt ist, bleibt im
  Arbeitsstand.
- Eine Rückfrage gibt es nur noch, wenn mehr daran hängt: ein Kestra-Auftrag, der mit endet, oder
  eine Freigabe, deren Plan schon schreiben kann.
- Ein alter Abbruch-Knopf mit der Marke eines anderen Laufs fragt weiterhin erst.

## 4 Der Masterskill-Hinweis kam erst ab der dritten Antwort

Das ist so gewollt. Die Zeile „[ edu-sharing Skill ] Chatbot Masterskill - aktiv“ steht einmal je
Sitzung über der **ersten Antwort der KI** (`domain/skill_ansagen.mit_master_ansage`). Startet die
erste Nachricht einen Ablauf, kommen die ersten Antworten als feste Texte aus dem Ablauf, ohne KI
und damit ohne Masterskill. Die Zeile erscheint bei der ersten Antwort, die die KI schreibt. Für
die festen Texte gilt der Masterskill nicht, er würde dort also nichts bewirken.

## 5 Prüfung „Daten, Schritte, Dialoge“ (zweiter Auftrag vom 13.11.)

Nach den ersten Fixes kam der Auftrag, das Zusammenspiel von Abläufen, Daten und Oberfläche
noch einmal ganz zu prüfen. Gefunden und behoben:

- **Getippte Antworten erreichten die KI nur über den Verlauf.**
  - Die Zeile `[ARBEITSSTAND — …]` nennt von getipptem Text nur den Namen des Teils („Text:
    thema“). Den Wert sah die KI allein in den letzten 10 Nachrichten.
  - Mit dem Thema als erster Frage ist es die älteste Nachricht im Fenster. Schon zwei Züge
    Gespräch am KI-Schritt schoben es hinaus.
  - Jetzt steht am KI-Schritt die Zeile `[ABLAUFDATEN — …]` mit den Antworten aus dem Vorgang
    (`ki_schritt.antwort_teile`, `ki_schritt.daten_zeile`), im Agent- und im Muster-Weg.
  - Die Werte sind Eingaben der Person oder Labels der Redaktion. Sie stehen in der
    Nutzer-Nachricht, als Daten gerahmt, je Antwort auf 200 Zeichen gekürzt, ohne Zeilenumbruch
    und ohne eckige Klammern.
  - Masterskill: Die KI nimmt die Antworten aus dieser Zeile, statt neu zu fragen.
- **„Ausführlich (3 Ebenen)“ ergab 2 Ebenen.** Der Wert kam an (`tiefe: 3`). Aber der Auftrag für
  Ebene 2 sagte dem Modell nur „0 bis 6 Unterthemen“, und es setzte fast überall 0. Der Auftrag
  sagt jetzt, dass eine weitere Ebene gewünscht ist (`strukturentwurf_prompt.unterthemen`).
  Nachgemessen: vorher 2 Ebenen (zweimal), danach 3.
- **Die Person sah nicht, was der Ablauf verstanden hat.** Neuer Schritt `notiert` vor dem
  Entwurf: „Danke! Notiert: Thema „Karate“ · wofür: … · für wen: … · Umfang: …“.
- **Die Fragen sagten nicht, dass man frei antworten kann.** „Wofür“ und „Für wen“ enden jetzt
  mit „Wähle aus oder schreib es …“.
- **Die KI überging eine Zwischenfrage und entwarf sofort.**
  - Der Hinweis des KI-Schritts beginnt jetzt mit „Auf eine Frage erst antworten“. Das allein
    reichte nicht: In 2 von 4 Läufen entwarf die KI trotzdem gleich.
  - Endet die Nachricht mit einem Fragezeichen, steht in der Zeile `[ABLAUFSCHRITT — …]` jetzt ein
    fester Satz dazu (`ki_schritt.zeile`, Parameter `nachricht`). Ob es eine Rückfrage ist,
    entscheidet weiter die KI („Kannst du jetzt entwerfen?“).
  - Nachgemessen mit drei verschiedenen Rückfragen: 3 von 3 beantwortet, danach 3 von 3 Entwürfe
    zum richtigen Thema.

### Durchtest im Chat (Wegwerf-DB, gpt-6-luna, Masterskill aus der lokalen Datei)

Zwei volle Durchgänge, der zweite nach den Review-Fixes (Abschnitt 6):

| Fall | Ergebnis |
|---|---|
| Alles getippt: „Karate“, „für eine Webseite über Karate“, ohne Stufe, „nur grob“ | Entwurf „Karate“, ohne Stufe, 1 Ebene (beide Durchgänge) |
| Knöpfe, „Karate (Sport)“, Sek II, 3 Ebenen, dann Zwischenfragen | Entwurf zu Karate, Fach Sport, Sek II, 3 Ebenen (beide Durchgänge); die Zwischenfrage einmal beantwortet, einmal übergangen — daraufhin der feste Satz oben |
| „Ablauf abbrechen“ in der Leiste, dann „aus meinem Ordner“ | sofort abgebrochen, der neue Ablauf startet ohne Rückfrage |
| Leiste mit fremder Laufmarke (zweiter Tab), dann mit der richtigen | erst die Rückfrage, dann abgebrochen |
| „Gleich entwerfen“ mit Thema in der ersten Nachricht | Entwurf „Photosynthese“, Biologie, Sek II |
| Aus einem Dokument (Lehrplan Augenoptik) | 5 von 5 Lernfeldern, keine fremden Punkte |
| Aus Ordnern | 4 Ordner als 4 Punkte |

Offen geblieben:

- An einer Frage mit Freitext gilt jeder getippte Text als Antwort, auch eine Rückfrage wie „Was
  meinst du damit?“. Das war bei „Für wen“ und „Thema“ schon so. Die Zusammenfassung zeigt es der
  Person jetzt wenigstens vor dem Entwurf.

## 6 Unabhängiges Review und Behebung

Ein zweites, unabhängiges Review der ganzen Lieferung: kein kritischer Befund, 1 MAJOR, 7 MINOR,
6 NIT. Behoben:

- **MAJOR (die Datenzeile las nach Teil-Namen):**
  - Ein Neustart desselben Ablaufs bleibt im selben Vorgang. Nach „Gleich entwerfen“ hätte die
    Zeile das Thema des vorigen Laufs gezeigt, dieselbe Fehlerklasse wie „Sport statt Karate“.
  - Der Lauf merkt sich jetzt die in ihm beantworteten Teile (`lauf.antworten`, nur Namen,
    `treiber.weiter_wahl`). Der Sitzungsverweis trägt die Namen, die Zeile zeigt nur diese.
  - Ein Teil, den auch ein Werkzeug, ein Auftrag, die KI oder ein Modul schreibt, gilt nicht als
    Antwort der Person.
- **MINOR 1 (Abweichung von „keine Eingaben in KI-Zeilen“, Review AS-3a, Befund 11):** als
  bewusste Ausnahme festgehalten, im Code (`treiber.py`, `ki_schritt.daten_zeile`) und in
  `docs/ablaeufe.md`. Die Kennzeile bleibt ohne Inhalt.
- **MINOR 2 (Entschärfung):** Anführungszeichen werden ersetzt, Steuer- und Formatzeichen
  entfernt, auch Doppelgänger eckiger Klammern werden rund. Eine Kürzung ist mit „…“
  gekennzeichnet. Bei vielen Antworten bekommt jede so viel Platz, dass alle ganz hineinpassen.
- **MINOR 3:** Freitext an einem Modul-Schritt zählt mit, die Wahl an einer Steuerfrage mit
  Ausstieg nicht.
- **MINOR 4 (veraltete Leiste):** Die Leiste schickt die Marke ihres Laufs mit. Zeigt sie einen
  anderen Lauf (zweiter Tab), fragt der Zug erst, statt den neuen Lauf abzubrechen.
- **MINOR 5:** Die Zeile liest in beiden Wegen mit einem eigenen Lader.
- **MINOR 6 (Tests):** Der Weg zurück wird wieder mit dem echten Code geprüft. Neue Fälle:
  veraltete Leiste, richtige Marke ohne Bestätigung, Abbruch am KI-Schritt.
- **MINOR 7:** Der Stand des Ablaufs steht in `[ARBEITSSTAND — …]` vor den Teilen. Am Ende der
  gedeckelten Zeile fiel er bei vielen Teilen weg.
- **NIT:** Kopfkommentar des Seeds, „oder schreib es mir“ auch bei „aus eigenen Inhalten“, die
  Rückfrage beim Abbrechen nennt die Freigabe.

Nicht geändert:

- `notiert` zählt als Schritt, die Leiste springt von „5 von 7“ auf „7 von 7“. Wegen der
  Platzhalter trägt die Antwort das Etikett „KI-generierte Antwort“.
- Der Muster-Weg (`respond.py`) hat für die Zeilen am KI-Schritt weiter keinen eigenen
  Verdrahtungs-Test; geprüft ist der Agent-Weg, im Test und im Chat.

## Tests

- `tests/test_ablauf_ki_daten.py` (neu): die Antwort-Teile eines Ablaufs, die Zeile
  `[ABLAUFDATEN — …]` (Reihenfolge, nur Antworten dieses Laufs, leere Werte, Entschärfung, Länge,
  Lesefehler), das Merken im Lauf und im Sitzungsverweis und der Auftrag für eine dritte Ebene.
- `tests/test_respond_agent.py`: die Zeile steht am KI-Schritt in der Nachricht.
- `tests/test_arbeitsstand.py`: der Stand des Ablaufs steht vor den Teilen.
- `tests/test_ablauf_ki_daten.py`: der Satz zur Rückfrage in der Schritt-Zeile.
- `tests/test_tw4_ausstieg.py`: auch der sofortige Abbruch ist ein Ausstieg.
- Widget: `chat-shell-ablauf-leiste.spec.ts` (die Marke des Laufs geht mit).
- `tests/test_ablauf_frageschritte_freitext.py` (neu): die Freitext-Regel und die Nachstellung von
  Punkt 1.
- Seed `themenbaum_aus_thema`: neuer Testfall „Zweck und Tiefe getippt“, die übrigen Fälle in der
  neuen Reihenfolge.
- `tests/test_ablauf_leiste.py`: sofortiger Abbruch, alter Knopf mit fremder Marke, Rückfrage
  nur noch an Auftrag und Freigabe.

## Deploy

- Keine Migration.
- Image neu bauen (Backend und Widget), dann `boerdi import-config --werksabgleich`. Die Fassung der drei Abläufe
  ändert sich, darum enden Läufe, die gerade an ihnen warten.
- Den Masterskill-Knoten in WLO mit `docs/skills/vorgehen-knapp.md` ersetzen.
