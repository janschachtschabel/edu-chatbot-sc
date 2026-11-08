/**
 * Paket K2c-4: die Schrittfolge eines Ablaufs als Liste — Schritt → nächster, bei Fehler → …
 *
 * Live aus dem Entwurf, ohne Server, nach dem **Treiber** (`treiber._rechne`, `_waehle`):
 * - `ende` hat keinen Nachfolger, auch kein `bei_fehler`;
 * - eine **Verzweigung** geht nach ihren Regeln (`sonst` springt vor allem anderen); greift keine —
 *   oder hat sie keine Liste —, läuft der Lauf aus (Review K2c-4, Befund 2);
 * - jeder andere Schritt: `weiter` als Text, leer (oder eine Liste — die Prüfung meldet sie,
 *   der Treiber nimmt sie wie leer) der folgende Schritt, nach dem letzten: läuft aus (`''`);
 * - `bei_fehler` zuletzt, nur bei `modul`, `werkzeug`, `agent` und `auftrag` (`pruefung.MIT_BEI_FEHLER`).
 *
 * Bewusste Abweichung von `pruefung._normal`: eine Regel mit `sonst` UND `dann` (die Prüfung meldet
 * sie) zeigt das Ziel des Treibers, `sonst`; die Prüfung vergleicht `dann` (Befund 4).
 *
 * Nur lesend; ein Entwurf mit falscher Form (kein Objekt, keine Liste) gibt eine leere oder
 * kürzere Liste statt eines Fehlers — das Formular zeigt die Form ohnehin am Feld.
 */

/** Ein Pfeil zum nächsten Schritt. `ziel` `''`: der Lauf endet hier ohne `ende`-Schritt. */
export interface FolgePfeil {
  readonly ziel: string;
  /** `weiter` (regulär), `regel` (eine Regel der Verzweigung), `fehler` (`bei_fehler`). */
  readonly art: 'weiter' | 'regel' | 'fehler';
  /** Nur `regel`: die Bedingungen, wie der Treiber sie liest (`sonst` gilt vor allem anderen). */
  readonly sonst?: boolean;
  readonly wennTeil?: string;
  readonly wennGewaehlt?: string;
  /** Nur `regel` einer Verzweigung: keine Regel greift (oder es gibt keine) — der Lauf läuft aus. */
  readonly keineGreift?: boolean;
  /** Das Ziel ist ein Schritt dieses Ablaufs (oder `''`). */
  readonly bekannt: boolean;
}

export interface FolgeZeile {
  /** Die Stelle in `schritte` (0…) — eindeutig auch bei doppelten Kennungen. */
  readonly nr: number;
  readonly id: string;
  readonly typ: string;
  readonly pfeile: readonly FolgePfeil[];
}

type Roh = Record<string, unknown>;

/** Wo der Treiber `bei_fehler` nimmt — wie `pruefung.MIT_BEI_FEHLER`. */
const MIT_BEI_FEHLER: ReadonlySet<string> = new Set(['modul', 'werkzeug', 'agent', 'auftrag']);

const text = (wert: unknown): string => (typeof wert === 'string' ? wert : '');

function istObjekt(wert: unknown): wert is Roh {
  return typeof wert === 'object' && wert !== null && !Array.isArray(wert);
}

/** Die Zeilen der Schrittfolge eines Ablaufs (`AblaufArea`) im Entwurf. */
export function schrittFolge(ablauf: unknown): FolgeZeile[] {
  const roh = istObjekt(ablauf) ? ablauf['schritte'] : null;
  if (!Array.isArray(roh)) return [];
  const schritte = roh.map((s) => (istObjekt(s) ? s : {}));
  const ids = new Set(schritte.map((s) => text(s['id'])));
  const bekannt = (ziel: string): boolean => ziel === '' || ids.has(ziel);
  return schritte.map((s, nr) => {
    const typ = text(s['typ']);
    const pfeile: FolgePfeil[] = [];
    if (typ !== 'ende') {
      pfeile.push(...regulaer(s, typ, schritte[nr + 1]).map((p) => ({ ...p, bekannt: bekannt(p.ziel) })));
      const fehler = text(s['bei_fehler']);
      if (fehler && MIT_BEI_FEHLER.has(typ)) pfeile.push({ ziel: fehler, art: 'fehler', bekannt: bekannt(fehler) });
    }
    return { nr, id: text(s['id']), typ, pfeile };
  });
}

function regulaer(s: Roh, typ: string, folgender: Roh | undefined): Omit<FolgePfeil, 'bekannt'>[] {
  const weiter = s['weiter'];
  if (typ === 'verzweigung') {
    const regeln: Omit<FolgePfeil, 'bekannt'>[] = (Array.isArray(weiter) ? weiter : []).map((r: unknown) => {
      const regel = istObjekt(r) ? r : {};
      const sonst = text(regel['sonst']);
      return {
        // wie `treiber._waehle`: eine `sonst`-Regel springt dorthin, auch wenn sie (falsch,
        // die Prüfung meldet es) zusätzlich `dann` trägt
        ziel: sonst || text(regel['dann']),
        art: 'regel' as const,
        ...(sonst ? { sonst: true } : {}),
        ...(text(regel['wenn_teil']) ? { wennTeil: text(regel['wenn_teil']) } : {}),
        ...(text(regel['wenn_gewaehlt']) ? { wennGewaehlt: text(regel['wenn_gewaehlt']) } : {}),
      };
    });
    // Eine Verzweigung, bei der keine Regel greift, läuft aus (`_waehle(...) or ""`).
    if (typ === 'verzweigung' && !regeln.some((r) => r.sonst)) {
      regeln.push({ ziel: '', art: 'regel', keineGreift: true });
    }
    return regeln;
  }
  return [{ ziel: (Array.isArray(weiter) ? '' : text(weiter)) || text(folgender?.['id']), art: 'weiter' }];
}
