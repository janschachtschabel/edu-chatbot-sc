/**
 * Der Zustand der Feld-Reiter eines Muster-Dokuments (A7): welche Reiter es
 * gibt, welcher offen ist, welche Felder er zeigt — und in welchem Reiter ein
 * gesperrtes Feld steckt.
 *
 * Aus `group-section.component.ts` herausgelöst (Paket 6), als Duplizieren und
 * Löschen dazukamen; den Schnitt selbst beschreibt `pattern-field-tabs.ts`.
 */
import { computed, signal } from '@angular/core';

import type { JsonSchema } from '../schema-form/json-schema';
import { rootField } from '../schema-form/schema-to-fields';
import { type FieldTab, patternFieldTabs } from './pattern-field-tabs';

export class FeldReiter {
  /** Welcher Reiter offen ist; leer = der erste. Er bleibt beim Wechsel des
   *  Dokuments stehen: alle Dokumente der Gruppe teilen ein Schema, und wer
   *  „Anweisungen" vergleicht, will nicht bei jedem Muster neu klicken. */
  private readonly wanted = signal('');

  readonly tabs = computed<readonly FieldTab[]>(() => {
    const schema = this.schema();
    if (!schema || !this.enabled()) return [];
    return patternFieldTabs(rootField(schema));
  });

  readonly active = computed(() => {
    const tabs = this.tabs();
    const wanted = this.wanted();
    return tabs.some((tab) => tab.id === wanted) ? wanted : (tabs[0]?.id ?? '');
  });

  readonly visiblePaths = computed<readonly string[] | null>(() => {
    const active = this.active();
    return this.tabs().find((tab) => tab.id === active)?.paths ?? null;
  });

  /**
   * Die gesperrten Felder mit ihrem Reiter. Ohne den Namen suchte man ein
   * gesperrtes Speichern in fünf Reitern; der Fehler steht ja unter dem
   * Formular, nicht bei seinem Feld.
   */
  readonly blocked = computed<readonly string[]>(() =>
    this.fieldErrors().map((path) => {
      const tab = this.tabs().find((entry) => entry.paths.some((p) => isUnder(path, p)));
      return tab ? `${path} (Reiter „${tab.label}")` : path;
    }),
  );

  constructor(
    private readonly schema: () => JsonSchema | null,
    private readonly enabled: () => boolean,
    private readonly fieldErrors: () => readonly string[],
  ) {}

  select(id: string): void {
    this.wanted.set(id);
  }
}

/** Fehlerpfad `frontmatter.tools` bzw. ein Kind davon (`…tools.0`)? */
function isUnder(path: string, field: string): boolean {
  return path === field || path.startsWith(`${field}.`);
}
