/**
 * Zustand und Bearbeitung des Strukturentwurfs — ohne Angular und ohne DOM (Paket BU-2; bis dahin
 * in der Angular-Komponente `UiStrukturentwurf`, Verhalten unverändert). Das Element zeichnet daraus und
 * führt die Fokuswünsche aus, die die Bearbeitungen zurückgeben.
 *
 * Die Review-Festlegungen aus U2 stehen an ihren Stellen: der gesendete Stand bleibt nach
 * „wieder offen“ (Befund 1), „bearbeitet“ ist ein eigener Merker (Gegenreview, Befund 2),
 * Rückgängig hält den aktiven Punkt (Befund 3), die Leiste gilt einem sichtbaren Punkt (drittes
 * Review, Befund 4), zu viele Schlagworte werden einmal angesagt (Befund 8).
 */
import { flach } from '../_baum/baum-tasten';
import type { ModulKontext } from '../_vertrag/ui-block';
import { alleMitKindern, ansicht, type EntwurfEintrag, schlagworte, vorfahren } from './entwurf-ansicht';
import type { EntwurfDaten } from './entwurf-export';
import {
  type Ablehnung, anzahl, ausruecken, type Baum, bereinigt, einruecken, finde, hinzufuegen, KEYWORD_ZEICHEN,
  KEYWORDS, loeschen, neueKennung, setzeFelder, verschieben,
} from './entwurf-regeln';
import { TEXTE } from './entwurf-texte';

/** So viele Schritte nimmt „Rückgängig“ zurück. */
const RUECK_HOECHSTENS = 20;

export type Bewegung = 'hoch' | 'runter' | 'ein' | 'aus';
export type Feld = 'titel' | 'beschreibung' | 'keywords';
/** Wohin der Fokus nach einer Bearbeitung soll: ins Titelfeld (markiert), auf den aktiven Punkt
 *  im Baum, auf „Punkt hinzufügen“ — oder er bleibt, wo er ist. */
export type Fokus = 'titel' | 'baum' | 'erster' | null;

const LEER: EntwurfDaten = { titel: '', quelle: 'ki', knoten: [] };

export class EntwurfZustand {
  daten: EntwurfDaten = LEER;
  kontext: ModulKontext | null = null;
  /** Der Stand der Person. */
  struktur: Baum = [];
  offen: ReadonlySet<string> = new Set();
  /** Das Schlagwort-Feld, solange es bearbeitet wird (sonst sprängen Komma und Leerzeichen weg). */
  kwText: string | null = null;
  private aktivId: string | null = null;
  private rueck: readonly Baum[] = [];
  /** Hat die Person etwas geändert? Rückgängig bis zum Anfang macht ihn wieder falsch — außer
   *  ältere Schritte fielen schon aus dem Stapel (`abgeschnitten`). */
  private geaendert = false;
  private abgeschnitten = false;
  private vorFeld: Baum | null = null;
  private kwGekuerzt = false;
  private bereit = false;

  /** `sagen`: die Statuszeile (eine Ansage je Bearbeitung, eine unmögliche mit ihrem Grund). */
  constructor(private readonly sagen: (text: string) => void) {}

  get texte(): (typeof TEXTE)[keyof typeof TEXTE] {
    return TEXTE[this.kontext?.sprache === 'en' ? 'en' : 'de'];
  }

  get nurLesen(): boolean {
    return this.kontext?.nurLesen === true;
  }

  get bearbeitet(): boolean {
    return this.geaendert;
  }

  /** Neue Daten oder neuer Kontext. Wird der Block nach dem Senden wieder offen (der Zug kam nicht
   *  an), bleibt der gesendete Stand — sonst gingen alle Bearbeitungen still verloren. Nur lesend
   *  zeigt er die Quelle: beantwortet die Antwort der Person, sonst die Daten des Blocks. */
  eingaben(daten: Record<string, unknown>, kontext: ModulKontext): void {
    this.daten = Array.isArray(daten['knoten']) ? (daten as unknown as EntwurfDaten) : { ...LEER, ...daten, knoten: [] };
    this.kontext = kontext;
    if (kontext.nurLesen || !this.bereit) this.struktur = this.quelle().knoten;
    this.bereit = true;
  }

  private quelle(): EntwurfDaten {
    const a = this.kontext?.antwort;
    return a && Array.isArray(a['knoten']) ? { ...this.daten, ...(a as Partial<EntwurfDaten>) } : this.daten;
  }

  // ── Ansicht ───────────────────────────────────────────────────────────────

  get baum(): EntwurfEintrag[] {
    return ansicht(this.struktur, this.offen);
  }

  get sichtbar(): EntwurfEintrag[] {
    return flach(this.baum);
  }

  /** Der aktive Punkt; ist er zugeklappt verborgen, sein nächster sichtbarer Vorfahr — nie still
   *  der erste Punkt, sonst träfe die Leiste etwas anderes. */
  get aktiv(): EntwurfEintrag | null {
    const sichtbar = this.sichtbar;
    const id = this.aktivId;
    const kette = id ? [id, ...[...(vorfahren(this.struktur, id) ?? [])].reverse()] : [];
    for (const k of kette) {
      const e = sichtbar.find((s) => s.knoten.id === k);
      if (e) return e;
    }
    return sichtbar[0] ?? null;
  }

  get zahl(): number {
    return anzahl(this.struktur);
  }

  get hatKinder(): boolean {
    return alleMitKindern(this.struktur).length > 0;
  }

  get allesOffen(): boolean {
    return alleMitKindern(this.struktur).every((id) => this.offen.has(id));
  }

  /** Die Statuszeile eines nur lesenden Blocks (leer, solange er offen ist). */
  get status(): string {
    const k = this.kontext;
    if (!k?.nurLesen) return '';
    if (!k.antwort) return this.texte.status.veraltet;
    return this.texte.status[k.antwort['uebernommen'] === true ? 'uebernommen' : 'mitgeschickt'];
  }

  istOffen(e: EntwurfEintrag): boolean {
    return this.offen.has(e.knoten.id);
  }

  setzeOffen(ids: readonly string[], auf: boolean): void {
    const neu = new Set(this.offen);
    ids.forEach((id) => (auf ? neu.add(id) : neu.delete(id)));
    this.offen = neu;
  }

  aktivieren(id: string): void {
    this.aktivId = id;
  }

  allesUmschalten(): void {
    if (this.allesOffen) this.offen = new Set();
    else this.setzeOffen(alleMitKindern(this.struktur), true);
  }

  antwortDaten(uebernommen: boolean): Record<string, unknown> {
    const { titel, quelle, thema, fach, bildungsstufe, wurzel_wlo_id, gekuerzt } = this.daten;
    return {
      titel, quelle, thema, fach, bildungsstufe, wurzel_wlo_id, gekuerzt,
      knoten: bereinigt(this.struktur, this.texte.neuerPunkt), uebernommen, bearbeitet: this.geaendert,
    };
  }

  /** Daten zum Herunterladen: der bereinigte Stand. */
  herunterladDaten(): EntwurfDaten {
    return { ...this.daten, knoten: bereinigt(this.struktur, this.texte.neuerPunkt) };
  }

  // ── Bearbeiten ───────────────────────────────────────────────────────────

  /** Einen neuen Stand übernehmen (mit Rückgängig-Schritt) oder den Grund der Ablehnung ansagen. */
  private uebernehmeStand(neu: Baum | Ablehnung, meldung: string): boolean {
    if ('grund' in neu) {
      this.sagen(this.texte.grund[neu.grund]);
      return false;
    }
    this.merkeSchritt(this.struktur);
    this.struktur = neu;
    this.sagen(meldung);
    return true;
  }

  private merkeSchritt(vorher: Baum): void {
    if (this.rueck.length >= RUECK_HOECHSTENS) this.abgeschnitten = true;
    this.rueck = [...this.rueck, vorher].slice(-RUECK_HOECHSTENS);
    this.geaendert = true;
  }

  hinzufuegen(wo: 'kind' | 'danach'): Fokus {
    if (this.nurLesen) return null;
    const a = this.aktiv;
    const neu = { id: neueKennung(this.struktur), titel: this.texte.neuerPunkt };
    const r = hinzufuegen(this.struktur, a?.knoten.id ?? null, a ? wo : 'danach', neu);
    const eltern = wo === 'kind' ? a?.knoten.titel : null;
    const meldung = eltern ? this.texte.getan.neu(eltern) : this.texte.getan.neuOben;
    if (!this.uebernehmeStand('grund' in r ? r : r.baum, meldung)) return null;
    if (wo === 'kind' && a) this.setzeOffen([a.knoten.id], true);
    this.aktivId = neu.id;
    return 'titel';
  }

  /** `ausLeiste`: der Knopf behält den Fokus (Review U2, Befund 10) — aus dem Baum der Punkt. */
  loeschen(ausLeiste: boolean): Fokus {
    const a = this.aktiv;
    if (!a || this.nurLesen) return null;
    const r = loeschen(this.struktur, a.knoten.id);
    if (!this.uebernehmeStand('grund' in r ? r : r.baum, this.texte.getan.geloescht(a.knoten.titel))) return null;
    if (!('grund' in r)) this.aktivId = r.fokus;
    // Befund 15: ohne Punkte bleibt nur „Punkt hinzufügen“ — dorthin.
    if (!this.struktur.length) return 'erster';
    return ausLeiste ? null : 'baum';
  }

  bewegen(art: Bewegung, ausLeiste: boolean): Fokus {
    const a = this.aktiv;
    if (!a || this.nurLesen) return null;
    const id = a.knoten.id;
    const s = this.struktur;
    const neu = art === 'hoch' ? verschieben(s, id, -1) : art === 'runter' ? verschieben(s, id, 1)
      : art === 'ein' ? einruecken(s, id) : ausruecken(s, id);
    const ebene = 'grund' in neu ? 0 : finde(neu, id)?.ebene ?? 0;
    const t = this.texte.getan;
    const meldung = art === 'ein' || art === 'aus' ? t[art](a.knoten.titel, ebene) : t[art](a.knoten.titel);
    if (!this.uebernehmeStand(neu, meldung)) return null;
    this.setzeOffen(vorfahren(this.struktur, id) ?? [], true);   // der Punkt bleibt sichtbar
    return ausLeiste ? null : 'baum';
  }

  /** Der aktive Punkt bleibt — fehlt er im alten Stand, sein Geschwister oder Elternpunkt; seine
   *  Vorfahren werden aufgeklappt. `imBaum`: stand der Fokus im Baum, bleibt er dort. */
  rueckgaengig(imBaum: boolean): Fokus {
    if (this.nurLesen) return null;
    const r = this.rueck;
    if (!r.length) {
      this.sagen(this.texte.getan.nichtsZuruecknehmen);
      return null;
    }
    const jetzt = this.struktur;
    const alt = r[r.length - 1];
    const id = this.aktiv?.knoten.id ?? null;
    const fund = id ? finde(jetzt, id) : null;
    const kandidaten = [id, fund?.geschwister[fund.index - 1]?.id, fund?.geschwister[fund.index + 1]?.id, fund?.eltern];
    const ziel = kandidaten.find((k): k is string => !!k && !!finde(alt, k)) ?? alt[0]?.id ?? null;
    this.struktur = alt;
    this.rueck = r.slice(0, -1);
    this.geaendert = r.length > 1 || this.abgeschnitten;
    this.aktivId = ziel;
    if (ziel) this.setzeOffen(vorfahren(alt, ziel) ?? [], true);
    this.sagen(this.texte.getan.rueckgaengig);
    return imBaum ? 'baum' : null;
  }

  /** Beim Betreten eines Felds den Stand merken: die erste Änderung darin wird EIN Rückgängig-Schritt. */
  feldBetreten(feld: Feld): void {
    this.vorFeld = this.struktur;
    if (feld === 'keywords') this.kwText = this.aktiv?.knoten.keywords?.join(', ') ?? '';
  }

  feldAendern(feld: Feld, wert: string): void {
    const a = this.aktiv;
    if (!a || this.nurLesen) return;
    if (this.vorFeld) {
      this.merkeSchritt(this.vorFeld);
      this.vorFeld = null;
    }
    let felder: { titel?: string; beschreibung?: string; keywords?: readonly string[] } = { [feld]: wert };
    if (feld === 'keywords') {
      this.kwText = wert;
      felder = { keywords: schlagworte(wert, KEYWORDS, KEYWORD_ZEICHEN) };
      // Review U2, Befund 8: was wegfällt, wird gesagt — einmal je Überschreiten, nicht je Taste.
      const roh = wert.split(',').map((w) => w.trim()).filter(Boolean);
      const gekuerzt = roh.length > KEYWORDS || roh.some((w) => w.length > KEYWORD_ZEICHEN);
      if (gekuerzt && !this.kwGekuerzt) this.sagen(this.texte.kwGekuerzt);
      this.kwGekuerzt = gekuerzt;
    }
    const neu = setzeFelder(this.struktur, a.knoten.id, felder);
    if (!('grund' in neu)) this.struktur = neu;
  }

  feldGeschlossen(): void {
    this.kwText = null;
    this.vorFeld = null;
    this.kwGekuerzt = false;
  }
}
