# Paket D: Konto-Knopf und „Meine Vorgänge“ (2026-11-20)

Plan: `docs/plans/2026-11-20-konto-vorgaenge-und-warten-auf-volltext.md`, Befunde R1/R2, Entscheide
E-D1/E-D2, Abnahme §4. Nur Widget (`frontend/projects/ui`), kein Backend.

## Was die Person sieht

**D1 – ein Konto-Knopf.** Kürzel-Kreis und Anmelde-Knopf sind zu einem Knopf zusammengelegt, 36 × 36 px
wie „Vollbild“ und Neustart.

- Abgemeldet: Umriss einer Person, ausgegraut, gestrichelter Rand. Klick → Anmeldung wie bisher.
  Name „Anmelden – nicht angemeldet“.
- Angemeldet: Initialen („JS“), ohne bekannten Namen die gefüllte Person. Name „Konto – angemeldet
  als {Name}“ bzw. „Konto – angemeldet“. Klick öffnet ein kleines Menü über der Fußzeile: „Angemeldet
  als {Name}“ und der Eintrag „Abmelden“ (Abmelden wie bisher, das Gespräch bleibt).
- Menü nach dem APG-Muster „Menu Button“: `aria-haspopup="menu"`, `aria-expanded`, `aria-controls`
  nur bei offenem Menü. Enter/Leertaste/Klick öffnen und fokussieren „Abmelden“, Pfeil runter/hoch
  öffnen auf dem ersten/letzten Eintrag, im Menü Pfeile, Pos1, Ende. Esc schließt, gibt den Fokus an
  den Knopf und schließt nicht das Chat-Fenster. Klick daneben und Tab hinaus schließen.

**D2 – „Meine Vorgänge“.**

- Eigenes, von Hand gezeichnetes Symbol: eine Liste mit zwei Häkchen und einem offenen Schritt.
  Bisher war es der Kreispfeil `restore`, der dem Neustart glich.
- Abzeichen mit der Zahl offener Vorgänge anderer Gespräche, ab zehn „9+“. Der Name nennt die genaue
  Zahl: „Meine Vorgänge – 3 offen“. Das Abzeichen selbst ist für Vorleser stumm.
- Markierung, solange in diesem Gespräch ein Auftrag läuft (`eingabeGesperrt` oder Ablauf-Stand
  `wartet_auftrag`): Rand und Symbol in `tertiary`, ein Punkt unten rechts, dazu im Namen „… – hier
  läuft ein Auftrag“. Farbe ist also nicht das einzige Zeichen.
- Sichtbar wie bisher nur mit Anmeldung, nicht in der Probe.

## Technik

- `shell/konto-knopf.component.{ts,scss}` (neu, präsentational): Knopf, Menü, Tastatur. Eingaben
  `angemeldet`, `name`, `translate`; Ausgaben `anmelden`, `abmelden`. Beide gehen in der Shell durch
  `onAuthClick()`, synchron, damit der Klick die Nutzergeste fürs Anmeldefenster bleibt.
- Kein CDK-Menü bzw. -Overlay: das Bündel stand vorher schon über der gzip-Warnschwelle, und ein Menü
  mit einem Eintrag braucht kein Overlay. Klick daneben über `composedPath()` (Shadow-DOM).
- Das Menü ist absolut zur Fußzeile platziert (`.chat-footer { position: relative }`), rechtsbündig,
  `max-width: calc(100% - 24px)`. So bleibt es auch bei 320 px ganz im Widget.
- `chat-shell.component.ts`: `authTitel`, `kuerzel` und `kuerzelTitel` fallen weg (die Texte bildet
  jetzt der Knopf). `anzeigename` ist öffentlich. Neu sind `vorgaengeHier`, `vorgaengeZahl` und
  `vorgaengeName`.
- Zahl ohne zweiten Abruf: `MeineVorgaengeController.vorladen()` nutzt dasselbe `laden()` wie das Panel
  (`POST /api/ui/vorgaenge/liste`), einmal je Gespräch und Block. Ausgelöst wird es im vorhandenen
  Effekt `_fortsetzenFragen`, also beim Öffnen, nach der Anmeldung und nach einem Wechsel oder
  Neustart (`vergessen()` setzt den Merker zurück). Bei offener Liste lädt es nicht erneut, sonst
  ginge eine Lösch-Rückfrage verloren. Fehler bleiben still. `anzahl` ist die Länge derselben Liste.
  Nach dem Löschen sinkt sie sofort, während eines neuen Ladens bleibt die alte Zahl stehen.
- `icons.ts`: neu `vorgaenge` (Raster 960, Strich 80, Rechnung im Kommentar). `restore` und `login`
  sind entfernt, sie waren danach ungenutzt. `logout` steht am Menüeintrag.
- i18n de/en: neu `auth.konto.{aus,an,anOhneName,abmelden}` und `vorgaenge.{knopfOffen,knopfHier}`.
  Entfernt sind `auth.signOut`, `auth.signOutAs` und `auth.notSignedIn` (ungenutzt).
- `_chat-footer.scss`: `.konto-kuerzel*` und die `.btn-auth`-Regel sind weg. Die Umbruchgrenzen
  sinken um die 36 px des Kreises: mit Anmelde-Angebot 320 px, angemeldet 364 px, mit Mikrofon je
  44 px mehr (vorher 356/400/444). Neu sind Abzeichen und Markierung.

## Entscheide und Abweichungen

1. **Probe:** Der Konto-Knopf steht in der Probe der Studio-Vorschau weiter da, als Anmelde-Knopf wie
   der bisherige `btn-auth`. Bisher fehlte dort nur der Kürzel-Kreis. Der Auftrag sagte „in der Probe
   wie bisher kein Knopf“, doch das hätte die Anmeldung in der Probe weggenommen. Soll er dort ganz
   fehlen, genügt `&& !probe()` im `@if` der Shell; der Test „bleibt in der Probe …“ in
   `chat-shell-kuerzel.spec.ts` dreht sich dann mit. „Meine Vorgänge“ fehlt in der Probe wie bisher.
2. Die Klasse `btn-auth` bleibt am Konto-Knopf, damit vorhandene Selektoren (`chat-shell-sitzung`,
   E2E) gelten. Der Wirt `boerdi-konto-knopf` trägt die Klasse `konto` und steht in der Reihe der
   Fußzeile.
3. Die Übergänge des Konto-Knopfs laufen nur bei `prefers-reduced-motion: no-preference`.
4. `chat-shell.component.ts` (rund 1950 Zeilen) wächst netto um etwa 15 Zeilen. Knopf und Menü liegen
   in der neuen Komponente.

## Budget

`npm run build:widget` + `node scripts/check-widget-budget.mjs`:

| | vorher | nachher | Grenze |
|---|---|---|---|
| raw | 688,38 kB | 695,38 kB (+7,0) | 700 kB |
| gzip | 200,02 kB | 202,00 kB (+2,0) | 210 kB (Warnung ab 200) |

Die Warnschwelle war schon vorher überschritten. Viel Luft ist roh nicht mehr da (99,3 %).

## Tests

- Neu: `shell/konto-knopf.component.spec.ts` (18 Fälle: abgemeldet und angemeldet, Initialen und
  Symbol, Menü öffnen und schließen, Pfeile/Pos1/Ende, Esc endet hier, Klick daneben, Tab hinaus,
  Abmelden schließt das Menü und gibt den Fokus zurück, englisch). Rot gesehen (Modul fehlte), dann
  grün.
- `meine-vorgaenge.spec.ts` +6 (`vorladen`/`anzahl`): rot (`TS2339`), dann grün.
- Angepasst (neues Soll): `chat-shell-kuerzel.spec.ts` (Kürzel im Knopf, kein zweiter Kreis, Probe,
  Lage), `chat-shell-auth-button.spec.ts` (Klick auf den Knopf meldet synchron an; angemeldet öffnet
  der Klick nur das Menü, erst „Abmelden“ meldet ab), `chat-shell-sitzung.spec.ts` (Name am Knopf
  „Konto – angemeldet als …“), `chat-shell-meine-vorgaenge.spec.ts` (+7: Symbol ≠ Neustart, Zahl und
  Name, „9+“, ohne Abzeichen bei 0, kein Doppelabruf, Markierung über `eingabeGesperrt` und
  Ablauf-Stand). Vor der Umsetzung 24 rot.
- E2E `auth-button.spec.ts`: 320 px ohne Überlauf mit Feld ≥ 120 px; gleich groß wie „Vollbild“
  (36 × 36, ab- und angemeldet); Kontrast abgemeldet (gestrichelt, hell 3,6 / dunkel 4,7 : 1) und
  angemeldet (Symbol 10,0, Initialen hell 10,0 / dunkel 10,3 : 1); Menü per Tastatur; Menü bei 320 px
  im Widget. `meine-vorgaenge.spec.ts`: Grenze 364 px (bei 380 px eine Zeile); Zahl wie die Liste,
  weg nach dem Löschen; Abzeichen 9,3 : 1; Markierung hell 5,2 / dunkel 9,5 : 1.
- Läufe: `npx ng test ui --watch=false` 124/124 Dateien grün. `npx playwright test` 130/130 grün.
  `auth-button` + `meine-vorgaenge` dreimal wiederholt 48/48.

## Hinweis aus dem Lauf

`e2e/strukturentwurf.spec.ts` („bearbeiten per Tastatur, dann übernehmen …“) schlug gegen einen
Zwischenbau viermal hintereinander fehl. Der Fokus landete nach dem Zug im Eingabefeld statt auf
der Statuszeile. Gegen den letzten Bau lief er 20/20 und in der ganzen Suite grün. Der Test bietet
keine Anmeldung an: der Konto-Knopf wird dort nicht gezeichnet, und `vorladen` läuft nicht.
Vermutlich ein Wettlauf zwischen dem Fokus des Moduls (`ui-strukturentwurf`, am 19.11. abends
geändert) und dem Zurückholen des Fokus durch die Shell nach dem Zug. Nicht untersucht, weil
`ui-module/**` außerhalb dieses Pakets liegt.

## Deploy

Keine Migration, keine Variable. Widget neu bauen (Image baut es selbst).

## Review behoben (20.11.)

Unabhängiges Review: 0 CRITICAL, 0 MAJOR, 6 MINOR, 4 NIT — alle behoben bzw. eingetragen. Test zuerst
wo testbar; rot gesehen bei 1, 2, 4, 7, 8, 10. Die beiden Tests zu 5 halten vorhandenes Verhalten fest
und waren gleich grün.

1. Umschalt+Tab aus dem Menüeintrag auf den Konto-Knopf schließt das Menü (`fokusWeg`), ohne den
   Fokus zu versetzen.
2. Der Lauscher für Klicks daneben hängt nur bei offenem Menü am Dokument (`Renderer2.listen` in
   `oeffnen`, abgemeldet in `schliessen` und beim Zerstören). Vorher plante jeder Klick auf der
   Gastseite einen Durchlauf.
3. Doku auf den Konto-Knopf gezogen: `docs/edu-sharing-einbindung.md` (Schritt 6, Abnahme),
   `docs/uebergabe-betrieb.md` (Abnahme §16). Der Satz zum Kreis ist gestrichen.
4. `_fortsetzenFragen`: erst `fortsetzen.pruefen()`, dann `meineVorgaenge.vorladen()`, nacheinander.
   Der zweite Abruf trifft den gewärmten `/auth/status`.
5. Neue Shell-Specs: nach `restart()` ein neuer Abruf mit neuer Kennung, die Zahl kommt aus der
   zweiten Antwort; „Fortsetzen“ in der Liste fragt für das neue Gespräch. Abweichung: Der Wechsel
   läuft echt über `ShellLifecycle.wechseln` mit gestubbter API (wie der vorhandene Test zu
   „Fortsetzen“), `wechseln` selbst ist nicht gemockt.
6. Budget als offener Punkt in `docs/offene-befunde-und-todo.md` §5 (Nachlade-Kandidat, z. B.
   `MeineVorgaengeComponent`), nicht umgebaut.
7. NIT: Wird abgemeldet, während der Fokus im Menü liegt, geht er an den Konto-Knopf.
8. NIT: Ein gehaltenes Enter oder eine gehaltene Leertaste (`repeat`) auf dem Eintrag meldet nicht
   ab.
9. NIT: Der Grund der Fußzeile heißt jetzt `--bb-footer-bg`; Abzeichen und Punkt ziehen ihren Ring
   daraus.
10. NIT: Scheitert `laden()` (und gilt die Antwort noch), versucht das nächste `vorladen()` es
    erneut.

Zusätzlich in `docs/offene-befunde-und-todo.md` §3: der E2E-Kippler `strukturentwurf.spec.ts:42`
(Z. 81) unter Last, vermutete Ursache `focusInput()`, eigenes Debug-Paket.

Tests: `konto-knopf.component.spec.ts` +4, `meine-vorgaenge.spec.ts` +1,
`chat-shell-meine-vorgaenge.spec.ts` +3. Läufe: `ng test ui` 124 Dateien / 1590 Tests grün, eslint
ohne Befund, E2E `auth-button` + `meine-vorgaenge` + `embed` 35/35, ganze E2E-Suite 130/130.

Budget danach: roh 695,97 / 700 kB (99,4 %), gzip 202,23 / 210 kB.
