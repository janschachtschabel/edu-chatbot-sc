/**
 * Vertrag zwischen Chat-Shell und UI-Modulen (Paket U1).
 *
 * Ein `UiBlock` ist ein Aufruf eines Moduls in einer Bot-Antwort, so wie das Backend ihn an
 * `ui.ui_bloecke` liefert (`backend/src/boerdi/api/schemas_ui.py`, `UiBlock`). Die Felder hier
 * spiegeln das Backend-Modell eins zu eins; ändert sich eines, ändern sich beide.
 */

export type UiModulArt = 'anzeigen' | 'abfragen';
export type UiBlockStatus = 'offen' | 'beantwortet' | 'nur_anzeige' | 'veraltet';

export interface UiBlock {
  readonly block_id: string;
  /** Modulname, z. B. `ui_inhaltsrahmen` — zugleich der Schlüssel im Register. */
  readonly modul: string;
  /** Hauptversion des Manifests, mit der die Daten gebaut wurden. */
  readonly version: number;
  readonly art: UiModulArt;
  /** Eingabe des Moduls, vom Backend gegen `manifest.eingabe` geprüft. */
  readonly daten: Record<string, unknown>;
  /** Textfassung (Markdown) — steht, wo das Modul fehlt oder die Version nicht passt. */
  readonly text: string;
  readonly status: UiBlockStatus;
  /** Bei `beantwortet`: die gegebene Antwort, damit das Modul sie nur lesend zeigt. */
  readonly antwort?: Record<string, unknown> | null;
}

/** Was jedes Modul neben seinen Daten bekommt. */
export interface ModulKontext {
  readonly blockId: string;
  readonly sprache: 'de' | 'en';
  /** `true` bei beantworteten oder veralteten Blöcken: nur zeigen, nichts mehr auslösen. */
  readonly nurLesen: boolean;
  readonly antwort: Record<string, unknown> | null;
  /** Schriftskala für Inhalte (0,7–1; aus den Anzeige-Regeln, Vorgabe 0,85). */
  readonly schriftSkala: number;
  /** Anzeige-Regeln der Nachricht (`display_rules`, z. B. Gruppen-Grenzen), sonst `null`. */
  readonly anzeigeRegeln: Record<string, unknown> | null;
}
