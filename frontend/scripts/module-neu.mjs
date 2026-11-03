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
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { erzeuge, pascal } from './module-register.mjs';

export function geruest({ quelle, backend, kurzname, abfragen = false }) {
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
  return { ordner, register: erzeuge({ quelle, backend }) };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const kurzname = process.argv[2];
  if (!kurzname) {
    console.error('Aufruf: npm run module:neu -- <name> [--abfragen]');
    process.exit(1);
  }
  const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const { ordner } = geruest({
    quelle: join(frontend, 'projects', 'ui-module', 'src'),
    backend: join(frontend, '..', 'backend', 'src', 'boerdi', 'ui_module'),
    kurzname, abfragen: process.argv.includes('--abfragen'),
  });
  console.log(`angelegt: projects/ui-module/src/${ordner}/ — Register erneuert.`);
}
