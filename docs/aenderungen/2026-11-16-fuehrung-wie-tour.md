# Führung durch WLO: dieselben Texte und Verzweigungen wie die Web-Tour (2026-11-16)

Anlass: Rückmeldung vom 16.11.: „Dieser Ablauf sollte die gleichen Texte und Verzweigungen haben
wie die alte Webseiten-Tour, die nicht mit Abläufen umgesetzt ist.“

## Was vorher abwich

Auf Staging lief noch das alte Beispiel mit drei Stationen („Kurze Führung durch WLO“) als eigene
Fassung. Aber auch der Nachbau vom 15.11. (Werksfassung) wich an mehreren Stellen ab:

- **Reihenfolge der Gruppen:** Lehrkraft, Lernende und Eltern standen vor Content-Abnehmer.
  Davon hingen auch die Chips und die Synonym-Treffer ab.
- **Einstieg mitten drin:** Auf den Einstiegstext folgte der volle Lösungen-Text samt Links zum
  Stöbern. Die Tour zeigt nur den Einstiegstext und die Angebote der Gruppe.
- **Lösungen:** Ein zusätzlicher Halt mit „Wenn du so weit bist: 👇“ trug den Chip.
- **Umschau:** Breite Muster (`/home/*`, `/angebote/*` …). Die Tour kennt nur die Angebote der
  Gruppe, die Stöber-Links und die Gruppenseite; überall sonst zeigt sie den Hinweis.
- **Links:** Sie standen als Liste untereinander. Die Tour setzt „Mehr zu den Inhalten“ und „Das
  brauchst du noch“ in eine Zeile mit „ · “.
- **Zeilenumbrüche:** Die Texte waren zu einer Zeile zusammengezogen. Die Tour behält die
  Umbrüche aus der Konfiguration, und das Widget zeigt sie.
- **Erster Fehlversuch und „Bin mir nicht sicher“:**
  - Die Tour zeigt den Hilfetext und darunter noch einmal die Frage nach der Gruppe, mit den
    Chips.
  - Der Nachbau zeigte nur den Hilfetext. Nach „Bin mir nicht sicher“ kam die Frage als zweite
    Nachricht.
  - Danach brauchte der Nachbau einen Fehlversuch mehr, bis er endete.
- **Synonym „oer“:** Es fehlte.

## Was sich ändert

- **Die Texte kommen aus der Tour selbst:** `backend/scripts/fuehrung_aus_tour.py` erzeugt
  `seeds/06-ablaeufe/fuehrung.yaml`.
  - Die Texte liefert `domain/tour.render` (deutsch und englisch, ohne `base_host`).
  - Einstiege folgen `detect_entry`, Ankunft und Umschau folgen `expected`, Gruppen und Synonyme
    `website-tour.yaml`.
  - Der Erzeuger lag bisher nur außerhalb des Repos.
- **39 Schritte:**
  - Gruppenwahl und Hilfetext (`gruppe`, `unsicher`, beide mit denselben Chips);
  - je Gruppe die Zielgruppenseite und die Lösungen;
  - der Zwischenstopp Bildungsinhalte;
  - je Einstiegsgruppe ein eigener Einstieg;
  - die Mitmach-Seite.
- **Fehlversuche wie in der Tour:**
  - Der erste Fehlversuch zeigt den Hilfetext mit der Frage. Der zweite beendet die Führung
    still, und der Chat antwortet.
  - Nach „Bin mir nicht sicher“ beendet schon der nächste Fehlversuch die Führung.
- **Neuer Test `tests/test_fuehrung_wie_tour.py`:**
  - Der Seed muss dem frisch erzeugten Stand entsprechen.
  - Jeder Text, Chip, Hinweis und Umschau-Text muss `render` gleichen, deutsch und englisch.
  - Der Einstieg je Seite muss `detect_entry` folgen, Ankunft und Umschau `expected`.
  - Jeder Chip muss in der Tour seine eigene Gruppe treffen.
- **Seed-Regel „Frage mit Teil nimmt auch getippten Text“:** Abläufe mit `endet_bei_text` sind
  ausgenommen. Dort beendet getippter Text ohne Treffer den Lauf mit Absicht.

### In der Ablauf-Engine (aus dem Review, gilt für alle Abläufe)

- **Auslöser-Satz mitten im Ablauf (M1):** Tippt die Person an einem wartenden Seiten-Schritt eine
  Wendung desselben Ablaufs („starte die Tour“), zeigt der Ablauf den Schritt erneut, wie die Tour
  (`seite_zug.wiederholen`).
  - Vorher beendete `endet_bei_text` die Führung.
  - Danach sperrte die Ausstiegs-Marke den Neustart für zwei Züge.
- **Getippte Wahl (m1):** Bei Optionen mit Synonymen gelten nur die Beschriftung in der Sprache
  der Person und die Synonyme.
  - Vorher traf „Impressum“ über das englische „Press“ die Presse, und „Teachers“ traf auch im
    deutschen Chat.
  - Optionen ohne Synonyme treffen weiter genau in jeder Sprache.
- **`{wahl.<teil>}` (m2):** Die Beschriftung kommt unverändert in den Text. Vorher stand im
  Verlauf „Content\-Abnehmer“ mit Backslash.
- **Krise an einer Frage (m4):** Ein Ablauf mit `endet_bei_text` endet bei einer Krise, wie die
  Tour. Sonst bekäme die nächste Nachricht den festen Hilfetext.
- **Leiste (m5):** Eine Frage, die eine andere mit demselben Teil und denselben Knöpfen wiederholt
  (der Hilfetext), zählt nicht als eigener Schritt und steht an deren Stelle. Vorher sprang die
  Leiste nach der Gruppenwahl von 2 auf 4.

## Was bleibt anders (Ablauf statt eingebauter Tour)

Diese Punkte stehen im Kopf von `fuehrung.yaml`:
- **Pfade:** relativ statt mit `base_host`, auch die Links in den Texten.
- **Leiste:** Über dem Chat steht die Ablauf-Leiste („Schritt n von m“, „Ablauf abbrechen“).
- **Widget:** Es öffnet sich nur, solange ein Seiten-Schritt wartet.
- **„Bin mir nicht sicher“:** Im Hilfetext zeigt der Chip den Hilfetext erneut; die Tour endete
  dort.
- **Etikett:** Die Antworten tragen nicht das Etikett „KI-generierte Antwort“, weil sie fester Text
  der Redaktion sind.
- **Quelle:** Das Skript liest den Seed `website-tour.yaml`, nicht eine im Studio geänderte Tour.
- **Zeilenumbrüche:** Mitten im Satz stehen sie wie in der Tour, weil die Texte dort als
  `|`-Blöcke stehen. Schöner wäre, sie in `website-tour.yaml` zu beheben (eine Zeile je Absatz)
  und das Skript neu laufen zu lassen.

## Eigenheiten der Tour, die jetzt mitkommen

- **„Lehrerin an einer Grundschule“** landet bei Content-Abnehmer, weil deren Synonym „schule“ vor
  der Gruppe Lehrkraft geprüft wird.
- **„oer“** trifft OER-Community auch in „Boerdi“.
- **Behebung:** Beides ließe sich in `website-tour.yaml` beheben (Synonyme oder Reihenfolge).
  Danach wäre der Erzeuger neu laufen zu lassen. So gelten Tour und Führung gleich.

## Umstieg auf Staging (Redaktion, im Studio)

1. **Sicherung → Werksfassung:** Beim Bereich der Führung „Aktiv: Werksfassung“ wählen. Die alte
   Fassung bleibt still liegen.
2. **Abläufe → „Führung durch WLO“:** einschalten und speichern.
3. **Tour & Lotse:** die Website-Tour ausschalten.

## Geprüft

- Unabhängiges Review: 1 MAJOR, 8 MINOR, 6 NIT.
  - Behoben: M1, m1, m2, m4, m5, m6 (der Erzeuger prüft vor dem Schreiben), m7 (Tests über die
    echte Engine), m8 (die Ausnahme der Seed-Regel gilt nur für die wiederholte Frage).
  - NITs: `raise` statt `assert`; Rückfallziele führen zum Ziel statt still zu einer falschen
    Gruppe; der Kopf ist berichtigt.
  - m3 (Zeilenumbrüche) und die Eigenheiten der Tour bleiben wie in der Tour.
- `tests/test_fuehrung_wie_tour.py`, alle grün, unter anderem:
  - die erste Nachricht je Einstiegsseite im echten Zug;
  - Auslöser-Satz, erster Fehlversuch, Hinweis und Umschau;
  - 18 getippte Sätze je Sprache gegen `match_group`;
  - die Leiste.
- Preflight-Tests für Krise und Auslöser-Satz.
- Prüfung der Führung ohne Befund, ihre eigenen Tests grün.
- **Im Browser nicht geprüft.**

## Deploy

- Image neu bauen. Keine Migration.
- `import-config --werksabgleich`. Die Werksfassung der Führung ändert sich; die eigene Fassung auf
  Staging bleibt, bis die Redaktion umschaltet.

## Nachtrag: CI-Kippler in der Entscheidungsfrage

Der E2E-Test „per Tastatur: Pfeiltaste wählt, Enter antwortet“ scheiterte im PR-Lauf, im Push-Lauf
desselben Commits nicht. Mit der Führung hat das nichts zu tun.

- **Ursache:** Enter auf einer Option löst die implizite Absendung des Browsers aus, und die hängt
  am Knopf „Antworten“ im DOM. Den gibt Angular (OnPush) erst beim nächsten Rendern frei. Im CI kam
  Enter 3 ms nach der Wahl, also davor, und der Browser verwarf die Absendung still.
- **Behebung:** `ui-entscheidung` schickt bei Enter auf einer Option selbst ab, sobald die Wahl im
  Zustand steht (`tasteInOption`). Die implizite Absendung ist dabei unterdrückt, damit nichts
  zweimal ankommt. Ohne Wahl oder während eines Zugs schickt Enter weiterhin nichts.
- **Geprüft:**
  - zwei neue Specs: „vor dem Neuzeichnen“ und „ohne Wahl“;
  - `ui-module`: 390 grün, ESLint sauber;
  - die E2E-Datei 15-mal gegen das gebaute Widget: 150 von 150 grün.
