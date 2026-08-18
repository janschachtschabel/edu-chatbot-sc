# Beispiel: Chrome-Erweiterung mit Agent-Schleife und strukturiertem Ergebnis

Eine Seitenleiste, in der man **ausprobieren** kann, was
`docs/browser-plugin-einbindung.md` §4a–§7a beschreibt:

* Kontext **automatisch** aus dem Tab, **manuell** getippt (Sammlung,
  Themenseite, Einzelinhalt, Suche) oder **ganz aus**,
* ein **Auftrag**, mit dem der Chat startet,
* ein **JSON-Schema** für die Form des Ergebnisses,
* die Unterhaltung selbst — man kann weiterchatten,
* und in der unteren Hälfte daneben: **was strukturiert herauskommt**, Zug für
  Zug.

Läuft mit `engine="agent"` und `show-welcome="false"` — siehe „Kein Empfang"
weiter unten.

## Getrennt vom übrigen Code

Dieser Ordner hat **keinen** Import aus `frontend/` oder `backend/`, keinen
Build-Schritt und keine Abhängigkeit. Der Dockerfile kopiert nur `frontend/`
und `backend/`; die CI arbeitet nur in diesen beiden. Er lässt sich
herauskopieren und woanders weiterverwenden.

Die einzige Doppelung ist die Adress-Erkennung in `context.js` — bewusst
nachgebaut statt importiert, siehe den Kopf der Datei.

Die `package.json` enthält **keine dependencies**. Sie sagt node allein, dass
die `.js`-Dateien ES-Module sind. Es gibt nichts zu installieren.

## Einrichten

**1 · Backend läuft** und liefert das Widget-Bündel unter
`/widget/boerdi-widget.js`.

**2 · Bündel holen** (Manifest V3 verbietet nachgeladenen Code — siehe
`vendor/LIESMICH.md`). Dieselbe Adresse, die auch im Feld „Backend" stehen soll:

```bash
node scripts/fetch-widget.mjs https://87.106.127.225.nip.io
```

Nur gegen ein Backend, dem ihr vertraut: was hier ankommt, läuft danach mit den
Rechten der Erweiterung.

**3 · Laden**: `chrome://extensions` → Entwicklermodus an → „Entpackte
Erweiterung laden" → diesen Ordner wählen. Klick auf das Symbol öffnet die
Seitenleiste.

**3a · „Verbindung prüfen" drücken.** Ins Feld „Backend" gehört die **Adresse
des Servers**, nicht die Bündel-Datei — `https://beispiel.test`, nicht
`https://beispiel.test/widget/boerdi-widget.js`. Der Chat-Client hängt `/api`
an, was dort steht; aus der Bündel-Adresse würde
`…/boerdi-widget.js/api/chat/stream` und jeder Zug endete mit „es ist ein
Fehler aufgetreten" (live gemessen 2026-08-14: 404 gegen 200).

Die Prüfung sagt es sofort und zeigt zugleich, **gegen welches Repositorium**
der Bot läuft — sonst merkt man das erst am Ziel eines Karten-Links.

**4 · Beim ersten „Starten" fragt Chrome nach Zugriff** auf die eingetragene
Backend-Adresse — bestätigen. `host_permissions` im Manifest deckt nur
`localhost` und `127.0.0.1`; jede andere Adresse (Staging-Server,
`nip.io`-Adresse) wird über `optional_host_permissions` zur Laufzeit erfragt,
und zwar für **genau diese eine Herkunft**. Das ist der Grund, warum das
Manifest nicht `<all_urls>` verlangt.

Lehnt ihr ab, sagt die Leiste es und startet nicht — statt in einen
CORS-Fehler zu laufen, der nur in der Konsole steht.

**5 · Alternative: das Backend erlaubt die Erweiterung.** Nach dem Laden zeigt
`chrome://extensions` die Kennung; beim Backend eintragen:

```
CORS_ORIGINS=chrome-extension://<eure-kennung>
```

**Seit dem 18.08.2026 meist unnoetig:** Erweiterungs-Herkuenfte sind von sich aus
erlaubt (`CORS_ALLOW_EXTENSIONS`, Vorgabe an). Der Eintrag oben schadet nicht und
bleibt der Weg, wenn ein Betreiber den Schalter ausgeschaltet hat.

Einer der beiden Wege genügt. Die Kennung ändert sich, wenn ihr den Ordner an
einen anderen Pfad legt.

## Bedienen — zwei Reiter

Auf 360 px Breite steht die Steuerung dem Gespräch im Weg. Deshalb:

* **Einstellungen** — Verbindung, Kontext, Auftrag, Schema.
* **Chat** — oben das Gespräch, unten die strukturierten Ergebnisse, je zur
  Hälfte.

„Starten" wechselt selbst in den Chat; sonst liefe der Zug unsichtbar. Der
Chat-Bereich wird beim Wechseln nur **versteckt**, nie neu gebaut —
`<boerdi-chat>` hält Sitzung und Verlauf in seiner Instanz. Die Reiter sind mit
Pfeiltasten, Home und End bedienbar.

| Abschnitt | was er tut |
|---|---|
| **Verbindung** | Backend-Adresse + „Verbindung prüfen" (zeigt Status, Repositorium, Modell). |
| **1 Kontext** | `automatisch` liest die Adresse des Tabs. `manuell` nimmt nur die getippten Felder. `aus` gibt gar keinen Kontext — die ehrliche Vergleichsgröße. Die Klappe „Was geht raus?" zeigt das Objekt, das an `replaceContext()` geht. |
| **2 Auftrag und Struktur** | Fünf Vorlagen; das Schema ist frei editierbar. Der Status darunter sagt, ob es gültig ist — und **kaputtes JSON startet nicht**: der Zug bliebe sonst 90 Sekunden lang ohne Ergebnis, das er gar nicht liefern kann. Ein **leeres** Feld startet sehr wohl, es heißt „ohne Struktur". |
| **Ergebnis** (Chat-Reiter, unten) | Je Zug ein Eintrag, neuester oben, mit `stop_reason` als Marke. „Starten" leert die Liste: sonst stünden Einträge zweier Läufe mit verschiedenen Schemata untereinander. |

Die fünf Vorlagen: **Fach und Stufe zuordnen** · **Kuratierung: Metadatensatz
bilden** (Titel, Beschreibung, Keywords, wwwurl, Fach, Bildungsstufe,
Inhaltstyp) · **Qualitätsprüfung mit Skills** · **Sachlich richtig? (gegen das
Kompendium)** · **Zusammenfassung + Schlagworte**. Die letzte braucht keine
MCP-Werkzeuge und ist damit der billigste Probelauf, wenn man nur sehen will, ob
der Weg überhaupt steht.

### Kein Empfang: `show-welcome="false"`

Die Leiste setzt das Attribut, der Chat startet also **leer** — ohne „Hey, schön
dass du da bist!" und ohne die vier Einstiegs-Chips. Der Auftrag steht schon im
Feld nebenan und geht sofort hinaus; eine Begrüßung wäre eine Nachricht, die
niemand gelesen hat, bevor die Antwort sie wegschiebt.

Das Attribut gibt es erst seit dem 14.08.2026. **Ein älteres Bündel in `vendor/`
kennt es nicht** und begrüßt weiter — daran hängt nichts, was man ansieht, also
prüft man es am Bündel selbst:

```bash
grep -c showWelcome vendor/boerdi-widget.js
```

`0` heißt: altes Bündel. Dann entweder `node scripts/fetch-widget.mjs …` gegen
ein Backend mit frischem Bündel, oder aus dem Repositorium heraus bauen:

```bash
cd ../../frontend && npm run build:widget
```

und `frontend/dist/widget/browser/main.js` nach `vendor/boerdi-widget.js`
kopieren. Danach in `chrome://extensions` auf „Neu laden" — ein getauschtes
Bündel sieht Chrome nicht von selbst.

### Seitentext: warum zwei Klicks

Adresse und Titel des Tabs gibt die `tabs`-Berechtigung her. Der **Text** braucht
eine Host-Berechtigung für genau diese Seite — `activeTab` genügt dafür
**nicht**, wenn die Erweiterung über die Seitenleiste bedient wird (live
2026-08-14 auf `de.wikipedia.org`: *„Extension manifest must request permission
to access this host"*).

Nachfragen lässt sich das nicht im selben Klick: `chrome.permissions.request`
verlangt eine Nutzergeste, und die ist nach `await chrome.tabs.query()`
verbraucht. Darum erscheint ein eigener Knopf **„Zugriff auf ‹Host› erlauben"**.
Auf internen Seiten (`chrome://`, Web Store) sagt die Leiste, dass Chrome dort
grundsätzlich nichts zulässt, statt einen Knopf ohne Aussicht anzubieten.

**Beide Klicks meinen denselben Tab.** Schritt 1 merkt sich die Tab-Kennung,
Schritt 2 liest genau diese. Wer stattdessen erneut „den aktiven Tab" abfragte,
bekäme nach einem Tab-Wechsel zwischen den Klicks den Text von Seite B unter der
Adresse von Seite A — bei gleicher Herkunft ohne jede Fehlermeldung. Gepinnt in
`scripts/check-tab.mjs`.

Die Eingaben werden gemerkt (`chrome.storage.local`), damit ein Neuladen der
Erweiterung nicht jedes Mal Tipparbeit kostet.

## Was man dabei sieht — und lernen soll

* **`result` ist je Zug optional.** „Danke!" ergibt kein Ergebnis. Der Eintrag
  erscheint trotzdem, mit dem Grund (`text`) — so ist der Unterschied zwischen
  „nichts dabei" und „abgeschnitten" (`deadline`) sichtbar.
* **Mit Schema kostet jeder Zug einen zusätzlichen Modellzug** (2–9 s gemessen).
  Stellt das Schema-Feld einmal leer und vergleicht die Antwortzeit.
* **Die `description`-Texte im Schema liest das Modell.** Sie sind Anweisung,
  nicht Notiz. In „Fach und Stufe zuordnen" steht deshalb ausdrücklich „die
  Vokabular-URI, NICHT der Klartext" — ohne diesen Satz kommt „Physik" zurück.
  Dasselbe gilt für den Auftrag: wo eine Aufgabe ein Werkzeug braucht
  (`lookup_wlo_vocabulary`, `search_skill`, `get_compendium_text`), steht es
  darin. Ohne den Hinweis rät das Modell aus dem Gedächtnis — und rät bei URIs
  zuverlässig falsch.
* **`auto-context="false"` ist gesetzt.** In einer Seitenleiste hat die eigene
  Erkennung nichts zu erkennen: die Adresse ist `chrome-extension://…` und
  ändert sich nie, auch wenn nebenan der Tab wechselt.

## Prüfen

```bash
npm run check
```

Sechs Prüfungen, alle ohne Browser und ohne Abhängigkeiten — und seit dem
14.08.2026 fährt die CI sie mit (eigener Job `beispiel-plugin`; vorher liefen
sie nur, wenn jemand sie tippte):

* `check-context.mjs` — 24 Fälle für `context.js` (Adress-Muster, die drei
  Betriebsarten, leere Felder, Parameter gegen Pfad).
* `check-backend.mjs` — 7 Fälle für `basisAusEingabe()`: die Bündel-Datei im
  Backend-Feld war der Fehler, der jeden Zug in ein 404 laufen ließ.
* `check-tab.mjs` — 19 Fälle für `tab-lesen.js` gegen ein `chrome`-Doppel.
  Wichtigster: Schritt 2 liest den Tab aus Schritt 1, nicht „den aktiven".
* `check-schemas.mjs` — „leer" gegen „kaputt", plus der 10 000-Zeichen-Deckel
  gegen jede Vorlage. Wer eine erweitert, merkt ihn sonst erst am 422.
* `check-ergebnisse.mjs` — die Liste gegen ein DOM-Doppel. Wichtigster Fall:
  nach „Starten" beginnt die Zählung wieder bei „Zug 1", statt über den Läufen
  weiterzulaufen.
* `check-ids.mjs` — jede `$('…')`-Kennung aus `panel.js` gibt es in
  `panel.html`. Ein Tippfehler dort wäre sonst ein `null`, das erst beim Klick
  auffällt — in einer Seitenleiste, deren Konsole man erst aufmachen muss.

Der Rest ist Formular-Verdrahtung und lässt sich nur im Browser beurteilen.

## Grenzen

* **Nicht live gemessen.** Der Ordner ist gegen die geschriebene Schnittstelle
  gebaut und über die fünf Prüfungen oben abgesichert; in einem echten Chrome
  lief er noch nicht. Das erste Laden ist die eigentliche Probe. Was die
  Prüfungen NICHT sehen: das Zusammenspiel im Formular (welcher Text nach
  welchem Klick wo steht) und alles, was Chrome selbst entscheidet.
* **Kein Linter.** Der Ordner hat bewusst keine Abhängigkeiten, also auch kein
  eslint — und `node --check` sieht nur Syntax. Eine vergessene Umbenennung
  (`baueChat(schema)`, wo die Variable inzwischen `stand` heißt) ist damit erst
  beim Klick ein Fehler. Beim Umbauen von `panel.js` lohnt ein Blick in die
  Konsole der Seitenleiste; die Alternative wäre eine Abhängigkeit, und die
  kostet mehr, als dieses Beispiel wert ist.
* **Kein Anmelde-Weg.** Es gibt weder Ticket noch Zugangsblock; der Bot
  arbeitet anonym und kann deshalb nichts schreiben. Für den angemeldeten
  Betrieb siehe `docs/edu-sharing-einbindung.md` §3.
* **`activeTab` + `scripting`** werden nur beim Klick auf „Aus dem Tab
  übernehmen" genutzt. Auf internen Seiten (`chrome://`, Web Store) verweigert
  Chrome das — die Leiste sagt es dann.
* **Der Seitentext wird bei 20 000 Zeichen gekappt**, der Grenze des
  Agent-Endpunkts. Ungekappt wäre er der häufigste Grund für ein 422.
