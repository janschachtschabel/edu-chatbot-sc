# Beispiel: Chrome-Erweiterung mit Agent-Schleife und strukturiertem Ergebnis

Eine Seitenleiste, in der man **ausprobieren** kann, was
`docs/browser-plugin-einbindung.md` §5–§7a beschreibt:

* Kontext **automatisch** aus dem Tab, **manuell** getippt (Sammlung,
  Themenseite, Einzelinhalt, Suche) oder **ganz aus**,
* ein **Auftrag**, mit dem der Chat startet,
* ein **JSON-Schema** für die Form des Ergebnisses,
* die Unterhaltung selbst — man kann weiterchatten,
* und unten: **was strukturiert herauskommt**, Zug für Zug.

Läuft mit `engine="agent"`.

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
`vendor/LIESMICH.md`):

```bash
node scripts/fetch-widget.mjs http://localhost:8000
```

**3 · Laden**: `chrome://extensions` → Entwicklermodus an → „Entpackte
Erweiterung laden" → diesen Ordner wählen. Klick auf das Symbol öffnet die
Seitenleiste.

**4 · Backend die Erweiterung erlauben.** Nach dem Laden zeigt
`chrome://extensions` die Kennung. Beim Backend eintragen:

```
CORS_ORIGINS=chrome-extension://<eure-kennung>
```

Ohne das schlägt jeder Zug mit einem CORS-Fehler in der Konsole der
Seitenleiste fehl. Die Kennung ändert sich, wenn ihr den Ordner an einen
anderen Pfad legt.

**5 · Anderes Backend als localhost?** Dann gehört seine Herkunft in
`manifest.json` unter `host_permissions` — dort stehen bisher nur
`http://localhost/*` und `http://127.0.0.1/*`.

## Bedienen

| Schritt | was er tut |
|---|---|
| **1 Kontext** | `automatisch` liest die Adresse des Tabs (Knopf „Aus dem Tab übernehmen"). `manuell` nimmt nur die getippten Felder. `aus` gibt gar keinen Kontext — die ehrliche Vergleichsgröße. Die Klappe „Was geht raus?" zeigt das Objekt, das an `replaceContext()` geht. |
| **2 Auftrag und Struktur** | Drei Vorlagen zum Loslegen; das Schema ist frei editierbar. Der Status unter dem Feld sagt sofort, ob es gültig ist — kaputtes JSON soll man **vor** dem Start sehen. |
| **3 Unterhaltung** | Das Widget. Nach dem Auftakt ist es ein gewöhnlicher Chat; jeder weitere Zug erzeugt wieder ein Ergebnis. |
| **4 Ergebnis** | Je Zug ein Eintrag, neuester oben, mit `stop_reason` als Marke. |

Die Eingaben werden gemerkt (`chrome.storage.local`), damit ein Neuladen der
Erweiterung nicht jedes Mal Tipparbeit kostet.

## Was man dabei sieht — und lernen soll

* **`result` ist je Zug optional.** „Danke!" ergibt kein Ergebnis. Der Eintrag
  erscheint trotzdem, mit dem Grund (`text`) — so ist der Unterschied zwischen
  „nichts dabei" und „abgeschnitten" (`deadline`) sichtbar.
* **Mit Schema kostet jeder Zug einen zusätzlichen Modellzug** (2–9 s gemessen).
  Stellt das Schema-Feld einmal leer und vergleicht die Antwortzeit.
* **Die `description`-Texte im Schema liest das Modell.** Sie sind Anweisung,
  nicht Notiz. In der Vorlage „Fachzuordnung" steht deshalb ausdrücklich „die
  Vokabular-URI, NICHT der Klartext" — ohne diesen Satz kommt „Physik" zurück.
* **`auto-context="false"` ist gesetzt.** In einer Seitenleiste hat die eigene
  Erkennung nichts zu erkennen: die Adresse ist `chrome-extension://…` und
  ändert sich nie, auch wenn nebenan der Tab wechselt.

## Prüfen

```bash
npm run check
```

Zwei Prüfungen, beide ohne Browser und ohne Abhängigkeiten:

* `check-context.mjs` — 22 Fälle für `context.js`, die einzige Stelle mit
  echter Logik (Adress-Muster, die drei Betriebsarten, leere Felder).
* `check-ids.mjs` — jede `$('…')`-Kennung aus `panel.js` gibt es in
  `panel.html`. Ein Tippfehler dort wäre sonst ein `null`, das erst beim Klick
  auffällt — in einer Seitenleiste, deren Konsole man erst aufmachen muss.

Der Rest ist Formular-Verdrahtung und lässt sich nur im Browser beurteilen.

## Grenzen

* **Nicht live gemessen.** Der Ordner ist gegen die geschriebene Schnittstelle
  gebaut und über `check-context.mjs` geprüft; in einem echten Chrome lief er
  noch nicht. Das erste Laden ist die eigentliche Probe.
* **Kein Anmelde-Weg.** Es gibt weder Ticket noch Zugangsblock; der Bot
  arbeitet anonym und kann deshalb nichts schreiben. Für den angemeldeten
  Betrieb siehe `docs/edu-sharing-einbindung.md` §3.
* **`activeTab` + `scripting`** werden nur beim Klick auf „Aus dem Tab
  übernehmen" genutzt. Auf internen Seiten (`chrome://`, Web Store) verweigert
  Chrome das — die Leiste sagt es dann.
* **Der Seitentext wird bei 20 000 Zeichen gekappt**, der Grenze des
  Agent-Endpunkts. Ungekappt wäre er der häufigste Grund für ein 422.
