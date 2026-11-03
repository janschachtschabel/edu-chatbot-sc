/**
 * Zeigt ein UI-Block sein Modul — oder nur die Textfassung (Review U1 gesamt)?
 *
 * Eine Stelle für den Platzhalter (`ui-bloecke.component`) und die Tore der Shell, die bisherige
 * Boxen schweigen lassen, sobald ein Modul sie zeigt (Trefferliste, Linkbox, Inhaltsrahmen). Prüften
 * die Tore nur den Namen, verschwand bei einer unbekannten Hauptversion die alte Box, und das Modul
 * erschien doch nicht — übrig blieb die Textfassung.
 */
import type { ModulRegister, UiBlock } from '@boerdi/ui-module';

import type { ChatMessage } from '../grouping/message-types';

/** Modul im Register, gleiche Hauptversion, Daten vorhanden (alter Verlauf hat keine). */
export function blockDarstellbar(block: UiBlock, register: ModulRegister): boolean {
  return register[block.modul]?.manifest.version === block.version && !!block.daten;
}

/** Trägt die Nachricht einen Block des Moduls `name`, den das Modul selbst zeigt? */
export function modulDarstellbar(msg: ChatMessage, name: string, register: ModulRegister): boolean {
  return !!msg?.ui?.ui_bloecke?.some((b) => b.modul === name && blockDarstellbar(b, register));
}
