# MCP-Anmeldung: Knopf in der Eingabezeile

Stand 2026-08-11 · Entwurf zur Abnahme · Nutzer-Auftrag vom selben Tag

## Ziel

Wer im Chatbot mit **seinen eigenen WLO-Rechten** suchen und kuratieren will,
soll sich dafür an- und abmelden können — über einen Knopf unten rechts neben
der Eingabezeile, der auch im rahmenlosen Einbettungs-Modus sichtbar bleibt.

## Ausgangslage (gemessen, nicht angenommen)

**Die Maschine ist gebaut. Es fehlt der Griff.** Das ist der wichtigste Befund
dieses Entwurfs — er verkleinert die Aufgabe von „Feature bauen" auf „Bedienung
anbringen".

| Baustein | Datei | Stand |
|---|---|---|
| OAuth-Protokoll (discover · register · exchange) | `ui/src/session/mcp-oauth.ts` | ✅ |
| Ablauf + Rückkanal-Seite | `ui/src/session/sign-in-flow.ts` | ✅ `runSignIn()` |
| Aufbewahrung im Browser | `ui/src/session/mcp-access.ts` | ✅ `readAccessBlock` / `writeAccessBlock` / `clearAccessBlock` |
| Kopfzeile bei jeder Anfrage | `ui/src/stream/stream-client.ts:128,209` | ✅ `WLO-Access-Block` |
| Backend übernimmt sie **je Zug** | `backend/api/chat.py:69` | ✅ setzt auch zurück — kein Zug erbt die Anmeldung des vorigen |
| Einstiegspunkt im Shell | `chat-shell.component.ts:461` | ✅ `startSignIn()` |
| Auslöser | `shell/input-routing.ts:54` | ⚠️ **nur** über einen `__auth__`-Chip bzw. getippten Text |
| Bedienelement im Template | `chat-shell.component.html` | ❌ **fehlt** |
| Abmelden | `clearAccessBlock()` | ⚠️ vorhanden, **kein Aufrufer** |
| Zustandsanzeige | — | ❌ niemand sieht, mit welchen Rechten er sucht |

`clearAccessBlock()` ohne Aufrufer ist in diesem Projekt ein bekanntes Muster
(„gebaut, dokumentiert, nie gerufen"). Hier wird es geschlossen.

### Die Eingabezeile heute

`.chat-footer` ist ein Flex mit 8 px Abstand; Knöpfe sind **36 px** breit:

```
[Mikro?]  [ Eingabefeld ]  [Größe?]  [Neustart]  [Senden]
```

Mikro und Größe sind bedingt (`languageButtonsVisible`, `sizeToggleVisibleBool`),
im Vollausbau stehen dort also **vier** Knöpfe.

Die Reihenfolge folgt einer im Code festgehaltenen Regel — Abstand zur
Absende-Handlung, von rechts nach links: **Senden > Neustart > Größe**.

### Zwei Dinge, die der Code schon entschieden hat

* **Der Klick IST die Nutzergeste**, ohne die der Browser das Anmeldefenster
  blockt (Kommentar an `signIn:` in `chat-shell.component.ts:398-401`). Der
  Knopf muss deshalb **synchron** starten — kein Rundlauf zum Backend davor.
* **`/api/health.mcp_auth` ist NICHT der Nutzerzustand.** Es meldet den
  Server-Modus aus `MCP_AUTH_TOKEN` (`service` / `anonymous`). Der persönliche
  Zustand lebt allein im Widget (`sessionStorage`) — der Knopf braucht also
  keinen Netzaufruf, um zu wissen, was er anzeigt.

## Abgrenzung

**Drin:** ein Knopf mit zwei Zuständen (anmelden / abmelden), seine Beschriftung
und Ansage, die Sichtbarkeitsregel, die Platzierung, i18n (DE+EN), Tastatur und
Kontrast, das Verhalten bei 320 px.

**Draussen, bewusst:**

* **Die Chat-Sitzung beenden.** Der Auftrag nannte „Abmelden der Session" — es
  gibt aber schon einen Neustart-Knopf, der genau das tut. Ein zweites
  Bedienelement mit überlappender Bedeutung nebeneinander verwirrt mehr, als es
  löst. Abmelden räumt **den Zugangsblock**, nicht das Gespräch. Falls doch
  beides zusammengehören soll: eigene Entscheidung, eigener Schnitt.
* **Anzeige des Kontonamens.** Der Zugangsblock ist undurchsichtig; das Widget
  weiss nicht, WER angemeldet ist, ohne einen zusätzlichen Aufruf. „Angemeldet"
  ja, „angemeldet als Jan" nein.
* **Reranker-Sichtbarkeit** und **Schreib-Abnahme** — siehe „Nicht Teil dieses
  Plans" am Ende.

## Ansatz

### Platzierung

Der Nutzer hat sie vorgegeben: **unten rechts neben der Eingabezeile**, damit
sie im rahmenlosen Modus bleibt (dort gibt es keine Kopfzeile mehr — der
Neustart ist aus genau diesem Grund 2026-08-09 dorthin gewandert).

Innerhalb der Knopfgruppe folgt die Position der bestehenden Regel: die
Anmeldung ist **weiter** von der Absende-Handlung entfernt als Neustart und
Größe — sie betrifft nicht dieses Gespräch, sondern die Sitzung. Also ganz
links in der Gruppe:

```
[Mikro?]  [ Eingabefeld ]  [Anmelden]  [Größe?]  [Neustart]  [Senden]
```

Damit steht er rechts vom Eingabefeld (die Vorgabe) und stört die eingeübte
Lage von Senden und Neustart nicht.

### Ein Knopf, zwei Zustände — nicht zwei Knöpfe

| | Anmelden | Abmelden |
|---|---|---|
| Bedingung | kein Block im Speicher | Block vorhanden |
| Symbol | `login` | `logout` |
| Beschriftung/Ansage | „Mit WLO-Konto anmelden" (Schlüssel gibt es: `auth.signIn`) | „Abmelden — wieder anonym suchen" |

Zwei getrennte Knöpfe wären ein fünfter und sechster in einer Zeile, die bei
320 px schon eng ist — und einer davon wäre immer sinnlos.

### Wann der Knopf gar nicht erscheint

`runSignIn` braucht `mcpAuthBase()`. Ist die Adresse nicht gesetzt, kann die
Anmeldung nicht gelingen — dann ist ein Knopf, der nur scheitern kann, schlechter
als keiner. **Regel: kein `mcpAuthBase` ⇒ kein Knopf.** Das ist zugleich der
Ausschalter für Betriebe, die das nicht anbieten wollen.

**Nachgeschärft beim Bau von Aufgabe 1 (2026-08-11).** Die Regel gilt nur fürs
*Anmelden*. Ein **vorhandener Zugangsblock schlägt die fehlende Adresse**: dann
zeigt der Knopf „Abmelden", auch ohne `mcpAuthBase`. Zwei Gründe, beide gemessen:

* **Abmelden kann nicht scheitern** — es räumt nur `sessionStorage`. Die
  Begründung fürs Verstecken („kann nur scheitern") trägt hier also nicht.
* **Der Fall tritt bei jedem Neuladen auf.** `guide-boot.ts:59` setzt
  `mcpAuthBase = signal('')` und füllt es erst nach dem Config-Abruf
  (`load()`, Z. 107) — der Block überlebt den Reload im selben Tab. Mit der
  strengen Regel wäre eine angemeldete Person nach jedem Neuladen kurz ohne
  Knopf, und **dauerhaft** ohne, sobald der Betrieb `mcp_auth_base` abschaltet:
  angemeldet ohne Weg zurück zu anonym.

### Alternativen, die verworfen wurden

| | Wie | Warum nicht |
|---|---|---|
| A | Anmeldung bleibt beim `__auth__`-Chip | Der Chip erscheint nur, wenn der Bot ihn anbietet — man kann sich nicht anmelden, *bevor* man etwas sucht. Genau das will der Auftrag |
| B | Knopf in einer Kopfzeile | Die gibt es rahmenlos nicht mehr; er wäre im Einbettungs-Modus unsichtbar — der ausdrückliche Grund für die Platzierung unten |
| **C** | **Zwei-Zustands-Knopf in der Fusszeile** | **Gewählt** |

## Architektur

### Datenfluss

```
Klick ──▶ chat-shell.component
            │  angemeldet?  (readAccessBlock() ≠ leer)
            ├─ nein ──▶ startSignIn()  ── synchron, der Klick ist die Geste
            │             └─ runSignIn ▶ mcp-oauth ▶ writeAccessBlock
            └─ ja ────▶ clearAccessBlock() + Bot-Blase „wieder anonym"
                                    │
      jede folgende Anfrage ◀───────┘
        stream-client hängt WLO-Access-Block an  ▶  api/chat._adopt_turn_auth_block
```

### Dateien

| Datei | Zuständigkeit | Änderung |
|---|---|---|
| `ui/src/session/mcp-access.ts` | Speicher | **unverändert** — `readAccessBlock`/`clearAccessBlock` reichen |
| `ui/src/session/auth-button.ts` | **neu** | Reine Zustandslogik: Block + `mcpAuthBase` ⇒ `'hidden' \| 'signIn' \| 'signOut'`. Ohne DOM, ohne Angular — deshalb ohne jsdom testbar |
| `ui/src/shell/chat-shell.component.html` | Darstellung | ein `<button>` in `.chat-footer`, links der Gruppe |
| `ui/src/shell/chat-shell.component.ts` | Verdrahtung | `authButtonState()`-Computed + `onAuthClick()`; `startSignIn` existiert |
| `ui/src/shell/_chat-footer.scss` | Maße | `.btn-auth` wie `.btn-restart` (36 px) |
| `ui/src/i18n/de.ts` · `en.ts` | Texte | `auth.signOut`, `auth.signedOut`; `auth.signIn` existiert |
| `ui/src/icons.ts` | Symbole | `login`, `logout` — prüfen, ob vorhanden, sonst ergänzen (Inline-SVG, kein Icon-Font — DSGVO-Regel des Projekts) |

### Schnittstellen

```typescript
// ui/src/session/auth-button.ts
export type AuthButtonState = 'hidden' | 'signIn' | 'signOut';

/** Was der Knopf zeigen soll. `hidden` nur, wenn es NICHTS zu tun gibt: keine
 *  Anmelde-Adresse UND kein Block. Ein Block schlägt die fehlende Adresse. */
export function authButtonState(
  mcpAuthBase: string, hasBlock: boolean,
): AuthButtonState;
```

### Abhängigkeitsrichtung

`auth-button.ts` ist rein und hängt von nichts ab; die Komponente ruft es. Keine
neue Abhängigkeit nach aussen, kein Zyklus.

## Nicht-funktionale Festlegungen

* **Platz bei 320 px.** Gemessen: 4 Knöpfe × 36 px + 4 Lücken × 8 px = 176 px,
  es bleiben ~114 px fürs Eingabefeld. Ein fünfter drückt das auf **~70 px**.
  Eng, aber tragbar — und der Knopf verschwindet ohnehin ohne `mcpAuthBase`.
  **Wird geprüft, nicht gehofft:** ein Test bei 320 px, dass die Zeile nicht
  umbricht und das Feld bedienbar bleibt.
* **Barrierefreiheit.** `<button>` (kein `div`), `aria-label` aus dem Katalog,
  sichtbarer Fokus wie bei den Nachbarn, Ziel 36 px — über dem WCAG-2.2-Minimum
  von 24 px, unter den komfortablen 44; **gleich den bestehenden Knöpfen**, eine
  Abweichung wäre hier die schlechtere Wahl. Der Ausgang der Anmeldung landet
  als Bot-Blase im Verlauf und wird damit von dessen Live-Region angesagt — der
  Weg, den `runSignIn` schon nimmt.
* **Kein Farb-allein-Signal.** Angemeldet/abgemeldet unterscheiden sich durch
  **Symbol und Beschriftung**, nicht durch Farbe.
* **i18n.** Beide Zustände in DE und EN. Der EN-Wächter des Studios verbietet
  wortgleiche Texte — hier gilt dieselbe Sorgfalt.
* **Datenschutz.** Der Block bleibt in `sessionStorage` (nicht `localStorage`,
  nicht Cookie — begründet in `mcp-access.ts`) und wird **nie protokolliert**.
  Abmelden räumt ihn wirklich.
* **Sicherheit.** Der Knopf ändert nichts am Vertrauensmodell: der Block reist
  weiter nur an den Chat-Endpunkt, das Backend speichert ihn nicht.

## Risiken

| Risiko | Gegenmittel |
|---|---|
| **Der Klick verliert die Nutzergeste** ⇒ der Browser blockt das Anmeldefenster, und zwar still | `onAuthClick` startet synchron; ein Test hält fest, dass vor `startSignIn` nichts awaited wird |
| Fünfter Knopf sprengt 320 px | Test bei 320 px; Knopf entfällt ohne `mcpAuthBase` |
| Abmelden räumt nur die Anzeige, nicht den Speicher | Test liest `sessionStorage` **nach** dem Klick |
| Nutzer glaubt, „Abmelden" beende das Gespräch | Beschriftung sagt, was passiert („wieder anonym suchen"), und der Neustart bleibt sichtbar daneben |
| Zustand veraltet, wenn ein anderer Tab abmeldet | Bewusst nicht behandelt: `sessionStorage` ist tab-lokal, ein anderer Tab hat seinen eigenen |

## Aufgaben

### Phase 1 — Zustandslogik (rein, ohne DOM)

**Schritt 0: `/better-coding-workflow` aufrufen.**

1. ✅ **`auth-button.ts` + Test** (2026-08-11). `authButtonState('', false) ===
   'hidden'` · `('https://…', false) === 'signIn'` · `('https://…', true) ===
   'signOut'` · leere/whitespace-Adresse zählt als nicht gesetzt ·
   **`('', true) === 'signOut'`** (die Nachschärfung oben).
   Beleg: `ng test ui --include projects/ui/src/session/auth-button.spec.ts`
   → 5 passed. Rot-grün des neuen Randfalls einzeln geprüft: mit der strengen
   Regel fällt **genau** dieser eine Test (`expected 'hidden' to be 'signOut'`).

### Phase 2 — Knopf und Verdrahtung

**Schritt 0: `/better-coding-workflow` + `/better-coding-frontend` aufrufen.**

2. ✅ **i18n** (2026-08-11): `auth.signOut`, `auth.signedOut` in `de.ts` und
   `en.ts`. Rot-grün über den **bestehenden** Wächter `i18n/en.spec.ts`: nur
   deutsch eingetragen ⇒ 3 von 7 Tests fallen (Schlüssel-Gleichheit, kein
   deutscher Rest, kein Rückfall); nach dem englischen Eintrag 7/7.
3. ✅ **Symbole** (2026-08-11). `login`/`logout` gab es **weder** im Satz noch im
   ALT-Baum. Von Hand auf dem 0 -960 960 960-Raster konstruiert wie die
   Größen-Symbole — ein Material-Pfad aus dem Gedächtnis wäre geraten, nicht
   gemessen. Beide teilen dieselben Maße (Rahmen y -800…-160, Stärke 80,
   Pfeilmitte -480), damit die zwei Zustände EINES Knopfs nicht springen.
   Geprüft durch Rasterung der Pfade (Punkt-in-Polygon, 48×24-Textbild): Rahmen
   links ⇒ Pfeil hinaus, Rahmen rechts ⇒ Pfeil hinein.
4. ✅ **Knopf im Template** + `.btn-auth` im SCSS, links der Gruppe (2026-08-11).
5. ✅ **`onAuthClick`** (2026-08-11). Rot-grün des Geste-Tests einzeln belegt:
   mit einem `await` vor `startSignIn` fallen **genau** die drei Klick-Tests,
   der Geste-Test mit „expected startSignIn to be called 1 times, but got 0".

**Beim Bauen dazugekommen, nicht im Entwurf vorgesehen:** der `__auth__`-Chip
meldet ebenfalls an. Ohne Nachziehen stünde der Knopf danach weiter auf
„Anmelden". Beide Auslöser laufen jetzt durch `_signInAndRefresh()`.

### Phase 3 — Abnahme

6. ✅ **320 px + Tastatur** (2026-08-11) — als E2E, weil jsdom kein Layout
   rechnet: `e2e/auth-button.spec.ts`, 4 Tests, alle grün.

   **Der Fund war grösser als die Aufgabe.** Gemessen bei 320 px:

   | | Inhalt der Zeile | Überlauf | Eingabefeld |
   |---|---|---|---|
   | ohne Knopf, VOR dem Fix | 329 px | **9 px** | 193 px |
   | mit Knopf, VOR dem Fix | 373 px | 53 px | 193 px |
   | mit Knopf, NACH dem Fix | 320 px | keiner | 120 px |

   Die Zeile lief also **schon vor diesem Plan** über (WCAG 1.4.10). Ursache:
   `.chat-input` hat `flex: 1` ohne `min-width: 0` und kann deshalb nicht unter
   seine Eigenbreite von 193 px schrumpfen — statt das Feld zu verkleinern,
   schob die Zeile hinaus. Der Sende-Knopf war dabei auf 28 px gequetscht.
   Eine Zeile in `_chat-footer.scss` (bewusste Abweichung vom ALT-Wortlaut,
   dort dokumentiert) räumt beides: kein Überlauf, alle Knöpfe volle 36 px,
   Feld 120 px. Ohne den Anmelde-Knopf sind es 164 px — die Differenz ist
   exakt seine 44 px.

   Zwei eigene Testfehler, beide korrigiert statt umgangen: `offsetTop` ist
   kein Umbruch-Kriterium (die Kinder sind verschieden hoch und zentriert,
   ihre Oberkanten liegen planmässig 2 px auseinander → Mittellinie prüfen),
   und `open()` refokussiert das Eingabefeld nach 100 ms, holt sich den Fokus
   also von einem zu früh gedrückten Tab zurück.

   Fokus-Ring gemessen: `outline: auto 2px` (SC 2.4.7 erfüllt, kein eigener
   Stil nötig). Tab landet vom Feld aus direkt auf dem Knopf.
7. Live-Smoke: anmelden, eine kuratierende Anfrage stellen, abmelden — und im
   Backend-Protokoll nachsehen, dass der Block wirklich je Zug mitkommt.
   (Ihre Domäne, sobald ein Server steht.)

## Abnahmekriterien

| Anforderung | Nachweis |
|---|---|
| Knopf sitzt unten rechts neben der Eingabezeile | Template-Test auf die Reihenfolge in `.chat-footer` |
| Bleibt im Einbettungs-Modus sichtbar | Er hängt an keiner Kopfzeile — Test mit `sizeToggleVisible=false` |
| Anmelden startet den echten Ablauf | Test: `startSignIn` gerufen, synchron |
| Abmelden räumt den Block | Test liest `sessionStorage` danach |
| Ohne Adresse **und ohne Block** kein Knopf | Test Aufgabe 1 + Template-Test |
| Angemeldet ⇒ Abmelden immer erreichbar, auch ohne Adresse | Test Aufgabe 1 |
| Zwei Zustände unterscheidbar ohne Farbe | Symbol + Beschriftung im Test |
| Zweisprachig | Katalog-Test DE/EN |
| 320 px tragen die Zeile | Test Aufgabe 6 |

## Offene Punkte

Keine.

---

## Nicht Teil dieses Plans (bewusst getrennt)

**✅ Reranker-Sichtbarkeit — erledigt 2026-08-11.** `reranker_status()` in
`services/rag/rerank.py`, ausgegeben als Feld `reranker` in `/api/health`; drei
Werte `ready` / `model-missing` / `off`. `ready` sagt bewusst nicht „geladen" —
das Modell kommt erst beim ersten Zug in den Speicher. OpenAPI-Vertrag
unberührt (`/api/health` gibt ein untypisiertes `dict` zurück, geprüft mit
`export_openapi.py --check`). INSTALL.md Abschnitt 8 und `deploy/.env.example`
nachgezogen. Ursprüngliche Notiz:

**Reranker-Sichtbarkeit — klein, unabhängig.** `RAG_RERANKER_ENABLED` steht auf
`true`, das Modell ist seit dem Mount ladbar. Was fehlt: eingeschaltet **ohne**
Modell ergibt nur eine Protokollzeile. Ein Feld in `/api/health`, das sagt, ob
der Reranker wirklich aktiv ist statt nur eingeschaltet, wäre eine Aufgabe von
Minuten — und erspart eine lange Suche.

**✅ ERLEDIGT 2026-08-11 — nachgetragen in `2026-08-11-seitenkontext-
erweiterung.md`, Phase 4. Suite jetzt 44/44 grün.**

**10 E2E-Tests fielen — Ursache war die Seitenkontext-Erweiterung, nicht dieser
Plan.** Beim vollen `npx playwright test` (33 grün, 10 rot) fallen Tests in
`chat.spec`, `guide.spec` und `embed.spec`. Der Anmelde-Knopf ist dort gar nicht
im DOM — diese Tests setzen kein `mcp_auth_base`. Der Mechanismus, gemessen an
`chat.spec.ts:14`: statt der Config-Begrüssung steht die **Ping-Antwort** in der
ersten Blase.

Ursache ist `shell/lifecycle.ts` aus dem Plan `2026-08-11-seitenkontext-
erweiterung`: `shouldSendContextPing` gibt für **jede Seite mit Hostnamen**
`true` zurück (Zweig `!kind || kind === 'other'`), und `_greetOnFirstLoad`
(Ansatz C) stellt die Begrüssung hinter den Ping zurück. Damit pingt jede
frische Sitzung, und `guide.spec.ts:87` — das ausdrücklich das ALT-Verhalten
„eine FRISCHE Session pingt nie" festhält — widerspricht dem jetzt.

Das ist **kein Zufallsbefund, sondern die offene Phase 4** jenes Plans: die
E2E-Suite wurde danach nie gefahren. Zwei Wege, und es ist eine
Produkt-Entscheidung, keine Aufräumarbeit:

* **Tests nachziehen** — die neue Absicht ist gewollt, die Tests sind veraltet.
  Preis: jeder Erstbesucher wartet vor der Begrüssung einen vollen Zug ab
  (gemessene Zug-Latenzen: 1,6–3,2 s Klassifikation, MCP bis 23 s).
* **Ping enger fassen** — nur pingen, wo die Seite wirklich etwas hergibt, und
  auf der eigenen Startseite/fremden Seite beim alten Verhalten bleiben.

**✅ Widget-Budget — erledigt 2026-08-11.** `npm run budget` meldete
„Single-File verletzt: 2 Dateien (main.js, oauth-callback.html)" — vorbestehend,
Ursache war der `assets`-Eintrag für die OAuth-Rückkehrseite in `angular.json`
(C5-c2), seit dem Staging unverändert.

Die Regel begründet sich mit „nichts auf der Gastseite lädt es" — und genau das
trifft auf diese eine Datei nicht zu: das Anmeldefenster ruft sie als
`redirect_uri` selbst auf. Sie ist also ein zweiter, eigener Einstiegspunkt, kein
toter Anhang. Deshalb eine **namentliche** Erlaubnisliste
(`ERLAUBTE_BEIGABEN`), keine Endungs-Ausnahme: ein versehentlich ausgelagertes
Stylesheet oder ein zweiter JS-Chunk muss weiterhin auffallen. **Rot-grün
belegt:** eine testweise angelegte `versehentlich.css` im Ausgabeverzeichnis
lässt das Gate weiterhin mit Exit 1 fallen.

**Schreib-Abnahme — braucht erst eine Messung.** `domain/write_confirm.py`
setzt den Menschen bereits strukturell ein: schreibende Werkzeuge liefern ohne
Schlüssel nur eine **Vorschau**, der Schlüssel wird dem Modell **entzogen**, und
bestätigt werden kann nur in einem **späteren Zug**. Was ich noch **nicht**
gemessen habe: wie diese Vorschau beim Nutzer ankommt und ob er sie ändern kann
— „um Zustimmung **oder Anpassung** fragen" aus dem Auftrag. Das ist eine eigene
Untersuchung mit eigenem Plan; sie hier mitzuschreiben hiesse raten.
