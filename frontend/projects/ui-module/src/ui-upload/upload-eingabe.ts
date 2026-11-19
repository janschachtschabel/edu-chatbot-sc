/**
 * Woher die Auswahl von `<boerdi-ui-upload>` kommt (aus dem Element gelöst, Paket U4, damit es bei
 * Zustand, Ereignissen und Fokus bleibt): zwei versteckte Datei-Eingaben (Ordner, Dateien) und das
 * Ablegen auf der Fläche. Gelesen wird nur die Liste der Dateien — nie ihr Inhalt.
 */
import { ausDateiliste, ausEintraegen, type Quelle } from './upload-erfassen';

/** Die beiden Datei-Eingaben; das Element hängt sie einmal und außerhalb des neu gezeichneten Inhalts
 *  ein (Querschnitts-Review FE-4: sonst hinge ein offener Dateidialog an einem entfernten Element). */
export function dateiEingaben(): HTMLInputElement[] {
  return (['ordner', 'dateien'] as const).map((quelle) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.hidden = true;
    input.dataset['quelle'] = quelle;
    if (quelle === 'ordner') input.setAttribute('webkitdirectory', '');
    return input;
  });
}

/** Die Dateien einer Ablage: Ordner über die FileSystem-Einträge (rekursiv, höchstens `maxDateien` + 1,
 *  damit `erfasse` die Warnung „zu viele“ setzen kann), sonst die flache Dateiliste. */
export async function quellenAusAblage(transfer: DataTransfer, maxDateien: number): Promise<Quelle<File>[]> {
  const eintraege = [...(transfer.items ?? [])]
    .filter((i) => i.kind === 'file')
    .map((i) => (i as DataTransferItem & { webkitGetAsEntry?: () => unknown }).webkitGetAsEntry?.())
    .filter((x): x is NonNullable<typeof x> => !!x);
  return eintraege.length
    ? [...await ausEintraegen(eintraege as never, maxDateien + 1)]
    : [...ausDateiliste(transfer.files ?? [])];
}
