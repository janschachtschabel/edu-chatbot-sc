import { describe, expect, it } from 'vitest';

import { AREA_SCHEMAS } from '../../schema-form/area-schemas.fixture';
import type { JsonSchema } from '../../schema-form/json-schema';
import { rootField, type SchemaField } from '../../schema-form/schema-to-fields';
import { areasWithForm } from '../../views/area-homes';
import { STUDIO_DE } from '../de';
import { STUDIO_EN } from '../en';

/**
 * Der Wächter von ST-1 (Plan 2026-09-26 §9.3): jedes Feld einer kuratierten
 * Seite hat Beschriftung und Hilfetext in beiden Sprachen — und kein
 * `feld.`-Text steht im Katalog, zu dem es kein Feld mehr gibt.
 *
 * Ohne die zweite Richtung ließe eine Umbenennung im Modell den alten Text
 * still liegen, und das umbenannte Feld fiele auf den Rohschlüssel zurück —
 * sichtbar nur für den, der genau hinsieht.
 */

/** Bereiche ohne eigenen Fixture-Eintrag teilen das Modell eines anderen
 *  (siehe Kopf der Fixture). Ausdrücklich statt als Pauschal-Rückfall: ein
 *  neuer Bereich soll hier laut scheitern, nicht still ein fremdes Schema
 *  prüfen. */
const GLEICHES_MODELL: Readonly<Record<string, string>> = {
  '01-base/guardrails': '01-base/base-persona',
  '02-domain/domain-rules': '01-base/base-persona',
  '02-domain/wlo-plattform-wissen': '01-base/base-persona',
};

function schemaOf(area: string): JsonSchema {
  const schema = AREA_SCHEMAS[area] ?? AREA_SCHEMAS[GLEICHES_MODELL[area] ?? ''];
  if (!schema) throw new Error(`kein Schema für den Bereich ${area}`);
  return schema;
}

function textKeys(field: SchemaField, into: Set<string>): Set<string> {
  if (field.textKey) into.add(field.textKey);
  for (const child of field.children ?? []) textKeys(child, into);
  if (field.item) textKeys(field.item, into);
  return into;
}

/** Die Klartext-Schlüssel der Auswahlwerte (ST-2d): `<choiceKey>.wahl.<wert>`. */
function choiceKeys(field: SchemaField, into: Set<string>): Set<string> {
  if (field.choiceKey) {
    for (const wert of field.choices ?? []) into.add(`${field.choiceKey}.wahl.${wert}`);
  }
  for (const child of field.children ?? []) choiceKeys(child, into);
  if (field.item) choiceKeys(field.item, into);
  return into;
}

/** Seit ST-9 auch die Bereiche, die auf Kosten und Evaluation eingebettet sind
 *  (`DASHBOARD_SECTIONS`) — dort erscheint dasselbe Formular. */
const KURATIERT = areasWithForm();

describe('Feldtexte der kuratierten Seiten (ST-1)', () => {
  it('jedes Feld trägt Beschriftung und Hilfetext in beiden Sprachen', () => {
    const fehlend: string[] = [];
    for (const area of KURATIERT) {
      for (const key of textKeys(rootField(schemaOf(area)), new Set())) {
        for (const teil of ['label', 'hint']) {
          for (const [sprache, katalog] of [['de', STUDIO_DE], ['en', STUDIO_EN]] as const) {
            if (!katalog[`${key}.${teil}`]?.trim()) fehlend.push(`${sprache} ${key}.${teil}`);
          }
        }
      }
    }
    expect(fehlend, `${fehlend.length} Feldtexte fehlen`).toEqual([]);
  });

  it('jeder Auswahlwert hat einen Klartext in beiden Sprachen (ST-2d)', () => {
    const fehlend: string[] = [];
    for (const area of KURATIERT) {
      for (const key of choiceKeys(rootField(schemaOf(area)), new Set())) {
        for (const [sprache, katalog] of [['de', STUDIO_DE], ['en', STUDIO_EN]] as const) {
          if (!katalog[key]?.trim()) fehlend.push(`${sprache} ${key}`);
        }
      }
    }
    expect(fehlend, `${fehlend.length} Klartexte fehlen`).toEqual([]);
  });

  it('jeder Regler mit Schwellen nennt seine drei Zonen in beiden Sprachen (ST-2h)', () => {
    const fehlend: string[] = [];
    const regler = (field: SchemaField): void => {
      if (field.thresholds?.length && field.textKey) {
        for (const zone of ['unter', 'mitte', 'ueber']) {
          const key = `${field.textKey}.zone.${zone}`;
          if (!STUDIO_DE[key]?.trim()) fehlend.push(`de ${key}`);
          if (!STUDIO_EN[key]?.trim()) fehlend.push(`en ${key}`);
        }
      }
      for (const child of field.children ?? []) regler(child);
      if (field.item) regler(field.item);
    };
    for (const area of KURATIERT) regler(rootField(schemaOf(area)));
    expect(fehlend).toEqual([]);
  });

  it('kein Feldtext ohne Feld — nach einer Umbenennung bliebe er still liegen', () => {
    const bekannt = new Set<string>();
    const werte = new Set<string>();
    for (const schema of Object.values(AREA_SCHEMAS)) {
      textKeys(rootField(schema), bekannt);
      choiceKeys(rootField(schema), werte);
    }
    const verwaist = Object.keys(STUDIO_DE)
      .filter((key) => key.startsWith('feld.'))
      .filter((key) => (key.includes('.wahl.')
        ? !werte.has(key)
        : !bekannt.has(key.replace(/\.(label|hint|zone\.(unter|mitte|ueber))$/, ''))));
    expect(verwaist).toEqual([]);
  });

  it('prüft wirklich etwas: die kuratierten Seiten haben Hunderte Felder', () => {
    let anzahl = 0;
    for (const area of KURATIERT) anzahl += textKeys(rootField(schemaOf(area)), new Set()).size;
    expect(anzahl).toBeGreaterThan(250);
  });
});
