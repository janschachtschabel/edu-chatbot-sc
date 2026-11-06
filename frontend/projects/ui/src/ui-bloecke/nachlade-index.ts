/**
 * Index der nachgeladenen Modul-Bündel (Paket U3-0): Modulname → Datei + SRI.
 *
 * Diese Datei ist absichtlich leer. Der Widget-Build (`npm run build:widget`) baut zuerst die Bündel
 * (`scripts/build-nachlade-module.mjs`), schreibt `nachlade-index.build.ts` (nicht eingecheckt) und
 * ersetzt diese Datei damit (`fileReplacements` in `angular.json`, Ziel `build-widget`). In Tests,
 * im Studio und im Dev-Build ist der Index leer — nachgeladene Module zeigen dort ihre Textfassung,
 * solange niemand einen eigenen Lader setzt.
 */
import type { NachladeIndex } from './nachladen';

export const NACHLADE_INDEX: NachladeIndex = {};
