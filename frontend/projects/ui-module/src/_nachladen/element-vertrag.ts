/**
 * Vertrag für nachgeladene UI-Module (Paket U3-0).
 *
 * Ein selten gebrauchtes Modul (`laden: "bei_bedarf"` im Manifest) ist kein Angular-Baustein, sondern
 * ein rahmenloses Custom Element in einem eigenen Bündel. So bleibt das Haupt-Bündel des Widgets
 * klein (Budget), und die klassische Einbettung mit einem `<script>` bleibt unverändert. Das Widget
 * zeigt an seiner Stelle den gemeinsamen Platzhalter (`nachlade-platzhalter.component.ts`), der das
 * Bündel lädt, das Element erzeugt und ihm dieselben Dinge gibt wie einer Komponente: Daten, Kontext
 * und — als einfaches Objekt — die Methoden des Block-Hosts.
 */
import { InjectionToken } from '@angular/core';

import type { ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';

/** Was ein Custom Element vom Host bekommt: alles ohne Angular-Typen. `markdown` (liefert
 *  `SafeHtml`) und `treffer` (Shell-Kontext der Trefferboxen) bleiben bei den Komponenten. */
export type ElementHost = Pick<ModulHost,
  'herunterladen' | 'drucken' | 'link' | 'aktion' | 'beschaeftigt' | 'antworten' | 'vormerken' | 'zweig'
  | 'hochladen' | 'ablegen' | 'auftrag'>;

/** Die Eigenschaften, die der Platzhalter am Element setzt; das Element zeichnet sich bei jeder
 *  Zuweisung neu. `beschaeftigt` spiegelt `host.beschaeftigt()`, weil ein Element keine Signale liest.
 *  `host` wird nur einmal gesetzt, vor dem Einhängen.
 *
 *  **Pflicht für jedes Bündel:** sich nur definieren, wenn der Name noch frei ist —
 *  `if (!customElements.get(name)) customElements.define(name, Klasse)`. Ein Bündel kann zweimal
 *  laufen (zwei Widgets mit verschiedener API-Basis, ein später doch noch geladenes Skript nach
 *  Fristablauf), und ein zweites `define` wirft. */
export interface NachladeElement extends HTMLElement {
  daten: Record<string, unknown>;
  kontext: ModulKontext;
  host: ElementHost;
  beschaeftigt: boolean;
}

/** Was der Platzhalter über seinen Block wissen muss; die Shell stellt es je Block bereit. */
export interface NachladeZiel {
  /** Name des Custom Elements, z. B. `boerdi-ui-upload`. */
  readonly element: string;
  /** Textfassung des Blocks (Markdown) — steht, wenn das Bündel nicht geladen werden kann. */
  readonly text: string;
  /** Lädt das Bündel (einmal je Modul); lehnt ab, wenn es nicht geht (Netz, SRI, CSP, Frist). */
  laden(): Promise<void>;
}

export const NACHLADE_ZIEL = new InjectionToken<NachladeZiel>('NACHLADE_ZIEL');
