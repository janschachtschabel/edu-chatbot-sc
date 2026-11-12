# Paket TW-6: Abläufe zuverlässig auslösen, Review der letzten Änderungen (2026-11-12)

Auftrag nach dem Merge von #56 und #58: die letzten Änderungen reviewen und die Befunde beheben.
Dazu die Abläufe selbst durchtesten, das Auslösen mit je mindestens 5 Formulierungen.

## Durchtest vorher

Lokal gegen eine Wegwerf-DB, OpenAI nativ (gpt-6-luna), alle vier Themenbaum-Abläufe an. Je
Formulierung eine frische Sitzung.

| Ablauf | gestartet (Wendung) | KI | nicht |
|---|---|---|---|
| aus einem Thema (6) | 2 | 3× nur Knopf, 1× Entwurf direkt | 1 |
| aus einem Dokument (6) | 2 | – | 4× Upload-Feld direkt |
| aus eigenen Inhalten, ohne Anmeldung (5) | – | – | 5× Upload-Feld, kein Hinweis |
| aus Ordnern (5) | 2 | – | 3× Upload-Feld direkt |

- Über die festen Wendungen startet jeder Ablauf zuverlässig. Die KI griff aber trotz der
  Master-Skill-Regel meist direkt zum Modul.
- Bei „Themenbaum zum Thema Photosynthese“ schlug sie einmal „aus Ordnern“ vor.

## Was

- **Abläufe zuerst beim Aufruf** (`vorschlag.umlenkung`, beide Maschinen):
  - Ruft die KI `ui_strukturentwurf` oder `ui_upload` **ohne Arbeitsgrundlage** auf, während ein
    passender Ablauf angeboten ist, läuft das Modul nicht. Die Werkzeug-Antwort nennt den Ablauf
    (`ablauf-…`), und die KI nimmt ihn in derselben Runde.
  - Für den Strukturentwurf zählen Abläufe ohne Upload-Schritt („aus einem Thema“), für das
    Upload-Feld die mit Upload (Dokument, Ordner, eigene Inhalte).
  - Arbeitsgrundlage (`arbeitsgrundlage`) ist ein gemerkter Entwurf oder ein Teil `draft` bzw.
    `document` im Vorgang, auch Tage später.
  - Nie umgelenkt wird:
    - nach einem Ausstieg („Ohne Ablauf“);
    - mit Argumenten wie `vorlage`, `vertiefen`, `wurzel_wlo_id` (Bestand), `aus_dokument`,
      `aus_inhalten`;
    - beim zweiten Versuch im selben Zug, denn dann will die Person es ausdrücklich ohne;
    - im KI-Schritt eines laufenden Ablaufs.
  - Der erste Entwurf verdeckte die Module pauschal. Das Review (siehe unten) fand damit fünf
    Wege, die brachen.
- **Direktstart auch mit Upload-Feld** (`werkzeuge.ablauf_schreibt_selbst`):
  - Ein Upload-Feld schreibt nicht von selbst. Es überträgt nur nach eigenem Klick, mit
    Anmeldung und Studio-Schalter.
  - „Aus einem Dokument“ und „aus Ordnern“ startet die KI jetzt direkt (`modus: direkt`).
  - Für die Erlaubnis der Einbettung (`tool_mode`) zählt der Upload weiter als schreibend.
- **„Aus Ordnern“:**
  - Einstiegsfrage („Ja, Ordner wählen / Ohne Ablauf“), wie die anderen Abläufe;
  - `wann` und `nicht_wann` grenzen gegen „nur ein Thema“ und „ein Dokument“ ab;
  - Seed-Tests.
- **Hinweis zur Anmeldung** (`zug.anmelde_satz`): Passt die Wendung zu einem Ablauf, dem die
  Anmeldung fehlt, hängt `turn_persist` den Satz an. Die KI ließ ihn weg, wenn sie ihn nur als
  Bitte bekam.
- **Master-Skill** (`docs/skills/vorgehen-knapp.md`):
  - Die Upload-Regel (M08 und „Ordner oder Lehrplan“) bekommt die Ausnahme „ein passender
    Ablauf geht vor“.
  - Gegen die Sackgasse: Bringt jemand Dateien ein und passt kein Ablauf genau, nimmt die KI den
    nächstliegenden, nie nur „lade hoch“ ohne Feld.
  - Wächter in `test_master_skill_vorlage`.
  - **Den WLO-Knoten zieht der Nutzer nach.**

## Review der letzten Änderungen (#56, #57, #58) und Behebung

Unabhängiges Review: 1 MAJOR, 9 MINOR, 4 NIT. Behoben:

- **MAJOR 1:**
  - Die Einzeldatei-Regel aus #56 wirkte in jedem Upload-Feld. Beim Übertragen nach WLO wäre eine
    einzelne Datei still als Strukturdokument markiert worden.
  - Jetzt nur auf Wunsch des Blocks (`einzeldatei_als_struktur`), den nur „aus einem Dokument“
    setzt.
  - Weg: Manifest (Dienst und Eingabe), `dienst_upload`, `vorschlagen(e, einzelneAlsStruktur)`.
- **MINOR 2:** Bei gesperrtem Wechsel geht der Fokus auf „Hier bleiben“, nicht auf „Verwerfen
  und wechseln“. Ein gehaltenes Enter verwarf sonst den Entwurf.
- **MINOR 3:** Eigener Ausstieg vor dem Upload (`frei_anfang`), ohne „mit deinem Dokument“.
- **MINOR 4:** Seed-Tests für „Nochmal wählen“ mit der Wahl vom Anfang und für den
  Modul-Auslöser mit gesetztem `vorgehen`.
- **MINOR 7:** Schalter „Aufträge an“ (`kestra.an`). Aus heißt: keine Aufträge, auch nicht die
  der Umgebung. Eine leere Liste fiel sonst auf `B_API_JOBS_FLOWS` zurück.
- **MINOR 8:** Das Speichern weist es ab, einen Flow zu entziehen, den ein **eingeschalteter**
  Ablauf nutzt. Die Meldung nennt die Abläufe.
- **NIT 9:** Gesamtfrist beim Abruf der Flows (`asyncio.wait_for`, 5 s).
- **NIT 10:** Die Kataloge im Studio tragen eine Generationsmarke, die ältere Antwort überschreibt
  nicht.
- **#57, MINOR 12:**
  - `e2e/frameless.spec.ts` hält jetzt die Regel selbst fest: `100dvh` und `safe-area`.
  - Grund: Playwright kann die Adressleiste nicht nachbilden.
- **#57, MINOR 13:** `padding-bottom: env(safe-area-inset-bottom)` im Vollbild, gegen die
  Home-Leiste beim iPhone. Der rahmenlose Einbau setzt sie auf 0.
- **Nicht geändert:**
  - NIT 5: Die Konflikt-Meldung hat ihre eigene Fokuslogik.
  - NIT 11: Die Studio-Probe ohne Freigabe lässt Flows trocken durch. Das ist vermerkt.
  - #57 (a): `dvh` folgt nicht der Bildschirmtastatur. Das zeigt erst der Test auf dem Handy.

## Durchtest nachher

Lokal, Wegwerf-DB, Master-Skill aus der lokalen Datei.

| Ablauf | Ergebnis |
|---|---|
| aus einem Thema (6) | **6 gestartet** (2 Wendung, 4 direkt durch die KI) |
| aus einem Dokument (6) | **6 gestartet** (2 Wendung, 4 direkt), auch „Kann ich ein Curriculum hochladen …?“ |
| aus Ordnern (5) | **5 gestartet** (2 Wendung, 3 direkt) |
| aus eigenen Inhalten, ohne Anmeldung (5) | 3× Upload-Feld mit Hinweis zur Anmeldung, 2× Ablauf „aus Ordnern“ (direkt) |

Keine Formulierung endet in einer Sackgasse. Der Ablauf selbst braucht die Anmeldung, darum
startet er hier nie. Stand: Lauf nach dem zweiten Review, Master-Skill aus der lokalen Datei.

**Durchläufe bis zum Entwurf**, alle grün:

- **aus einem Thema:** Fragen, Startknopf, Entwurf (Lichtausbreitung … Optische Geräte).
- **aus einem Dokument:** Upload eines Rahmenlehrplans (Markdown), Lesen, Ordnung „Lernfelder“,
  Zweck, Entwurf.
  - Oben genau die fünf Lernfelder.
  - Kompetenzerwartungen, Vorbemerkungen und Leistungsbewertung sind keine Punkte.
- **aus Ordnern:** Einstieg, Ordner, Entwurf (Optik, Mechanik, Elektrizität, Wärmelehre).
- **Ohne Ablauf:** „Doch mit Ablauf“; die Wendung startet ihn danach nicht neu.

**Grenzen:**

- „Aus eigenen Inhalten“ mit Anmeldung ließ sich lokal nicht durchtesten, denn dazu fehlt eine
  WLO-Anmeldung am MCP.
- Die Ergebnisse der KI schwanken von Lauf zu Lauf. Feste Wendungen bleiben der sichere Weg.

## Deploy

1. Keine Migration. Image neu bauen.
2. `boerdi import-config --werksabgleich` ausführen: neue Seeds „aus Ordnern“ und „aus einem
   Dokument“.
3. Den Master-Skill-Knoten in WLO durch `docs/skills/vorgehen-knapp.md` ersetzen.

Die Schritte von „aus Ordnern“ und „aus einem Dokument“ sind neu, damit auch ihre Fassung. Ein Lauf,
der beim Deploy gerade wartet, wird nicht fortgesetzt, sondern endet. Das gilt wie bei jeder
Änderung im Studio, und die Person startet ihn neu.

## Review TW-6 (unabhängig) und Behebung

5 MAJOR, 2 MINOR, 5 NIT, alle behoben oder gegenstandslos. Nach der Behebung folgt ein zweites,
unabhängiges Review.

- **MAJOR 1–3: Pauschales Verdecken brach Wege.**
  - Nach „Ohne Ablauf“ verdeckten die anderen Abläufe weiter.
  - Ein Entwurf im Vorgang (Tage später) zählte nicht.
  - Bestand („Neue Gliederung dazu entwerfen“ mit `wurzel_wlo_id`), Abgleich und Übertragen
    brachen.
  - Ersetzt durch die Umlenkung beim Aufruf (oben).
- **MAJOR 4:** Ein Ablauf mit Upload-Feld galt für `frisch` weiter als schreibend. Der Direktstart
  ohne Klick schloss so die freie Arbeit samt Entwurf. Jetzt beginnt nur ein Ablauf, der selbst
  schreibt, in einem frischen Vorgang (`ablauf_schreibt_selbst`).
- **MAJOR 5:** Der Flow-Wächter brach Werksabgleich und Wiederherstellen ab, und er sperrte
  Flows, die nie freigegeben waren. Jetzt gilt er nur beim Speichern dieses einen Bereichs, und
  nur für Flows, die heute frei sind und entzogen würden.
- **MINOR 6:** Der Satz zur Anmeldung steht jetzt vor dem Speichern, also auch nach dem Neuladen.
- **MINOR 7:** `einzeldatei_als_struktur` wirkt nur aus einem Ablauf-Schritt
  (`Umgebung.aus_ablauf`). Die KI sieht das Feld, es wirkt bei ihr nicht.
- **NIT 8:** Texte zu „Upload → nie direkt“ nachgezogen (Prüftext `direkt_schreibt`, Modell,
  Modul-Docstring).
- **NIT 9:** Die Kataloge setzen `inFlight` nur in der eigenen Generation zurück.
- **NIT 10/11:** Gegenstandslos, das Verdecken ist entfallen.
- **NIT 12:** Kommentar zu `role="alert"` korrigiert.

## Zweites Review TW-6 (unabhängig) und Behebung

1 MAJOR, 4 MINOR, 3 NIT, alle behoben.

- **MAJOR 1:** Rief die KI in derselben Runde das Upload-Feld **und** `respond_to_user` auf, wurde
  das Modul umgelenkt, die Antwort („lade hier hoch“) blieb aber stehen: Sackgasse ohne Feld und
  ohne Ablauf. Jetzt verwerfen beide Maschinen die Antwort dieser Runde (`ANTWORT_UMGELENKT`), die
  nächste Runde ruft den Ablauf. Test: `test_tw6_umlenkung.py` (Agent und Muster).
- **MINOR 2:** Ein umgelenktes Modul galt in der Agent-Schleife noch als „Frage der Runde“; ein
  Ablauf derselben Runde bekam darum „nach der Frage“. Die Prüfung fragt jetzt die Umlenkung,
  ohne einen Versuch zu zählen (`merken=False`).
- **MINOR 3:** Das Umschalten der Fassung eines einzelnen Bereichs (`umschalten`) prüft den
  Flow-Wächter wie das Speichern.
- **MINOR 4/5:** Tests für die Arbeitsgrundlage (gemerkter Entwurf) und für das Prüfen ohne
  Zählen.
- **NIT 6–8:** englischer Prüftext, Sprache des Hinweises (`lang`), Docstring.
- Dazu: Nach einer Umlenkung zählt ein zweiter, gleicher Aufruf nicht als Stillstand
  (`last_call = None`), sonst brach der Fluchtweg „ohne Ablauf“ ab.
- **Volle Suite danach:** 14 Tests hingen noch am alten Seed „aus Ordnern“ (erst Upload-Feld) oder
  an der alten Regel „Upload schreibt“. Nachgezogen, ohne ihre Absicht zu ändern:
  - Die Zug- und Postgres-Tests wählen zuerst „Ja, Ordner wählen“.
  - FT1 nimmt einen Ablauf mit Upload und Auftrag. Neu: Ein Ablauf nur mit Upload-Feld behält die
    freie Arbeit.
  - Der AS-0-Fassungstest prüft die Umstellung selbst, nicht mehr den heutigen Seed.
  - `wann` von „aus Ordnern“ ist auf unter 120 Zeichen gekürzt, sonst bräuchte das Feld eine
    Textfläche.
  - Ein älterer Zeit-Test (Z-6, Verlauf wartet nicht auf die Anmeldung) kippte unter Last bei
    2,5 s. Er misst jetzt mit 30 s Wartezeit gegen eine Grenze von 10 s.
- **Endstand:** Backend 9 962 grün (zuvor 1 Kippler, nachgezogen); Frontend 4 Projekte grün,
  Lint, Prüfskripte, Widget-Bau, Budget, Modulregister grün.

