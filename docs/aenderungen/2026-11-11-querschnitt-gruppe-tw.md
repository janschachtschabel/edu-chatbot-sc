# Querschnitts-Review TW-1 bis TW-5 (2026-11-11)

Plan `plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`. Ein unabhängiges Review prüfte, was
zwischen den Paketen bricht und ob das Ziel des Nutzers erreicht ist. Ergebnis: 0 CRITICAL,
5 MAJOR (einer davon schon vorher vorhanden), 7 MINOR, 5 NIT. Wegen der fünf MAJOR folgt nach der
Behebung ein zweites, unabhängiges Review.

## Befunde und Behebung

- **MAJOR 1: Die Wendungen waren zu breit.**
  - „einen themenbaum zu/für“ startete auch bei Fragen nach dem Bestand („Gibt es in WLO einen
    Themenbaum für Chemie?“) und bei „… zu meinem Lehrplan“.
  - „Aus einem Thema“ kennt jetzt nur die ausdrückliche Neuanlage („einen themenbaum erstellen“,
    „erstelle einen themenbaum“, „einen neuen themenbaum“ …). „Einen Themenbaum zu Karate
    erstellen“ entscheidet die KI, die den Ablauf direkt startet.
  - Der Dokument-Ablauf kannte „themenbaum zu/für meinen lehrplan“; beide fielen im zweiten
    Review und im Nach-Review weg (Grenze von 10 Wendungen, Fragen nach vorhandenen Bäumen).
  - Die Bestandsfragen stehen als Gegenprobe in `test_tw4_seeds`.
- **MAJOR 2: Ein `nicht_wann` kam gekürzt beim Modell an.** `_BESCHREIBUNG_ZEICHEN` steigt von 600
  auf 800. Ein Test prüft, dass keine Beschreibung eines Seeds gekürzt wird.
- **MAJOR 3: „Abbrechen“ in der Leiste setzte keine Sperre.** Jetzt merkt sich auch der Abbruch
  durch die Person den Ausstieg (`abbruch_zug`).
- **MAJOR 4: Die Sperre hatte kein Ende**, sie galt so lange wie der Vorgang, bis zu 30 Tage, ohne
  Knopf zurück.
  - Der Ausstieg ist jetzt eine kurze Marke im Gespräch (`zug_basis.AUSSTIEG_KEY`). Sie gilt
    `AUSSTIEG_ZUEGE` = 3 Züge und verfällt dann.
  - Die Antwort auf „Ohne Ablauf“ bietet „Doch mit Ablauf“ (Direktaktion `ablauf_starten`) statt
    „Neues Vorhaben“ (NIT 14).
- **MAJOR 5, vorher vorhanden: Muster-Maschine am KI-Schritt.** Das Muster bot nur Module an, die
  es selbst nennt, also nicht `ui_strukturentwurf`. Jetzt kommen am KI-Schritt die UI-Module des
  Schritts dazu (`ki_schritt.mit_schrittmodulen`).
- **MINOR 6:**
  - „Thema aus dem Verlauf, fehlt es, einmal nachfragen“ steht jetzt im Hinweis an die KI, nicht
    mehr in den Vorgaben.
  - Der Studio-Hinweis zu den Vorgaben sagt, dass sie an den Generator gehen.
- **MINOR 7:** Die Vorgaben gelten nur am KI-Schritt. Das steht unter den Grenzen von TW-2.
- **MINOR 8:** Der Hinweis auf den Dokument-Ablauf (`nach_dokument`) sagt ehrlich, dass das
  Dokument dort noch einmal gewählt wird.
- **MINOR 9:** Auch der Muster-Weg lässt den eben abgelehnten Ablauf aus (`generate._abgelehnt`).
- **MINOR 10:** „Weiter im Ablauf“ übersteht auch die Deckel in `turn_persist` und
  `begrenze_pillen`.
- **MINOR 11:** Ein Eintrag in den offenen Befunden, mit den Deploy-Schritten und dem Hinweis auf
  angepasste Abläufe im Werksabgleich.
- **MINOR 12:** Die Notiz TW-4 und `ablaeufe.md` geben den Endstand wieder.
- **NIT 13:** Ein abgewähltes `ausstieg` (`false`) gilt als nicht gesetzt, die Fassung bleibt.
- **NIT 15:** Der Name des Knopfs heißt „Senden: Auswahl an den Chat“ und beginnt mit der
  sichtbaren Beschriftung.
- **NIT 16:** Ein Kommentar in `test_ui_upload` ist nachgezogen.
- **NIT 17, als Grenze vermerkt:** Ein Start per Wendung übernimmt das Thema nicht in den Teil;
  die KI liest es aus dem Verlauf.

## Prüfung

- **Tests:**
  - `test_tw4_ausstieg` (5);
  - `test_tw4_seeds` mit Wendungen, Modul-Auslöser, Direktstart, ungekürzten Beschreibungen,
    Modulen im Muster-Weg und `ohne` im Muster-Weg;
  - `test_tw3_ablaeufe_zuerst`.
- **Zahlen:**
  - vor der Behebung: alle 133 Testdateien, die geänderte Module berühren, mit 2995 grün;
  - nach der Behebung: 184 Dateien mit 4194 grün, nach dem zweiten Review 4202 grün;
  - Frontend: ui-module 348, Studio 2144, lint sauber.

## Zweites Review (unabhängig) und Behebung

2 MAJOR, 5 MINOR, 3 NIT. Behoben sind laut Review MAJOR 2, 3 und 5 sowie im Code MAJOR 4. Dazu:

- **MAJOR 1:** Die Marke nach „Ohne Ablauf“ wurde nach dem Speichern der Sitzung gesetzt und nie
  festgeschrieben, die Schleife blieb im Betrieb. Jetzt wird sie vor `update_session` gesetzt.
  Ein neuer Test prüft die geschriebenen Entities.
- **MAJOR 2:** Die allgemeinen Wendungen von „aus einem Thema“ trafen auch „… aus diesem PDF“,
  „… aus meinen Materialien“ und „Wie kann ich einen Themenbaum erstellen?“.
  - „Aus einem Thema“ kennt nur noch „themenbaum aus einem thema“. Den Rest entscheidet die KI.
  - Dokument und Inhalte haben weitere Quellen-Wendungen (PDF, Bildungsplan, Materialien,
    Unterlagen). Die Prüfung erlaubt höchstens 10 Wendungen je Auslöser, den Rest entscheidet
    die KI.
  - Die Sätze stehen als Gegenprobe in `test_tw4_seeds`.
- **MINOR 3:** Am KI-Schritt hebt `mit_schrittmodulen` die Degradation des Musters auf. Ein
  fehlender Slot leerte sonst die Werkzeuge; der Hinweis fragt selbst nach dem Thema.
- **MINOR 4:** Die obere Ebene heißt „höchstens `anzahl_oben`, so viele, wie das Thema trägt“
  statt „genau“, damit nichts aufgefüllt wird.
- **MINOR 5:** Wahl- und Weiter-Knöpfe werden in einem Lauf geschützt. Zwei Läufe verdrängten
  unter Deckel 1 den Bestätigungsknopf des Abbruchs.
- **MINOR 6, als Grenze in `ablaeufe.md`:** „Doch mit Ablauf“ startet von vorn.
- **NIT 8:** Ein neuer Start desselben Ablaufs hebt die Marke auf.
- **NIT 9/10:** Doku: Muster-Weg-Grenze gestrichen; „drei Züge mit der KI“.

## Nach-Review der Behebung

Ein kurzes, unabhängiges Nach-Review fand die Behebungen 1, 2, 4 und 5 korrekt und vollständig.
Dazu:

- **MINOR:** Die aufgehobene Degradation öffnete alle Werkzeuge des Musters, die KI hätte ohne
  Thema suchen können. Jetzt bleiben am KI-Schritt nur die Module des Schritts (`tools: []`).
- **MINOR:** „themenbaum zu meinem lehrplan“ traf auch „Ich habe schon einen Themenbaum zu meinem
  Lehrplan, kannst du ihn prüfen?“. Dafür steht jetzt „themenbaum aus dem dokument“ in der Liste.
- **NIT:** `anzahl_oben` heißt im Manifest „Höchstzahl“. Eine genaue Zahl geht über `hinweise`.
- **NIT:** Die Prüfung erlaubt höchstens 10 Wendungen; die Liste des Dokument-Ablaufs ist darauf
  gekürzt.
- **Als Grenze vermerkt:**
  - Wortvergleich kennt keine Verneinung („kein Themenbaum aus dem Lehrplan, sondern …“), dafür
    gibt es „Ohne Ablauf“.
  - „Abbrechen“ am Freigabe- oder Auftragsschritt setzt keine Marke, nur die Leiste.
  - Eine ausdrückliche Modul-Wahl „Strukturdokument“ in den drei Zügen nach „Ohne Ablauf“
    startet den Dokument-Ablauf nicht; „Doch mit Ablauf“ steht in der Antwort davor.
  - `DebugInfo` und Qualitätslog zeigen am KI-Schritt das Muster mit seiner Degradation.
