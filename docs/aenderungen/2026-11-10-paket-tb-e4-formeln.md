# Paket TB-E4: Formeln im Widget als MathML (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md` §4, Gruppe E. Grundlage ist der Nutzer-Entscheid
N5: „direkt integrieren — wir erhöhen die Limits für die Größe des Widgets um 10 kB.“

## Befund (nachgestellt mit dem Muster des Nutzers vom 10.11.)

Das Modell schreibt Formeln als LaTeX, etwa `\(\frac{2}{3}\cdot\frac{3}{5}\)`. Im Widget sah man
„(⅔\cdot³⁄₅)“ und „(\frac{1+2}{4}=¾)“. Drei Ursachen kamen zusammen:

- `stripLatex` lief vor allem anderen. Es machte aus reinen Zahlenbrüchen Unicode (`⅔`), ließ aber
  `\frac{1+2}{4}`, `\cdot`, `^`, `_` und die griechischen Buchstaben roh stehen.
- `marked` liest `\(` und `\[` als maskierte Klammern und machte daraus `(` und `[`.
- Einen Formel-Renderer gab es nicht.

## Entscheid zum Weg (selbst getroffen, dokumentiert)

**Keine Bibliothek.** Laut npm-Metadaten bringt temml (MIT, LaTeX→MathML) 2,1 MB entpackt mit,
seine minifizierte Datei liegt bei über 150 kB. KaTeX ist noch größer und braucht dazu Schriftdateien.
Beide lägen weit über den 10 kB. Deshalb gibt es eine **eigene kleine Umwandlung** von LaTeX in
**MathML**:

- MathML zeichnet der Browser selbst. Es braucht keine Schriftdatei und keine Netzquelle (DSGVO).
- Bildschirmleser lesen MathML als Formel.
- Die Größe misst +2,3 kB gzip.

## Umsetzung

- **`ui/src/markdown/formel.ts`:**
  - `formelnHerausnehmen` findet `\(…\)`, `\[…\]`, `$$…$$` und `$…$`.
    - Code (Backticks, Zaunblöcke) bleibt unberührt.
    - Ein `$` gilt nur ohne Leerraum direkt daran und ohne folgende Ziffer. So ist „$5 und $10“
      keine Formel.
    - An die Stelle der Formel tritt der Platzhalter `@@FORMEL:n@@`.
  - `texZuMathml` wandelt die häufigen Formen um:
    - Potenz und Index (`msup`, `msub`, `msubsup`), Bruch (`mfrac`), Wurzel (`msqrt`, `mroot`);
    - Zahlen mit Dezimalkomma als eine Zahl;
    - Relationen, Operatoren und Pfeile;
    - griechische Buchstaben, Funktionen (`sin`, `log` …), `\text{…}`;
    - Akzente (`\vec`, `\overline`, `\hat`), `\left`/`\right`.
  - Ein unbekannter Befehl bleibt als Text lesbar (`\befehl`).
  - Eine kaputte Klammer beendet nur die Gruppe.
  - Bei mehr als 2000 Zeichen oder mehr als 40 Ebenen bleibt das LaTeX als Text stehen.
- **`markdown-renderer.ts`:**
  1. Formeln herausnehmen.
  2. `stripLatex` (nur noch für LaTeX außerhalb von Formeln).
  3. `marked`.
  4. DOMPurify.
  5. Dann erst das MathML einsetzen.
- **Sicherheit:**
  - Jedes Zeichen aus dem LaTeX wird maskiert. Markup entsteht nur aus den festen Tags der
    Umwandlung.
  - DOMPurify bekommt **kein** MathML-Profil. So bleibt rohes `<math href=…>` aus dem Modelltext
    verboten wie bisher.
  - Ein vom Modell getippter Platzhalter ohne Formel fällt weg.
- **CSS:** Eine abgesetzte Formel scrollt quer, statt die Blase zu sprengen (Reflow bei 320 px).
  Inline ist sie etwas größer als der Text.
- **Budget:** Roh 690 → 700 kB, gzip 200 → 210 kB, Warnung 190 → 200 kB
  (`check-widget-budget.mjs`). Angular warnt ab 660 kB und bricht bei 700 kB ab.
- **Master-Skill** (`docs/skills/vorgehen-knapp.md`, Wissensfrage):
  - „Formeln als LaTeX: im Satz `\( … \)`, abgesetzt `\[ … \]`“;
  - einfache Zahlen und Einheiten ohne LaTeX.
  - Den Knoten in WLO aktualisiert der Nutzer.

## Review (unabhängig) und Behebung

Es gab 2 CRITICAL, 1 MAJOR, 6 MINOR und 3 NIT. Der Prüfer hat die Befunde mit einem node-Skript
gegen marked, DOMPurify und jsdom nachgestellt.

- **CRITICAL 1:** Ein getippter Platzhalter ohne Formel wurde **leer** ersetzt, und zwar nach
  DOMPurify. Aus `java@@FORMEL:9@@script:` wurde so ein `javascript:`-Link.
- **CRITICAL 2:** Steht ein Platzhalter in einem Attribut (Link-Titel), brachen die Anführungszeichen
  im MathML (`display="block"`) aus dem Attribut aus. Ergebnis: `<img onerror>`.
- **Behebung beider:** Eingesetzt wird jetzt **im DOM** (`formelnEinsetzen`, über ein inertes
  `<template>`).
  - MathML nur in Textknoten außerhalb von `code` und `pre`.
  - In `code` und `pre` und in Attributen steht der LaTeX-Quelltext.
  - URL-Attribute mit Platzhalter fallen ganz weg.
  - Der Platzhalter trägt einen **Zufallswert je Render** (`@@FORMEL-<nonce>-n@@`). Ein vom Modell
    getippter trifft nie und wird nie geleert.
- **MAJOR:** Regressionstests für genau diese Angriffe, als DOM geprüft (`img`, `onerror`, `href`).
- **MINOR:**
  - Code in `~~~`, in Code-Spans mit mehreren Backticks und in eingerückten Blöcken bleibt Quelltext
    (über `code`/`pre` im DOM).
  - `\[1\]` ist keine Formel mehr (nur mit `\`, `^`, `_` oder `=` darin).
  - Formeln enden an einem Absatz.
  - `$PATH:$HOME` ist keine Formel.
  - Geldbeträge behalten ihr `$` (`stripLatex(…, { dollar: false })` im Renderer).
  - Zeichen außerhalb der BMP bleiben ganz.
  - `\left (` mit Leerzeichen geht; `\\` (Zeilenumbruch) wird ein Abstand.
- **Bewusst so gelassen:**
  - `1,2` gilt als Dezimalzahl (deutsche Schreibweise). Koordinaten wie `f(1,2)` liest ein
    Bildschirmleser dadurch als Zahl.
  - `\sum` mit Grenzen in abgesetzten Formeln steht als `msubsup`, nicht als `munderover`.
  - Eine quer scrollende Blockformel bekommt kein `tabindex` (neuere Browser scrollen per Tastatur).
- **Im Browser geprüft** (Chromium, Prüfseite mit dem Muster des Nutzers):
  - Brüche, `·`, gemischte Zahl, Wurzel mit Index, Vektorpfeile und Formeln im Satz werden richtig
    gezeichnet.
  - Dabei kam ein eigener Fehler ans Licht: `display: block` stapelte die Teile abgesetzter Formeln
    untereinander. Richtig ist `display: block math`, dazu `overflow-y: hidden` gegen einen leeren
    Rollbalken.
- **Bündel danach:** 192,1 kB gzip / 660,3 kB roh. Angular warnt beim Roh-Budget 660 kB um 0,3 kB; das
  ist nur eine Warnung, die Grenze liegt bei 700 kB.

## Grenzen

- Nur eine Teilmenge von LaTeX. Matrizen, `\begin{…}`-Umgebungen und `\overbrace` bleiben Text.
- Der Canvas zeigt Formeln weiter als Text (`stripLatex`); sein Prompt verbietet LaTeX deshalb
  weiter. Druckfenster und Vorlesen behandeln Formeln seit dem Querschnitts-Review
  (`aenderungen/2026-11-10-querschnitt-gruppe-e.md`).

## Prüfung

- `formel.spec.ts`: 11 Fälle.
  - Sie decken Erkennen, Umwandlung, Sicherheit und das Muster des Nutzers ab.
  - Zuerst rot, weil das Modul fehlte.
  - Gegenprobe: Ohne die Einbindung in den Renderer sind 4 Fälle rot.
- `markdown-renderer.spec` und `latex.spec` bleiben grün.
- Widget-Bündel: 191,6 kB gzip / 658,8 kB roh, das Budget ist eingehalten. `check:tokens` sauber.
