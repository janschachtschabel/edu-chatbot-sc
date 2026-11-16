# Webseitenführung als Ablauf (2026-11-15)

Anlass: Rückmeldung des Nutzers vom 15.11.: „Die Führung in der neuen Ablauf-Version entspricht
nicht der originalen Führung und funktioniert auch nicht richtig – falsche Sprünge.“ Gemeint ist
die Webseitenführung. Die Ablauf-Fassung („Kurze Führung durch WLO“, `06-ablaeufe/fuehrung.yaml`)
soll der eingebauten Führung (`01-base/website-tour.yaml`, `domain/tour.py`,
`graph/nodes/tour.py`) entsprechen, damit die eingebaute irgendwann abgeschaltet werden kann.

## Ausgangslage (Analyse 15.11.)

**Original:** Funnel `intro → group → group_page → content → solutions → contact`.

- **Einstieg:** Er hängt an der aktuellen Seite (`detect_entry`):
  - Startseite → Gruppenwahl;
  - Zielgruppen- oder Angebotsseite → Lösungen;
  - `/mitmachen` → Kontakt;
  - sonst Intro.
- **Gruppenwahl:** 11 Gruppen plus „Bin mir nicht sicher“, getippt auch über Synonyme (Teilstring).
  - Erster Fehlversuch → Hilfetext und die Chips noch einmal.
  - Zweiter Fehlversuch → die Führung endet still, die Nachricht geht an den Chat.
- **Ankunft:** wird per exaktem Pfad erkannt. Auf einer anderen Seite kommt ein Hinweis („Nudge“) mit
  demselben Weiter-Chip; auf Angebots- und Unterseiten in der Lösungen-Phase ein Umschau-Text
  („Explore“).
- **Widget:** öffnet sich während der Führung auf jeder Seite von selbst (`boerdi_tour_active`).

**Ablauf-Fassung heute:** ein Beispiel mit drei Stationen (Plan AS-7c, F-8), ohne Gruppen, Angebote
und Einstiege. Was dort und in der Ablauf-Sprache fehlt:

| | Lücke | Wirkung |
|---|---|---|
| L1 | Das Widget öffnet sich nicht von selbst, wenn ein Lauf auf einen Seitenwechsel wartet | Die Ankunft wird erst gemeldet, wenn die Person das Widget öffnet — die Führung „hängt“ |
| L2 | Kein Hinweis auf falscher Seite, kein Umschau-Text | Die Führung schweigt auf jeder anderen Seite |
| L3 | Höchstens 8 Optionen je Schritt | 12 Gruppen-Chips passen nicht |
| L4 | Keine Synonyme an Optionen; getippter Text wählt nur bei exakt gleicher Beschriftung | „ich bin Lehrerin“ trifft keine Gruppe |
| L5 | Kein Fehlversuch, getippter Text wird am Freitext-Schritt immer geschluckt | Kein Ausweg in den freien Chat |
| L6 | Platzhalter der Wahl nur deutsch; ein `seite`-Schritt hat eine feste URL | Je Gruppe eine eigene Schrittkette nötig |
| L7 | Der Zähler „Schritt x von y“ zählt Verzweigungen mit | Sprünge in der Anzeige (Dokument-Ablauf: 2 von 8 → 4 von 11) |
| L8 | Am Ende stehen „Neues Vorhaben“ und „Arbeitsstand löschen“ | Unpassend für eine Führung |

## Entscheide (selbst getroffen, 15.11.)

- **E1:** Die Lücken schließt die Ablauf-Sprache, nicht eine Fassung mit 40 Schritten und 178
  Regeln (die geht heute schon, ist aber nicht pflegbar). Jede Erweiterung ist optional und
  ändert vorhandene Abläufe nicht.
- **E2:** Pfade relativ (wie heute), kein `base_host`. Die Führung gilt dort, wo das Widget auf
  den WLO-Seiten selbst eingebettet ist; ein relativer Pfad öffnet die Seite auf demselben Host.
  Test- und Produktivhost müssen nicht umgeschaltet werden.
- **E3:** Die Eigenheiten des Originals werden übernommen, wo sie Absicht sind (Reihenfolge der
  Gruppen beim Treffer, zwei Fehlversuche); dass „Lehrerin an einer Grundschule“ wegen „schule“
  bei Content-Abnehmer landet, ist keine Absicht — die Gruppen Lehrkraft, Lernende und Eltern
  stehen in der Ablauf-Fassung vor Content-Abnehmer.
- **E4:** Die eingebaute Führung bleibt, bis die Redaktion die Ablauf-Fassung im Studio
  einschaltet und die eingebaute abschaltet (`website_tour.enabled: false`). Der Umstieg ist ein
  Eintrag im Studio, kein Deploy.
- **E5:** L7 (Zähler) gilt für alle Abläufe: Verzweigungen zählen nicht mehr als Schritt.

## Pakete

- **WF-1 (L7, L8):** Zähler ohne Verzweigungen; am Ende eines Ablaufs, der nichts schreibt und
  keinen Vorgang braucht, keine Vorgangs-Chips.
- **WF-2 (L3, L4, L5):**
  - bis 12 Optionen;
  - `synonyme` an Optionen (Teilstring ohne Groß/Klein, mindestens 3 Zeichen, erste passende
    Option gewinnt);
  - am Freitext-Schritt `nur_bei_treffer` mit `fehlversuche` (Hilfetext, danach Ausstieg und
    die Nachricht an den Chat).
- **WF-3 (L6):** Platzhalter `{wahl.<teil>}` mit der Beschriftung in der Sprache des Zugs.
- **WF-4 (L2):** an `seite` die optionalen Felder `abweichung` (Hinweis auf einer anderen
  Seite) und `umsehen` (Muster und Text): Text plus derselbe Chip, ohne den Lauf
  weiterzuschieben.
- **WF-5 (L1):** Wartet ein Lauf auf eine Seite, öffnet sich das Widget nach dem Seitenwechsel
  von selbst (Merker wie `boerdi_tour_active`) und meldet die Ankunft.
- **WF-6:** `fuehrung.yaml` als Nachbau mit allen Gruppen, Angeboten, Einstiegen und Texten
  (de/en), Selbsttests nach den Fällen des Originals. Umstieg in der Betriebsdoku.

Nach jedem Paket ein unabhängiges Review mit Behebung.

## Feinentscheide (15.11.)

- **WF-1, Zähler:**
  - Verzweigungen zählen nicht.
  - Der längste Weg ab einem Schritt läuft nicht über Schritte, von denen aus man diesen
    Schritt erreicht (Rückwege). „Nochmal wählen“ verlängert die Gesamtzahl so nicht mehr; der
    Docstring versprach das schon, die Suche schloss aber nur die Schritte ab hier aus.
- **WF-1, Vorgangs-Chips:** Am Ende nur, wenn der Ablauf einen Arbeitsstand erzeugt — einen
  Schritt vom Typ `modul`, `werkzeug`, `agent`, `auftrag` oder `freigabe`.
- **WF-2, Optionen:** Höchstens 12 Optionen.
- **WF-2, Synonyme:** `synonyme` an einer Option.
  - Nur Optionen mit Synonymen treffen auch per Teilwort: Beschriftung oder Synonym im
    getippten Text, ohne Groß/Klein, ab 3 Zeichen.
  - Zuerst gilt der genaue Treffer einer Beschriftung, dann die erste passende Option in der
    Reihenfolge.
  - Bestehende Abläufe ohne Synonyme ändern sich nicht.
- **WF-2, Fehlversuch:** `kein_treffer: {de, en}` an einem Wahl-Schritt ohne `freitext`.
  - Ein getippter Text ohne Treffer bekommt einmal je Besuch des Schritts diesen Hinweis mit
    denselben Chips.
  - Danach geht getippter Text wie heute an die KI, und der Lauf wartet weiter.
  - Abweichung vom Original, bewusst: Das Original beendet die Führung beim zweiten
    Fehlversuch still. Hier kann die Person sie jederzeit abbrechen; nichts verschwindet
    ungefragt.
- **WF-3, Platzhalter:** `{wahl.<teil>}` zeigt die Beschriftung der gewählten Option in der
  Sprache des Zugs. Der Teil speichert weiter das deutsche Label; die Option wird darüber
  gefunden.
- **WF-3, kein `url_je_wahl` (Entscheid beim Bau):** Mit 12 Optionen und Synonymen braucht die
  Führung je Zielgruppenseite einen eigenen `seite`-Schritt hinter einer Verzweigung, insgesamt
  rund 30 Schritte (Grenze 40).
  - `url_je_wahl` hätte URL und Ankunft an vier Stellen veränderlich gemacht (Treiber,
    Ankunft, Chip unter späteren Antworten, Leiste).
  - Die beiden letzten lesen nur den Verweis der Sitzung, dessen Felder auf 40 Zeichen gekürzt
    werden.
  - Aufwand und Fehlerrisiko stehen in keinem Verhältnis zu den gesparten Schritten.
- **WF-1 nach dem Review:**
  - **Rückwege** werden über alle Kanten gesucht, auch `bei_fehler`.
  - **Arbeitsstand:** Getippter Text (`freitext`) und Startdaten zählen als Arbeitsstand (die
    Person muss ihn löschen können); eine Wahl zählt nicht. Nach „Abbrechen“ gilt dieselbe
    Regel für die Chips.
  - **Bekannte Grenze des Zählers:** Bietet ein Schritt, den man auch überspringen kann, einen
    Rückweg auf einen früheren Schritt an, kann `n` den Umweg mitzählen. Kein Seed ist
    betroffen.
  - **Vorgang einer Führung:** Eine Führung legt weiter einen Vorgang an (wie jeder Ablauf). Er
    bleibt nach dem Ende aktiv, bis ein Ablauf mit Arbeitsstand oder „Neues Vorhaben“ ihn
    ablöst, und verfällt mit der Aufbewahrung.
- **WF-6, Angebote je Gruppe:** Sie stehen im Text eines eigenen Lösungen-Schritts je Gruppe,
  hinter einer Verzweigung über den Teil.

## Zweites Review der ganzen Lieferung (2026-11-16)

- **M1:** Die Führung endete nie von selbst. Neu `endet_bei_text` am Ablauf
  (`wahl_zug.still_beenden`, aufgerufen im Preflight), in der Führung an. Damit entfällt die
  Abweichung „kein stilles Ende beim zweiten Fehlversuch“ (Feinentscheid WF-2): Mit dem Schalter
  endet der Lauf wie im Original.
- **m1:** Beim Einstieg mitten drin zählt die Leiste den längsten Weg. Beschrieben, nicht
  geändert: Das Original hatte keinen Zähler.
- **m2, m3, n3:** Deploy- und Umstiegs-Text berichtigt (wartende Läufe der geänderten Seeds,
  zuerst die Werksfassung übernehmen, Grenzen der relativen Pfade und des Merkers).
- **m4:** Kürzerer Text am Weg zur Anfrage.
- **n1:** `umsehen: /home/*` trifft auch fremde Gruppenseiten. Hingenommen, weil der Text dort
  nicht falsch ist.
- **n2:** Synonym „oer“ gestrichen.
- **n4:** Kommentar zu Enter berichtigt.

