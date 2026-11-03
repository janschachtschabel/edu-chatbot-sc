/*
 * Öffentliche Schnittstelle der UI-Module (Paket U1). Die Chat-Shell liest von hier nur den
 * Vertrag und das Register; einzelne Module importiert sie nie direkt.
 */
export type { ModulKontext, UiBlock, UiBlockStatus, UiModulArt } from './_vertrag/ui-block';
export type { ModulFaehigkeit, UiModulManifest } from './_vertrag/manifest';
export { MODUL_HOST } from './_vertrag/modul-host';
export { INHALTSRAHMEN, LINKBOX, TREFFERLISTE } from './_vertrag/modul-namen';
export type { KartenAktion, ModulHost, TrefferUmgebung } from './_vertrag/modul-host';
export { UI_MODUL_REGISTER } from './_vertrag/register';
export type { ModulRegister, RegisterEintrag, RegisterManifest } from './_vertrag/register';
