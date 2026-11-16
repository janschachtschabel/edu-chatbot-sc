# Webseitenführung als Ablauf (2026-11-16)

Anlass: Rückmeldung vom 15.11.: Die Führung als Ablauf („Kurze Führung durch WLO“) entsprach
nicht der eingebauten Webseitenführung und sprang falsch. Plan
`docs/plans/2026-11-15-webseitenfuehrung-als-ablauf.md` (WF-1 bis WF-6).

## Was sich ändert

### Für alle Abläufe

- **Zähler „Schritt n von m“ (WF-1):** Verzweigungen zählen nicht mehr, und ein Rückweg
  („Nochmal wählen“) verlängert die Gesamtzahl nicht. Im Dokument-Ablauf zeigte die Leiste
  vorher „Schritt 2 von 8“, dann „Schritt 4 von 11“; jetzt 2 von 6, nach dem Fehlversuch 3 von 3,
  nach „Nochmal wählen“ wieder 2 von 6.
- **Chips am Ende (WF-1):** „Neues Vorhaben“ und „Arbeitsstand löschen“ stehen nur noch nach
  einem Ablauf mit Arbeitsstand: ein Schritt vom Typ Modul, Werkzeug, KI oder Auftrag, getippter
  Text oder Startdaten. Gilt auch nach „Abbrechen“.
- **Wahl-Schritte (WF-2):**
  - Bis zu 12 Schnellantworten statt 8.
  - Neu `synonyme` an einer Schnellantwort: getippter Text trifft auch mitten im Satz (ohne
    Groß/Klein, ab 3 Zeichen). Zuerst gilt ein genauer Treffer, dann die erste passende Antwort
    von oben. Antworten ohne Synonyme treffen wie bisher nur genau.
  - Neu `kein_treffer` am Schritt: Trifft getippter Text nichts, erscheint der Hinweis einmal je
    Besuch des Schritts mit denselben Chips. Danach geht Text wie bisher an die KI, der Ablauf
    wartet weiter.
- **Platzhalter `{wahl.<teil>}` (WF-3):** die Beschriftung der gewählten Antwort in der Sprache
  der Person. `{teil.<teil>}` zeigte immer das deutsche Label.
- **Seiten-Schritte (WF-4):**
  - Neu `abweichung`: Hinweis, wenn die Person auf einer anderen Seite landet, während der
    Schritt wartet.
  - Neu `umsehen` (Seiten und Text): Auf diesen Seiten erscheint statt des Hinweises ein
    Umschau-Text.
  - Beide jeweils mit demselben Chip; der Lauf wartet weiter. Die Hinweise werden nicht
    gespeichert, wie bei der eingebauten Tour.
- **Ablauf endet bei eigenem Text (zweites Review):** Neu `endet_bei_text` am Ablauf. Tippt die
  Person an einer Frage oder auf dem Weg zu einer Seite etwas, das der Ablauf nicht nimmt, endet
  er still, und der Chat antwortet. An einer Frage mit `kein_treffer` greift das erst beim
  zweiten Fehlversuch. So endet auch die eingebaute Tour; sonst stünden die Gruppen-Chips unter
  jeder Antwort, bis jemand „Abbrechen“ findet.
- **Widget (WF-5):** Wartet ein Ablauf auf einen Seitenwechsel, öffnet sich das Widget auf der
  neuen Seite von selbst und meldet die Ankunft. Vorher blieb es zu, und die Führung „hing“, bis
  die Person es öffnete.
  - Merker `boerdi_ablauf_seite` im `localStorage`, wie `boerdi_tour_active` der Tour.
  - Er fällt, sobald kein Lauf mehr wartet, bei einem neuen Gespräch und bei einem leeren
    Verlauf.
  - Wer das Widget während der Führung zuklappt, sieht es auf der nächsten Seite wieder offen,
    wie bei der Tour — solange ein Seiten-Schritt wartet. An der Gruppenwahl fällt der Merker;
    das Original öffnete sich in jedem Schritt.

### Die Führung selbst (WF-6)

`06-ablaeufe/fuehrung.yaml` ist jetzt ein Nachbau der eingebauten Web-Tour, erzeugt aus
`01-base/website-tour.yaml`: dieselben Texte (de/en), elf Gruppen mit Synonymen, „Bin mir nicht
sicher“, Zielgruppenseiten, Zwischenstopp Bildungsinhalte, Angebote je Gruppe, Hinweis auf einer
anderen Seite, Umschau-Text auf Angebotsseiten, Mitmach-Seite. Sie steigt wie das Original mitten
ein:
- auf der Startseite bei der Gruppenwahl;
- auf einer Zielgruppen- oder Angebotsseite bei den Lösungen;
- auf `/mitmachen` beim Kontakt.

33 Schritte, Prüfung ohne Befund, Selbsttests in der Datei. Bewusste Abweichungen stehen im Kopf
der Datei:
- relative Pfade statt `base_host` (sie gelten auf dem Host, auf dem das Widget läuft — in einer
  Einbettung außerhalb der WLO-Seiten, etwa in edu-sharing, führen sie ins Leere);
- die Reihenfolge der Gruppen beim Treffer, und das Synonym „oer“ fehlt (es steckt in „Boerdi“);
- das Widget öffnet sich von selbst, solange ein Seiten-Schritt wartet (das Original in jedem
  Schritt);
- beim Einstieg mitten drin der volle Lösungen-Text; die Leiste zählt dann den längsten Weg
  (etwa „Schritt 6 von 6“ gleich am Weg zur Anfrage) — das Original hatte keinen Zähler.

## Umstieg (Redaktion, im Studio, ohne Deploy)

1. Abläufe → „Führung durch WLO“: Wurde die alte „Kurze Führung“ im Studio schon bearbeitet oder
   eingeschaltet, gilt sie als eigene Fassung, und der Werksabgleich lässt sie stehen. Dann zuerst
   die Werksfassung übernehmen. Danach einschalten (`aktiv`).
2. Betrieb → Webseiten-Tour ausschalten (`website_tour.enabled: false`).
3. Der Start-Chip „Web-Tour starten“ und die getippten Auslöser starten dann die Führung. Bei
   abgeschalteter Tour fällt der Zug zur Ablauf-Erkennung durch. Das ist aus dem Code abgeleitet
   und **nicht live geprüft**: nach dem Umstieg einmal im Browser starten.

Ändert die Redaktion Texte der eingebauten Tour, gilt die Führung weiter in ihrer eigenen Fassung.

## Geprüft

- Reviews je Paket (WF-1 bis WF-5), dazu ein zweites Review der ganzen Lieferung samt Führung
  (1 MAJOR, 4 MINOR, 4 NIT): alles behoben oder als Abweichung beschrieben. Einzelheiten im
  Plan.
- Backend: alle Tests zu Abläufen, Seeds, Studio-Schema, Vorgängen und Zusammenstellung grün.
- Frontend: `ui` (1 513), `ui-module` (387), `studio` (2 156) grün, ESLint sauber.
- Die Führung im Browser: nicht geprüft.

## Deploy

- Image neu bauen. Keine Migration.
- `import-config --werksabgleich` (neue Fassung der Führung und der anderen Abläufe). Die
  Führung bleibt aus, bis die Redaktion sie einschaltet.
- Die neuen Felder haben die Vorgabe `None`; an sich ändert das keine Fassung. Der Werksabgleich
  ändert aber die Schritte der vier Abläufe mit dem neuen Chip-Text und der Führung — ein Lauf
  dieser Abläufe, der gerade wartet, wird beim nächsten Zug abgebrochen (die Person startet neu).
  Läufe anderer Abläufe bleiben.
