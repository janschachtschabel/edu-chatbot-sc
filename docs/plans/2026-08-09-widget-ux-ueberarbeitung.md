# Entwurf: Widget-UX/UI-Überarbeitung (U1–U5)

> Status: **Entwurf, wartet auf Freigabe.** Quelle für die Umsetzung; wenn die
> Wirklichkeit abweicht, wird DIESES Dokument nachgezogen, nicht nur der Code.
> Nutzer-Vorgaben vom 2026-08-09 (Screenshots + vier beantwortete Fragen) sind
> in „Festgelegt" wörtlich übernommen.

## Ziel

Das Custom Element `<boerdi-chat>` bekommt (1) einen rahmenlosen Einbettungs-Modus,
(2) zwei Größenstufen mit daran gekoppelter Kachel-/Textlink-Regel, (3) eine
sichtbare Denk-Anzeige, (4) einen hellen Anstrich im edu-sharing/Material-3-Stil
mit umschaltbarem Theme und (5) Ereignisse nach außen, die Fremd-Apps nachnutzen
können.

## Kontext — was heute da ist (gemessen, nicht vermutet)

| Sache | Ist-Zustand |
|---|---|
| Host-Attribute | **19**, eingefroren als §5.5-Vertrag; Wächter in `widget.component.spec.ts:57`, Referenz in `studio/…/widget-contract-data.ts` |
| Kopfzeile | Sprachausgabe (optional) · Sprache · Debug (optional) · **Studio-Nav-Knöpfe aus `header-nav.yaml`** · Neustart · Schließen |
| Denk-Anzeige | **Vollständig verdrahtet**: Backend sendet `phase` (C9, 8 Schritte) → `stream/phase-label.ts` → `send-message.ts` → `message-store.updateLoadingPhase`. Zusätzlich „denkt nach …" im Kopf (`role="status"`) |
| Kacheln | `wlo-card-tile` / `card-list` / `result-groups` — **es gibt keine kompakte Textlink-Darstellung** |
| Layout-Hoheit | Welle E hat die Embed-Layout-Schalter **abgeschafft**; `domain/widget_modes.py` ist nur noch ein Kompat-Echo (`cards_enabled: True` …), Steuerung liegt zentral im Studio (`display-rules.yaml`) |
| Ereignisse nach außen | `host-events.ts`: globale CustomEvents `badboerdi:guide-suggestion`, `badboerdi:routing-debug`, guide-navigate — je hinter einem Opt-in-Attribut |
| Angular Material | **Bereits Abhängigkeit** (`@use '@angular/material'` im Widget-SCSS, `MatButtonModule`/`MatCardModule` in der ui-Bibliothek) |
| Bundle-Budget | Widget-Build: Warnung 550 kB, **Fehler 600 kB** (CI-Tor) |

Drei Konsequenzen daraus, die den Entwurf tragen:

1. **Der M3-Look kostet keine neue Abhängigkeit.** Material ist da; es geht um
   Tokens, Formgebung und Radien — nicht um einen Framework-Zukauf. Das Budget
   bleibt trotzdem das Tor.
2. **Ein Kachel-Schalter am Host dreht Welle E teilweise zurück.** Das ist hier
   sachlich richtig — ob ein 320-px-Seitenleisten-Einbau Kacheln zeigen kann, ist
   eine Frage des Einbauorts, keine redaktionelle. Aber es wird *benannt*, nicht
   stillschweigend gemacht: der Host entscheidet nur „darf/soll", die Redaktion
   behält im Studio, *was* angezeigt wird.
3. **Die Denk-Anzeige wird nicht gebaut, sondern sichtbar gemacht.** Sie
   existiert. Die Aufgabe ist Diagnose + Darstellung, nicht Neubau.

## Umfang

**In:** rahmenloser Modus als Einbettungs-Parameter · Neustart-Knopf von oben
nach unten neben „Senden" · zwei Größenstufen mit Umschalt-Knopf · kompakte
Textlink-Darstellung (neu) · Kachel-Schalter `auto/always/never` · sichtbare
Phasen-Anzeige · Theme `auto/hell/dunkel` · M3-/edu-sharing-Formgebung mit
weniger Außenradius · outlined Kopf-Symbole · Opt-in-Ereignisse nach außen.

**Out (bewusst):** kein Umbau der Studio-Konfiguration `header-nav.yaml` (die
Redaktion behält ihre Knöpfe) · kein stufenloses Ziehen (Nutzer-Entscheid: zwei
feste Stufen) · keine Änderung am Backend-Vertrag (`openapi-v1.json` bleibt
unberührt) · keine neue Abhängigkeit.

## Festgelegt (Nutzer-Entscheide 2026-08-09)

- **Größe:** zwei feste Stufen + Knopf, Startgröße per Attribut.
- **Theme:** Attribut `hell/dunkel/auto`; Ziel ist „mehr typischer edu-sharing-Look
  mit Material-Design-v3-Elementen, weniger runde Ecken außen rum"
  (Referenz: <https://m3.material.io/components>; Nutzer liefert bei Bedarf Bilder).
- **Kopf-Symbole:** Die Redaktion definiert die Knöpfe weiterhin über das Studio —
  **außer den mit Code verknüpften** (Neustart, Schließen, Sprache, Debug,
  Sprachausgabe). Symbolbasierte Knöpfe.
- **Rahmenlos:** ausschließlich als Parameter für die Einbindung der Webkomponente.
- **Zusätzlich:** die Webkomponente soll Ereignisse nach außen reichen, die andere
  Apps nachnutzen können.

## Vertragsänderung: 19 → 23 Host-Attribute

Rein additiv, wie der bewusste additive Schritt am OpenAPI-Vertrag bei C1-g2e.
Jede Ergänzung zieht **vier** Stellen nach: Komponente, `HOST_ATTRIBUTES`-Referenz,
Wächter-Spec, Sprachkataloge (de + en).

| Attribut | Werte | Vorgabe | Wirkung |
|---|---|---|---|
| `embed-mode` | `panel` \| `frameless` | `panel` | `frameless`: kein FAB, keine Kopfzeile, kein Panel-Rahmen — nur Verlauf + Eingabezeile; füllt den Container des Hosts |
| `size` | `small` \| `large` | `small` | Anzeigedichte, **nicht nur Pixel**. Deshalb wirkt sie auch rahmenlos (dort bestimmt der Host die Box, `size` die Dichte) |
| `show-cards` | `auto` \| `always` \| `never` | `auto` | `auto` = die Regel: `small` → Textlinks, `large` → Kacheln |
| `theme` | `auto` \| `light` \| `dark` | `auto` | `auto` folgt `prefers-color-scheme` |

Namen englisch (Code-Konvention), Werte englisch, alle sichtbaren Texte über den
Katalog. `embed-mode` statt „headless": headless heißt üblicherweise *ganz ohne
Oberfläche*; hier ist die Oberfläche da, nur ohne Rahmen.

## Architektur

### Wo was hingehört

| Datei | Verantwortung | Änderung |
|---|---|---|
| `widget/src/app/widget/widget.component.ts` | Attribut-Deklaration, Modus-Ableitung | +4 `input()`, abgeleitete Signale `frameless()`, `effectiveSize()`, `cardsVisible()`, `resolvedTheme()` |
| `widget/src/app/widget/widget.component.html` | Hülle | Kopfzeile + FAB hinter `@if (!frameless())`; Neustart raus |
| `widget/src/app/widget/_widget-panel.scss` u. a. | Panel-Form | Radien, Theme-Variablen, Größenstufen |
| **neu** `ui/src/widget/embed-mode.ts` | *reine* Ableitung Attribute → Modus | `resolveEmbedMode`, `resolveCardsVisible`, `resolveTheme` — testbar ohne DOM |
| **neu** `ui/src/cards/card-link-list.component.ts` | kompakte Textlink-Darstellung | ersetzt Kacheln bei `small` |
| `ui/src/shell/chat-shell.component.ts/.html` | Eingabezeile | Neustart-Knopf links neben „Senden" |
| `ui/src/shell/message-store.ts` + Nachrichten-Template | Phasen-Label | sichtbar rendern (Diagnose zuerst) |
| `ui/src/host-events/host-events.ts` | Ereignisse | +Ereignisse, +Präfix-Entscheid |
| **neu** `ui/src/theme/_tokens.scss` | M3-/edu-sharing-Tokens | Farben, Radien, Elevation für beide Themes |
| `studio/…/views/widget-contract-data.ts` | Referenz | +4 Einträge |
| `ui/src/i18n/{de,en}.ts` · `studio/…/i18n/*` | Texte | neue Schlüssel je Sprache |

**Abhängigkeitsrichtung:** `widget` → `ui` → reine Helfer. Die neuen
Ableitungs-Funktionen (`embed-mode.ts`) sind rein und kennen weder Angular noch
DOM — dasselbe Muster wie `widget-language.ts` und `phase-label.ts`. Keine
Datei überschreitet 300 Zeilen; `card-link-list` ist bewusst eine eigene
Komponente statt eines Zweigs in `wlo-card-tile`.

### Ereignisse nach außen (U5)

Muster von `host-events.ts` übernehmen: **Opt-in per Attribut**, globales
`CustomEvent` *und* Angular-Output. Neu:

| Ereignis | Nutzlast | Wozu |
|---|---|---|
| `boerdi:turn` | `{ role, text, pattern, intent, cards: n }` | Fremd-App kann mitschreiben/protokollieren |
| `boerdi:cards` | `{ cards: [...], query_url }` | Fremd-App rendert Ergebnisse selbst |
| `boerdi:state` | `{ open, size, theme, embedMode }` | Host passt sein Layout an |

**Präfix-Entscheid:** neue Ereignisse unter `boerdi:`. Die zwei Bestands-Ereignisse
heißen im neuen Projekt noch `badboerdi:` — sie werden während P11 unter **beiden**
Namen gesendet und der Alt-Name mit §9-Schritt 6 (ALT-Stilllegung) entfernt.
So bricht kein Host-Einbau während des Parallelbetriebs.

## Nicht-funktionale Vorgaben

- **Barrierefreiheit (WCAG 2.2 AA, Boden):** Kontrast in **beiden** Themes geprüft,
  inklusive Zuständen; Fokus sichtbar; die Phasen-Anzeige bleibt `aria-live="polite"`,
  auch wenn der Kopf rahmenlos wegfällt; der Größen-Knopf hat einen sprechenden Namen,
  nicht nur ein Symbol; Ziele ≥ 24 px.
- **i18n:** kein neuer Text ohne Katalogschlüssel in **de und en**. Der `en.spec.ts`-
  Wächter verbietet wortgleiche DE/EN-Texte und Umlaute im EN-Katalog.
- **Datenschutz:** keine Fremd-Hosts, keine Font-CDN, keine neuen Netzaufrufe.
  Ereignisse nach außen sind seiten-lokal und **Opt-in** — ohne Attribut wird
  nichts gesendet.
- **Budget:** Widget-Bundle < 600 kB (CI-Fehlergrenze) nach jedem Paket messen.
- **Leistung:** Theme über CSS-Variablen, kein Neu-Rendern bei Umschaltung.

## Pakete

Jedes Paket: **Schritt 0 = `/better-coding-workflow` + `/better-coding-frontend` laden.**
Abschluss je Paket: `npx ng test ui`, `npx ng test widget`, `npm run build:widget`
(Budget), `eslint`, `check:a11y`, `check:tokens` — plus die Studio-Suite, sobald
`widget-contract-data.ts` berührt ist.

### U3 — Denk-Anzeige · **✅ nichts zu bauen (Diagnose 2026-08-09)**

**Die Anzeige ist vollständig vorhanden, sichtbar und getestet.** Belegt statt
vermutet: `phase-label.ts` (Erlaubnisliste, 8 Schritte) → `updateLoadingPhase`
(`message-store.spec.ts:109`) → `chat-shell.component.html:41`
`<span class="typing-phase">` (`chat-shell-template.spec.ts:99`), gestylt in
`chat-shell.component.scss:201` (0,82 rem, `on-surface-variant`, kursiv,
Einblendung), und sie liegt in der Live-Region `role="log" aria-live="polite"`.
Lauf zur Abnahme: `npx ng test ui --watch=false` → **59 Dateien / 572 Tests grün**.

**Korrektur der Reihenfolge.** Dieses Paket war mit dem Argument vorgezogen
worden, U1 entferne die Kopfzeile und damit die einzige sichtbare Rückmeldung.
Das war falsch: das Phasen-Label hängt **in der Blase**, nicht im Kopf, und
überlebt den rahmenlosen Modus ohne Zutun. Das „denkt nach …" im Kopf ist ein
zweiter, redundanter Anzeiger. **Damit beginnt die Umsetzung mit U1**, wie vom
Nutzer ursprünglich gewählt.

Offen bleibt aus diesem Paket nur eine Beobachtung für U1, kein Auftrag: fällt der
Kopf rahmenlos weg, entfällt der wackelnde Boerdi-Kopf als *Bewegung*. Ob dort ein
schlanker Spinner nötig ist, entscheidet sich in U1 am gebauten Ergebnis — die
Lade-Punkte (`typing-dots`) sind ohnehin schon in der Blase.

<details><summary>Ursprünglich geplante Schritte (nicht ausgeführt)</summary>

1. **Diagnose:** rendert das Nachrichten-Template `loadingPhase` überhaupt? Befund
   dokumentieren, bevor etwas geändert wird.
2. Phasen-Text in der laufenden Bot-Blase sichtbar rendern (Spinner + Text).
3. `aria-live` so setzen, dass Screenreader den Wechsel bekommen, aber nicht bei
   jedem der 8 Schritte unterbrochen werden.
4. Wächter: acht Schritte → acht Katalogtexte, unbekannter Schritt → kein Label
   (`phase-label.ts` ist eine Erlaubnisliste; das bleibt so).

</details>

### U1 — Rahmenlos + Neustart nach unten · **zuerst**

> **Teil 1 ✅ 2026-08-09 — rahmenloser Modus steht.** Schritte 1, 2, 4, 5 erledigt.
>
> **Teil 2 ✅ 2026-08-09 — Neustart-Knopf umgezogen** (Schritt 3). Er sitzt jetzt
> in `.chat-footer` links vom Senden-Knopf und ist aus der Kopfzeile der Hülle
> entfernt. Zwei Entscheidungen mit Begründung im Code: er ist **nicht gesperrt,
> während der Bot arbeitet** (genau dann will man einen festgefahrenen Zug
> abbrechen — Eingabefeld und Senden sind es sehr wohl), und `.btn-restart` ist
> eine **eigene** SCSS-Regel neben `.btn-mic` statt einer gemeinsamen Klasse,
> weil `.btn-mic` zusätzlich den Aufnahme-Zustand trägt.
>
> Der Test prüft die **Reihenfolge** (`nextElementSibling` ist `.btn-send`), nicht
> bloße Anwesenheit — „links neben dem Absende-Knopf" ist die Anforderung, und ein
> Anwesenheits-Test wäre auch mit dem Knopf ganz vorn grün.
>
> Belege Teil 2: ui **578** · widget **42** · Bundle **510,02 kB** · eslint sauber.
> Nebenbefund: die Kopfzeilen-Zusammensetzung war **nicht** gepinnt — das Entfernen
> des Knopfes brach keinen Test. Bewusst kein Abwesenheits-Test nachgereicht; der
> Umzug ist durch den ui-Test an seinem neuen Ort festgehalten.
>
> **Teil 3 ✅ 2026-08-09 — `/widget/frameless` (Schritt 6) ⇒ U1 ZU.** Vierte
> Demo-Seite im BACKEND (`api/widget_demo_html.py` + eine Route in `api/widget.py`);
> `_render` bekam ein optionales `extra_style`, weil nur diese Seite einen
> Wirts-Container braucht und eine `.frame`-Regel im geteilten Blatt auf drei
> Seiten tot läge.
>
> **Vertrags-Entscheid, ausdrücklich:** die Demo-Seiten stehen im **eingefrorenen
> OpenAPI-Dokument**, eine vierte Route ist also eine Vertragserweiterung. Gemessen
> vor dem Regenerieren: **rein additiv — genau ein Pfad kommt hinzu, kein
> bestehender Pfad und kein Schema ändert sich.** Damit ist es dieselbe Klasse wie
> die drei V3-Routen, die schon über ALTs Inventar hinausgehen. Nachgezogen an
> allen vier Stellen: `openapi-v1.json`, `EXPECTED_ROUTES`, `PUBLIC_ROUTES`,
> Routentabelle im Neubau-Plan. Zurücknehmbar, falls unerwünscht.
>
> **Der eigentliche Ertrag ist der Browser-Lauf — er fand einen Fehler aus Teil 1,
> den 2550 Tests nicht finden konnten.** Rahmenlos war der Panel **393 px hoch in
> einem 504-px-Kasten**: meine Teil-1-Regeln setzten Host und Panel, übersprangen
> aber die Hülle `.boerdi-widget` dazwischen. Die hat Auto-Höhe, und `height: 100%`
> am Panel braucht einen Bezug mit fester Höhe — es fiel auf Inhaltshöhe zurück und
> ließ unten Luft stehen. Im schwebenden Modus fällt das nie auf, weil das Panel
> dort absolut positioniert ist. **Kein Unit-Test kann das sehen: jsdom rechnet kein
> Layout.** Nach dem Fix ist die Kette lückenlos: 506 → 504 → 504 → 504
> (Verlauf 445 + Fußzeile 59). Nebenbei bekommt die Klasse
> `.boerdi-widget--frameless`, die seit Teil 1 nur Test-Markierung war, ihren
> ersten echten Verbraucher.
>
> **Regel daraus:** eine reine Layout-Änderung ist erst belegt, wenn sie im Browser
> gemessen wurde. Grüne Komponenten-Tests sind dafür kein Ersatz, sie können es
> prinzipiell nicht sein.
>
> Gegenprobe im selben Lauf, dass der schwebende Modus unberührt ist: FAB da, nach
> Klick 399 × 646, Radius 16 px, Schatten, Kopfzeile — und der Neustart-Knopf sitzt
> unten in `.chat-footer`, nicht mehr oben. Begrüßung kam vom Backend, der Datenweg
> steht also auch.
>
> Nebenbei berichtigt: die Seiten behaupteten „die vollständige Liste der **18**
> Host-Attribute". Es sind 20, und die Zahl wäre bei jeder weiteren Erweiterung
> wieder falsch — sie ist jetzt ersatzlos raus, der Verweis aufs Studio bleibt.
>
> Belege Teil 3: pytest **2550/4** (davon test_widget_router **35**, 9 davon zuvor
> rot) · widget **42** · Bundle **510,08 kB** · ruff sauber · `export_openapi.py
> --check` → „openapi contract unchanged". Anmerkung: `ruff format` ist **kein**
> Gate (CI fährt nur `ruff check`), und der Baum ist dort ohnehin nicht sauber —
> meine Zeile folgt dem Stil ihrer Nachbarin, fremde habe ich nicht angefasst.
>
> **Zwei Entwurfsentscheidungen, die beim Bauen entstanden.** Erstens: statt eines
> eigenen `embed-mode.ts` bekam `element/attr.ts` den generischen `_attrEnum` —
> die Datei besitzt bereits die Zuständigkeit „Host-Attribut normalisieren"
> (`_attrIsTrue`), und alle vier neuen Aufzählungs-Attribute brauchen dieselbe
> Behandlung. Ein eigenes Modul je Attribut wäre vier Dateien für je drei Zeilen.
> Zweitens, und das ist der Fund: **eine CSS-Regel `:host([embed-mode="frameless"])`
> wäre eine stille Falle** — Attributselektoren vergleichen exakt, `_attrEnum`
> toleriert Schreibweise und Leerzeichen; `embed-mode="FRAMELESS"" hätte im
> TypeScript gegriffen und im CSS nicht. Deshalb trägt ein `host`-Binding die
> **normalisierte** Klasse `.boerdi-frameless` ans Host-Element, und das SCSS
> hängt daran. Dieselbe Fehlerklasse wie das tote `data-position` (8-5).
>
> Dritter Punkt, der ohne Test durchgerutscht wäre: rahmenlos MUSS das
> Lazy-Mount-Gate offen sein (`chatMounted = everExpanded() || frameless()`) —
> es gibt keinen FAB, der es je öffnen würde.
>
> Belege: widget **42** · ui **575** · studio **889** · Bundle **509,65 kB**
> (Grenze 600) · eslint sauber. Der Studio-Wächter hat den Vertragsbruch von sich
> aus gemeldet (19 → 20) — genau wozu er da ist.

1. `embed-mode` deklarieren, reine Ableitung in `embed-mode.ts` (Test zuerst).
2. Kopfzeile, FAB und Panel-Rahmen hinter `@if (!frameless())`.
3. Neustart-Knopf aus der Kopfzeile in die Eingabezeile, links neben „Senden".
4. Rahmenlos: Container füllen, kein Außenradius, kein Schlagschatten.
5. Vertrag: `HOST_ATTRIBUTES` +1, Wächter von 19 auf 20, Kataloge de/en.
6. Demo-Seite für den rahmenlosen Einbau (es gibt bereits `/widget/`, `/inline`, `/classic`).

### U2 — Größenstufen + Kachel-Regel

> **Messung 2026-08-09, vor dem Bauen — Schritt 3 entfällt, beide Darstellungen
> gibt es schon.** `result-groups` (Gruppen-Boxen) rendert **Icon + Titel als
> Textlink**, null `<img>`; die **Kacheln mit Vorschaubild** stecken
> ausschließlich in `wlo-card-tile`, das nur `card-list` verwendet. Genau das
> Paar „Textlinks ↔ Kacheln", das gewünscht ist, existiert also bereits — nur
> hängt die Wahl heute am Attribut `inline-result-grouping` statt an Größe und
> Kachel-Schalter. Ein `card-link-list.component` wäre eine dritte Darstellung
> für einen Zweck, den die erste schon erfüllt.
>
> **Folge für den Schnitt:** `show-cards` und `inline-result-grouping` steuern
> dieselbe Wahl. Statt zweier konkurrierender Attribute bekommt die Ableitung
> eine ausdrückliche Rangfolge (`resolveCardsVisible(size, showCards,
> inlineGrouping)`), die jedes Bestands-Embed unverändert lässt: `always`/`never`
> gewinnen; bei `auto` gilt weiterhin `inline-result-grouping="false"` ⇒ Kacheln;
> sonst entscheidet die Größe. Nicht bloß visuell verschieden: `card-list` trägt
> zusätzlich Sammlungs-Aktionen und Pagination, die `result-groups` nicht hat.
>
> **Abweichung vom Entwurf, mit Grund:** der Größen-Umschalter ist rahmenlos
> **nicht** sichtbar. Dort bestimmt die Gastanwendung die Maße — ein Knopf
> „vergrößern", der nichts vergrößert, wäre eine Lüge. Das Attribut `size` wirkt
> rahmenlos trotzdem, weil es zusätzlich die Kachel-Regel speist.

> **U2a + U2b ✅ 2026-08-09 ⇒ U2 ZU.** 22 Host-Attribute (`size`, `show-cards`).
>
> **Wo die Größe wohnt:** in `PanelState` (`ui/src/widget/`), nicht in der Shell.
> `size` setzt nur den ANFANG (`initSize` in `ngOnInit`, bewusst kein Effect —
> der würde jede Handbedienung beim nächsten Signal-Lauf überschreiben); danach
> gehört die Stufe dem Panel. Die Eingabezeile meldet den Wunsch per Output nach
> oben und hält keinen eigenen Größen-Zustand: die Maße kennt das Panel.
>
> **Kleiner Architektur-Fund:** der gemeinsame Typ `PanelSizeStep` hätte die
> ERSTE Kante zwischen `shell/` und `widget/` gezogen — und zwar in die falsche
> Richtung, denn die Hülle setzt die Shell zusammen, nicht umgekehrt. Er wohnt
> jetzt in `element/attr.ts`, wohin beide Ordner schon zeigen.
>
> **Zwei Eingänge statt einem** (`sizeToggleVisible` + `sizeStep`): der eine
> beantwortet „gibt es hier etwas zu verändern", der andere „wie heißt der Knopf
> gerade". Zusammengelegt wäre es wieder eine Zeichenkette mit zweitem,
> unsichtbarem Auftrag.
>
> **Symbole:** `fullscreen`/`fullscreen_exit` sind die einzigen beiden im Set,
> die NICHT aus dem Material-Set kopiert sind, sondern auf demselben Raster von
> Hand konstruiert (vier Eckwinkel, Strichstärke 80, Rand 120) — jeder Punkt
> nachgerechnet. Einen fremden Pfad abzutippen, den ich nicht prüfen kann, wäre
> geraten gewesen; im Modul steht es dabei.
>
> **U2b — die Messung hat das Paket halbiert.** `card-link-list` entfällt: die
> kompakte Darstellung ist `result-groups` und war seit 8-2h da. Geblieben ist
> die Rangfolge in `resolveCardsVisible` — `always`/`never` gewinnen, bei `auto`
> gilt weiter `inline-result-grouping="false"` ⇒ Kacheln, sonst entscheidet die
> Größe. Damit sieht **jedes Bestands-Embed unverändert aus**, was der erste
> Testblock festnagelt. `cardsEnabledBool` (Welle-E-Konstante) ist aus der
> Bedingung raus: `show-cards` IST sein Nachfolger, mit drei Stellungen statt
> zwei.
>
> **Belege:** ui **597** · widget **47** · studio **889** · eslint 0 ·
> Bundle **512,95 kB** (Fehlergrenze 600). Rot-Grün beobachtet: 4 PanelState-,
> 4 Umschalter-, 5 Regel- und 5 Widget-Tests fielen zuerst; die Vertrags-Wächter
> meldeten 20→21 und 21→22 von sich aus.
>
> **Live gegen `127.0.0.1:8021`:** Host-Klasse kippt `'' ⇄ boerdi-large`, die
> Regel steht im Shadow-Stylesheet
> (`:host(.boerdi-large) .boerdi-panel { width: 640px; height: min(920px, …) }`),
> Beschriftung wechselt „Chat vergrößern" ⇄ „Chat verkleinern", Reihenfolge
> Größe → Neustart → Senden. Kachel-Regel im Betrieb: klein = Boxen, groß =
> Kacheln, und ein zur LAUFZEIT gesetztes `show-cards="never"` schaltet sofort
> zurück — das belegt den ganzen Weg Attribut → Eingang → Shell.
> **Nicht gemessen:** die tatsächliche Pixelbreite. Der Browser-Bereich war
> diesmal nicht eingeblendet, also rechnet die Seite kein Layout (alle Rechtecke
> 0). Anders als bei U1 fehlt hier kein Glied in der Kette — die Regel greift am
> Host, genau wie die rahmenlose, die gemessen wurde —, aber gesehen habe ich
> die 640 px nicht.

**U2a — Größenstufen**

1. `size` deklarieren (klein/groß, Standard klein) — Anfangswert für den Schalter.
2. Zwei Stufen im Panel-SCSS; Umschalter in der Eingabezeile, rahmenlos verborgen.
3. Vertrag +1 (→ 21), Wächter, Kataloge de/en.

**U2b — Kachel-Regel**

4. `show-cards` deklarieren; `resolveCardsVisible` rein und testbar (Rangfolge oben).
5. Beide Renderer an `cardsVisible` hängen statt an `inlineResultGroupingBool`.
6. Vertrag +1 (→ 22), Kataloge, Größe im `boerdi:state`-Ereignis (U5).

### U4 — Theme + M3-/edu-sharing-Anstrich

> **Ersetzt durch den Nachtrag am Ende des Dokuments** (Messbefunde vom
> 2026-08-09 verkleinern dieses Paket erheblich). Die Schritte hier bleiben als
> Entstehungsstand stehen.

1. `theme` deklarieren, `resolveTheme(attr, mediaQuery)` rein und testbar.
2. `_tokens.scss`: Farb-, Radius- und Elevation-Tokens für hell und dunkel.
3. Kopf-Symbole auf outlined + helle Akzentfarbe — **im Code**, die Icon-Namen
   in `header-nav.yaml` bleiben unberührt (Nutzer-Vorgabe: Redaktion behält die Knöpfe).
4. Außenradien reduzieren, M3-Formgebung für Knöpfe/Chips/Karten.
5. Kontrast-Durchgang in beiden Themes; `check:tokens` muss sauber bleiben.
6. Vertrag +1 (→ 23), Kataloge.

### U5 — Ereignisse nach außen

1. Opt-in-Attribut im Muster von `emit-guide-suggestion` (kein neues Muster).
2. Die drei Ereignisse mit Test je Ereignis (gesendet / nicht gesendet ohne Opt-in).
3. Doppelname `badboerdi:` + `boerdi:` für die zwei Bestands-Ereignisse, mit
   Ablaufdatum an §9-Schritt 6 geknüpft.
4. Dokumentation im Studio-Referenzbereich und in der Widget-README.

## Risiken

| Risiko | Gegenmittel |
|---|---|
| Bundle-Budget (600 kB) reißt durch neue Komponente + Tokens | Nach jedem Paket messen; `card-link-list` ist klein und ersetzt keine Kachel-Logik |
| Der eingefrorene 19-Attribut-Vertrag driftet | Wächter-Zahl in derselben Änderung mitziehen; die Studio-Referenz ist Teil der Definition of Done |
| Kontrast fällt im zweiten Theme durch | Kontrast ist Abnahmekriterium je Paket, nicht Nachpolitur |
| Rahmenlos verliert Zustände (Status, Lotsen-Banner, Sprachwechsel) | U3 zuerst; je entfallenem Kopf-Element ausdrücklich entscheiden, wohin es wandert oder dass es bewusst entfällt |
| „M3-Look" ohne verbindliche Vorlage franst aus | Nutzer liefert Bilder; bis dahin: Tokens + Radien, keine Neuerfindung von Komponenten |
| Ereignisse nach außen als stiller Datenabfluss | Opt-in, seiten-lokal, dokumentiert; ohne Attribut passiert nichts |

## Offene Punkte

- ~~Bildvorlagen für den M3-/edu-sharing-Look~~ — **geliefert 2026-08-09**, siehe Nachtrag.
- Bestätigung des Präfix-Entscheids `boerdi:` + Doppelname während P11 (U5).

---

# Nachtrag 2026-08-09 — Vorlagen des Nutzers + drei Messbefunde, die U4 verkleinern

## Die Vorlagen

Nutzer-Referenzen: M3 **Fullscreen-Dialog**, **Loading-Indicator** (oder wie bisher
der wackelnde Boerdi-Kopf), **Navigation Bar**, **Search**, **Text Fields**,
**Color Roles** — dazu vier Bilder: Navigationsleiste mit Pillen-Indikator,
angedockte Suchleiste, Outlined-Textfeld mit schwebendem Label, und eine
Chat-Oberfläche mit Verfasser-Zeile unten (führendes „+", Eingabe, nachgestellte
Symbole, Senden).

## Drei Messbefunde — was davon schon steht

1. **Material 3 ist bereits eingerichtet.** `mat.theme()` an `:host` (bewusst
   nicht `:root`, sonst stylt das Widget die Gastseite um), Palette aus der
   Markenfarbe `#1c4587` erzeugt, `--mat-sys-*`-Token in den Komponenten in
   Gebrauch. Die **Color Roles sind also schon der Farbenkanon** — sie müssen
   benutzt, nicht eingeführt werden.
2. **Der Dunkelmodus funktioniert bereits.** Das Widget nutzt `light-dark()` und
   folgt dem geerbten `color-scheme` der Gastseite (im Code als „gemessen"
   dokumentiert). Damit ist `theme="auto"` **das heutige Verhalten**; das neue
   Attribut muss es nur übersteuern: `light`/`dark` setzen `color-scheme` an
   `:host`, `auto` setzt nichts und erbt. Wenige Zeilen, kein zweites Stylesheet.
3. **Die M3-Formskala ist installiert** (`--mat-sys-corner-extra-small … -full`).
   Die Radien im Code sind heute handgesetzt und uneinheitlich: **3, 4, 5, 6, 8,
   16, 18, 20 px, 50 %, 999 px**. Das Aufräumen hat damit ein benanntes Ziel.

**Warum das zweite Bild moderner wirkt** — und was daraus folgt: die Kopfzeile ist
mit der **Markenfarbe** gestrichen (`primary`), nicht mit einem Flächen-Token.
Das ist die eigentliche Änderung, nicht „ein helles Theme bauen".

## Entwurfsentscheidungen zu den Vorlagen

**Verfasser-Zeile (Bild 4) — ja.** Die Eingabezeile wird eine M3-Verfasser-Zeile:
Neustart links, **Outlined-Textfeld** (Bild 3) in der Mitte, Senden rechts; die
code-gebundenen Umschalter (Sprachausgabe, Sprache, Debug) wandern als
nachgestellte Symbolknöpfe hinein. Outlined statt Pillen-Form, weil du „weniger
runde Ecken außen rum" willst — innen bleibt die M3-Form erlaubt.

**Suchleiste (Bild 2) — nein, und das ist eine Sachentscheidung.** Die M3-Suche ist
ein *Such*-Muster: sie erwartet eine Ergebnisansicht und trägt Suchfeld-Semantik.
Ein Chat-Verfasser ist etwas anderes; die Suchleisten-Rolle würde
Screenreadern das Falsche ansagen und ein Verhalten versprechen, das es nicht gibt.
Das Vorbild für unten ist Bild 4, nicht Bild 2.

**Navigationsleiste (Bild 1) — nein.** Eine M3-Navigationsleiste steht für
*mehrere gleichrangige Ziele innerhalb* der App. Das Widget hat ein Ziel (den
Chat); die Studio-Knöpfe sind **ausgehende Links** auf andere Seiten. Sie als
Navigationsleiste zu bauen, verspräche einen Wechsel innerhalb des Widgets. Sie
bleiben deshalb oben — als outlined Symbole in heller Akzentfarbe, wie gewünscht,
und weiterhin von der Redaktion im Studio gepflegt. **Rahmenlos entfallen sie**,
weil dort die Gastanwendung ihre eigene Navigation stellt — genau wie du den
rahmenlosen Modus beschrieben hast (Verlauf + Eingabe + Neustart + Senden).

**Loading-Indicator — der Kopf bleibt.** Der wackelnde Boerdi-Kopf existiert
(`is-thinking`), ist Marke und kostet nichts. Der M3-Loading-Indicator ist eine
neue Komponente in einem Bundle mit 600-kB-Fehlergrenze. Entschieden: **Kopf als
Bewegung + Phasentext daneben** (U3). Falls der Kopf rahmenlos wegfällt, tritt ein
schlanker M3-Spinner an seine Stelle.

**Fullscreen-Dialog** als Vorbild für die **große** Größenstufe: großflächig,
kaum Außenradius, eigene Kopf-/Fußzone — das trägt U2.

## U4 neu geschnitten (ersetzt die Schritte oben)

1. `theme`-Attribut → `color-scheme` an `:host` (`light`/`dark`/nicht gesetzt).
   Reine Ableitung `resolveTheme` mit Test; **kein** zweites Stylesheet.
2. Kopfzeile von der Markenfarbe auf ein Flächen-Token umstellen
   (`surface-container`), Text/Symbole auf die zugehörigen `on-*`-Rollen.
3. Handradien durch `--mat-sys-corner-*` ersetzen; Panel-Außenradius reduzieren.
   Wächter: kein handgesetzter `border-radius`-Pixelwert mehr in Widget/ui-SCSS
   (Ausnahmen mit Begründung, Muster wie `check:tokens`).
4. Kopf-Symbole outlined + helle Akzentfarbe — im Code, `header-nav.yaml` bleibt
   unberührt.
5. Kontrast-Durchgang hell **und** dunkel; `check:a11y` und `check:tokens` sauber.
6. Vertrag +1 (→ 23), Kataloge de/en.

### U4 in vier Scheiben (2026-08-09)

Die sechs Schritte oben sind zwei verschiedene Arbeiten: ein **Schalter** (1+6)
und ein **Anstrich** (2+3+4+5). Der Schalter ist in sich fertig und macht den
Anstrich überhaupt erst prüfbar — ohne ihn gibt es keine Möglichkeit, den
Dunkelmodus anzusehen, ohne die Systemeinstellung des Rechners zu drehen.

- **U4a — `theme`-Attribut** (Schritte 1+6). Reine Ableitung + Vertrag + Kataloge.
- **U4b — Kopfzeile auf Flächen-Token + Symbole outlined** (2+4). Zusammen, weil
  Schritt 4 nur auf der neuen Fläche entscheidbar ist: „helle Akzentfarbe" heißt
  auf dem heutigen dunkelblauen Band etwas anderes als auf `surface-container`.
- **U4c — Radien auf `--mat-sys-corner-*` + Wächter** (3).
- **U4d — Kontrast-Durchgang hell und dunkel** (5). Zuletzt, weil er das
  Ergebnis von U4b/U4c misst. ⇒ alle vier erledigt, **U4 ist zu**.

### U4a — `theme` (erledigt 2026-08-09)

`theme="auto|light|dark"`, 23. Host-Attribut. Die ganze Entscheidung steckt in
`resolveTheme` (`ui/src/element/attr.ts`): `auto` ergibt **`null`**, nicht
`'light'`. Das Widget hatte nie einen eigenen Schalter — es folgte dem geerbten
`color-scheme` der Gastseite, und die `light-dark()`-Aufrufe im M3-Theme sind
genau darauf gebaut. Ein Vorgabewert `'light'` hätte diese Vererbung
stillschweigend abgeschaltet und jede dunkle Gastseite hell gemacht. `null`
löscht die Eigenschaft auch wieder, deshalb kann eine Gastseite mit eigenem
Umschalter zur Laufzeit auf `auto` zurückstellen (eigener Test).

Gesetzt wird ein **Inline-Stil am Host** (`[style.color-scheme]`), nicht — wie
bei `embed-mode` und `size` — eine Host-Klasse mit CSS-Regeln dahinter. Dort
hängen viele Regeln an der Stufe, hier ist es genau eine Deklaration mit einem
Wert; und der Inline-Stil ist das, was ein Test beobachten kann, während eine
Klasse nur die Markierung belegt hätte (jsdom wertet keine Stylesheets aus).

Live gegen `127.0.0.1:8021` (Browser auf dunkel), Panel-Hintergrund gemessen:

| `theme` | `style.color-scheme` | `.boerdi-panel` |
|---|---|---|
| nicht gesetzt | leer | `rgb(18,19,24)` |
| `dark` | `dark` | `rgb(18,19,24)` |
| `light` | `light` | `rgb(249,249,255)` |
| zurück auf `auto` | leer | `rgb(18,19,24)` |

Damit ist die ganze Kette belegt: Attribut → Ableitung → Host-Stil → geerbtes
`color-scheme` → `light-dark()` in den M3-Token → Fläche.

### U4b — Kopfzeile auf einer M3-Fläche (erledigt 2026-08-09)

Kehrt eine im Code festgehaltene Entscheidung um: „Die KOPFZEILE bleibt bewusst
markenfarben … Weiß auf #1c4587 trägt ~10:1 in BEIDEN Modi." Die Analyse war
richtig; nur ist das Mitkippen jetzt das Ziel. Gewechselt haben Kopffläche,
Titel/Status, Aktions-Chips, Schließen-Knopf und alle vier Fokusringe.

Nicht `primary` als Fläche, sondern `surface-container`: die Kopfzeile ist eine
Fläche, keine Aktion. Die Markenfarbe bleibt, wo sie etwas aussagt — Fokusringe
und (über die Token-Brücke) die Chips der Shell.

**Drei Entwürfe, zwei davon durch Messung gestorben.** Das ist der Ertrag der
Scheibe, nicht das Ergebnis:

| Entwurf für „aktiv" | gemessen | Urteil |
|---|---|---|
| `secondary-container` (M3-Ton für „ausgewählt") | **1,09:1** gegen die Kopffläche | hell auf hell / dunkel auf dunkel — als Zustand unbrauchbar |
| dazu Kante in `primary` | je ≥3:1 gegen die Fläche, aber **1,1:1** gegen die Aus-Kante (dunkel) | Unterschied nur im Farbton ⇒ SC 1.4.1 verletzt |
| `inverse-surface` / `inverse-on-surface` | **11,32 / 12,75** | trägt — der Ton kehrt sich MIT dem Schema um |

`inverse-surface` ist genau die Aussage, die früher der weiße Pill auf dem
Farbband machte, nur in beiden Schemata. Bewusst neutral statt markenfarben:
die Kundenfarbe darf beliebig hell sein, ein darauf gebauter Vordergrund wäre
eine Wette — denselben Grund nennt die Token-Brücke dafür, `on-primary` nicht
zu überschreiben.

**Zweiter Messbefund:** der Tonschritt zwischen Kopf- und Panel-Fläche beträgt
nur **1,11:1** (hell) bzw. 1,13:1 (dunkel). Die neue Trennlinie IST damit die
Trennung, nicht ihre Verzierung — deshalb `outline` (3,84 / 5,17) statt des
üblichen Divider-Tons `outline-variant` (1,46).

**Nebenbei behoben:** die Redaktions-Nav-Knöpfe trugen im Ist-Zustand eine Kante
mit **2,52:1** — unter der 3:1-Schwelle aus SC 1.4.11. Jetzt 3,84 / 5,17.

Kontrast am ausgelieferten Bundle, je Schema an einem frisch gebauten Element
gemessen (hell / dunkel): Titel 14,78 / 12,75 · Symbol aus 8 / 12,75 · Kante aus
3,84 / 5,17 · Chip aktiv 11,32 / 12,75 · Symbol auf dem Chip 11,62 / 10,2 ·
Schließen 8 / 12,75. Alle über der jeweiligen Schwelle.

**Eine Ausnahme, begründet:** `.boerdi-owl-mini` behält `#ffffff`. Das Logo ist
ein Bild mit festen eigenen Farben; die weiße Scheibe ist sein Kontrastträger,
kein vergessener Hellwert (dieselbe Begründung wie beim FAB). Mein erster
Testentwurf hatte genau diese Ausnahme übersehen und hätte das blaue Motiv im
Dunkelmodus unsichtbar gemacht — gefunden beim Lesen der Nachbardatei, nicht
durch einen Test.

**Nicht verifiziert:** ob ein Sprachwechsel des `theme`-Attributs ZUR LAUFZEIT
in einem echten Browser sofort durchschlägt. Im nicht gezeichneten Browser-Panel
blieb ein Teil der Stilwerte auf dem alten Schema stehen, während Fläche und
Titel umsprangen; an frisch gebauten Elementen stimmt alles. Das sieht nach
Invalidierung im nicht komponierten Panel aus, ist aber mit diesem Werkzeug
nicht zu trennen. Am Gerät nachsehen.

### U4c — Radien auf der M3-Skala (erledigt 2026-08-09)

Das Widget hatte **elf** verschiedene Eckenwerte (3, 4, 5, 6, 8, 10, 12, 14, 16,
18, 20 px) plus zwei SCSS-Variablen, die je einen davon versteckten. Die
M3-Skala hat sechs Stufen. Jeder Einzelwert war für sich plausibel; zusammen
liest sich das als „aus Teilen zusammengesetzt".

**Der Wächter kam zuerst** — `frontend/scripts/check-radii.mjs`, gebaut nach dem
Muster von `check:tokens`. Er lief rot mit **32 Fundstellen** und hat dabei zwei
Stellen gefunden, die mein eigener `grep` übersehen hatte: die
`border-bottom-left/right-radius` der Sprechblasen-Spitze. Danach die
Umstellung, dann grün. Gegenprobe an einer Attrappe: ein `border-radius: 7px`
lässt ihn fallen, `var(--mat-sys-corner-small)` und `50%` nicht.

Zuordnung: 3/4/5 → `extra-small` · 6/8 → `small` · 10/12/14 → `medium` ·
16 → `large` · 18/20/999 → `full`. Erlaubt bleiben `0`, `50%` und `inherit` —
sie sagen eine **Form**, keine Größe (Kreis, geerbt, keine Ecke).

**Panel-Außenradius 16 → 12px** (`medium`), die eigentliche Vorgabe („weniger
runde Ecken außen rum"). Bewusste Abweichung von M3, das großen Flächen große
Ecken gibt. Wer es kantiger will: **ein** Token tauschen (`small` = 8px).

**Eine begründete Ausnahme:** `print-utils.ts`. Es baut mit `window.open` +
`document.write` ein EIGENES Dokument — die `--mat-sys-*`-Token leben am `:host`
des Widgets und existieren dort nicht. Ein `var()` darauf wäre eine ungültige
Deklaration und damit gar kein Radius.

**Vorher geprüft, weil genau das die Falle wäre:** kein `ui/`-Bauteil wird
ausserhalb des Widget-Elements gerendert (der Studio importiert aus `@boerdi/ui`
nur Typen und reine Logik, nie eine Komponente). Sonst wären die Token dort
undefiniert — und eine undefinierte `var()` löscht die ganze Deklaration
lautlos, genau der Fehler, für den `check:tokens` gebaut wurde. Am Bundle
nachgemessen: Panel 12px, Aktions-Knopf 8px, Eulen-Blase 12px, Scheibe 50 %,
Eingabezeile 9999px — nichts weggefallen.

Zwei SCSS-Variablen sind ersatzlos entfallen (`$card-radius` 2×, `$radius` 1×):
sie hatten je einen Leser und trugen einen Wert, der auf keiner Stufe lag.

### U4d — Kontrast-Durchgang hell und dunkel (erledigt 2026-08-09) ⇒ U4 ZU

Der Durchgang ist **kein Protokoll, sondern ein Tor**: `e2e/contrast.spec.ts`
misst bei jedem Lauf jeden sichtbaren Text im Shadow-DOM gegen seine tatsächlich
gerenderte Fläche — hell und dunkel, in zwei Karten-Oberflächen. Ein Durchgang
von Hand belegt einen Stand; dieser belegt jeden.

**Warum im Browser und nicht als Unit-Test.** Der Kontrast eines Textes steht
nirgends im Quelltext. Er entsteht erst aus `light-dark()`, `color-mix()`,
geerbten Farben, halbdurchsichtigen Flächen und der Frage, welcher Vorfahr
überhaupt eine deckende Fläche trägt. jsdom rechnet davon nichts aus. Zwei
Kniffe im Messer (`e2e/fixtures/contrast.ts`), ohne die die Zahlen falsch sind:
`getComputedStyle` gibt für `color-mix()` **`oklab(…)`** zurück — deshalb wird
die Farbe auf ein 1×1-Canvas gemalt und der Pixel zurückgelesen; und der Weg zur
Fläche geht über `.host`, weil `parentElement` an der Shadow-Grenze `null` ist.

**Der Fund, mit dem der erste Lauf rot war** — und der Grund, warum es dieses
Tor geben muss:

> `div.debug-row  rgb(226,226,232) auf rgb(248,250,252)` → **1,23:1** (dunkel)

Das Debug-Feld setzte seine Fläche fest auf `#f8fafc` und ließ die Zeilentexte
die Farbe des Chats **erben**. Seit U4b/U4c folgt diese geerbte Farbe dem
Schema — also stand fast weißer Text auf fast weißer Fläche. Die Zeilen waren
schlicht unsichtbar. **Kein bestehender Test konnte das sehen**, weil der Defekt
erst aus dem Zusammentreffen zweier Dateien entsteht: die eine kippt, die andere
nicht. Genau die Klasse Fehler, die ein Farbdurchgang finden soll.

Der Ausweg war nicht, den Text festzunageln (dann wäre das Panel eine grellweiße
Insel im dunklen Widget), sondern die Fläche mitkippen zu lassen. Damit ist
`debug-panel.component.scss` die erste Datei, die bewusst nicht mehr
ALT-verbatim ist; die Begründung steht im Dateikopf.

**Drei weitere Funde derselben Suche:**

1. Zwei feste Hex-Werte im `style`-Attribut des Templates
   (`debug-panel.component.ts:228-229`, `#1f7a39` / `#ad6f00`) — dunkel gemessen
   **3,19:1** und **4,11:1**. Beide sagten dasselbe wie die Klassen `.debug-ok`
   und `.debug-warn` zwei Zeilen weiter oben; sie wurden durch die Klassen
   ersetzt statt neu eingefärbt. Ein `grep` über `.scss` hätte sie nie gefunden.
2. `.debug-warn` / `.debug-ok` sind die **einzigen zwei Farben des Panels, die
   etwas bedeuten**. Sie behalten darum ihren Farbton und bekommen je Schema
   einen eigenen Wert, statt auf eine neutrale Rolle zu wandern — M3 hat für
   „gut" keine Rolle (`error` gibt es, „success" nicht).
3. `card-list.component.scss` trug zwei Farbvariablen **ohne einen einzigen
   Leser** (`$border`, `$text-muted: #767676` — letztere mit einem Kommentar, der
   ihre Knappheit auf Weiß erklärt). Beide einwertig, also blind fürs Schema:
   ein späterer Griff danach hätte im Dunkeln stillschweigend danebengelegen.
   Ersatzlos entfallen.

**Der letzte Test ist der wichtigste.** Er schleust einen zu schwachen Grauton
in die Blase und verlangt, dass der Messer ihn findet. Ohne ihn wären die
anderen vier auch dann grün, wenn die Messung gar nichts misst — dazu passend
eine Untergrenze auf die Zahl der gemessenen Texte, denn ein leerer Lauf wäre
sonst der beste aller Läufe.

**Damit die Messung etwas zu messen hat**, ist die Debug-Nutzlast in den
Fixtures voll ausgefüllt (`debugInfo()`), mit **gegenläufigen** Flaggen:
`plausible: true` rendert `.debug-ok`, `llm_engine_match: false` rendert
`.debug-warn` — beide Bedeutungsfarben stehen gleichzeitig im Bild.

Gemessen, je engster Fall (hell / dunkel):

| Stelle | hell | dunkel |
| --- | --- | --- |
| `.debug-warn` (ALT-Wert hell) | **4,55** | 7,92 |
| `.debug-ok` | 4,97 | 8,36 |
| `.debug-label` (Markenfarbe) | 8,46 | 5,93 |
| `.card-license-badge` | 7,22 | 7,22 |
| `.card-desc` / `.card-source` | 8,88 | 14,38 |
| Quick-Reply (`mdc-button__label`) | 10,00 | 10,27 |
| Fließtext / Überschrift / Karte | 16,39 | 14,38 |

Abdeckung: **88 Texte in 27 Selektoren** je Schema. `.debug-warn` liegt hell mit
**4,55:1** nur 0,05 über der Grenze — der ALT-Wert, gerade noch konform. Wenn
die Panel-Fläche je einen Ton heller wird, geht das Tor rot. Das ist gewollt.

**Grenze, bewusst:** geprüft wird SC 1.4.3 (Textkontrast). SC 1.4.11
(Bedienelement-Ränder ≥ 3:1) misst dieses Werkzeug nicht — Ränder haben keinen
Textknoten. Die Ränder der Kopfzeile sind in U4b von Hand belegt.

Kein CI-Schritt nötig: `npx playwright test` läuft dort schon (`ci.yml:146`).

### Offener Doku-Durchgang (aus U4a, gilt weiter)

**Gefunden, NICHT gefixt (gehört in keine dieser Scheiben):** die §5.5-Liste im
Neubau-Plan (`2026-07-10-…:384-390`) steht noch auf **18** Attributen und kennt
`language`, `embed-mode`, `size` und `show-cards` nicht; die Ereignisnamen
darunter sind noch die alten `badboerdi:`. Das ist seit U1/U2/U5a offen. Nur
`theme` in eine mit „18" beschriftete Liste nachzutragen, machte es schlimmer —
das ist ein eigener Doku-Durchgang. Der lebende Vertrag
(`widget-contract-data.ts` + die Attribut-Spec der Hülle) ist aktuell.

## U6 — Nachbesserungen aus dem ersten Test (2026-08-09)

Drei Punkte aus der Rückmeldung, ein vierter kam nach.

**U6 (erledigt).** Die Redaktions-Knöpfe (`header-nav.yaml`) stehen jetzt VORN in
`.boerdi-header-actions`, in einer eigenen `.boerdi-nav-group` mit
`margin-inline-end: 12px`. Begründung im Code: sie führen aus dem Chat HERAUS auf
die Webseite, die Knöpfe rechts daneben bedienen den Chat SELBST — ohne die Lücke
stehen sieben gleich aussehende Symbole in einer Reihe. Bewusst nur ein Abstand,
kein Trennstrich: eine Linie im Farbband wäre ein zweites Gestaltungsmittel für
dieselbe Aussage. Seed: `fachportale` von `topic` auf `menu_book`; die Lupe war
schon `search`. Die laufende Instanz zieht das NICHT nach — `import-config`
überschriebe den ganzen Config-Baum für ein Symbol, also macht es die Redaktion
im Studio.

Die gemeldeten „fehlenden Kacheln im großen Modus" ließen sich nicht
reproduzieren: sauberer Lauf = klein Textlink-Boxen, groß 9 Kacheln, zurück
Boxen. Auf dem Bild war der Zug fehlgeschlagen — ohne Treffer keine Kacheln.

**U6b (erledigt) — der Such-Absprung bleibt im großen Modus.** Nutzer-Vorgabe:
„was im großen modus drin bleiben sollte ist der absprung button zur suche mit
entsprechenden filter." Er hing bis dahin INLINE in `result-groups`, und U2b
zeigt im großen Modus stattdessen das Kachelraster — die Funktion fiel also
genau in der Stufe weg, die sie am ehesten braucht. Das ist ein Defekt von U2b,
kein Wunsch.

- Neu: `grouping/search-cta.component.ts` + `.scss`. Der Block ist verbatim
  umgezogen, das gerenderte DOM ist unverändert (Klassen `result-group--cta`
  &c.) — die Bestandstests der Gruppen-Box liefen ohne Anpassung weiter.
- `_result-group.scss` gibt die CTA-Regeln ab. Verhaltenserhaltend, weil `--cta`
  JEDE Eigenschaft der Basisklasse überschrieb (border, radius, padding,
  background). Angular-Komponentenstile reichen nicht in ein Kind hinein — die
  Regeln MUSSTEN mitziehen.
- `ResultGroupsContext` wandert von `result-groups.component.ts` nach
  `result-grouping.ts`. Grund: die Gruppen-Box importiert bereits einen Typ AUS
  `cards/`; hätte das Raster den Kontext von ihr geholt, wäre ein Ring
  entstanden. Die Shell reicht dem Raster jetzt `resultGroupsCtx`.
- Zwei Tests zuerst (einer rot: „expected null not to be null"), dann gebaut.

**Offen aus U6b, NICHT gebaut** (eigene Entscheidung, kein Nebenbei-Fix):
`domain/inline_grouping.py` sagt dem Modell „Einzelinhalte sind NICHT sichtbar,
nur über die Such-CTA erreichbar". Seit U2b stimmt das im großen Modus nicht
mehr — dort SIND sie als Kacheln sichtbar. Der Prompt kennt nur
`inline_result_grouping`, nicht die Größenstufe. Folge ist ein schiefer Satz,
kein Ausfall. Sauber wäre, dass der Client die aktive Darstellung mitschickt —
das ist eine Vertragsfrage und gehört nicht in diesen Commit.

## U5a — Ereignisse heißen `boerdi:` (erledigt 2026-08-09)

Nutzer-Entscheid: umbenennen, mit Doppelversand während P11.

Neu: `ui/src/host-events/event-names.ts` — die vier Namen und `dispatchHostEvent`
an EINER Stelle. Vorher standen sie als Zeichenketten an sechs Stellen (vier
Sender, zwei Zuhörer); ein Umbenennen hieße, alle gleichzeitig zu treffen, und
die Doppelung hieße, alle zu verdoppeln.

**Gesendet wird zweimal, gehört wird einmal.** Die Widget-Hülle hört auf zwei
dieser Ereignisse als Rückfallweg für ihre eigene Chat-Shell. Hörte sie auch auf
den alten Namen, liefe jede Seiten-Aktion doppelt — einmal navigieren, einmal
nochmal. Der alte Name ist Nachsicht gegenüber FREMDEN Empfängern, kein Eingang;
die Studio-Vertragstabelle und die Demo-Seite zeigen deshalb nur den neuen.

**Was der Test gefunden hat, bevor es jemand gemerkt hätte:** `destroy()` nahm
die Zuhörer weiter unter den ALTEN Namen ab — die unter den neuen Namen
registrierten wären nie abgemeldet worden. Ein Leck, das keine Sichtprüfung des
Diffs gezeigt hätte, weil an- und abmelden 40 Zeilen auseinanderliegen.

**Eigener Fehler, protokolliert:** ein Generator-Skript schrieb ein echtes
Backspace-Zeichen (0x08) statt `\b` in den Backend-Test; die Regex traf dadurch
nichts und der Wächter wurde blind. Sichtbar wurde es erst, weil der Test rot
blieb. Ersetzt durch eine Ausschau nach hinten `(?<!bad)boerdi:` — ohne
Escape-Zeichen, damit derselbe Unfall nicht wiederkommen kann. **Regel: Wächter
ohne Escapes schreiben, wenn es geht.**

## Der Prompt und die Darstellungsform — gemessen, nicht gebaut

Aus U6b stammte die Sorge, `domain/inline_grouping.py` sage dem Modell
„Einzelinhalte sind NICHT sichtbar, nur über die Such-CTA erreichbar", während
der große Modus sie als Kacheln zeigt. **Die Messung sagt etwas anderes — meine
Sorge war in der Richtung falsch.**

Drei Fakten:

1. `response_prompt_builder.py:139` schaltet den Block nur ein, wenn
   `environment.cards_enabled is False` **und** `inline_result_grouping is not
   False`.
2. Das Widget sendet **weder das eine noch das andere**. Das `Environment` in
   `stream/chat-api.ts:20-35` hat die Felder nicht — nicht auf `false`, sondern
   gar nicht.
3. ⇒ `_inline_grouping_mode` ist **immer falsch**. Weder der UI-BOX-STATUS-Fuß
   noch die Redaktion der Einzelinhalte (`_redact_search_content_for_llm`)
   laufen jemals. Der Prompt beschreibt dem Modell durchgehend das Kachelraster.

Damit ist der Apparat der **10. Fall der Klasse „dokumentiert ohne Konsumenten"**
— und der erste, der ein Tor besitzt, das live aussieht.

**Zweiter Befund: dasselbe Konzept, zwei Formeln.** `turn_links.py:154` und
`widget_postprocess.py:697` rechnen `_grouping_on = (ig is not False) and not
legacy` — bei denselben fehlenden Feldern ergibt das **wahr**. Off-Topic-Filter
und Link-Re-Extraktion laufen also im Gruppen-Modus, der Prompt nicht. Zwei
Formeln, gleiche Eingabe, entgegengesetztes Ergebnis.

**Warum ich das NICHT wie besprochen verdrahtet habe.** „Das Widget schickt die
aktive Darstellung mit" würde den Block scharf schalten — und sein Text ist
inzwischen sachlich falsch: die Gruppen-Box hat seit Welle E eine
**Materialien-Box** (`result-groups.component.ts`, `groupedContentCards`), die
Einzelinhalte sehr wohl zeigt. Das Feld zu senden hieße, dem Modell eine
Unwahrheit einzuschalten, die es heute nicht liest. Erst der Text, dann der
Schalter.

**Drei Wege, Empfehlung zuerst:**

- **A (empfohlen): den Apparat löschen.** `_ui_box_state_footer` und
  `_redact_search_content_for_llm` samt Parameter-Durchreichung raus; die
  Anti-Halluzinations-Absicht ist durch den Wächter aus C1-f2b4 und die
  Wahrheitspflicht im Basis-Prompt abgedeckt. Kleinster Eingriff, entfernt eine
  Falle.
- **B: Text richtigstellen, dann verdrahten.** Ein Feld `rendering: "boxes" |
  "tiles"` im `environment` (additive Vertragsänderung), Block-Text neu
  schreiben (was ist je Form sichtbar), beide Formeln auf EINE ziehen. Mehr
  Arbeit, und der Nutzen ist unbelegt — niemand hat je eine Halluzination
  dieser Art im NEU-System gesehen.
- **C: nichts tun**, den Befund im Plan lassen. Kein Ausfall, aber die Falle
  bleibt: wer irgendwann `cards_enabled: false` sendet, schaltet unbemerkt einen
  falschen Prompt scharf.

Entscheidung offen — sie gehört dem Nutzer, weil A Code entfernt, den ALT
bewusst gebaut hat.

**Nicht verifiziert:** die Pixelbreite der großen Stufe (`clamp(480px, 56vw,
1280px)`). Der Browser-Bereich war auch diesmal nicht eingeblendet; die Seite
kompositiert dann keine Frames und friert die Layout-Werte ein — `offsetWidth`
lieferte für klein und groß denselben Wert, und selbst ein per Hand gesetztes
`width: 900px !important` änderte die Zahl nicht. Das sind Messartefakte, keine
Befunde. DOM-Abfragen (Kachel-/CTA-Zählung, Host-Klasse) sind davon unberührt
und wurden live bestätigt. **Regel, zum zweiten Mal:** Layout misst man im
Browser — und nur, wenn der auch anzeigt.

## U8 — Bedienpult auf den Demo-Seiten (erledigt 2026-08-09)

Nutzer-Rückmeldung: „prüfe bitte ob die widget seiten alle parameter korrekt
unterstützen — sowas wie embedded usw. ging nicht. auch ein hell und dunkles
design umschalter von außen wäre nett."

**Der Befund zuerst, denn er ist nicht der erwartete.** Die Attribute stimmen
alle. Nachgemessen am laufenden Element auf allen vier Seiten:
`embed-mode="frameless"` greift (kein Eulen-Knopf, keine Kopfzeile, Klasse
`boerdi-frameless`), `show-debug-button="false"` greift, `inline-result-grouping`
greift. Was **nicht** greift, ist eine Erwartung an einen Namen:

> `show-language-buttons` schaltet die **Sprach-AUSGABE** (Mikrofon + Vorlesen),
> nicht den EN/DE-Umschalter.

Der Name ist ALT-Erbe. Solange es nur die Sprachausgabe gab, war er eindeutig;
seit C1-c sitzt daneben ein Sprach-Umschalter in der Kopfzeile, und der Text der
Seite „ohne die beiden Bedien-Knöpfe für **Sprache** und Debug" versprach genau
das, was er nicht hält. Wer die Seite öffnete, sah den EN-Chip stehen und schloss
auf einen Defekt. Der Satz ist ersetzt und nennt jetzt beide Attributnamen
wörtlich.

**Die eigentliche Lücke war eine andere:** die vier Seiten zeigten je EINE feste
Kombination, zusammen **acht der 23 Host-Attribute**. `theme`, `size`,
`show-cards`, `language`, `primary-color`, `initial-state` liessen sich auf
keiner Seite ausprobieren. „Geht nicht" liest sich schnell wie ein Defekt, wenn
es gar keinen Weg gibt, es zu sehen.

Neu: `backend/src/boerdi/api/widget_demo_controls.py` — ein Bedienpult über dem
Einbettungs-Beispiel, auf allen vier Seiten. Neun Attribut-Schalter, ein
Farbwähler, plus der gewünschte Umschalter — **zwei** davon, und das ist der
Punkt:

| Schalter | stellt | zeigt |
| --- | --- | --- |
| Farbschema der Gastseite | `color-scheme` am `<html>` | wie das Widget einer fremden Seite folgt |
| Widget-Farbschema | `theme` | wann es das **nicht** mehr tut |

Mit einem einzigen Schalter liesse sich die Regel aus U4a auf keiner Demo-Seite
vorführen. Live nachgemessen: Seite dunkel + `theme=auto` → Widget dunkel; Seite
dunkel + `theme=light` → Widget hell.

**Serverseitig gebaut, nicht per JavaScript.** Die naheliegende Fassung erzeugt
die Felder im Browser aus einer JSON-Liste und liest den Anfangswert aus dem
Element zurück. Der ist aber schon bekannt — die Seite hat die Attribute selbst
gesetzt. Also speist **eine** Quelle Element und Pult; `selected` steht im HTML,
ein Test kann es lesen, und übrig bleibt ein Skript, das nur zuhört.

**Ehrlich statt bequem bei zwei Attributen.** `size` und `initial-state` sind
laut Vertrag Startwerte — ein `setAttribute` darauf tut nichts. Statt sie
wegzulassen oder so zu tun, als wirkten sie, baut das Pult das Element neu auf
und schreibt „(Neustart)" ins Etikett. Der Verlauf überlebt, er hängt an der
Sitzungs-ID im `localStorage`.

**Der Fehler, den der Live-Lauf fand — mein eigener.** Die erste Fassung hielt
das Element in einer Variablen: `var el = document.querySelector('boerdi-chat')`.
Das Pult steht im Dokument aber ÜBER dem Element (es ist eine Bedienleiste, die
gehört nach oben), also war `el` beim Laden `null` und **jeder** Schalter warf
still eine TypeError in die Konsole — sichtbar als „nichts passiert". Sechs
Backend-Tests waren grün, weil sie das HTML prüfen, nicht die Ausführung. Erst
das Klicken im Browser hat es gezeigt. Behoben durch Nachschlagen bei jedem
Zugriff, was zugleich den zweiten Fall löst: nach `neuAufbauen()` zeigte eine
gehaltene Referenz auf ein Element ausserhalb des Dokuments.

**Ein Wächter gegen die zweite Kopie.** Die Attributliste des Pults ist die
zweite Liste im Repo — und dieses Projekt hat schon zweimal eine driften sehen.
`test_no_control_promises_an_attribute_the_element_does_not_have` liest den
lebenden Vertrag (`widget-contract-data.ts`) und vergleicht. Gegenprobe: ein
erfundenes `show-owl-hat` wird gemeldet, die echte Liste ist leer.

**Bewusst nicht im Pult:** `api-url`, `page-context`, `auto-context`,
`trusted-domains`, `session-*`, `intercept-edu-sharing-links`, `emit-*`,
`greeting`. Sie ändern nichts Sichtbares oder nähmen der Seite ihre eigene
Aufgabe — die `emit-*` speisen den Ereignis-Spiegel, `api-url` die Verbindung.

**Offen, Produktentscheidung des Nutzers:** der EN/DE-Umschalter hat **kein**
Host-Attribut. Ein Portal, das einsprachig deutsch auftritt, kann ihn nicht
abschalten. Das wäre das 24. Attribut (`show-language-switch`) — Vertrag,
Studio-Katalog de/en, Referenzseite. Empfehlung: bauen, sobald ein Einbetter
danach fragt; vorher ist es Vorrat.

## W7 — ONNX-Cross-Encoder zurück (erledigt 2026-08-09)

Nutzer-Auftrag: „onnx und reranker zurückholen und integrieren — an allen
Stellen wie im alten chatbot auch". Auslöser war seine Erinnerung, ALTs RAG sei
mit Reranker nachweislich besser gewesen. **Sie stimmt, und meine vorige Aussage
war falsch.**

**Die Korrektur.** Der V13-Kommentar begründete den Wegfall damit, ein
*Bi-Encoder*-Rerank mit demselben Embedder reproduziere die pgvector-Reihenfolge.
Das ist richtig — und schliesst genau diese eine Alternative aus. ALT benutzte
einen **Cross-Encoder**, der Frage und Textstück gemeinsam durch ein Netz
schickt; er kann die Embedding-Reihenfolge gar nicht reproduzieren. Der Beleg
lag die ganze Zeit im ALT-Repo: `scripts/eval_reranker_result.json` —
**10 Anfragen, 8 Rerank-Siege, 0 Baseline-Siege, 2 Unentschieden**, je zwei
Judges mit getauschten Positionen.

**Zwei Verbraucher, ein Modell** (die zweite Stelle war die Frage des Nutzers):

| | ALT | vorher | jetzt |
| --- | --- | --- | --- |
| RAG-Chunks | `rag_service.py:651` im Pool | direkter Aufruf, Backend `None` | `run_in_rerank_pool` |
| WLO-Karten | `chat_turn_answer.py:307–339` im Pool | direkter Aufruf, Backend `None` | `run_in_rerank_pool` |
| Start-Warmup | `main.py:143` | fehlte | `warm_cross_encoder` |

**Der gefährlichste Teil war nicht das Modell, sondern der Ausführungsort.**
Beide Aufrufstellen hatten den Pool entfernt, mit der Begründung „das Gate ist
synchron und deterministisch". Das stimmte, solange hinter dem Seam nichts hing.
Mit echtem ONNX sind das 0,2–3 s CPU **im Event-Loop** — in dieser Zeit steht
der ganze Worker samt der SSE-Ströme aller anderen Nutzer. „Synchron" sagt etwas
über Determinismus, nichts über den Ausführungsort.

**Ein Paket leichter als ALT:** kein `transformers`. Gemessen — die
`tokenizer.json` des Exports reicht `tokenizers` allein, und das Modell (XLM-R)
kennt keine `token_type_ids`. Laufzeit: `onnxruntime` (MIT), `tokenizers`
(Apache-2.0), `numpy` — kein Torch. Lizenz-Gate bestanden.

**Das CPU-Budget, nach Nutzer-Vorgabe „halbe System-CPU".** Zwei Knöpfe spannen
dasselbe Budget aus zwei Richtungen auf:

    RERANK_MAX_CONCURRENCY (Worker) × RERANK_INTRA_OP_THREADS (Kerne je Inferenz)

Vorgabe: `max(1, cpu_count // 2)` Worker à 1 Thread. Gemessen (25 Paare):

| Text | intra_op=1 | 2 | 3 | 4 | 6 |
| --- | --- | --- | --- | --- | --- |
| RAG-Chunk (~900 Z.) | 3079 ms | 2138 | 1795 | 1489 | 1274 |
| Kartenzeile (~180 Z.) | 507 ms | 299 | 232 | 201 | 217 |

**Textlänge schlägt alles** — ein Chunk kostet das Sechsfache einer Kartenzeile.
Daraus die Betriebsregel: wer *Durchsatz* will, nimmt viele Worker à 1 Thread;
wer *kurze Einzel-Latenz* will, wenige Worker à mehreren Threads. Gleiches
Budget, andere Verteilung. Die Startzeile nennt beide Zahlen und ihr Produkt.

**Zwei Bestandstests geändert, beide mit Begründung im Code:**
`test_seam_has_no_backend_today` pinnte die ABWESENHEIT des Backends (Test war
nicht falsch — er hielt eine Entscheidung fest, die gekippt ist), und
`test_fallback_sorts_…` verliess sich darauf, dass es keines gibt.

**Ein Testplatz-Fehler nebenbei gefunden und behoben:** die
`test_rag_retrieval`-Familie lief **je nach Umgebung anders** — lokal mit
Modell-Asset sortierte der CE um und das Etikett trug `| Rerank: …`, in CI ohne
Asset nicht. Zwei Ergebnisse für denselben Test sind kein Test. `_wire` schaltet
den CE jetzt ausdrücklich ab; der CE-Pfad hat seinen eigenen Test mit Attrappe.

Live belegt (Start, echtes Asset):

    Rerank-Threadpool: max_workers=8
    Reranker geladen: cross-encoder__mmarco-…-int8 · 8 Worker × 1 Thread(e) = 8 von 16 Kernen
    cross-encoder warmup done in 1996ms

**Offen, Nutzer-Entscheidungen:** (1) wie das 135-MB-Asset ins Image kommt —
Git LFS oder Build-Zeit-Download; heute liegt es unter `backend/models/`.
(2) Golden-Referenzlauf: die Kartenauswahl ändert sich sichtbar, weil das
absolute Off-Topic-Gate wieder greift. (3) **Noch nicht gemessen:** das lokale
ONNX-Embedding (bekko) — eigenes Paket.

## W8 — Lokales Embedding als Option (erledigt 2026-08-09)

Nutzer-Entscheid 2026-08-09: „wir werden aber wohl auf openai oder mistral
embeddings bleiben — die sind über api einfach schneller und der chatbot ist
zeitkritisch. das lokale embedding bleibt aber im code um eine option zu haben."

Also **eine Naht, kein Umzug.** Die Vorgabe bleibt `api`; ein Test pinnt genau
das, damit die Option nicht versehentlich zum Standard wird.

**Die Fassade sitzt in `services/rag/embed.py`, nicht in `llm.py`.** Vorher
riefen vier Stellen den LiteLLM-Transport direkt. Der ist der richtige Baustein
für den Anbieter-Weg und der falsche Ort für eine Wahl: `llm.py` darf nichts
über RAG oder ONNX wissen, sonst zeigt die Abhängigkeit nach aussen und es
entsteht ein Ring mit `rag/retrieval`.

**`kind` ist Pflicht, nicht Vorrat.** e5-Modelle verlangen `query:`/`passage:`-
Präfixe; ohne sie sucht das Modell messbar schlechter — und zwar lautlos. Die
Aufrufer wissen es ohnehin (die Suche fragt, der Ingest speichert), also trägt
die Naht es. MiniLM und bekko brauchen keine; genau dieser Unterschied steht in
`LOCAL_MODELS` statt im Kopf des Betreibers.

Drei Kandidaten, alle **384-dimensional** (Voraussetzung dafür, dass sie ohne
Schema-Änderung gegeneinander austauschbar sind), ein Test hält das fest:

| Modell | Präfixe | Anmerkung |
| --- | --- | --- |
| `multilingual-e5-small` | ja | intfloat, 118M — Vorgabe |
| `paraphrase-multilingual-MiniLM-L12-v2` | nein | sentence-transformers, 118M |
| `bekko-embedding-v1-a8m` | nein | hotchpotch, 7,7M aktiv, MIT, ~124 MiB |

**Korrektur zur bekko-Annahme des Nutzers:** die ~124 MiB sind die *normale*
ONNX-Variante; eine int8-Fassung gibt es, sie ist vom Autor aber ausdrücklich
„not recommended". Und `a3m` existiert nicht — es gibt `a8m` und das grössere
`a25m`.

**Ehrliche Lücke.** Die reinen Teile sind getestet (Backend-Wahl, Dimension,
Präfixe, Fehlerpfade, dass ein Tippfehler in `EMBED_BACKEND` ein Fehler ist und
kein stiller Rückfall). **Der ONNX-Inferenz-Pfad selbst ist NICHT gegen ein
echtes Modell belegt** — kein Asset heruntergeladen, weil der Betrieb dort nicht
hin will. Wer ihn nutzen will, lädt einen Export nach `backend/models/<slug>/`
und setzt `EMBED_BACKEND=local`; der Startlog nennt Modell und Dimension. Bis
dahin gilt: die Option ist gebaut und geprüft, aber nicht bewiesen.

**Nebenbefund derselben Klasse wie schon achtmal:** `get_always_on_rag_context`
hat **keinen Produktiv-Aufrufer** — nur Tests. Der in der Plan-Zeile 6-1
beschriebene Area-Modus „always" ist nicht verdrahtet. Folge für die
Default-Frage unten: der teure RAG-Rerank feuert **nur**, wenn das LLM das
Wissens-Werkzeug ruft, nicht bei jedem Zug.

## W9 — Rerank-Kosten steuerbar machen (erledigt 2026-08-09)

Nutzer-Rückfrage: „die kosten für das reranking sind nicht ganz ohne … wir
können nur 3-4 cpu kerne nutzen … was würde es mit 3 kernen und 10 kandidaten
kosten?"

Gemessen auf **AMD Ryzen 7 7730U (8 Kerne, 2,0 GHz Basis — ein Mobil-Prozessor,
kein Desktop)**, Chunks à **1000 Zeichen** (die echte Chunk-Größe aus
`chunk_markdown(max_chunk=1000)`), Median aus 5 Läufen:

| Kandidaten | intra=1 | intra=2 | **intra=3** | intra=4 |
| --- | --- | --- | --- | --- |
| 25 (ALT-Vorgabe) | 3726 ms | 2225 | **1853** | 1628 |
| 15 | 2132 | 1346 | **1070** | 932 |
| **10** | 1471 | 840 | **703** | 617 |
| 5 | 707 | 409 | **338** | 289 |

Karten-Gate (Zeilen à ~130 Zeichen): 25 Karten = **227 ms** bei intra=3, 10 = 90 ms.

**Zwei Befunde, die die Entscheidung tragen:**

1. **Die Kandidatenzahl dominiert die Latenz**, nicht die Threadzahl. Von 25 auf
   10 spart mehr als von 1 auf 4 Threads. Sie stand als Konstante im Code.
2. **Die beiden Pfade kosten 8:1** (1853 gegen 227 ms bei je 25 Elementen) und
   hingen an EINEM Schalter. Wer den teuren loswerden wollte, verlor das billige
   Off-Topic-Gate der Karten gleich mit — den Teil, der sichtbar Qualität
   bringt.

**Eine Wechselwirkung, die man sonst erst im Betrieb merkt:** der Aufrufer nimmt
`max(RERANK_CANDIDATES, RAG_TOP_K)`. Wer die Kandidaten auf 10 setzt, aber
`RAG_TOP_K=15` stehen lässt, bekommt 15 → 1070 statt 703 ms. Steht jetzt im
Feld-Text der Settings **und** im Docstring von `rerank_candidates()`.

Drei Knöpfe, alle mit gemessener Begründung im Code:

| Knopf | Vorgabe | wirkt auf |
| --- | --- | --- |
| `RAG_RERANKER_ENABLED` | true | Hauptschalter (lädt das Modell überhaupt) — ALT-verbatim |
| `CARD_RERANKER_ENABLED` | true | Off-Topic-Gate der Karten (billig) |
| `RAG_CHUNK_RERANKER_ENABLED` | true | Cross-Encoder über die RAG-Chunks (teuer) |
| `RERANK_CANDIDATES` | 25 | Chunks in den RAG-Rerank — **der Latenz-Hebel** |

Die Vorgaben bleiben ALT-treu; die Empfehlung für den 6-Kern-Server steht im
Bericht, nicht im Code — welche Zahl dort steht, ist eine Produktentscheidung
und keine Voreinstellung, die ich still ändere.

## W10 — Vorgaben auf Geschwindigkeit (erledigt 2026-08-09)

Nutzer-Entscheid: „standardmäßig reranker aber ausschalten und nur optional
zuschaltbar halten. wir gehen erstmal auf max. geschwindigkeit." Plus: beim
Einschalten 10 Kandidaten, `RAG_TOP_K` zieht mit.

| Vorgabe | vorher | jetzt | Grund |
| --- | --- | --- | --- |
| `RAG_RERANKER_ENABLED` | true (ALT) | **false** | Modell wird gar nicht geladen |
| `RERANK_CANDIDATES` | 25 (ALT) | **10** | 703 statt 1853 ms bei 3 Threads |
| `RAG_TOP_K` (`_RAG_DEFAULTS`) | 15 (ALT) | **10** | sonst greift `max(10, 15)` = 15 |

**Der Fehler, den erst der Live-Start fand — mein eigener.** Nach dem Setzen der
Vorgabe meldete das Startlog weiterhin „Reranker geladen". Ursache: die
Doppelung, die ich eine Scheibe vorher bewusst stehen liess.
`_reranker_enabled_via_env()` las `os.getenv` direkt und gab bei UNBESETZTER
Variable ALT-verbatim `True` zurück — **an den Settings vorbei**. Zwei Leser
derselben Variablen, und der ALT-Zweig gewann. Behoben: bei leerer Variable
entscheiden die Settings; bei gesetzter bleibt ALTs Wertetabelle unverändert.
2580 grüne Tests hatten das nicht gezeigt — nur der Start.

Belegt (Start mit Vorgaben):

    Reranker per RAG_RERANKER_ENABLED abgeschaltet — embedding-only
    (0 Zeilen „Reranker geladen")

### Blockiert etwas? — der Durchgang

| Stelle | Befund |
| --- | --- |
| Karten-Gate | im gedeckelten Pool (W7); bei Vorgabe aus: 0 |
| RAG-Rerank | im gedeckelten Pool (W7); bei Vorgabe aus: 0 |
| Lokales Embedding | im selben Pool (W8) |
| Chat-Embedding | **eine** Anfrage je RAG-Suche, über alle Bereiche wiederverwendet; `LLM_MAX_CONCURRENCY`=20 |
| **Ingest-Embedding** | **war der Blocker** — streng seriell, ein Netz-Roundtrip JE Chunk |

Der Ingest bettete in einer `for`-Schleife mit `await` ein: bei 906 Chunks 906
Wartezeiten hintereinander. Neu `embed_many` — gedeckelt nebenläufig, Reihenfolge
erhalten, Fehler je Chunk isoliert.

**Der Deckel ist ein EIGENER** (`EMBED_INGEST_PARALLEL`, Vorgabe 4) und nicht der
`LLM_MAX_CONCURRENCY`-Semaphor des Chats. Grund: sonst könnte ein
Redaktions-Import alle 20 Plätze belegen und die Züge echter Nutzer warten
lassen — genau das Blockieren, das vermieden werden soll.

**Ein Test hat dabei einen echten Verlust gefunden:** die Chunk-ID im
Fehler-Log. `embed_many` kennt den Grund, aber nicht die Zeile; ohne eine zweite
Log-Zeile im Aufrufer hätte der Betrieb die ID verloren — also genau die Angabe,
mit der man den kaputten Chunk findet.

**Offen, Nutzer-Domäne:** ob der Anbieter **Sammel-Embedding** (Array im
`input`-Feld) kann. Das wäre der grössere Hebel als Nebenläufigkeit — 906 Chunks
in ~10 Anfragen statt 906. OpenAI kann es; für die AcademicCloud-Route ist es
unbelegt und braucht einen Live-Versuch mit echtem Schlüssel.

## W11 — Standard-Config bestätigt (erledigt 2026-08-09)

Nutzer-Korrektur, eine Nachricht nach W10: „ich korrigiere nochmal folge deiner
standard konfig". W10s Vorgabe AUS ist damit zurückgenommen.

| Knopf | Wert | Herkunft |
| --- | --- | --- |
| `RAG_RERANKER_ENABLED` | **true** | wie ALT |
| `CARD_RERANKER_ENABLED` | true | W9 |
| `RAG_CHUNK_RERANKER_ENABLED` | true | W9 |
| `RERANK_CANDIDATES` | 10 | ALT hatte 25 — gemessen 703 statt 1853 ms |
| `RAG_TOP_K` | 10 | zieht mit, sonst `max(10, 15)` = 15 |
| `RERANK_MAX_CONCURRENCY` | **1** | Latenz vor Durchsatz |
| `RERANK_INTRA_OP_THREADS` | **abgeleitet, hier 3** | siehe unten |

**Eine Abweichung von der wörtlichen Vorgabe, bewusst.** Der Nutzer nannte
`RERANK_INTRA_OP_THREADS=3` — richtig für SEINEN 6-Kern-Server. Als harte
Konstante wäre das auf einem 2-Kern-Server Überbuchung: genau der Fehler, den
ALTs Lasttest lt-e91ef209c1d6 teuer gelernt hat (CPU-Spitze 13/16, Tail 85 s).
Deshalb abgeleitet: `min(3, halbe CPU)`. Auf 6 Kernen ergibt das **exakt 3**, auf
4 Kernen 2, auf 2 Kernen 1 — und nie mehr als die Hälfte. Der Deckel bei 3 ist
gemessen: darüber wird es kaum noch schneller (25 Chunks: 1853 ms bei 3 Threads,
1628 ms bei 4). Wer einen festen Wert will, setzt die Variable.

Dieselbe Logik beim Gegenstück: `RERANK_MAX_CONCURRENCY` ist jetzt **1** statt
„halbe CPU". Das Budget steckt damit vollständig in den Threads JE Inferenz —
dieselbe halbe Maschine, nur auf Latenz verteilt statt auf Durchsatz. Steigt die
Gleichzeitigkeit, dreht man es um; beide Knöpfe bleiben.

Live belegt:

    Rerank-Threadpool: max_workers=1
    Reranker geladen: cross-encoder__…-int8 · 1 Worker × 3 Thread(e) = 3 von 16 Kernen
    cross-encoder warmup done in 2110ms

Ein Test hält die ganze Standard-Config an einer Stelle fest
(`test_the_standard_config_of_a_six_core_server`) — inklusive der Rechnung
`Worker × Threads = 3 = halbe CPU`, damit eine spätere Änderung an einem der
beiden Knöpfe nicht still das Budget verdoppelt.

---

## W12 — Modellwechsel auf `gpt-5.6-luna` + EU-AI-Act-Kennzeichnung

**Nutzer-Vorgabe:** Standardmodell `gpt-5.6-luna`, Reasoning niedrig, Verbosity
niedrig, Ziel hohe Geschwindigkeit; dazu die nach Art. 50 EU-AI-Act nötige
Offenlegung, dass hier eine KI antwortet und kein Mensch.

### W12a — Umstellung, Parameter, Kennzeichnung

`_PROVIDER_DEFAULTS` (`openai` + `b-api-openai`) auf `gpt-5.6-luna`;
`llm_verbosity` von `medium` auf `low`; die erlaubte Menge für
`LLM_REASONING_EFFORT` um **`max`** ergänzt (der Wert existiert laut Doku, wurde
beim Start aber als Tippfehler abgewiesen).

Ein Bestandstest hat dabei etwas Echtes gefangen: die Temperatur-Ausnahme ist an
die **5.4-Familie** gepinnt (`startswith("gpt-5.4")`). Ein pauschales Umbenennen
auf das neue Modell machte ihn zu Recht rot.

Kennzeichnung an **zwei** Stellen, weil eine nicht reicht:
* Begrüßung (Seed, de + en) — das ist der erste Kontakt und damit der Ort, den
  Art. 50 meint.
* Unter jeder Bot-Antwort `chat.aiGenerated` — für alle, die mitten im Verlauf
  einsteigen oder zurückscrollen. Kein `aria-hidden`; der Hinweis steht NACH dem
  Inhalt, damit er nicht als Rauschen vorweg vorgelesen wird.

### W12b — Der Blocker, und warum die Fehlermeldung in die Irre führt

Der erste echte Zug scheiterte:

    Function tools with reasoning_effort are not supported for gpt-5.6-luna
    in /v1/chat/completions.

Naheliegende Lesart: „wir senden den Parameter, obwohl wir nicht dürfen." Diese
Lesart ist **falsch** — mit `LLM_REASONING_EFFORT=none` kam derselbe Fehler,
obwohl unser Gate den Parameter dann nachweislich gar nicht schickt.

Statt weiter zu raten: eine Matrix gegen die echte API, beide Familien.

| mit Werkzeugen | gpt-5.6-luna | gpt-5.4-mini |
|---|---|---|
| `reasoning_effort` **weggelassen** | ❌ 400 | ✅ tool_call |
| `reasoning_effort="none"` | ✅ tool_call | ✅ tool_call |
| `reasoning_effort="low"` | ✅ tool_call | ✅ tool_call |

Genau **eine** rote Zelle im ganzen Raster. Gemeint ist nicht „du hast zu viel
geschickt", sondern das Gegenteil: **ohne Angabe gilt das Vorgabe-Reasoning des
Anbieters, und DAS verträgt sich nicht mit Function Tools.** luna verlangt eine
ausdrückliche Angabe; `none` ist dabei ein echter API-Wert, kein Weglassen.

Unser Gate tat also seit W12a systematisch das Falsche — und weil praktisch jeder
Zug Werkzeuge trägt, war **jeder** Zug betroffen.

### Die Lösung: Modellgruppen statt verstreuter Präfix-Prüfungen

Die Ausnahmen standen als `startswith`-Prüfungen mitten in `build_chat_kwargs`.
Das ist der falsche Ort: dort entscheidet sich, WIE eine Anfrage gebaut wird,
nicht WAS ein bestimmtes Modell akzeptiert. Neu in `llm_models.py`:

* `ParamRules` (`gpt5_params`, `effort_with_tools`, `temperature_on_none`)
* `_GROUPS` — Präfix → Regeln, **längster Präfix gewinnt** (`gpt-5.6` vor `gpt-5`)
* `param_rules(model)` — inklusive der Provider-Sperre für `b-api-academiccloud`

`build_chat_kwargs` wertet nur noch aus. Ein neues Modell braucht damit eine
Zeile in der Tabelle statt einer weiteren Verzweigung im Bauplan.

Bewusst NICHT verallgemeinert: dass ein ausdrücklicher Wert auch mit Werkzeugen
durchgeht, ist für gpt-5.4 und gpt-5.6 gemessen — für o1/o3/o4 nicht. Dort bleibt
die vorsichtigere ALT-Regel stehen.

### Der zweite Fund: die Klassifikation hing an derselben Sache

Der volle Lauf legte einen zweiten roten Test frei — und der war kein Ärgernis,
sondern die andere Hälfte des Befunds. `classify.py` benutzt `instructor` im
`Mode.TOOLS`, und **instructor spritzt sein eigenes Werkzeug ein**: jede
Klassifikation ist am Draht ein Werkzeug-Aufruf. Der Gating-Marker sorgt nur
dafür, dass der richtige Zweig greift. Unter der alten Regel wäre also auch jede
*Klassifikation* am 400er gestorben; der Test pinnte das mit
(`"reasoning_effort" not in kw`). Erwartung nach der Messung korrigiert.

### Kennzeichnung optisch zurückgenommen (Nutzer-Wunsch)

Der Vermerk unter jeder Antwort war ein eigener Absatz mit 0,72 rem. Jetzt
0,68 rem und 2 px Abstand statt 6 — er hängt an der Blase statt darunter zu
stehen. **Die Farbe bleibt `on-surface-variant`:** die eigentliche Offenlegung
trägt die Begrüßung, diese Zeile ist die beiläufige Erinnerung und darf leise
sein — aber die untere Grenze ist SC 1.4.3, nicht Geschmack. Deshalb sinkt hier
die Größe, nicht der Kontrast. Der Wächter in `e2e/contrast.spec.ts` misst es in
hell und dunkel nach.

### Belege

    pytest -q                 → 2583 passed, 4 skipped
    ruff check .              → All checks passed
    export_openapi.py --check → openapi contract unchanged
    npx ng test ui            → 608 passed
    npx playwright test       → 39 passed (inkl. Kontrast-Gate)

Live gegen `gpt-5.6-luna`, `verbosity=low`, `reasoning_effort=none`:

    Hallo, wer bist du?              5695 ms · M15 · query_knowledge (prefetch)
    Suche Material Bruchrechnung     4869 ms · M06 · 5 Karten
    Erklaer mir, was ein Bruch ist   5990 ms · M04

**Nebenbefund zur Latenz — bewusst KEIN Urteil:** je drei Züge mit `none`
(7436 / 8262 / 13183 ms) und `low` (8334 / 15258 / 9594 ms). Eine Stichprobe je
Frage, und die dominante Streuung kommt nachweislich von der MCP-Suche
(1,2–23,3 s, siehe W1-Messung), nicht vom Modell. Die Zahlen trennen die beiden
Quellen nicht — ein belastbarer Vergleich braucht den Golden-/Lasttest-Lauf.

**Dritter Fall in Folge:** ein hängengebliebener uvicorn auf Port 8021 lieferte
alte Werte aus. `pkill` greift hier nicht; nötig ist
`Get-NetTCPConnection -LocalPort 8021 -State Listen` + `Stop-Process -Force`.
Vor jedem Live-Check zuerst den Listener prüfen.

---

## Klassifikations-Latenz — Voranalyse (2026-08-10, ZURÜCKGESTELLT)

Nutzer-Entscheid: „lassen wir erstmal so und optimieren das später". Kein Code
geändert. Hier stehen nur die Messungen, damit sie nicht neu erhoben werden
müssen — und zwei Defekte, die dabei aufgefallen sind.

### Zwei Defekte (offen, unabhängig von der Optimierung)

**D1 — die Token-Abrechnung ist tot.** `graph/state.py:94` setzt
`usage: dict = Field(default_factory=dict)`, also `{}`. `obs/usage.add_usage`
beginnt mit `if not acc: return` — und ein leeres Dict ist falsch. **Jede**
Faltung verpufft still; `debug.token_usage` ist bei jedem Zug `{}`.
`obs/usage.new_accumulator()` ist gebaut, dokumentiert und hat **null Aufrufer**
im Produktivcode (9. Fall „dokumentiert ohne Konsumenten"). Mitbetroffen: die
Eval-Metriken `token_usage_aggregate` und die Cache-Hit-Rate rechnen mit Nullen.
Fix: `default_factory=new_accumulator` + ein Test, der einen echten Zug mit
nicht-leerem `per_phase` festhält.

**D2 — irreführender Docstring.** `api/schemas.py:74` behauptet,
`pattern_id_hint` sei „purely a measurement signal in Phase 1 (Shadow-Mode): the
deterministic Pattern-Engine still chooses the final pattern". Das beschreibt
ALT. `domain/pattern_engine.py:1-8` sagt das Gegenteil: seit Welle E v4 ist der
Hint der **primäre Pfad**, Phase 1 und 2 wurden gelöscht, „weil der
Hint-Shortcut immer griff". Reihenfolge heute: `enforced_pattern_id` (Safety) →
`pattern_id_hint` → Fallback M15. Der veraltete Satz hat in dieser Sitzung zu
einer Empfehlung geführt, die den Klassifikator entkernt hätte.

### Gemessen

Prompt (echt, über den App-Lifespan mit DB — eine Sonde ohne DB log um
Faktor 68 daneben und meldete 838 statt 57.151 Zeichen):

    Systemprompt      57.151 Zeichen  ≈ 14.300 Token
    stabiles Präfix   57.064 Zeichen  = 99,8 %   (nur 87 Zeichen variieren)

    Patterns  23.999 Z.  42,0 %      Intents   17.410 Z.  30,5 %
    Personas   6.229 Z.  10,9 %      Entities   3.774 Z.   6,6 %
    States     1.151 Z.   2,0 %      Signals      267 Z.   0,5 %
    Rest       4.321 Z.   7,6 %      (Kopf, Overrides, Few-Shot, Turn-Kontext)

Reine Klassifikations-Latenz (n=5, Median; Sonde ohne DB, also **untere
Schranke**): luna/`low` 1676 ms · luna/`none` 2087 ms · gpt-5.4-mini/`none`
1206 ms.

### Struktur-Befunde

* **Der Klassifikationsprompt ist caching-optimal gebaut** — statische Blöcke
  vorn, Turn-Kontext hinten („dynamic turn-context (last, for prompt-cache
  stability)"). Dort ist strukturell nichts zu holen.
* **Der Antwort-Prompt ist gegenläufig gebaut.** `response_prompt_builder.py:97`
  beginnt mit `base_persona, domain_rules` (statisch), dann `persona_prompt` und
  `render_pattern_layer(...)` — beide variieren je Zug. Das stabile Präfix endet
  nach Layer 2; alles danach ist unkacheerbar, darunter rein statische Blöcke
  (`RERANK_HINT_BLOCK`, Modulations-Regeln, Guardrails, Tools-Block). Wiegt
  schwerer, weil der Tool-Loop bis zu 5 Runden je Zug fährt.
  **Aber:** die Guardrails stehen laut Kommentar absichtlich zuletzt („always
  last, not overridable") — Umsortieren ist ein Eingriff in eine
  Sicherheitsentscheidung und braucht einen Golden-Lauf.
  **Ungeprüft:** ob der Prompt einmal je Zug oder einmal je Tool-Runde gebaut
  wird. Ersteres würde den Ertrag deutlich kleiner machen.
* **Aufteilen in Teilprompts lohnt nicht.** Gekoppelt sind Personas + Intents +
  States + Patterns = **85,4 %** (`pattern_id_hint` braucht Persona/Intent/State,
  `tool_id_hint` wird gegen die Tool-Whitelist des Patterns geprüft). Wirklich
  unabhängig ist nur `signals` (0,5 %). `entities` sah frei aus, ist es aber
  nicht: `graph/nodes/merge.py:92-136` faltet Entities **je nach `turn_type`**.
* **`assess` ist bereits parallel** (`asyncio.gather` über safety/classify/
  memory) — der Block ist `max()`, nicht Summe. Ungemessen und wichtig: ob die
  Moderation ohnehin länger braucht als die Klassifikation.

### Entitäten — drei Klassen (relevant für jeden Router-Ansatz)

| Entität | Wertebereich | Art |
|---|---|---|
| `stufe` | 6 (WLO `educationalContext`) | rein deterministisch — die Regel („Klasse 1-4 = Grundschule …") steht wörtlich im Prompt |
| `fach` / `medientyp` / `lizenz` | geschlossen | Vokabular-Zuordnung |
| **`thema`** | frei | echte Extraktion — **der Suchbegriff** |

Das LLM liefert bei den geschlossenen Mengen nur ein **Label**, das ohnehin über
`_resolve_filter_uris` → Label→URI-Cache → `lookup_wlo_vocabulary` aufgelöst
wird. `arg_resolvers._llm_vocab_match` ist bereits ein **zweiter** LLM-Aufruf für
Fehlschläge („sciences", „Naturwiss"), gecacht je `(vocab, value)` — das
Hybrid-Muster läuft also schon, eine Ebene tiefer.

### Ideen-Rangfolge (falls später aufgegriffen)

0. **D1 zuerst.** Ohne den Token-Zähler ist jede Aussage zu Prompt-Caching,
   Ausgabe-Token und Kaskaden-Ertrag geraten. Eine Zeile.
1. Fast-Path für Quick-Reply-/Tour-Chips: **unsere eigenen Strings**, die
   Klassifikation ist vorab bekannt → spart den Aufruf ganz.
2. `LLM_CLASSIFY_MODEL` getrennt vom Chat-Modell (gemessen ~880 ms) — braucht
   einen Golden-Lauf.
3. `tool_reasoning` (nur eine Log-Zeile in `prefetch.py:192`) und
   `pattern_reasoning` (nur Eval-Judge + Debug-Panel) im Betrieb weglassen,
   für Eval-Läufe zuschaltbar. Ausgabe-Token auf dem kritischen Pfad.
4. Encoder-Router auf pgvector als Vorstufe, gespeist aus den `Beispiele:`-
   Blöcken, die in der Config **bereits stehen**; lokales ONNX-Embedding (W8)
   ist hier der richtige Weg, weil bei 10 Wörtern der Netz-Roundtrip dominiert.
   Risikofrei prüfbar: `turn_persist` schreibt jede Klassifikation mit — der
   Router lässt sich **offline** gegen echten Verkehr auszählen, ohne eine Zeile
   im Live-Pfad zu ändern.
