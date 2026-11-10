# Paket BU-1 — Widget-Bündel: Debug-Panel ohne Pipes, Logo gerundet (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5i (Entscheide BU-a, BU-b, BU-c).

**Anlass:** Nach AS-Ub stand `main.js` bei 689,5 kB roh / 200,0 kB gzip, also an beiden harten
Grenzen (690 / 200).

**Geändert:**
- **Debug-Panel** (`ui/src/debug/debug-panel.component.ts`): Die vier Angular-Pipes `number`,
  `json`, `keyvalue` und `slice` sind durch kleine Funktionen ersetzt (`zahl`, `eintraege`, `json`,
  `String.slice`). Die Ausgabe bleibt gleich:
  - gerundet wird wie bei `DecimalPipe` auf den Dezimalziffern (0,825 → „0.83“; `Intl` allein
    ergäbe „0.82“);
  - en-US mit Tausendertrennern und festen Stellen;
  - Schlüssel sortiert wie bei `keyvalue`;
  - JSON eingerückt wie bei `json`;
  - was auf Null rundet, trägt kein Minus (Review, NIT 7).

  Neue Spec-Fälle „Formate ohne Pipes (BU-1)“ halten das fest. Sie liefen zuerst gegen die Pipes
  (Charakterisierung) und danach unverändert gegen die Funktionen.
- **Logo** (`ui/src/branding/boerdi-logo.ts`): Die Pfadzahlen sind auf eine Nachkommastelle gerundet,
  Schritt 4 im Dateikopf beschreibt das.
  - Der Pixelvergleich bei 512 px zeigt Abweichungen nur in der Kantenglättung: 37 von 262.144
    Pixeln, fast durchsichtige Randpixel oder eine Graustufe an der Pupillenkante.
  - Zahlenfolgen ohne Trenner (`1.5.3`) bleiben richtig.

**Bewusst nicht (BU-b):** Die acht scheinbar ungenutzten Icons bleiben im Widget. Das Icon der
Kopfzeilen-Knöpfe ist im Studio ein freies Feld („ein Icon aus dem Widget“). Ein entferntes Icon
würde in einer bestehenden Konfiguration ohne Warnung zu `explore`.

**Wirkung:** `main.js` sinkt von 689,5 auf 677,1 kB roh und von 200,0 auf 195,1 kB gzip.

**Prüfung:**
- Debug-Panel-Spec: 17 Fälle grün.
- ui 1275 und widget 93 grün.
- ESLint sauber.
- `npm run budget` eingehalten.

**Review:** gemeinsam mit BU-2 (Tabelle in `2026-11-10-paket-bu-2-strukturentwurf-nachgeladen.md`). Für BU-1 kam nur NIT 7 (`-0.00`); er ist behoben.
