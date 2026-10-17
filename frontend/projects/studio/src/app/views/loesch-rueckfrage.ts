/**
 * Die Rückfrage vor dem Löschen eines Ordner-Dokuments (ST-3d), an EIN
 * Dokument gebunden (Review Paket 6).
 *
 * Vorher hing sie an einem Schalter: Duplizieren oder Anlegen öffnete ein
 * anderes Dokument, die Rückfrage blieb offen und nannte nun dieses — mit dem
 * Hinweis zum Auslieferungsstand des alten —, und „Ja, löschen“ traf die neue
 * Kopie. Jetzt gilt sie nur für den Schlüssel, für den sie gestellt wurde, und
 * ein Fehler steht nur bei seinem Dokument.
 */
import { signal } from '@angular/core';

import type { GroupDocuments } from './group-documents';

export class LoeschRueckfrage {
  /** Der Schlüssel, für den die Rückfrage offen ist; leer = keine. */
  private readonly fuer = signal('');
  /** Gehört das Dokument zum Auslieferungsstand? `null` = unbekannt. */
  readonly shipped = signal<boolean | null>(null);
  readonly busy = signal(false);
  private readonly fehler = signal<{ readonly key: string; readonly text: string } | null>(null);

  constructor(private readonly docs: Pick<GroupDocuments, 'remove' | 'shipped'>) {}

  offenFuer(key: string): boolean {
    return key !== '' && this.fuer() === key;
  }

  fehlerFuer(key: string): string {
    const fehler = this.fehler();
    return fehler && fehler.key === key ? fehler.text : '';
  }

  fragen(key: string): void {
    this.fehler.set(null);
    this.shipped.set(null);
    this.fuer.set(key);
    void this.docs.shipped(key).then((value) => {
      // Eine späte Antwort für ein anderes Dokument fällt weg.
      if (this.fuer() === key) this.shipped.set(value);
    });
  }

  /** Abbrechen, Wechseln, Anlegen, Duplizieren: die Rückfrage ist zu. */
  schliessen(): void {
    this.fuer.set('');
    this.shipped.set(null);
  }

  /**
   * Löscht das Dokument, für das die Rückfrage offen ist. `true` heißt gelöscht;
   * bei einem Fehler schließt die Rückfrage (ein zweites „Ja“ änderte nichts am
   * Grund) und der Fehler steht beim Dokument.
   */
  async loeschen(
    key: string, version: number | null, beschreibe: (err: unknown) => string,
  ): Promise<boolean> {
    if (!this.offenFuer(key) || this.busy()) return false;
    this.busy.set(true);
    try {
      await this.docs.remove(key, version);
      this.schliessen();
      return true;
    } catch (err) {
      this.schliessen();
      this.fehler.set({ key, text: beschreibe(err) });
      return false;
    } finally {
      this.busy.set(false);
    }
  }
}
