/**
 * Der Gruppen-Abschnitt: die Dokumente eines Ordners — Muster, Personas — als
 * Liste│Editor (ST-3d, Paket 6). Aus `area-editor.ts` herausgelöst, als
 * Duplizieren und Löschen dazukamen; der Teil stand dort schon über der
 * 300-Zeilen-Grenze.
 *
 * `groupSection.duplicate` heißt „den Namen gibt es schon“ — die Aktion
 * Duplizieren heißt `groupSection.copy`.
 */
import type { CataloguePart } from './catalogue-part';

export const GROUP_SECTION: CataloguePart = {
  de: {
    'groupSection.listLoading': 'Lade Liste …',
    'groupSection.docs': 'Dokumente',
    'groupSection.empty': 'Noch keine Dokumente. Unten eines anlegen.',
    'groupSection.new': 'Neues Dokument',
    'groupSection.newKey': 'Kennung: {id}',
    'groupSection.newHint': 'Aus dem Namen wird die Kennung.',
    'groupSection.create': 'Anlegen',
    'groupSection.creating': 'Wird angelegt …',
    'groupSection.created': 'Angelegt.',
    /** Während der Anfrage begann jemand, das offene Dokument zu ändern (Review Paket 6). */
    'groupSection.createdNotOpened':
      'Angelegt, aber nicht geöffnet: Hier gibt es ungespeicherte Änderungen. Das neue Dokument steht in der Liste.',
    'groupSection.pick': 'Links ein Dokument wählen, um es zu bearbeiten.',
    'groupSection.needName': 'Bitte einen Namen angeben.',
    'groupSection.duplicate': '„{name}“ gibt es schon — bitte einen anderen Namen wählen.',
    'groupSection.switchBlocked':
      'Bitte erst speichern oder verwerfen — sonst gehen die Änderungen an diesem '
      + 'Dokument verloren.',
    'groupSection.createBlocked':
      'Erst das offene Dokument speichern oder verwerfen — sonst gehen die Änderungen '
      + 'beim Wechsel verloren.',

    // ── Duplizieren und Löschen (ST-3d, Paket 6) ────────────────────
    'groupSection.copy': 'Duplizieren',
    'groupSection.copyEntry': 'Duplizieren: {title}',
    'groupSection.copyLabel': '{label} (Kopie)',
    'groupSection.copying': 'Wird dupliziert …',
    'groupSection.copied': 'Kopie angelegt: {title}.',
    'groupSection.copyBlocked':
      'Bitte erst speichern oder verwerfen — die Kopie entsteht aus dem gespeicherten Stand.',
    'groupSection.remove': 'Löschen',
    'groupSection.removeEntry': 'Löschen: {title}',
    'groupSection.confirmRemove': '„{title}“ endgültig löschen?',
    'groupSection.removeShipped':
      'Es gehört zur Werksfassung und bleibt gelöscht, bis du es unter Sicherung → „Werk und '
      + 'eigene Fassung“ wiederherstellst.',
    'groupSection.removeOwn': 'Es steht nur in dieser Anlage und ist danach weg.',
    'groupSection.removeDiscards': 'Die ungespeicherten Änderungen gehen dabei verloren.',
    /** 409 beim Löschen: der geladene Stand gilt nicht mehr (Review Paket 6). */
    'groupSection.removeConflict':
      'Nicht gelöscht: Jemand hat dieses Dokument inzwischen gespeichert. Lade es neu und entscheide dann.',
    'groupSection.removing': 'Wird gelöscht …',
    'groupSection.removed': '„{title}“ ist gelöscht.',

    // ── Wirksame Wissensbereiche eines Musters (S4, Paket 6) ─────────
    'groupSection.rag.set': 'Wirksame Wissensbereiche: {areas}.',
    'groupSection.rag.setEmpty': 'Keine Wissensbereiche — die Liste ist ausdrücklich leer.',
    'groupSection.rag.default':
      'Nicht gesetzt — es wirken die Bereiche des Katalogs: {areas}.',
    'groupSection.rag.defaultEmpty': 'Nicht gesetzt — im Katalog ist kein Bereich zum Abruf eingestellt.',
    'groupSection.rag.noRag': 'Keine Wissensbereiche — „rag“ steht nicht unter den Quellen.',
    'groupSection.rag.unknown': 'Nicht im Katalog, wirkt nicht: {areas}.',
  },
  en: {
    'groupSection.listLoading': 'Loading list …',
    'groupSection.docs': 'Documents',
    'groupSection.empty': 'No documents yet. Create one below.',
    'groupSection.new': 'New document',
    'groupSection.newKey': 'Id: {id}',
    'groupSection.newHint': 'The name becomes the id.',
    'groupSection.create': 'Create',
    'groupSection.creating': 'Creating …',
    'groupSection.created': 'Created.',
    'groupSection.createdNotOpened':
      'Created but not opened: there are unsaved changes here. The new document is in the list.',
    'groupSection.pick': 'Pick a document on the left to edit it.',
    'groupSection.needName': 'Please enter a name.',
    'groupSection.duplicate': '“{name}” already exists — please pick another name.',
    'groupSection.switchBlocked':
      'Please save or discard first — otherwise the changes to this document would be lost.',
    'groupSection.createBlocked':
      'Save or discard the open document first — otherwise its changes would be lost when '
      + 'switching.',

    'groupSection.copy': 'Duplicate',
    'groupSection.copyEntry': 'Duplicate: {title}',
    'groupSection.copyLabel': '{label} (copy)',
    'groupSection.copying': 'Duplicating …',
    'groupSection.copied': 'Copy created: {title}.',
    'groupSection.copyBlocked':
      'Please save or discard first — the copy is made from the saved state.',
    'groupSection.remove': 'Delete',
    'groupSection.removeEntry': 'Delete: {title}',
    'groupSection.confirmRemove': 'Delete “{title}” for good?',
    'groupSection.removeShipped':
      'It belongs to the factory version and stays deleted until you restore it under '
      + 'Backup → “Factory and own version”.',
    'groupSection.removeOwn': 'It exists only in this installation and will be gone.',
    'groupSection.removeDiscards': 'The unsaved changes will be lost.',
    'groupSection.removeConflict':
      'Not deleted: someone has saved this document in the meantime. Reload it, then decide.',
    'groupSection.removing': 'Deleting …',
    'groupSection.removed': '“{title}” has been deleted.',

    'groupSection.rag.set': 'Knowledge areas in effect: {areas}.',
    'groupSection.rag.setEmpty': 'No knowledge areas — the list is explicitly empty.',
    'groupSection.rag.default': 'Not set — the areas of the catalogue apply: {areas}.',
    'groupSection.rag.defaultEmpty': 'Not set — no area in the catalogue is set up for retrieval.',
    'groupSection.rag.noRag': 'No knowledge areas — “rag” is not among the sources.',
    'groupSection.rag.unknown': 'Not in the catalogue, no effect: {areas}.',
  },
};
