/**
 * Die Kataloge, aus denen ein Formularfeld seine Vorschläge zieht (S4).
 *
 * Gehalten statt bei jedem Feld geholt: ein Bereichs-Formular hat leicht ein
 * Dutzend Katalog-Felder, und alle zeigen auf dieselben sieben Listen. Der
 * erste Abruf gilt für die ganze Sitzung; ein zweiter Aufruf von `prime()`
 * hängt sich an den laufenden an, statt einen weiteren zu starten.
 *
 * Ein Fehlschlag ist kein Fehlerzustand der Oberfläche: ohne Kataloge bleibt
 * das Feld ein normales Textfeld, so wie vor S3. Er wird deshalb geschluckt und
 * nirgends festgehalten — ein Formular soll nicht daran scheitern, dass eine
 * Bedienhilfe nicht kam, und ein Merker, den niemand liest, ist nur Ballast.
 */
import { Injectable, inject, signal } from '@angular/core';

import { StudioApi } from './studio-api.service';

export interface ChoiceEntry {
  readonly value: string;
  readonly label: string;
  /** Bereichsschlüssel für den Sprung ins Formular; leer = keine eigene Seite. */
  readonly area: string;
}

export type ChoiceCatalogs = Readonly<Record<string, readonly ChoiceEntry[]>>;

@Injectable({ providedIn: 'root' })
export class ChoicesApi {
  private readonly api = inject(StudioApi);
  private readonly loaded = signal<ChoiceCatalogs>({});
  private inFlight: Promise<void> | null = null;

  /** Leer, solange nichts geladen ist — nie `undefined`. */
  readonly catalogs = this.loaded.asReadonly();

  /** Holt die Kataloge einmal. Mehrfach zu rufen ist erlaubt und billig. */
  prime(): Promise<void> {
    this.inFlight ??= this.api
      .get<ChoiceCatalogs>('/config/choices')
      .then((katalog) => this.loaded.set(katalog))
      .catch(() => {
        // Bewusst still: das Feld fällt auf Freitext zurück, und ein Formular
        // mit einer roten Meldung über eine fehlende Vorschlagsliste wäre
        // lauter als der Schaden.
        this.inFlight = null; // ein späterer Versuch darf es nochmal probieren
      });
    return this.inFlight;
  }

  entries(catalog: string | undefined): readonly ChoiceEntry[] {
    return catalog ? (this.catalogs()[catalog] ?? []) : [];
  }

  /** Der Bereichsschlüssel zu einem Wert, oder `''` wenn es keinen gibt. */
  areaFor(catalog: string | undefined, value: string): string {
    return this.entries(catalog).find((e) => e.value === value)?.area ?? '';
  }
}
