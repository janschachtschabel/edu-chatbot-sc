# Das Upload-Feld stellt nur bereit (2026-11-16)

Anlass: Rückmeldung vom 16.11.:

> Das Upload-Feld (und andere UI-Module) soll Daten nur bereitstellen. Was damit geschieht,
> entscheiden die nachfolgenden Schritte. Feste Knöpfe wie „Themenbaum aus dem Strukturdokument
> erstellen“ gehören nicht ins Upload-Feld.

Pakete TG-1 (Frontend und Manifest) und TG-2 (Backend) im Plan
`docs/plans/2026-11-16-themenbaum-generisch.md`, Entscheide G-E4 bis G-E6, mit den Befunden zweier
unabhängiger Reviews und einer Nachprüfung behoben (erstes: 4 MAJOR, 7 MINOR, 4 NIT; zweites:
2 MAJOR, 6 MINOR, 3 NIT; Nachprüfung: 5 MINOR, 4 NIT und ein Fehler der vollen Suite).

## Was sich ändert

### Upload-Feld (`ui_upload`)

- **Keine Zielknöpfe mehr.** Es entfallen „Als Themenbaum-Entwurf übernehmen“ (Aktion
  `ordner_als_entwurf`) und „Themenbaum aus dem Strukturdokument erstellen“ (`dokument.ziel`).
- **„Lesen lassen“** (englisch „Read document“): Der Knopf am markierten Strukturdokument heißt
  neutral so; der Hinweis mit dem Dateinamen beschreibt ihn (`aria-describedby`). Die Antwort
  `aktion: dokument` trägt kein `ziel` mehr. Die Blase im Chat lautet „Dokument „…“ lesen lassen“
  bzw. „Read “…””.
- **Nach dem Lesen:** Läuft gerade ein Zug, wartet der Befund wie bisher auf einen Knopf. Er heißt
  jetzt „Weiter“ (Name „Weiter: gelesenes Dokument an den Chat“) statt „Themenbaum jetzt
  erstellen“.
- **Hauptknopf:** „Senden“ — außer ein Strukturdokument ist markiert und darf gelesen werden, dann
  „Lesen lassen“ (nach einem endgültigen Lesefehler wieder „Senden“).
- **Lehrplan-Automatik:** Sie merkt einen Lehrplan weiter als Strukturdokument vor. Gelesen wird
  erst auf Klick.
- **Datenschutzsatz:** Er nennt genau, was heute an den Chat geht: „Ordnernamen, Zahlen und der
  Name des Strukturdokuments gehen an den Chat.“ Dazu, je nach Angebot, dass das Strukturdokument
  erst beim Lesen hochgeladen wird und Dateien erst beim Übertragen an WLO gehen. Dateinamen
  fließen erst ab TG-3; dann ändert sich der Satz.
- **Manifest:**
  - `zweck` kennt `bereitstellen` (neu, Vorgabe) und `sammlungsstruktur` (bleibt gültig).
  - `ziel` und `ordner_als_entwurf` sind aus dem Antwortschema entfernt.
  - Beschreibung und `wann` enthalten keine Themenbaum-Anweisung mehr.
  - `einzeldatei_als_struktur` bleibt.

### Backend

- **Neutrale Rahmen:** `[ORDNER DER PERSON …]` und `[DOKUMENT DER PERSON …]` sagen, was
  bereitliegt, und weisen nicht mehr an, `ui_strukturentwurf` zu rufen. Wortlaut: „Geht aus dem
  Verlauf und der Nachricht nicht hervor, was sie mit den Daten will: frag kurz und nenne passende
  Möglichkeiten (etwa …). Ist es klar (etwa Themenbaum): ruf den passenden Ablauf auf bzw. schlag
  ihn vor. Entwirf nichts ungefragt.“
  - Die Möglichkeiten folgen den Schaltern des Zugs: „die Dateien nach WLO übertragen“ nur mit
    Ablage und Anmeldung, „mit dem Dokument arbeiten“ nur im Dokument-Rahmen, „das
    Strukturdokument lesen lassen“ nur, wenn eins markiert ist und gelesen werden darf, „einen
    Themenbaum daraus“ nur, wenn `ui_strukturentwurf` an ist oder ein Ablauf passend zur Art
    angeboten ist (Dokument: einer, der ein Dokument liest; Ordner: einer mit Entwurf aus Ordnern).
- **Satz bei nicht gelesenem Strukturdokument:** Er verweist auf „Lesen lassen“ und zeigt das Feld
  erst, wenn die Person das will.
- **Sicherheitsprüfung:** Sie liest bei jeder Ordner-Antwort mit Unterordnern zuerst die Punkte des
  Entwurfs aus den Ordnern, die auch die KI sieht (gedeckelt wie dessen Kompaktfassung), gleich
  welche `aktion` — der Ablauf „aus Ordnern“ baut den Entwurf ohne LLM aus `erfasst`, und die
  Übersicht allein ist gedeckelt.
- **Kein Entwurf ohne LLM mehr aus dem Upload-Feld:** `services/ordner_aktion.py`, der Zweig im
  Preflight, `Ausloeser.ordner` und die Texte `action.folderDraft.*` sind entfernt. Eine
  Ordner-Antwort geht den gewöhnlichen Weg; ihre Teile übernimmt `persist` in den Vorgang.
- **Vorgang:** Ein neuer Vorgang ohne Ablauf trägt den Zweck `bereitstellen` statt
  `sammlungsstruktur` (eine Konstante `ui_module/namen.ZWECK_BEREITSTELLEN`).
- **Umlenkung auf Abläufe:** `ui_upload` mit `zweck: bereitstellen` wird nur noch auf einen
  Themenbaum-Ablauf umgelenkt, wenn die Nachricht des Zugs einen Themenbaum nennt: „Themenbaum“
  (auch „Themen-Baum“), „Sammlungsstruktur“, „Sammlungsbaum“, „topic tree“ (auch „topic-tree“),
  „collection structure/tree“ sowie „Struktur“ und „Gliederung“ als ganzes Wort (nicht
  „Strukturdokument“, „Ordnerstruktur“, „Zellstruktur“ …). Sonst dient das Feld ebenso
  einem Dokument oder dem Übertragen nach WLO. Mit `sammlungsstruktur` (oder ohne Zweck) lenkt es
  weiter immer um.
- **Abläufe „aus einem Dokument“ und „aus Ordnern“ übernehmen Bereitgestelltes** (G-E6):
  - Sie beginnen mit dem neuen Dienst `bereitgestellt` (ohne LLM, Teil `bereit`). Er meldet ein
    Dokument nur als lesbar, wenn es das lesbare Dokument der Sitzung ist, und Ordner mit der Zahl
    der Unterordner.
  - Danach eine von zwei Fassungen des Einstiegs: ohne nutzbare Daten wie bisher, sonst „Gern …
    aus deinem Dokument „…“ / deinen Ordnern „…“. Soll ich … verwenden?“ (Ja / Andere wählen /
    Ohne Führung). Ordner ohne Unterordner und unlesbare Dokumente werden nicht angeboten.
  - Die Leiste zählt so ohne Sprung; einen Zwischenschritt „übernehmen“ gibt es nicht.
- **Schnellantworten können Teile verwerfen** (`verwirft: [teil, …]`, neues Feld, Vorgabe leer):
  Der Treiber entfernt sie aus dem Vorgang, bevor es weitergeht, die Simulation ebenso; die
  Prüfung meldet unbekannte Teile. „Andere wählen“ verwirft das alte Dokument bzw. die alten
  Ordner — sonst nähme der Ablauf nach bloßem „Senden“ still das abgelehnte Dokument.
- **Bereitgestelltes geht beim Start mit:** Freie Arbeit landet wie bisher im aktuellen Vorgang.
  Schließt ein Start ihn, weil sein Lauf beendet ist oder einem anderen Ablauf gehört, übernimmt
  der neue Vorgang die Bereitstellungs-Teile `structure` und `document` (Inhalt bzw. Verweis auf
  das Sitzungsdokument; kein Entwurf, kein Lauf, keine Antworten). Vorher gingen sie mit dem alten
  verloren. Ein erster Ansatz, freie Arbeit nach einem beendeten Lauf in einen neuen Vorgang zu
  legen, ist zurückgenommen (Randfälle: zwei Tabs, weiter bearbeiteter Entwurf, wartende Führung,
  Grenze von drei Vorgängen); die Zahl der Vorgänge steigt nicht stärker als vor TG-2.
- **Nicht verwerfbar:** `verwirft` darf keine Teile mit Verweisen ins Repositorium nennen (heute
  `ablage`); die Prüfung meldet es. `verwirft: [document]` nimmt nur den Teil, das
  Sitzungsdokument bleibt lesbar (im freien Chat könnte `aus_dokument` es noch lesen).
- **Ablauf „aus einem Dokument“:** Der Modul-Auslöser `wenn_teil: document` entfällt. Ein
  gelesenes Dokument startet nichts von selbst. Die Texte nennen „Lesen lassen“. Die Frage nach dem
  Lesen samt Ausstieg (`gelesen_frage`, `frei`) ist entfallen; erreichbar war sie nur über den
  Modul-Auslöser.
- **Master-Skill** (`docs/skills/vorgehen-knapp.md`): `ui_upload` mit `zweck: bereitstellen`;
  Punkt „Nach dem Hochladen“ mit demselben Wortlaut wie der Rahmen; ohne angebotenen Ablauf aus
  Ordnern `ui_strukturentwurf` mit dem Ordnernamen als Thema und den oberen Ordnern als
  `hinweise`.
- **Studio:** Die Hinweise „Dokument im Chat lesen“ und „Auch ohne WLO-Anmeldung“ sind neutral.

## Rückwärts

- **Alte Antworten aus offenen Verläufen** (ein noch offenes Widget mit altem Bündel) nimmt das
  Backend einen Release lang an. Die Antwortform hebt sie **vor** der Schema-Prüfung auf die neue
  Form (`Form.rueckwaerts`, `upload_antwort.rueckwaerts`):
  - `aktion: ordner_als_entwurf` gilt als `erfasst` — „Senden“, ohne direkten Entwurf; auch ein
    wartender Lauf „aus Ordnern“ geht damit weiter;
  - `dokument.ziel: themenbaum` entfällt — wie „Lesen lassen“.
  - Ein unbekanntes Ziel verwirft das Schema weiter.
- **`zweck: sammlungsstruktur`** bleibt gültig: in den Seeds der übrigen Abläufe und bei einem
  älteren Master-Skill im Repositorium.
- **Laufende Läufe** von „aus einem Dokument“ und „aus Ordnern“ brechen beim Werksabgleich ab, weil
  sich die Fassung ändert. Andere Abläufe behalten ihre Fassung: `verwirft` ist ohne Angabe nicht
  gesetzt.

## Geprüft

- **Backend:** `pytest -k "upload or ablauf or ordner or dokument or seed or ui_modul or skill or
  vorschlag or arbeitsstand or vorgang or fortschritt or restbefunde"`: 2289 bestanden,
  1 übersprungen. Gezielt (Upload, Preflight, Umlenkung, Seeds, Arbeitsstand, Vorgänge gegen
  Postgres, Master-Skill, Ablauf-Zug und -Pg, Beispiele, Leiste, Simulation, Prüfung, Datenfluss,
  Agent- und Tool-Schleife, Dienste, Restbefunde RB-2, Querschnitt Vorgang): 837 grün. Darin neu:
  - Rückwärtstests (alte Ordner- und Dokument-Antwort, auch in einen wartenden Lauf, unbekanntes
    Ziel), neutrale Rahmen und ihre Möglichkeiten je Schalter, Sicherheitsprüfung bei `erfasst`;
  - Dienst `bereitgestellt` (lesbar, fremd, Unterordner, kaputte Teile, Kurzbeschreibung);
  - `verwirft` (Modell, Fassung, Treiber, Simulation, Prüfung, `vorgaenge.teil_entfernen` gegen
    Postgres samt Ablage, Historie und Konflikt);
  - Integration im Ablauf-Harness: beendeter Lauf → freier Upload → Start → Übernahme (Ordner und
    Dokument), wartender fremder Lauf → Upload → anderer Start → Übernahme, zweiter Tab lässt den
    wartenden Lauf unberührt, Entwurf nach dem Ende bleibt im selben Vorgang, freie Arbeit legt
    keinen Vorgang an, nur Bereitstellung wird übernommen, unlesbares Dokument, „Anderes wählen“
    + „Senden“ → Rückfrage; `verwirft` auf `ablage` ist ein Befund;
  - Leiste beider Seeds ohne Sprung, Umlenkung mit Wortgrenzen (Negativfälle), Zugstand je Zug.
  - ruff sauber.
- **Frontend:** `ui-module` 403, `studio` 2156 (auch nach dem Typnamen `bereit`), `ui` 1513 (Lauf der ersten Runde, das Projekt blieb unverändert) Specs grün (darunter `fields.spec.ts`:
  jedes Schema-Feld hat Texte, auch `verwirft`). ESLint sauber.
- **Playwright:** `upload-erfassen`, `upload-uebertragen`, `upload-und-fortschritt` nach
  `npm run build:widget`: 12 grün.
- **Drift:** Manifeste neu erzeugt; Studio-Schema und OpenAPI neu erzeugt (nur das Feld
  `verwirft`), danach ohne Drift.
- **Nicht geprüft:** Chat-Smoke mit der KI (ob sie nach dem Hochladen fragt statt zu entwerfen) und
  die ganze Backend-Suite.

## Deploy

- Image neu bauen (es baut Widget und nachgeladene Module selbst, `npm run build:widget`). Keine
  Migration. Danach im Browser neu laden: das alte Modul-Bündel ist cachebar.
- `import-config --werksabgleich` für die Abläufe „aus einem Dokument“ und „aus Ordnern“, wenn sie
  auf Staging im Studio nicht angepasst wurden.
- **Eigene Studio-Fassungen** von „aus einem Dokument“ und „aus Ordnern“ behalten den alten
  Knopftext („Themenbaum aus dem Strukturdokument erstellen“), den Modul-Auslöser und den
  Neustart ohne Übernahme. Die Redaktion übernimmt die Werksfassung (Studio, „Abläufe“).
- **Master-Skill gleichzeitig** im Repositorium über den md-editor aus
  `docs/skills/vorgehen-knapp.md` übertragen. Vorher widerspricht der alte („den Themenbaum …
  entwerfen“) dem neutralen Rahmen; die KI ruft das Feld weiter mit `sammlungsstruktur`, das
  gültig bleibt und wie bisher auf einen Ablauf umlenkt.
