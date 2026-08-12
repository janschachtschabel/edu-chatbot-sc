# Material 3 + edu-sharing-Optik für die Webkomponente

**Stand 2026-07-31.** Nutzer-Vorgabe: die Optik der Webkomponente soll näher an
edu-sharing rücken und **Angular-Material-3-Elemente** nutzen; das Größenlimit
darf dafür steigen.

## Was diese Entscheidung umkehrt

`projects/ui/src/theme/tokens.scss` trägt im Kopf die Gegenentscheidung:

> „CSS custom properties only — **no Angular Material component library** (it
> would blow the widget's §5.5 gzip budget)."

Das war also bewusst so, nicht vergessen. Der Nutzer überstimmt es. **§5.5 der
Spec muss nachgezogen werden**, sonst widersprechen sich Spec und Code — das ist
eine offene Aufgabe, keine Nebensache.

## Gemessene Ausgangslage (nicht geschätzt)

| | vorher | nachher (Theme + 1 Button-Modul) | Differenz |
|---|---|---|---|
| `main.js` roh | 416,57 kB | **480,91 kB** | +64,3 kB |
| übertragen | 110,45 kB | **121,35 kB** | +10,9 kB |

Ich hatte vorab 80–200 kB geschätzt — **die Schätzung war zu pessimistisch**,
der gemessene Wert ist deutlich niedriger. Budget entsprechend von
418/420 kB auf **550/600 kB** gesetzt: Luft für weitere Komponenten, aber immer
noch ein Gate, das bei Wildwuchs anschlägt.

## Zwei technische Festlegungen

**1. Das Theme hängt an `:host`, nicht an `:root`.**
Das Widget läuft als Custom Element in fremden Seiten und liefert **kein**
globales Stylesheet aus (`"styles": []` in `build-widget`). Ein `:root`-Theme
würde die Gastseite mit-umstylen. An `:host` bleiben alle `--mat-sys-*`-Token
im Widget. Ausgegeben wird das Theme an **genau einer** Stelle
(`widget.component.scss`) — stünde es in `theme/tokens.scss`, gäben es alle
einbindenden Komponenten mehrfach aus.

**2. Keine Google-Schrift.** `mat.theme` bekommt die selbst gehostete
System-Schrift als `plain-family`. Der DSGVO-Guardrail (keine externen
Font-CDNs) bleibt unangetastet — `check:tokens` läuft weiter sauber.

## Gebaut (Scheibe 1)

* `@angular/material` + `@angular/cdk` **21.2.14**, beide **MIT** — Lizenz-Gate
  erfüllt.
* M3-Theme an `:host` des Widget-Roots, Palette vorläufig `mat.$azure-palette`.
* Der von dir bemängelte Knopf „Inhalt anzeigen" ist jetzt ein
  `matButton="tonal"` **in** der Karte statt einer eigenen umrandeten Leiste
  darunter.

Verifikation: `npx ng test ui` → **461 passed** · `npm run lint` → sauber ·
`npm run check:tokens` → „Jedes gelesene Token ist definiert" ·
`npm run build:widget` → 480,91 kB, Budget-Gate grün.

## Die Vorlage (Screenshots 2026-07-31)

Vier Bilder: WLO-Kacheln, vhb-Kacheln, vhb-Sammlungen, vhb-Gesamtseite. Beides
edu-sharing; **vhb ist näher am edu-sharing-Look** (Nutzer).

**Was aus einem Screenshot verlässlich ablesbar ist, ist der AUFBAU — nicht der
exakte Farbwert.** Deshalb unten Struktur als Festlegung, Farben nur als
Näherung, die gegen die echten edu-sharing-Werte zu tauschen ist.

### Aufbau, den beide Vorlagen teilen (≠ unsere heutige Kachel)

| | Vorlage | heute bei uns |
|---|---|---|
| Vorschaubild | **formatfüllend oben**, volle Kachelbreite | 92 × 72 px **neben** dem Text |
| Quelle | eigene Zeile über dem Titel („Geogebra", „Youtube") | fehlt |
| Titel | 2 Zeilen, gekürzt | 2 Zeilen ✓ |
| Beschreibung | 2 Zeilen, gekürzt | 3 Zeilen |
| Metadaten | **Zeilen** mit kleinem Symbol: Materialart / Fach / Stufe | Typ oben im Kopf, Fach+Stufe unten im Fuß |
| Rahmen | **keiner**, nur weicher Schatten | 1 px Rahmen + Schatten |
| Lizenz | Siegel-Symbol | Badge auf dem Bild ✓ |

**Unsere Daten passen exakt auf die WLO-Kachel:** `publisher` → Quellzeile,
`learning_resource_types` → Materialart, `disciplines` → Fach,
`educational_contexts` → Stufe, `preview_url` → Medium, `license` → Siegel.
Deshalb: **WLO-Aufbau, vhb-Anmutung** (randlos, weicher Schatten, ruhigere
Typografie). Das ist eine Entscheidung von mir — der Nutzer nannte vhb als
näher dran, aber die vhb-Kachel führt Schlüssel-Wert-Zeilen („zuletzt geändert",
„Herkunft"), die unsere Karte nicht hat.

### Weiteres aus der Gesamtseite (Bild 4)

* Filterfeld-Optik = **Angular Material `appearance="outline"`** mit
  schwebendem Label — das ist der greifbarste M3-Beleg in der Vorlage.
* Dunkle Kopfleiste, Suchfeld mit Filter-Symbol links und dunklem Suchknopf.
* Abschnittsüberschriften mit Trefferzahl („Materialien (2211)").

## Gebaut (Scheibe 2): die Kachel auf den Vorlagen-Aufbau

`wlo-card-tile.component.{ts,scss}` umgebaut — Medium formatfüllend oben
(16:9), darunter Quelle → Titel → Beschreibung → Metazeilen. Dazu:

* **Der Schatten sitzt jetzt am Wrapper, nicht an der Karte.** Die Sammlungs-
  Aktionsleiste wird als Geschwister der Karte in den Wrapper projiziert; auf
  der Karte hätte der Schatten eine sichtbare Naht quer über die angesetzte
  Leiste gezogen. `.card-actions` ist entsprechend randlos geworden.
  **Kein `overflow: hidden` am Wrapper** — das Themenseiten-Aufklappmenü
  (`.tp-dropdown`) liegt in der Leiste und würde abgeschnitten.
* **Der Medienbereich steht immer**, auch ohne `preview_url`. Das ersetzt den
  bisherigen `min-height`-Behelf an `.card-body-row`; ohne ihn wäre eine
  bildlose Kachel ~20 px flacher als ihre Nachbarn.
* **Der Platzhalter ist ein neutrales Bildsymbol, nicht das Typ-Symbol.** Erste
  Fassung nahm das Typ-Symbol — damit stand der Inhaltstyp groß im Medienfeld
  UND klein in der Metazeile: exakt die Doppelung, die der Nutzer beim Knopf
  bemängelt hatte. Ein Test vergleicht jetzt die **gerenderten** Symbole (gegen
  `ICONS.*` verglichen wäre er auch bei gleicher Optik grün).
* `publisher` wird zum ersten Mal überhaupt angezeigt — das Feld stand im
  Vertrag und im Backend (`cards/build.py:172`), hatte aber keinen Konsumenten.
  Es kann leer sein (Default `""`), die Zeile entfällt dann.

### Messung (Playwright, echte Layout-Engine, kompiliertes SCSS)

| Bühne | Kachelhöhe | Bild | Titel | Meta-Oberkante |
|---|---|---|---|---|
| 720 px (2 Spalten) | **405** einheitlich | **199 × 354** einheitlich | **36** einheitlich | **295** einheitlich |
| 340 px (1 Spalte) | 397 / 362 / 365 | 191 × 340 einheitlich | 36 einheitlich | 287 / 252 / 255 |

Vier bewusst ungleiche Datensätze (lang/kurz, mit/ohne Bild, mit/ohne Quelle).
**Nebeneinander ist alles gleich** — das war die Nutzer-Vorgabe. Einspaltig
unterscheiden sich die Höhen um bis zu 35 px, weil jede Kachel eine eigene
Rasterzeile ist und `flex: 1` nichts zum Strecken hat; der Unterschied kommt
allein aus der Beschreibung (0/1/2 Zeilen). Das ist **bewusst nicht** durch
reservierte Leerzeilen geglättet: untereinander fällt ungleiche Höhe nicht auf,
tote Fläche unter jeder beschreibungslosen Kachel dagegen schon.

320 px: `scrollWidth == innerWidth` → kein waagerechtes Scrollen (WCAG 1.4.10).

Verifikation: `npx ng test ui` → **461 passed** · `npm run lint` → sauber ·
`npm run build:widget` → **480,81 kB** (Budget 550/600 kB grün).

## Gebaut (Scheibe 3): Palette aus der ALT-Markenfarbe

Nutzer-Entscheid: **die Farbwerte des alten Chatbots nehmen**, nicht aus den
Screenshots schätzen. Erhoben statt geraten: ALT hat **genau eine**
Markenfarbe — `#1c4587`, der Fallback von `--boerdi-primary`, 71 Fundstellen im
ALT-Frontend; alles Übrige ist Slate-Grau (`#1e293b`, `#e2e8f0`, `#f1f5f9`,
`#475569`, `#cbd5e1`, `#f8fafc`, `#94a3b8`).

Daraus die M3-Tonwertpaletten erzeugt (`ng generate
@angular/material:theme-color`, Ergebnis in `projects/ui/src/theme/_m3-palette.scss`).
**Ton 30 der Primärpalette ist exakt `#1c4587`** — Karte und
Material-Komponenten stammen jetzt aus derselben Farbe. `mat.$azure-palette`
ist raus.

Stolperstein fürs nächste Mal: `--directory` hängt der Schematic den Pfad als
**Namenspräfix** an, statt einen Ordner zu benutzen — die Datei landet im
Projektstamm und muss verschoben werden.

### Gemessene Systemfarben (kompiliertes Theme, nicht geschätzt)

| Token | hell | dunkel |
|---|---|---|
| `primary` | `#385da0` | `#adc6ff` |
| `primary-container` | `#d8e2ff` | **`#1c4587`** |
| `secondary-container` (tonaler Knopf) | `#d8e2ff` | `#3a4761` |
| `surface` | `#f9f9ff` | `#121318` |

Kontraste (WCAG SC 1.4.3, ≥ 4,5:1) in **beiden** Modi: on-primary/primary
6,48 / 7,71 · on-primary-container/primary-container 7,22 / 7,22 ·
on-secondary-container/secondary-container 7,21 / 7,21 · on-surface/surface
16,39 / 14,38. Alle bestanden.

Verifikation: `ng test ui` **461** · `ng test widget` **30** · `lint` sauber ·
`check:tokens` sauber · `build:widget` **480,81 kB** — der Palettenwechsel
kostet **kein** Byte.

### Zwei Befunde, die dabei aufgefallen sind (nicht gefixt, bewusst)

**B1 — `primary-color` des Embedders greift bei M3-Komponenten nicht.**
→ **GELÖST**, siehe Scheibe 4.

**B2 — das Theme ist dunkelmodus-fähig, unsere Karte nicht.** `mat.theme` gibt
alle Token als `light-dark(hell, dunkel)` aus; die Kachel trägt dagegen die
`simplify:`-Notiz „kein Dark-Mode, ALT war hell-only".

Präziser als zuerst notiert — **gemessen statt behauptet**: der Auslöser ist
nicht `prefers-color-scheme`, sondern die **vererbte** CSS-Eigenschaft
`color-scheme`. Setzt die Gastseite `color-scheme: dark`, erbt das Widget das
und die Token kippen (Knopffläche `#d8e2ff` → `#3a4761`, gemessen). Bei bloßer
Systemvorliebe ohne gesetztes `color-scheme` passiert nichts — das Bundle gibt
selbst nirgends `color-scheme` aus. Heute betrifft es einen Knopf, wächst aber
mit jeder weiteren M3-Komponente.

## Gebaut (Scheibe 4): Token-Brücke zur Kundenfarbe (löst B1)

Der Umfang war kleiner als befürchtet: eine Zählung im **gebauten** Bundle
zeigt, dass der tonale Knopf genau **zwei** Farbtoken liest —
`--mat-sys-secondary-container` (Fläche) und `--mat-sys-on-secondary-container`
(Text, Ripple, State-Layer). Damit braucht es keine HCT-Mathematik zur
Laufzeit: die betroffenen Token werden in `widget.component.scss` per
`color-mix` aus `--boerdi-primary` abgeleitet — **dasselbe Muster, das
`.card-btn`, `.btn-load-more` und `.tp-toggle` schon benutzen.**

`light-dark()` bleibt dabei erhalten (siehe B2 — ein einwertiger Override hätte
den geerbten Dunkelmodus stillschweigend abgeschaltet). Überschrieben wird nur,
was Markenfarbe *trägt*; Flächen, Umrisse und Elevation bleiben neutral.
`on-primary` bleibt bewusst der gebackene Wert — es gehört zur gefüllten
Knopfvariante, die wir nirgends rendern, und ein pauschales Weiß wäre bei einer
hellen Kundenfarbe ein Kontrastbruch.

**Preis, offen genannt:** für den Normalfall ohne `primary-color` ersetzt die
Formel Materials eigene HCT-Tonwerte. Die Fläche wird dadurch minimal anders
(`#d8e2ff` → ca. `rgb(223, 229, 238)`). Dafür stammen Karte, handgeschriebene
Knöpfe und Material-Knöpfe aus **einer** Quelle statt aus zweien.

### Drei E2E-Tests statt einer Behauptung (`e2e/embed.spec.ts`)

Der richtige Ort, weil nur ein echter Browser `color-mix`/`light-dark` auflöst:

1. **ohne** `primary-color` — der ausgelieferte Normalfall: Fläche bleibt blau
   (B > R), Kontrast ≥ 4,5:1;
2. **mit** `primary-color="#7a1f5c"` — eine Farbe mit umgekehrtem Verhältnis
   (R > B), sodass ein Rest-Blau den Test kippen würde;
3. **mit** `color-scheme: dark` auf der Gastseite — Fläche ändert sich, bleibt
   aus der Kundenfarbe abgeleitet, Kontrast hält.

Alle drei liefen erst **rot** (Fläche blau, R=58 < B=97), dann grün.

### Nebenbefund: ein Bestandstest war seit M17 rot

`chat.spec.ts` „flaches Karten-Grid" erwartete **eine** `.card-actions`-Leiste
mit dem Kommentar „nur Sammlungen tragen die Aktionsleiste". Seit dem
M17-Knopf tragen **auch Einzelinhalte** eine — der M17-Frontend-Slice wurde
ohne E2E-Lauf abgeschlossen, der Test war seitdem rot, ohne dass es auffiel.
Erwartung nachgezogen (2 Leisten, Radius 12 px statt der alten 10 px) und eine
dritte Karte **ohne** `node_id` ergänzt, damit die Rundungsprüfung ihren
Gegenpol ohne Leiste behält.

Verifikation: `npx playwright test` → **31 passed** · `ng test ui` **461** ·
`ng test widget` **30** · `lint` · `check:tokens` · `build:widget`
**481,28 kB** (+0,47 kB gegenüber Scheibe 3, Budget 550/600 kB grün).

**Tertiary** ist die algorithmische Ergänzungsfarbe (`#804a8a`, violett) und
**wird derzeit von nichts benutzt** — sie würde erst sichtbar, wenn eine
Komponente Tertiary-Token zieht.

## Gebaut (Scheibe 5): die Aktionsleisten auf Material

**Geschlossen umgestellt, nicht halb.** Eine Leiste aus Material-Pille neben
handgezeichnetem Rechteck wäre schlechter als die alte — genau die
Inkonsistenz, die der Nutzer am Volltext-Knopf bemängelt hatte.

| Element | vorher | jetzt |
|---|---|---|
| Inhalte / Lernpfad | `.card-btn--primary/--secondary` | `matButton="outlined"` |
| Themenseite (`<a>`) | `.card-btn--tertiary` | `<a matButton="outlined">` |
| Varianten-Umschalter | `.tp-toggle` (Handarbeit) | `matIconButton` |
| Volltext in der Gruppen-Box | `.result-group__item-btn` (Handarbeit) | `matIconButton` |

**Der Split-Button ist aufgelöst.** ALT schweißte Themenseite + Umschalter
zusammen (linke Ecken rund, rechte eckig, 1 px Überlappung). Das ist kein
M3-Muster und ließe sich nur durch Übermalen von Materials Rundung nachbauen —
jetzt zwei eigenständige Knöpfe mit 2 px Abstand. Der Zusammenhang bleibt über
Nähe und das `aria-label` des Umschalters lesbar.

**Gesteuert wird über Komponenten-Token, nicht durch Überschreiben von
Materials Regeln** (`--mat-button-outlined-container-height: 30px` usw.).
Materials Vorgabe wären 40 px — zu wuchtig für eine Leiste in einer 260 px
breiten Kachel. So bleiben Ripple, Zustands-Overlay und Fokusring die von
Material gelieferten. Farbwerte stehen in diesen Dateien **gar keine** mehr:
sie kommen über `--mat-sys-primary` aus dem Theme und damit aus
`--boerdi-primary` (Scheibe 4).

### Zwei Funde beim Aufräumen

* `.card-btn--guide` und `--remix` waren **in keinem Template** — toter Stil aus
  dem ALT-Port (`--guide` ist ALTs „Bring mich hin"-Knopf, der in NEU noch
  nicht existiert). Mit dem `.card-btn`-Block entfernt; kommt er zurück, ist er
  ein `matButton="filled"`.
* Ein Bildschirmfoto gegen das **gebaute** Bundle zeigte, dass die Symbole am
  Text klebten: Materials `icon-spacing`-Token greift nur für `<mat-icon>`, wir
  liefern Inline-SVG (DSGVO: keine Icon-Font vom CDN). Eine eigene Regel für
  `.bb-icon` behebt es — im Code wäre das nicht aufgefallen.

Verifikation: `ng test ui` **463** · `ng test widget` **30** ·
`npx playwright test` **31** · `lint` · `check:tokens` · `build:widget`
**485,10 kB** (+3,8 kB für die outlined-/Icon-Knopf-Stile; Budget 550/600 grün).
Drei Bestandstests hingen an den entfernten Handklassen (`.card-btn`,
`.card-btn--tertiary`) — Selektoren nachgezogen, Zusicherungen unverändert.

## Gebaut (Scheibe 6): einheitliche Breite der Bot-Blasen

Nutzer-Beobachtung am Bildschirmfoto: die Blase mit den Ergebnis-Boxen war
schmaler als die Begrüßung darüber — **obwohl sie mehr trägt**. Nachgemessen:
**234 px gegen 290 px**.

Ursache: `.msg-bubble` hatte nur `max-width: 80%`, also schrumpfte jede Blase
auf ihren eigenen Inhalt. Die Begrüßung war breit, weil zwei Quick-Reply-Chips
nebeneinander passen; die Ergebnis-Boxen sind schmaler als das. Jetzt haben
Bot-Blasen `width: 80%` — die Kanten fluchten, und die Ergebnis-Boxen füllen
die Blase (der Volltext-Knopf sitzt dadurch rechts außen statt eingeklemmt).

**Nur Bot-Blasen.** Nutzer-Nachrichten sind kurz und rechtsbündig; eine
aufgeblasene „Ja."-Blase wäre dort leerer Raum ohne Gewinn.

**Preis, offen genannt:** eine kurze Bot-Antwort („Ja.") sitzt jetzt in einer
breiten, luftigen Blase. Im Bildschirmfoto geprüft — sie wirkt wie eine flache
Karte, nicht wie ein Fehler. Wenn das stört, wäre die Alternative, die feste
Breite nur für Blasen MIT Ergebnissen/Karten zu setzen; dann wären die Blasen
allerdings wieder ungleich, also genau das, was beanstandet wurde.

E2E-Zusicherung (`chat.spec.ts`): alle `.bot-bubble` eines Verlaufs haben
**eine** Breite. Lief erst rot mit der Meldung „ungleiche Blasenbreiten:
290,234".

Verifikation: `ng test ui` **463** · `ng test widget` **30** ·
`npx playwright test` **32** · `lint` · `check:tokens` · `build:widget`
**485,11 kB**.

## Gebaut (Scheibe 7): Chips auf Material — und `mat-form-field` verworfen

### Gemessen und ABGELEHNT: `mat-form-field` für die Eingabezeile

Der Plan nannte es „den größten sichtbaren Sprung, aber auch den teuersten
Posten". Gebaut, gemessen, zurückgebaut:

| | vorher | mit `mat-form-field` |
|---|---|---|
| `main.js` roh | 485,11 kB | **590,98 kB** (+105,9) |
| übertragen | 121,77 kB | **140,06 kB** (+18,3) |

Dazu die Budget-Warnung (550 kB um 41 kB gerissen). **+18 kB übertragen für ein
Feld, das bereits wie ein Outline-Feld aussieht** — das Verhältnis stimmt
nicht. Die Eingabezeile bleibt handgeschrieben; der Grund steht als Kommentar
im Template, damit es niemand ohne Messung erneut versucht.

Der Sende-Knopf bleibt aus einem zweiten Grund handgeschrieben: `matIconButton`
kennt in Material 21 **keine gefüllte Variante** (im Paket nachgesehen, nicht
vermutet) — er ist aber ein gefüllter Kreis.

### Gebaut: die Quick-Reply-Chips

`matButton="tonal"` für die Vorschläge, `matButton="filled"` für den
Lotsen-Chip. Das ist die ALT-Hierarchie in M3-Begriffen (getönt vs. voll
eingefärbt); `outlined` hätte die Tönung verloren.

**Bewusst kein `mat-chip-set`:** eine weitere Material-Komponentenfamilie liegt
in derselben Größenordnung wie `mat-form-field`, während `MatButtonModule`
bereits im Bundle ist. Das ist eine Analogie, keine eigene Messung — so
notiert, nicht als Messwert ausgegeben.

**Kostet netto nichts:** 485,11 → **484,90 kB**. Die entfallenden
handgeschriebenen Chip-Farben wiegen die Material-Nutzung auf.

### Zwei Fehler, die nur das Bild zeigte

* **Zentrierter Text bei langen Chips.** Material zentriert seine Beschriftung;
  ALT hatte `text-align: left`, weil mehrzeilige Vorschläge vorkommen. Im
  Bildschirmfoto als Rückschritt sichtbar, mit `justify-content: flex-start`
  behoben. Der lange Chip bricht korrekt um, statt überzulaufen — auch das ist
  gemessen, nicht angenommen.
* **Backticks im Template-Kommentar.** Das Template ist ein Template-Literal;
  meine Erklärung mit `tonal`/`filled` in Backticks hat es beendet — 24
  Compiler-Fehler. Der Code warnt an anderer Stelle genau davor.

Verifikation: `ng test ui` **464** · `ng test widget` **30** ·
`npx playwright test` **32** · `lint` · `check:tokens` · `build:widget`
**484,90 kB**.

## Gebaut (Scheibe 8): `mat-card` + Dunkelmodus (B2, teilweise)

### `mat-card` gemessen — und behalten

Anders als `mat-form-field`: **+5,75 kB roh / +0,73 kB übertragen.** Behalten,
weil es zugleich der Träger für B2 ist — `mat-card` holt seine Fläche aus
`--mat-sys-surface` und kippt damit von selbst mit.

### B2: Kachel, Blase und Pagination folgen jetzt dem Dunkelmodus

Farben in `wlo-card-tile`, `chat-shell` und der Pagination kommen aus
`--mat-sys-*`. Für den Kachel-Titel `on-primary-container` und nicht `primary`:
sein **Hellwert ist exakt ALTs #1c4587**, sein Dunkelwert das passende
Hell-Blau.

E2E (`embed.spec.ts`): Kachelfläche UND Blasenfläche ändern sich beim Kippen,
und in **beiden** Modi bleibt der Kontrast ≥ 4,5:1. Erst rot
(`rgb(255,255,255)` blieb weiß).

**Noch NICHT dunkelmodus-fähig** — ehrlich benannt, im Bild geprüft: der
Panel-Rahmen (`_widget-panel.scss`), die Fuß-/Eingabezeile
(`_chat-footer.scss`) und der Lade-/Fehlerzustand. Der Inhaltsbereich ist
konsistent, die Chrome drumherum noch hell.

### Befund: `theme/tokens.scss` ist im ausgelieferten Widget gar nicht aktiv

Die Datei definiert einen kompletten `--boerdi-*`-Satz **inklusive
Dunkelmodus** (`prefers-color-scheme`), wird aber nur von
`widget/src/styles.scss` eingebunden — und `build-widget` liefert
`"styles": []` aus. Im ausgelieferten Widget ist davon **nichts** aktiv, nur in
Studio und Dev-Seite. Zwei Folgen:

* Es gibt im Widget nur **ein** Farbsystem (`--mat-sys-*`) — deshalb konnte B2
  überhaupt sauber gelöst werden.
* `--boerdi-primary` ist dort auf `#1f6feb` gesetzt, nicht auf ALTs `#1c4587`.
  In Produktion greift der Fallback `#1c4587`, in der Dev-Vorschau nicht — eine
  **Dev/Prod-Abweichung in der Markenfarbe**. Nicht angefasst.

### Das Token-Gate war blind für Material — jetzt nicht mehr

`check:tokens` meldete alle 45 `--mat-sys-*`-Nutzungen als undefiniert: es
scannt Projektdateien nach `--name:`, und Materials Token entstehen erst beim
Kompilieren. Statt sie per Präfix durchzuwinken, **kompiliert das Skript jetzt
das Widget-Theme und sammelt die 169 tatsächlich erzeugten Token ein**.
Gegenprobe gefahren: ein eingebauter Tippfehler (`--mat-sys-surfase-container`)
wird weiterhin gemeldet.

Verifikation: `ng test ui` **464** · `npx playwright test` **33** · `lint` ·
`check:tokens` (169 aus mat.theme, 228 definiert, 45 gelesen) ·
`build:widget` **491,13 kB**.

**Eigener Fehler, repariert:** die PowerShell-Rundreise für die Gegenprobe hat
`card-list.component.scss` als ANSI zurückgeschrieben — alle Umlaute in den
Kommentaren wurden Mojibake. Datei neu geschrieben.

## Gebaut (Scheibe 9): B2 fertig — die Hülle folgt jetzt mit

Scheibe 8 endete mit einer ehrlich benannten Grenze: Inhaltsbereich konsistent,
Chrome drumherum hell. Diese Scheibe schließt sie.

### Die Bestandsaufnahme korrigierte den Zuschnitt

Statt aus dem Gedächtnis zu arbeiten, erst alle festen Hellwerte gesucht
(`#fff`/`white`/`rgba(0,0,0,…)` über `projects/**/*.scss`). Der Fund verschob
die Aufgabe: **die Boxen aus `_result-group.scss` sind die AUSGELIEFERTE
Standard-Darstellung von Ergebnissen** — das Kachelraster erscheint nur bei
`inline-result-grouping="false"`. Der B2-Test aus Scheibe 8 hatte genau dieses
Flag gesetzt und damit die Fläche geprüft, die Nutzer im Normalfall *nicht*
sehen. Panel und Fußzeile umzustellen und die Ergebnisboxen weiß zu lassen wäre
derselbe halbe Dunkelmodus gewesen, den Scheibe 8 gerade verhindern wollte —
deshalb in einer Scheibe: 10 Dateien, jeweils nur Farbwert → Token.

Die Umrechnung folgt einer Regel, nicht dem Gefühl:
`var(--boerdi-primary, #1c4587)` → `var(--mat-sys-primary)` (im Hellmodus per
Token-Brücke **derselbe Wert**, im Dunkelmodus aufgehellt), `white`/`#fff` als
Mischgrund → `var(--mat-sys-surface)`, Text/Rahmen → `on-surface` /
`on-surface-variant` / `outline-variant`. Der Aufnahme-Zustand am Mikrofon
(`#FEE2E2`/`#EF4444`/`#DC2626`) ging auf die Fehler-Rolle des Themes.

### Zweimal bewusst NICHT umgestellt

- **Die Kopfzeile** (`.boerdi-panel-header`) bleibt markenfarben. Weiß auf
  `#1c4587` trägt ~10:1 in beiden Modi; über `--mat-sys-primary` würde sie
  dunkel hell, und Eulenkopf, Aktions-Pillen, Outlines und vier Fokusringe
  (alle weiß) müssten mit. Das ist eine Gestaltungsfrage, kein Defekt.
- **Der FAB** behält seinen weißen Hof. Der Kommentar im Code erklärte warum:
  das Eulen-Logo ist ein Bild mit eigenen, festen Farben — auf dunkler Fläche
  verschwände das blaue Motiv. Der weiße Kreis *ist* hier der Kontrastträger.
  Beides im Code vermerkt, damit es nicht als vergessener Hellwert gelesen wird.

### Belegt statt behauptet

Neuer E2E-Test (`embed.spec.ts`), **ohne** `inline-result-grouping="false"` —
also gegen die Voreinstellung. Er misst Panel, Fußzeile, Eingabefeld und
Ergebnisbox, verlangt in allen vieren einen Wechsel und in beiden Modi ≥ 4,5:1
für Eingabe- und Box-Text. Erst rot gefahren: `Panel-Fläche kippt nicht —
"rgb(255, 255, 255)"`.

Dazu ein **Bildpaar hell/dunkel** gegen das gebaute Bundle (Wegwerf-Spec,
danach gelöscht). Das war nötig, weil in Scheibe 8 nicht die Tests, sondern der
Screenshot den halben Dunkelmodus zeigte. Beide Bilder sind stimmig; die
Nutzer-Blase steht dank `secondary-container` sichtbar von der Bot-Blase ab —
mit `color-mix(… 10%, surface)` wären beide im Dunkelmodus fast gleich gewesen.

Verifikation: `ng test ui` **464** · `npx playwright test` **34** · `lint` ·
`check:tokens` (169 aus mat.theme, 228 definiert, **52** gelesen) ·
`build:widget` **492,41 kB** (Budget 550/600, vorher 491,13 — +1,28 kB durch die
längeren Token-Namen).

## Gebaut (Scheibe 10): Studio — der geplante Punkt gemessen und verworfen

Der offene Posten lautete „Studio auf dieselbe Theme-Basis". Vor dem Umbau
gemessen, und die Messung widerlegt ihn:

| Messung | Wert |
| --- | --- |
| Material-Komponenten im Studio | **0** (`@angular/material`-Importe: 0, `<mat-*>`: 0) |
| `--st-*`-Nutzungen in Studio-SCSS | 1437 |
| Feste Hex-Werte AUSSERHALB der Token-Datei | **0** (die 2 Grep-Treffer waren Kommentare) |
| `rgba(0,0,0,…)` / `#fff` im Studio | **0** |
| Bundle | 297,50 kB von 900 kB |

`mat.theme()` einzuziehen brächte ohne eine einzige Material-Komponente nur 169
ungenutzte Token und Bundle-Zuwachs. Und 1437 `--st-*` auf `--mat-sys-*`
umzuschreiben würde das Studio **verschlechtern**: `--st-ok-text` /
`--st-warn-text` / `--st-danger-text` samt der `-dot`-Paare tragen dokumentierte
Kontrastwerte (5,55:1 / 5,05:1 / 6,54:1) für eine Ampel-Semantik, die M3 nicht
kennt — M3 hat nur `error`. Sie müssten als eigene Token bleiben, und man hätte
am Ende zwei Systeme statt einem.

Das Studio hat bereits, was dem Widget fehlte: ein Token-System mit
Kontrast-Nachweisen je Wert, eine Space-Skala, einen funktionierenden
Dunkelmodus, Skip-Link, `aria-current`, und eine Nav-Registry, aus der Routen
UND Sidebar abgeleitet werden (Drift ist dort strukturell unmöglich). Der Punkt
war von mir notiert worden, ohne ihn zu prüfen. **Er entfällt.**

### Was die Messung stattdessen fand

Zwei echte Lücken, beide WCAG 1.3.1, beide unsichtbar im Bild:

- **20 von 69 `<th>` ohne `scope`** in drei Referenz-Views. Ohne `scope` kann
  ein Screenreader eine Zelle ihrer Kopfzeile nicht zuordnen und liest bei einer
  vierspaltigen Tabelle nackte Werte vor.
- **2 doppelte `<h1>`** (`backup`, `widget-preview`): die Shell trägt bereits
  `<h1>BOERDi Studio</h1>`. Zwei Dokument-Titel machen die Überschriften-Liste
  eines Screenreaders unbrauchbar.

Beide Normen waren im Bestand **etabliert und nur nicht durchgehalten** (49 von
69 `th` hatten `scope`, 9 von 11 Seiten-Views nutzten `h2`). Genau diese Sorte
Lücke kehrt zurück, wenn niemand sie prüft — deshalb nicht nur die 22 Stellen
gefixt, sondern ein Gate: `scripts/check-a11y-structure.mjs` + `npm run
check:a11y` + CI-Schritt, im Muster von `check-tokens.mjs`.

`angular-eslint` prüft Template-a11y bereits, kann diese beiden aber nicht
sehen: sie ergeben sich erst aus dem **Zusammenspiel** (dass die Shell schon ein
`h1` trägt) oder aus einem fehlenden Attribut, das kein Element erzwingt.

### Das Gate hat beim ersten Lauf mich selbst erwischt

Der erklärende Kommentar, den ich über den geänderten `h2` gesetzt hatte, nennt
`<h1>` im Fließtext — und wurde als Verstoß gemeldet. Ein Prüfer, der eine
Begründung als Verstoß meldet, erzieht dazu, keine Begründung zu schreiben.
Also blendet das Skript HTML-Kommentare aus, **zeilentreu** (jedes Zeichen außer
`\n` wird ein Leerzeichen), damit die gemeldeten Zeilennummern stimmen.

Gegenprobe gefahren: eine Fixture, in der ein Kommentar `<h1>` und `<th>`
erwähnt (kein Alarm), daneben ein echtes `<h1>` und ein `<th>` ohne `scope`
(beide gemeldet, mit korrekter Zeile).

Verifikation: `ng test studio` **734** · `lint` · `check:tokens` ·
`check:a11y` (40 Templates, 69 `th`) · `ng build studio` **297,50 kB**
(Budget 900).

## Gebaut (Scheibe 11): Spec-Abgleich — und ein Gate, das neun Scheiben rot war

Aufgabe war „§5.5 nachziehen, sie sagt noch *keine Material-Bibliothek*".
**Diese Notiz war falsch:** §5.5 erwähnt Material mit keinem Wort. Der Satz
steht im Kopf von `projects/ui/src/theme/tokens.scss`. Ich hatte die Quelle
verwechselt und in zwei Scheiben-Berichten so weitergegeben.

Beim Nachlesen von §5.5 stand dafür etwas Schlimmeres da:

> **Bundle-Budget:** … CI-Gate ≤ 420 KB raw / ≤ 140 KB gzip

### Das dedizierte Budget-Gate war rot — ich hatte es nie laufen lassen

| | gemessen | altes Limit | Ergebnis |
|---|---|---|---|
| roh | 492,41 kB | 420,00 kB | **117,2 %** |
| gzip | 143,41 kB | 140,00 kB | **102,4 %** |

Es gibt **zwei** Größen-Prüfungen: das Budget in `angular.json` (Bauzeit) und
`scripts/check-widget-budget.mjs` hinter `npm run budget`, das zusätzlich gzip
und die Single-File-Eigenschaft prüft — beides kann Angulars Budget nicht
ausdrücken. In Scheibe 1 habe ich das angular.json-Budget auf 550/600 angehoben
und **das Gate-Skript und den §5.5-Satz nicht mitgezogen**. Seither habe ich in
jeder Scheibe „Budget grün" berichtet und mich dabei auf das eine Budget
bezogen, ohne das andere zu kennen. Genau die Konfig-Paar-Drift, vor der die
Review-Regeln warnen: zwei Stellen nennen dieselbe Grenze, eine wird gepflegt.

Der Nutzer hatte die Erhöhung von Anfang an genehmigt („das Größenlimit darf
dafür steigen"), es war also kein Konflikt mit seiner Vorgabe, sondern eine
halb ausgeführte Änderung von mir. Jetzt stehen alle **drei** Stellen auf
600 kB roh / 175 kB gzip: `angular.json` · das Gate-Skript · §5.5. Alle drei
nennen einander im Text, damit die nächste Änderung nicht wieder nur eine trifft.

Das gzip-Limit ist **abgeleitet, nicht geraten**: das Bundle komprimiert auf
29,1 % seiner Rohgröße, 600 kB roh landen also bei ~175 kB gzip. Der Beleg
steht im Messwert — 82,1 % roh gegen 82,0 % gzip: beide Decken werden bei
demselben Wachstum erreicht, keine ist heimlich die strengere.

Gemessene Material-Kosten für die Akte: **+75,8 kB roh / +33 kB gzip**
(416,57 → 492,41 kB). Die alte §5.5-Begründung („Budget erzwingt die
zoneless-Einsparung") ist erledigt und wurde ersetzt: die Einsparung IST
realisiert — 416,57 kB vor Material lagen 38 kB unter ALT.

### Zwei Kommentare, die in die Irre führten

`tokens.scss` behauptete im Kopf „CSS custom properties only — no Angular
Material component library". Richtiggestellt, zusammen mit dem in Scheibe 8
gemessenen Befund, den die Datei verschwieg: **sie ist im ausgelieferten Widget
gar nicht aktiv** (`"styles": []`), und ihr `--boerdi-primary` (#1f6feb) weicht
von der Laufzeit-Rückfallfarbe des Widgets (#1c4587) ab. Beides steht jetzt
dort, wo jemand es liest, bevor er die Datei ändert. Die Farbe selbst blieb
unangetastet — das ist eine Marken-Entscheidung, keine Aufräumarbeit.

Verifikation: `npm run budget` → **82,1 % roh / 82,0 % gzip, eingehalten**
(vorher: verletzt) · Gegenprobe mit 700-kB-Fixture → rot · `check:tokens`.

## Offen

1. ~~Palette~~ — erledigt (Scheibe 3), ~~**B1**~~ (Scheibe 4),
   ~~**B2**~~ (Scheiben 8+9).
2. ~~Restliche Knöpfe~~ — erledigt (Scheibe 5).
   ~~Eingabezeile / Chips~~ — Chips erledigt (Scheibe 7), `mat-form-field`
   gemessen und **verworfen**.
3. ~~**Karte** auf `mat-card`~~ — erledigt (Scheibe 8), gemessen und behalten.
4. ~~**Studio** auf dieselbe Theme-Basis~~ — gemessen und **verworfen**
   (Scheibe 10); stattdessen die zwei a11y-Lücken geschlossen.
5. ~~**§5.5 der Spec nachziehen**~~ — erledigt (Scheibe 11), zusammen mit dem
   rot gewesenen Budget-Gate und dem irreführenden `tokens.scss`-Kopf.
6. **Debug-Panel** (`debug-panel.component.scss`) bleibt hell-only. Bewusst:
   es erscheint nur mit gesetztem Debug-Schalter, ist kein Produkt-Sichtfeld.

**Damit ist die Liste dieser Reihe abgearbeitet.** Was offen bleibt, ist nicht
mehr Material 3, sondern die Nutzer-Domäne: der Eindruck auf einer echten
WLO-Seite, Screenreader und Zoom am Gerät.

**Nicht geprüft:** wie das Widget in einer echten Gastseite aussieht. Belegt
sind Bau, Tests, Token-Gate, Bundle-Größe und ein Bildpaar gegen das gebaute
Bundle in einer synthetischen Gastseite — nicht der Eindruck auf einer echten
WLO-Seite.
