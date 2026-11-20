/**
 * Darstellung der Frage „Wo sollen sie verarbeitet werden?“ in `<boerdi-ui-upload>` (Plan 2026-11-17,
 * Paket U4, E7/E13): abgerundete Chips nebeneinander, je Chip eine Erklärzeile darunter; ein
 * gesperrter Ort bleibt sichtbar und nennt seinen Grund als Text. Darunter Hinweise zum gewählten
 * Ort und der Datenschutz-Satz dazu (was geht wohin, wie lange).
 *
 * Die Chips sind echte Radioknöpfe in einem `fieldset` mit `legend`: Pfeiltasten wählen, Tab springt
 * in die Gruppe auf den gewählten Ort, gesperrte überspringt der Browser — ohne eigenes Tastaturmuster.
 * Den gewählten Chip zeigt der Radiokreis und eine Umrandung, nicht nur eine Farbe. Fremdtext steht
 * hier nicht; die Knoten baut das Element (`knoten`), damit Gestalt und Fokus-Schlüssel gleich sind.
 */
import type { LokaleGrenzen, Orte, OrtStand } from './upload-orte';
import type { UploadTexte } from './upload-texte';
import { MAX_STAPEL } from './upload-uebertragen';

export interface OrteAnsicht {
  readonly t: UploadTexte;
  readonly orte: Orte;
  /** Der Ort, den „Hochladen“ nimmt (`gewaehlt`); `null`: nur die Namen gehen. */
  readonly wahl: 'chat' | 'wlo' | null;
  readonly grenzen: LokaleGrenzen;
  /** Nicht ignoriert, aber nicht lesbar — gilt für „Hier im Chat“. */
  readonly nichtLesbar: number;
  /** Lesbar, aber über der Grenze je Datei — gilt für „Hier im Chat“. */
  readonly zuGross: number;
  /** Darf „Hier im Chat“ „ohne Anmeldung“ versprechen (`chatOhneAnmeldung`)? */
  readonly ohneAnmeldung: boolean;
  /** Was beim Übertragen nach WLO wegfällt (Art, Größe) — ein Satz oder leer. */
  readonly ausgelassenWlo: string;
  /** Die Wahl ruht (ein Zug läuft). */
  readonly gesperrt: boolean;
  knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string, text?: string): HTMLElementTagNameMap[K];
}

const MB = 1024 * 1024;
const GESPERRT = new Set(['nur_angemeldet', 'ablauf', 'keine']);

/** MB mit höchstens einer Nachkommastelle, abgerundet — ein Rest verspricht nie mehr, als geht. */
function mb(bytes: number): number {
  return Math.floor((bytes / MB) * 10) / 10;
}

/** Welche Grenze „Hier im Chat“ sperrt, als Satzteil; ein Rest von null heißt: kein Platz mehr. */
function grenzSatz(t: UploadTexte, g: LokaleGrenzen, grenze: OrtStand['grenze']): string {
  if (grenze === 'gesamt') return t.zuGrossHier(Math.round(g.maxBytes / MB));
  // Ob WLO hilft, sagt hier der Grund (`ueber_grenze_anmelden`) bzw. der wählbare Chip daneben
  if (grenze === 'frei_anzahl') return g.freiDateien ? t.freiHier(g.freiDateien) : t.sitzungVoll(g.aufbewahrungH, false);
  if (grenze === 'frei_gesamt') {
    return g.freiBytes && mb(g.freiBytes) > 0 ? t.freiMbHier(mb(g.freiBytes)) : t.sitzungVoll(g.aufbewahrungH, false);
  }
  return t.zuVieleHier(g.maxDateien);
}

/** Die Erklärzeile eines Orts: was er tut — oder, gesperrt, warum nicht. */
export function erklaerung(a: Pick<OrteAnsicht, 't' | 'grenzen' | 'ohneAnmeldung'>, ort: 'chat' | 'wlo', s: OrtStand): string {
  const { t, grenzen: g } = a;
  if (s.geht) {
    if (ort === 'chat') return t.erklaerChat(Math.min(g.maxDateien, g.freiDateien ?? Infinity), g.aufbewahrungH, a.ohneAnmeldung);
    return s.hinweis === 'ohne_erschliessung' ? t.erklaerWloOhne : t.erklaerWlo;
  }
  let grund: string;
  if (s.grund === 'ueber_grenze' || s.grund === 'ueber_grenze_anmelden') {
    grund = grenzSatz(t, g, s.grenze);
    if (s.grund === 'ueber_grenze_anmelden') grund = t.mitAnmeldung(grund);
  } else if (s.grund === 'grenze_sitzung') {
    grund = t.sitzungVoll(g.aufbewahrungH, true);
  } else if (s.grund === 'stapel') {
    grund = t.zuVieleStapel(MAX_STAPEL);
  } else if (s.grund === 'keine' && ort === 'chat') {
    grund = s.grenze === 'datei' ? t.zuGrossDateiHier(Math.round(g.maxBytesDatei / MB)) : t.keineHier;
  } else {
    grund = t.gesperrt[s.grund && GESPERRT.has(s.grund) ? s.grund as keyof UploadTexte['gesperrt'] : 'aus'];
  }
  return t.nichtWaehlbar(grund);
}

/** Der Datenschutz-Satz zum gewählten Ort. */
export function datenschutzSatz(t: UploadTexte, orte: Orte, wahl: 'chat' | 'wlo' | null, g: LokaleGrenzen): string {
  if (wahl === 'chat') {
    // Paket C: die Seitenbilder verlassen den Server — das sagt das Feld vor dem Hochladen
    return orte.chat.texterkennung ? `${t.datenschutzChat(g.aufbewahrungH)} ${t.datenschutzOcr}` : t.datenschutzChat(g.aufbewahrungH);
  }
  if (wahl === 'wlo') return orte.wlo.hinweis === 'ohne_erschliessung' ? t.datenschutzWloOhne : t.datenschutzWlo;
  return t.datenschutz;
}

function chip(a: OrteAnsicht, ort: 'chat' | 'wlo'): HTMLElement {
  const s = a.orte[ort];
  const an = a.wahl === ort;
  const huelle = a.knoten('div', 'u__ort');
  const label = a.knoten('label', `u__chip${an ? ' u__chip--an' : ''}${s.geht ? '' : ' u__chip--aus'}`);
  const radio = a.knoten('input');
  radio.type = 'radio';
  radio.name = 'u-ort';
  radio.value = ort;
  radio.checked = an;
  radio.disabled = !s.geht || a.gesperrt;
  radio.dataset['ort'] = ort;
  radio.dataset['fokus'] = `r:${ort}`;
  const id = `u-ort-${ort}`;
  radio.setAttribute('aria-describedby', id);
  label.append(radio, a.knoten('span', undefined, a.t.ort[ort]));
  const zeile = a.knoten('p', 'u__erklaer', erklaerung(a, ort, s));
  zeile.id = id;
  huelle.append(label, zeile);
  return huelle;
}

/** Frage, Chips, Hinweise zum gewählten Ort und der Datenschutz-Satz. */
export function orteTeile(a: OrteAnsicht): Node[] {
  const gruppe = a.knoten('fieldset', 'u__orte');
  gruppe.append(a.knoten('legend', 'u__frage', a.t.frage));
  const chips = a.knoten('div', 'u__chips');
  chips.append(chip(a, 'chat'), chip(a, 'wlo'));
  gruppe.append(chips);
  const teile: Node[] = [gruppe];
  if (a.wahl === 'chat' && a.nichtLesbar) teile.push(a.knoten('p', 'u__hinweis', a.t.nichtLesbar(a.nichtLesbar)));
  if (a.wahl === 'chat' && a.zuGross) {
    teile.push(a.knoten('p', 'u__hinweis', a.t.zuGrossHinweis(a.zuGross, Math.round(a.grenzen.maxBytesDatei / MB))));
  }
  if (a.wahl === 'wlo' && a.ausgelassenWlo) teile.push(a.knoten('p', 'u__hinweis', a.ausgelassenWlo));
  teile.push(a.knoten('p', 'u__hinweis', datenschutzSatz(a.t, a.orte, a.wahl, a.grenzen)));
  return teile;
}
