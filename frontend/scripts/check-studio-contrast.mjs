#!/usr/bin/env node
/**
 * CI-Gate gegen drei Fokus- und Kontrastfehler in den Studio-Stylesheets
 * (Review 2026-09-29). Jede der Deklarationen ist gültiges CSS — kein Linter,
 * kein Build und kein Test meldet sie, und im Bild fallen sie nur auf, wenn man
 * weiß, wonach man sucht.
 *
 * **Regel 1 — `fokus`: kein `outline: none`.** Den Fokusring zeichnet EINE
 * Regel: `:focus-visible` in `styles.scss` (2px `--st-accent`, 4,63:1 auf dem
 * Panel). 57 Stellen schalteten ihn ab und setzten einen halbtransparenten
 * `box-shadow` dagegen — auf Weiß rund 1,9:1 statt 3:1 (SC 1.4.11), und im
 * Forced-Colors-Modus verwirft der Browser `box-shadow` ganz: dort war der Fokus
 * unsichtbar (SC 2.4.7). Eine Stelle las den Schatten-Wert als Outline-Farbe;
 * die Deklaration wurde erst zur Laufzeit ungültig und nahm den globalen Ring
 * mit, weil sie ihn in der Kaskade schon geschlagen hatte.
 *
 * **Regel 2 — `auf-akzent`: `--st-on-accent` und `--st-accent` nur als Paar.**
 * `--st-on-accent` ist die Schrift AUF der Akzentfläche — im hellen Schema Weiß.
 * Als Schrift auf dem Panel war sie unsichtbar (sieben Stellen, dazu der Link im
 * Skill-Verzeichnis). Umgekehrt braucht Text auf der Akzentfläche genau dieses
 * Token: `--st-bg` darauf erreicht nur 4,43:1.
 *
 * **Regel 3 — `feldrahmen`: Formularfelder nicht mit Trennlinien-Token rahmen.**
 * Der Rand eines Eingabefelds ist die Kante, an der man es als Feld erkennt
 * (SC 1.4.11, 3:1). `--st-rule-strong` erreicht rund 2,5:1, `--st-rule` 1,35:1 —
 * beide sind für Trennlinien da; Felder rahmen mit `--st-text-muted` (7,0:1).
 * Welche Klassen Felder tragen, liest das Skript aus den Templates (`class` an
 * `<input>`, `<select>`, `<textarea>`), dazu Selektoren, deren Subjekt eines
 * dieser Elemente direkt nennt (`.qf-field input`).
 *
 * Warum ein Skript und kein Komponententest: jsdom rechnet keine Kaskade mit
 * `var()`, und der Defekt ist eine Eigenschaft ALLER Stylesheets, auch der noch
 * nicht geschriebenen. Gebaut im Muster von `check-a11y-structure.mjs`.
 *
 * Aufruf: node scripts/check-studio-contrast.mjs [wurzel]
 * Ohne Argument: `projects/studio/src`.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const STANDARD_WURZEL = 'projects/studio/src';
const SKIP_DIRS = new Set(['node_modules', 'dist', '.angular']);

/**
 * `datei|selektor` → Begründung. Ein Eintrag ohne Grund ist, wie ein Gate
 * leise aufhört zu prüfen.
 */
const AUSNAHMEN_FOKUS = new Map([
  [
    'app/shell/shell.component.scss|.main:focus',
    'Sprungziel des Skip-Links (`<main tabindex="-1">`), kein Bedienelement — '
    + 'ein Ring rahmte die ganze Seite.',
  ],
]);

const AKZENT = /var\(\s*--st-accent\s*\)/;
const AUF_AKZENT = /var\(\s*--st-on-accent\s*\)/;
const TRENNLINIE = /var\(\s*--st-rule(?:-strong)?\s*\)/;
const RAHMEN = /^border(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?(?:-color)?$/;
const FELD_ELEMENT = /^(?:input|select|textarea)$/;
/** Start-Tag eines Felds; Anführungszeichen geklammert, damit `>` in Bindungen nicht abschneidet. */
const FELD_TAG = /<(input|select|textarea)\b((?:[^>"']|"[^"]*"|'[^']*')*)>/gi;

const wurzel = resolve(process.argv[2] ?? STANDARD_WURZEL);

function* wandern(verzeichnis) {
  for (const eintrag of readdirSync(verzeichnis)) {
    if (SKIP_DIRS.has(eintrag)) continue;
    const pfad = join(verzeichnis, eintrag);
    if (statSync(pfad).isDirectory()) yield* wandern(pfad);
    else yield pfad;
  }
}

function kurzpfad(pfad) {
  return relative(wurzel, pfad).replace(/\\/g, '/');
}

/** Zeile (1-basiert) eines Zeichen-Index. */
function zeileVon(text, index) {
  return text.slice(0, index).split('\n').length;
}

/** Backtick-Strings nach `schluessel:` in einer .ts-Datei, mit Start-Index. */
function literale(quelle, schluessel) {
  const funde = [];
  const kopf = new RegExp(`\\b${schluessel}\\s*:\\s*\\[?`, 'g');
  for (const treffer of quelle.matchAll(kopf)) {
    let i = treffer.index + treffer[0].length;
    while (/[\s,]/.test(quelle[i] ?? '') || quelle[i] === '`') {
      if (quelle[i] !== '`') { i += 1; continue; }
      const ende = quelle.indexOf('`', i + 1);
      if (ende < 0) break;
      funde.push({ text: quelle.slice(i + 1, ende), start: i + 1 });
      i = ende + 1;
    }
  }
  return funde;
}

/** Kommentare ZEILENTREU ausblenden, damit die gemeldeten Zeilen stimmen. */
function ohneKommentare(css) {
  const leer = (block) => block.replace(/[^\n]/g, ' ');
  return css
    .replace(/\/\*[\s\S]*?\*\//g, leer)
    .replace(/(^|[^:'"])(\/\/[^\n]*)/gm, (_, vor, rest) => vor + leer(rest));
}

/** Komma-Liste auf oberster Ebene teilen (`:is(a, b)` bleibt ganz). */
function teileListe(selektor) {
  const teile = [];
  let tiefe = 0;
  let anfang = 0;
  for (let i = 0; i < selektor.length; i += 1) {
    const z = selektor[i];
    if (z === '(') tiefe += 1;
    else if (z === ')') tiefe -= 1;
    else if (z === ',' && tiefe === 0) {
      teile.push(selektor.slice(anfang, i).trim());
      anfang = i + 1;
    }
  }
  teile.push(selektor.slice(anfang).trim());
  return teile.filter(Boolean);
}

/** SCSS-Verschachtelung (`&`) zu vollständigen Selektoren auflösen; @-Regeln zählen nicht. */
function aufloesen(kette) {
  let aussen = [''];
  for (const glied of kette) {
    if (glied.startsWith('@')) continue;
    const neu = [];
    for (const a of aussen) {
      for (const t of teileListe(glied)) {
        if (t.includes('&')) neu.push(t.replaceAll('&', a));
        else neu.push(a ? `${a} ${t}` : t);
      }
    }
    aussen = neu;
  }
  return aussen.filter(Boolean);
}

/** Das Subjekt eines Selektors: das letzte Glied, ohne den Inhalt von Pseudo-Klammern. */
function subjekt(selektor) {
  const flach = selektor.replace(/\((?:[^()]|\([^()]*\))*\)/g, '');
  const glieder = flach.split(/\s*[>+~]\s*|\s+/).filter(Boolean);
  return glieder.at(-1) ?? '';
}

/**
 * `none` als Stil, eine Breite von null oder `transparent` als Farbe — auch mit
 * `!important`. `transparent` ist der Umweg, der den Ring nur im Forced-Colors-
 * Modus zeigt und im Normalbetrieb einem Schatten überlässt.
 */
function ohneRing(wert) {
  return wert.replace(/\s*!important$/i, '').split(/\s+/)
    .some((teil) => teil === 'none' || teil === 'transparent' || /^0(?:[a-z]+)?$/i.test(teil));
}

function istFeld(selektor, feldKlassen) {
  const s = subjekt(selektor);
  const element = s.match(/^[a-z][a-z0-9-]*/i)?.[0] ?? '';
  if (FELD_ELEMENT.test(element)) return true;
  return [...s.matchAll(/\.([\w-]+)/g)].some(([, klasse]) => feldKlassen.has(klasse));
}

/** Blöcke mit Selektor-Kette und Deklarationen (inkl. Zeile) — reicht für die Studio-SCSS. */
function bloecke(css, zeilenVersatz) {
  const text = ohneKommentare(css);
  const ergebnis = [];
  const stapel = [{ kette: [], dekl: [] }];
  let puffer = '';
  let pufferZeile = 0;
  let zeile = 1;
  const deklarationAbschliessen = () => {
    const m = puffer.trim().match(/^([a-z-]+)\s*:\s*([\s\S]+)$/i);
    if (m) {
      stapel.at(-1).dekl.push({
        eigenschaft: m[1].toLowerCase(),
        wert: m[2].replace(/\s+/g, ' ').trim(),
        zeile: pufferZeile + zeilenVersatz,
      });
    }
    puffer = '';
  };
  for (const zeichen of text) {
    if (zeichen === '{') {
      const kopf = puffer.trim().replace(/\s+/g, ' ');
      stapel.push({ kette: [...stapel.at(-1).kette, kopf], dekl: [] });
      puffer = '';
    } else if (zeichen === '}') {
      deklarationAbschliessen();
      const block = stapel.pop();
      if (stapel.length === 0) stapel.push({ kette: [], dekl: [] });
      if (block.kette.length) ergebnis.push(block);
    } else if (zeichen === ';') {
      deklarationAbschliessen();
    } else {
      if (!puffer.trim() && zeichen.trim()) pufferZeile = zeile;
      puffer += zeichen;
    }
    if (zeichen === '\n') zeile += 1;
  }
  return ergebnis;
}

// ── Quellen einsammeln ────────────────────────────────────────────────
const stylesheets = [];
const templates = [];
let dateien = 0;
for (const pfad of wandern(wurzel)) {
  if (pfad.endsWith('.spec.ts')) continue;
  const endung = pfad.slice(pfad.lastIndexOf('.'));
  if (!['.scss', '.css', '.html', '.ts'].includes(endung)) continue;
  dateien += 1;
  const quelle = readFileSync(pfad, 'utf8');
  const datei = kurzpfad(pfad);
  if (endung === '.html') templates.push(quelle);
  else if (endung === '.ts') {
    for (const { text, start } of literale(quelle, 'styles')) {
      stylesheets.push({ datei, css: text, versatz: zeileVon(quelle, start) - 1 });
    }
    for (const { text } of literale(quelle, 'template')) templates.push(text);
  } else stylesheets.push({ datei, css: quelle, versatz: 0 });
}

const feldKlassen = new Set();
for (const html of templates) {
  for (const [, , attribute] of html.matchAll(FELD_TAG)) {
    for (const [, doppelt, einfach] of attribute.matchAll(/\bclass\s*=\s*(?:"([^"]*)"|'([^']*)')/g)) {
      for (const k of (doppelt ?? einfach).split(/\s+/)) if (k && !k.includes('{')) feldKlassen.add(k);
    }
    for (const [, gebunden] of attribute.matchAll(/\[class\.([\w-]+)\]/g)) feldKlassen.add(gebunden);
  }
}

// ── Prüfen ────────────────────────────────────────────────────────────
/** `{ regel, ort, ausschnitt }` je Verstoß. */
const verstoesse = [];
let regelBloecke = 0;
for (const { datei, css, versatz } of stylesheets) {
  for (const { kette, dekl } of bloecke(css, versatz)) {
    regelBloecke += 1;
    const selektoren = aufloesen(kette);
    const liste = selektoren.join(', ') || kette.join(' » ');
    const ort = (d) => `${datei}:${d.zeile}`;

    for (const d of dekl) {
      if (!/^outline(?:-style|-width|-color)?$/.test(d.eigenschaft) || !ohneRing(d.wert)) continue;
      if (selektoren.some((s) => AUSNAHMEN_FOKUS.has(`${datei}|${s}`))) continue;
      verstoesse.push({ regel: 'fokus', ort: ort(d), ausschnitt: `${liste} { ${d.eigenschaft}: ${d.wert} }` });
    }

    const hintergrund = dekl.find((d) => /^background(?:-color)?$/.test(d.eigenschaft));
    const aufAkzentflaeche = hintergrund && AKZENT.test(hintergrund.wert);
    for (const d of dekl.filter((x) => x.eigenschaft === 'color')) {
      const schriftAufAkzent = AUF_AKZENT.test(d.wert);
      if (schriftAufAkzent === Boolean(aufAkzentflaeche)) continue;
      const grund = schriftAufAkzent
        ? `Hintergrund ist ${hintergrund ? hintergrund.wert : 'nicht die Akzentfläche'}`
        : `Hintergrund ist var(--st-accent), Schrift ${d.wert}`;
      verstoesse.push({ regel: 'auf-akzent', ort: ort(d), ausschnitt: `${liste} — ${grund}` });
    }

    if (!selektoren.some((s) => istFeld(s, feldKlassen))) continue;
    for (const d of dekl) {
      if (!RAHMEN.test(d.eigenschaft) || !TRENNLINIE.test(d.wert)) continue;
      verstoesse.push({ regel: 'feldrahmen', ort: ort(d), ausschnitt: `${liste} { ${d.eigenschaft}: ${d.wert} }` });
    }
  }
}

console.log(`Wurzel:        ${wurzel}`);
console.log(`Dateien:       ${dateien}`);
console.log(`Regel-Blöcke:  ${regelBloecke}`);
console.log(`Feld-Klassen:  ${feldKlassen.size}`);

if (verstoesse.length) {
  const texte = {
    fokus: 'Kein `outline: none` (auch nicht 0 oder transparent) — den Fokusring'
      + ' zeichnet die globale `:focus-visible`-Regel in styles.scss. Ein Schatten'
      + ' als Ersatz verschwindet im Forced-Colors-Modus (SC 2.4.7).',
    'auf-akzent': '`--st-on-accent` ist die Schrift AUF `--st-accent` — beide'
      + ' gehören in denselben Block. Text auf Panel/Flächen: `--st-text` oder'
      + ' `--st-accent` (SC 1.4.3).',
    feldrahmen: 'Formularfelder rahmen mit `--st-text-muted` (7,0:1). `--st-rule`'
      + ' und `--st-rule-strong` bleiben unter 3:1 (SC 1.4.11).',
  };
  for (const regel of ['fokus', 'auf-akzent', 'feldrahmen']) {
    const treffer = verstoesse.filter((v) => v.regel === regel);
    if (!treffer.length) continue;
    console.error(`\n${treffer.length}× ${regel}: ${texte[regel]}`);
    for (const { ort, ausschnitt } of treffer) console.error(`  ${ort}  ${ausschnitt}`);
  }
  process.exit(1);
}
console.log('\nFokusring, Akzent-Paare und Feldrahmen sind in Ordnung.');
