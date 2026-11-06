/**
 * Der Ablauf „Strukturdokument lesen lassen“ in `<boerdi-ui-upload>` (Paket U3-2c) — aus dem Element
 * gelöst (Review U3-2, Befund 15), damit das Element beim Erfassen bleibt. Der Ablauf kennt kein
 * Angular und baut keine Ansicht: er hält den Zustand (`lauf`), lädt über den Host hoch, meldet den
 * Fortschritt an Ort und Stelle (Befund 9) und antwortet; neu zeichnen und ansagen lässt er das
 * Element über `AblaufUmgebung`.
 */
import type { ElementHost } from '../_nachladen/element-vertrag';
import {
  codeVon, dokumentAntwort, dokumentErlaubt, type DokumentLauf, type DokumentZiel, strukturDatei,
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

  /** Hochladen und lesen lassen; danach antworten (oder, wenn gerade ein Zug läuft, den Befund bis
   *  zum Knopf „… jetzt erstellen“ halten). */
  async lesen(ziel: DokumentZiel): Promise<void> {
    const e = this.u.erfassung();
    const sd = e ? strukturDatei(e) : null;
    const host = this.u.host();
    if (!e || !sd || !host || this.laeuft() || !dokumentErlaubt(this.u.daten())) return;
    const t = this.u.t();
    this.lauf = { phase: 'sendet', ziel, anteil: 0 };
    this.u.ansagen(t.sendet(0));
    this.u.zeichne();
    try {
      const befund = await host.hochladen(sd.handle, (anteil) => this.fortschritt(ziel, anteil));
      if (this.u.erfassung() !== e) return this.verwerfen();   // inzwischen neu gewählt
      const antwort = dokumentAntwort(e, befund, ziel, t.dokumentOhneName);
      if (!antwort) throw Object.assign(new Error('Befund unbrauchbar'), { code: 'fehler' });
      this.lauf = { phase: 'fertig', ziel, antwort };
      this.senden();
    } catch (fehler) {
      if (this.u.erfassung() !== e) return this.verwerfen();
      const code = codeVon(fehler);
      this.lauf = { phase: 'fehler', ziel, code };
      this.u.ansagen(dokumentFehlerSatz(t, code));
      this.u.zeichne();
    }
  }

  senden(): void {
    if (this.lauf?.phase !== 'fertig' || this.u.nurLesen?.()) return;
    const { antwort, ziel } = this.lauf;
    const t = this.u.t();
    if (this.u.beschaeftigt()) {
      this.u.ansagen(t.gelesen(t.abschnitte(antwort.dokument?.befund.abschnitte ?? 0)));
      this.u.zeichne();
      return;
    }
    this.u.host()?.antworten(antwort as unknown as Record<string, unknown>,
      t.blaseDokument[ziel](antwort.dokument?.name ?? ''));
  }

  /** Ein Fortschrittsschritt: nur Balken und Satz an Ort und Stelle — neu gezeichnet und angesagt
   *  wird nur beim Wechsel zu „wird gelesen“. */
  private fortschritt(ziel: DokumentZiel, anteil: number): void {
    if (this.lauf?.phase !== 'sendet') return;
    const t = this.u.t();
    if (anteil >= 1) {
      this.lauf = { phase: 'liest', ziel };
      this.u.ansagen(t.liestDokument);
      this.u.zeichne();
      return;
    }
    this.lauf = { phase: 'sendet', ziel, anteil };
    const prozent = Math.round(anteil * 100);
    const balken = this.u.wurzel().querySelector('progress');
    const zeile = this.u.wurzel().querySelector<HTMLElement>('[data-fokus="s:dokument"]');
    if (balken) {
      balken.value = prozent;
      balken.setAttribute('aria-label', t.sendet(prozent));
    }
    if (zeile) zeile.textContent = t.sendet(prozent);
  }

  /** Antwort oder Fehler kamen für eine Auswahl, die es nicht mehr gibt — das Modul bleibt bedienbar. */
  private verwerfen(): void {
    this.lauf = null;
    this.u.zeichne();
  }
}
