#!/usr/bin/env node
/**
 * Legt das Gerüst eines neuen UI-Moduls an (Paket U1-a) und erneuert danach das Register.
 *
 * Aufruf: npm run module:neu -- <name> [--abfragen]
 *   <name> ohne Präfix, Kleinbuchstaben und Bindestriche, z. B. `linkbox` → Ordner `ui-linkbox`,
 *   Modulname `ui_linkbox`, Klasse `UiLinkbox`. `--abfragen` legt ein abfragendes Modul an
 *   (mit Antwort-Schema).
 *
 * Danach: manifest.json ausfüllen (Beschreibung, Eingabe mit description je Feld, Beispiele),
 * Komponente bauen, `npm run module:register`, Tests.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { erzeuge, pascal } from './module-register.mjs';

/** Paket R3-g: die Vorschau-Spec des Studios verlangt den Manifest-Import JEDES Moduls — das Gerüst
 *  trägt ihn ein (Import vor dem Register, Name in `MANIFESTE`). Fehlt die Stelle, bleibt es beim
 *  Hinweis: der Test der Vorschau sagt dann, was fehlt. */
export function inVorschauEintragen(specPfad, ordner) {
  const text = readFileSync(specPfad, 'utf8');
  const kurz = ordner.slice(3).replace(/-([a-z0-9])/g, (_m, c) => c.toUpperCase());
  // Querschnitts-Review, NIT 11: trägt die Spec den Namen schon (etwa `function text`), ein Präfix
  const name = new RegExp(`\\b${kurz}\\b`).test(text) ? `manifest${pascal(ordner).slice(2)}` : kurz;
  const anker = "import { MODUL_REGISTER } from '@boerdi/ui-module/register.generated';";
  const liste = /const MANIFESTE = \[([^\]]*)\] as unknown/;
  if (!text.includes(anker) || !liste.test(text)) return false;
  const neu = text
    .replace(anker, `import ${name} from '@boerdi/ui-module/${ordner}/manifest.json';\n${anker}`)
    .replace(liste, (_m, alt) => `const MANIFESTE = [${alt}, ${name}] as unknown`);
  writeFileSync(specPfad, neu);
  return true;
}

export function geruest({ quelle, backend, kurzname, abfragen = false, vorschauSpec = null }) {
  if (!/^[a-z][a-z0-9-]{1,38}$/.test(kurzname)) {
    throw new Error(`Name „${kurzname}“: Kleinbuchstaben, Ziffern, Bindestriche, ohne Präfix ui-`);
  }
  const ordner = `ui-${kurzname}`;
  const name = ordner.replace(/-/g, '_');
  const klasse = pascal(ordner);
  const ziel = join(quelle, ordner);
  if (existsSync(ziel)) throw new Error(`${ordner} gibt es schon`);
  mkdirSync(ziel);

  const manifest = {
    name, version: 1, art: abfragen ? 'abfragen' : 'anzeigen',
    titel: { de: klasse, en: klasse },
    beschreibung: 'TODO: Was zeigt das Modul, wofür ist es gut? (Grundlage der Werkzeugbeschreibung)',
    wann: ['TODO: wann die KI das Modul nutzen soll'],
    nicht_wann: ['TODO: wann nicht (und welches Modul stattdessen)'],
    agent: false,
    eingabe: {
      type: 'object', additionalProperties: false, required: ['text'],
      properties: { text: { type: 'string', maxLength: 2000, description: 'TODO: Bedeutung des Felds' } },
    },
    ...(abfragen ? {
      antwort: {
        type: 'object', additionalProperties: false, required: ['wert'],
        properties: { wert: { type: 'string', description: 'TODO: was zurückkommt' } },
      },
    } : {}),
    datenquelle: null,
    faehigkeiten: abfragen ? ['antworten'] : [],
    textfassung: { vorlage: 'markdown', feld: 'text' },
    darstellung: { breit: false },
    beispiele: [{ titel: 'Standard', daten: { text: 'Beispieltext' }, ...(abfragen ? { antwort: { wert: 'a' } } : {}) }],
  };
  writeFileSync(join(ziel, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');

  writeFileSync(join(ziel, `${ordner}.component.ts`), `import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { ModulKontext } from '../_vertrag/ui-block';

/** Eingabe laut manifest.json (\`eingabe\`). */
export interface ${klasse}Daten {
  readonly text: string;
}

@Component({
  selector: '${ordner}',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './${ordner}.component.scss',
  template: \`<div class="${ordner}">{{ daten().text }}</div>\`,
})
export class ${klasse} {
  readonly daten = input.required<${klasse}Daten>();
  readonly kontext = input.required<ModulKontext>();
}
`);
  writeFileSync(join(ziel, `${ordner}.component.scss`), `.${ordner} {\n  font: inherit;\n}\n`);
  writeFileSync(join(ziel, `${ordner}.component.spec.ts`), `// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';

import manifest from './manifest.json';
import { ${klasse} } from './${ordner}.component';

/** Jedes Beispiel aus manifest.json muss rendern — Angular fängt Fehler nicht je Modul ab. */
describe('${klasse}', () => {
  afterEach(() => TestBed.resetTestingModule());

  for (const beispiel of manifest.beispiele) {
    it(\`rendert das Beispiel „\${beispiel.titel}“\`, async () => {
      TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
      const f = TestBed.createComponent(${klasse});
      f.componentRef.setInput('daten', beispiel.daten);
      f.componentRef.setInput('kontext', { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null });
      await f.whenStable();
      expect((f.nativeElement as HTMLElement).textContent?.trim()).not.toBe('');
    });
  }
});
`);
  writeFileSync(join(ziel, 'README.md'), `# ${name}

TODO: Wofür ist das Modul da, was zeigt es, wo sind seine Grenzen?

- Eingabe und Antwort: \`manifest.json\` (JSON Schema, je Feld eine description — die KI liest sie).
- Beispiele: \`manifest.json\` → \`beispiele\` (Vorschau, Vertragstests, Studio).
- Nach jeder Manifest-Änderung: \`npm run module:register\`.
`);
  const vorschau = vorschauSpec !== null && inVorschauEintragen(vorschauSpec, ordner);
  return { ordner, register: erzeuge({ quelle, backend }), vorschau };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const kurzname = process.argv[2];
  if (!kurzname) {
    console.error('Aufruf: npm run module:neu -- <name> [--abfragen]');
    process.exit(1);
  }
  const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const { ordner, vorschau } = geruest({
    quelle: join(frontend, 'projects', 'ui-module', 'src'),
    backend: join(frontend, '..', 'backend', 'src', 'boerdi', 'ui_module'),
    kurzname, abfragen: process.argv.includes('--abfragen'),
    vorschauSpec: join(frontend, 'projects', 'studio', 'src', 'app', 'views',
                       'ui-modul-vorschau.component.spec.ts'),
  });
  console.log(`angelegt: projects/ui-module/src/${ordner}/ — Register erneuert`
    + (vorschau ? ', Vorschau-Spec ergänzt.' : '; Vorschau-Spec bitte von Hand ergänzen.'));
}
