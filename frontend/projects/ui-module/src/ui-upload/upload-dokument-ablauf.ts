/**
 * Der Ablauf „Strukturdokumente lesen lassen“ in `<boerdi-ui-upload>` (Paket U3-2c) — aus dem Element
 * gelöst (Review U3-2, Befund 15), damit das Element beim Erfassen bleibt. Der Ablauf kennt kein
 * Angular und baut keine Ansicht: er hält den Zustand (`lauf`), lädt über den Host hoch, meldet den
 * Fortschritt an Ort und Stelle (Befund 9) und antwortet; neu zeichnen und ansagen lässt er das
 * Element über `AblaufUmgebung`.
 *
 * Plan 2026-11-16, TG-3e: alle markierten Dokumente (bis fünf) nacheinander, jedes mit eigenem
 * Hochladen. Fortschritt und Fehler nennen das Dokument („Dokument 2 von 3“). Scheitert eines, hält
 * der Ablauf an: „Noch einmal“ liest es erneut, „Ohne dieses weiter“ macht mit dem nächsten weiter —
 * die schon gelesenen bleiben (das Backend hält sie an der Sitzung). Geantwortet wird einmal, mit
 * allen gelesenen. Mit einem Dokument sind Texte und Antwort wie vorher.
 */
import type { ElementHost } from '../_nachladen/element-vertrag';
import {
  codeVon, dokumenteAntwort, dokumentErlaubt, type DokumentLauf, type DokumentStelle, gelesenAus,
  type GelesenesDokument, strukturDateien,
} from './upload-dokument';
import type { Erfassung } from './upload-erfassen';
import { dokumentFehlerSatz, type UploadTexte } from './upload-texte';

export interface AblaufUmgebung {
  host(): ElementHost | undefined;
  erfassung(): Erfassung<File> | null;
  daten(): Readonly<Record<string, unknown>>;
  beschaeftigt(): boolean;
  t(): UploadTexte;
  wurzel(): ShadowRoot;
  ansagen(text: string): void;
  zeichne(): void;
  /** Der Block ist nicht mehr offen — ein Befund geht dann nicht mehr als Antwort hin. */
  nurLesen?(): boolean;
}

/** Der Satz zum Hochladen — mit einem Dokument wie vor TG-3e. */
export function sendetSatz(t: UploadTexte, prozent: number, stelle?: DokumentStelle): string {
  return stelle && stelle.von > 1 ? t.sendetNr(stelle.nr, stelle.von, prozent) : t.sendet(prozent);
}

/** Der Satz zum Lesen im Backend — mit einem Dokument wie vor TG-3e. */
export function liestSatz(t: UploadTexte, stelle?: DokumentStelle): string {
  return stelle && stelle.von > 1 ? t.liestNr(stelle.nr, stelle.von) : t.liestDokument;
}

/** Der Fehlersatz — bei mehreren mit dem Namen des Dokuments. */
export function fehlerSatz(t: UploadTexte, code: string, stelle?: DokumentStelle): string {
  const satz = dokumentFehlerSatz(t, code);
  return stelle && stelle.von > 1 ? t.fehlerBei(stelle.name, satz) : satz;
}

export class DokumentAblauf {
  lauf: DokumentLauf | null = null;

  constructor(private readonly u: AblaufUmgebung) {}

  laeuft(): boolean {
    return this.lauf?.phase === 'sendet' || this.lauf?.phase === 'liest';
  }

  /** Eine andere Rolle macht einen Fehler oder einen wartenden Befund gegenstandslos. */
  auswahlGeaendert(): void {
    if (this.lauf?.phase === 'fehler' || this.lauf?.phase === 'fertig') this.lauf = null;
  }

  zuruecksetzen(): void {
    this.lauf = null;
  }

  /** Kann „Ohne dieses weiter“ etwas bewirken — gibt es schon Gelesenes oder ein weiteres? */
  ueberspringbar(): boolean {
    const l = this.lauf;
    if (l?.phase !== 'fehler' || !l.stelle || l.stelle.von < 2) return false;
    return (l.bisher?.length ?? 0) > 0 || l.stelle.nr < l.stelle.von;
  }

  /** Hochladen und lesen lassen; danach antworten (oder, wenn gerade ein Zug läuft, den Befund bis
   *  zum Knopf „Weiter“ halten). Plan 2026-11-16, TG-1: ohne Ziel — nur bereitstellen. TG-3e: nach
   *  einem Fehler geht es mit demselben Dokument weiter, die gelesenen bleiben. */
  async lesen(): Promise<void> {
    const l = this.lauf;
    if (l?.phase === 'fehler' && l.stelle) return this.ab(l.stelle.nr - 1, l.bisher ?? []);
    return this.ab(0, []);
  }

  /** TG-3e: das gescheiterte Dokument auslassen und mit dem nächsten weitermachen. */
  async ueberspringen(): Promise<void> {
    const l = this.lauf;
    if (l?.phase !== 'fehler' || !l.stelle || !this.ueberspringbar()) return;
    return this.ab(l.stelle.nr, l.bisher ?? []);
  }

  private async ab(start: number, bisher: readonly GelesenesDokument[]): Promise<void> {
    const e = this.u.erfassung();
    const dateien = e ? strukturDateien(e) : [];
    const host = this.u.host();
    if (!e || !dateien.length || !host || this.laeuft() || !dokumentErlaubt(this.u.daten())) return;
    const t = this.u.t();
    const gelesen = [...bisher];
    for (let k = start; k < dateien.length; k++) {
      const stelle: DokumentStelle = { nr: k + 1, von: dateien.length, name: dateien[k].name };
      this.lauf = { phase: 'sendet', anteil: 0, stelle };
      this.u.ansagen(sendetSatz(t, 0, stelle));
      this.u.zeichne();
      try {
        const befund = await host.hochladen(dateien[k].handle, (anteil) => this.fortschritt(anteil));
        if (this.u.erfassung() !== e) return this.verwerfen();   // inzwischen neu gewählt
        const dok = gelesenAus(befund, t.dokumentOhneName);
        if (!dok) throw Object.assign(new Error('Befund unbrauchbar'), { code: 'fehler' });
        gelesen.push(dok);
      } catch (fehler) {
        if (this.u.erfassung() !== e) return this.verwerfen();
        const code = codeVon(fehler);
        this.lauf = { phase: 'fehler', code, stelle, bisher: gelesen };
        this.u.ansagen(fehlerSatz(t, code, stelle));
        this.u.zeichne();
        return;
      }
    }
    const antwort = dokumenteAntwort(e, gelesen, t.dateiOhneName);
    if (!antwort) return this.verwerfen();                       // alle ausgelassen
    this.lauf = { phase: 'fertig', antwort };
    this.senden();
  }

  senden(): void {
    if (this.lauf?.phase !== 'fertig' || this.u.nurLesen?.()) return;
    const { antwort } = this.lauf;
    const t = this.u.t();
    const mehrere = antwort.dokumente?.length ?? 0;
    if (this.u.beschaeftigt()) {
      const abschnitte = t.abschnitte((antwort.dokumente ?? (antwort.dokument ? [antwort.dokument] : []))
        .reduce((n, d) => n + d.befund.abschnitte, 0));
      this.u.ansagen(mehrere > 1 ? t.gelesenMehrere(mehrere, abschnitte) : t.gelesen(abschnitte));
      this.u.zeichne();
      return;
    }
    this.u.host()?.antworten(antwort as unknown as Record<string, unknown>,
      mehrere > 1 ? t.blaseDokumente(mehrere) : t.blaseDokument(antwort.dokument?.name ?? ''));
  }

  /** Ein Fortschrittsschritt: nur Balken und Satz an Ort und Stelle — neu gezeichnet und angesagt
   *  wird nur beim Wechsel zu „wird gelesen“. */
  private fortschritt(anteil: number): void {
    if (this.lauf?.phase !== 'sendet') return;
    const t = this.u.t();
    const { stelle } = this.lauf;
    if (anteil >= 1) {
      this.lauf = { phase: 'liest', stelle };
      this.u.ansagen(liestSatz(t, stelle));
      this.u.zeichne();
      return;
    }
    this.lauf = { phase: 'sendet', anteil, stelle };
    const prozent = Math.round(anteil * 100);
    const balken = this.u.wurzel().querySelector('progress');
    const zeile = this.u.wurzel().querySelector<HTMLElement>('[data-fokus="s:dokument"]');
    if (balken) {
      balken.value = prozent;
      balken.setAttribute('aria-label', sendetSatz(t, prozent, stelle));
    }
    if (zeile) zeile.textContent = sendetSatz(t, prozent, stelle);
  }

  /** Antwort oder Fehler kamen für eine Auswahl, die es nicht mehr gibt — das Modul bleibt bedienbar. */
  private verwerfen(): void {
    this.lauf = null;
    this.u.zeichne();
  }
}
