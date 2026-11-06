/**
 * Lädt die Bündel nachgeladener UI-Module (Paket U3-0).
 *
 * Ein Modul mit `laden: "bei_bedarf"` ist ein rahmenloses Custom Element in einer eigenen Datei
 * `widget/module/<ordner>.<hash>.js`, die das Backend unveränderlich ausliefert. Geladen wird es als
 * klassisches `<script>` — wie das Widget selbst, damit jede Einbettung funktioniert, die das Widget
 * lädt — mit **Subresource Integrity** aus dem Index, den der Build schreibt
 * (`scripts/build-nachlade-module.mjs` → `nachlade-index.build.ts`, per `fileReplacements`). Ohne
 * passenden Eintrag (Dev-Build, Tests) lädt nichts, und der Platzhalter zeigt die Textfassung.
 *
 * Verlangt die Gastseite Trusted Types, geht die Adresse durch eine eigene Richtlinie (eine je Seite),
 * die nur gehashte Bündel unter `/widget/module/` zulässt.
 */

export interface NachladeEintrag {
  /** Dateiname unter `widget/module/`, mit Inhalts-Hash. */
  readonly datei: string;
  /** SRI-Wert, z. B. `sha384-…`. */
  readonly integritaet: string;
}

export type NachladeIndex = Readonly<Record<string, NachladeEintrag>>;

export interface LaderOptionen {
  readonly fristMs?: number;
  readonly dokument?: Document;
}

const FRIST_MS = 10_000;
const PFAD = '/widget/module/';
const RICHTLINIE = 'boerdi-ui-module';

interface TrustedTypesFabrik {
  createPolicy(name: string, regeln: { createScriptURL(url: string): string }): { createScriptURL(url: string): unknown };
}

/** Basis der Modul-Dateien aus der API-Basis der Shell: `https://x/api` → `https://x/widget/module/`. */
function modulBasis(apiBasis: string): string {
  return apiBasis.replace(/\/+$/, '').replace(/\/api$/, '') + PFAD;
}

/** Was die Trusted-Types-Richtlinie durchlässt: nur gehashte Modul-Bündel unter `…/widget/module/`
 *  (nach dem Auflösen der Adresse, also ohne `..`-Umwege). Die Herkunft prüft sie nicht — die
 *  Adresse baut nur dieser Lader, aus der API-Basis der Shell und dem Build-Index. Ein Präfix davor ist
 *  erlaubt: eine API unter `https://x/boerdi/api` lädt von `/boerdi/widget/module/` (Querschnitts-Review
 *  FE-7). */
const ERLAUBT = /^(?:\/[^/]+)*\/widget\/module\/ui-[a-z0-9-]+\.[0-9a-f]{8}\.js$/;

/* Je Seite (Realm) einmal, nicht je Shell: zwei Widgets auf einer Seite teilen sich die Richtlinie
 * (ein zweites `createPolicy` mit demselben Namen wirft unter einer CSP ohne `'allow-duplicates'`)
 * und die laufenden Ladevorgänge (ein Bündel läuft sonst zweimal). Schlüssel ist die Adresse. */
let richtlinie: { createScriptURL(url: string): unknown } | undefined;
const laufend = new Map<string, Promise<void>>();

/** Nur für Tests: gemeinsamen Zustand der Seite vergessen. */
export function zuruecksetzenFuerTests(): void {
  richtlinie = undefined;
  laufend.clear();
}

function adresse(url: string, dok: Document): unknown {
  const tt = (globalThis as { trustedTypes?: TrustedTypesFabrik }).trustedTypes;
  if (!tt) return url;
  // Einmal je Seite; eine Seite, die den Namen nicht erlaubt, wirft hier — dann lädt nichts.
  richtlinie ??= tt.createPolicy(RICHTLINIE, {
    createScriptURL(u: string): string {
      if (!ERLAUBT.test(new URL(u, dok.baseURI).pathname)) throw new Error('Keine Adresse eines Modul-Bündels');
      return u;
    },
  });
  return richtlinie.createScriptURL(url);
}

function lade(modul: string, url: string, eintrag: NachladeEintrag, optionen: LaderOptionen): Promise<void> {
  const dok = optionen.dokument ?? document;
  return new Promise<void>((erfuellt, abgelehnt) => {
    const skript = dok.createElement('script');
    const ende = (fehler?: Error): void => {
      clearTimeout(frist);
      if (fehler) {
        skript.remove();
        abgelehnt(fehler);
      } else {
        erfuellt();
      }
    };
    const frist = setTimeout(() => ende(new Error(`Frist für ${modul} abgelaufen`)), optionen.fristMs ?? FRIST_MS);
    try {
      skript.integrity = eintrag.integritaet;
      skript.crossOrigin = 'anonymous';
      skript.async = true;
      skript.dataset['boerdiModul'] = modul;
      skript.addEventListener('load', () => ende(), { once: true });
      skript.addEventListener('error', () => ende(new Error(`${modul} konnte nicht geladen werden`)), { once: true });
      (skript as unknown as { src: unknown }).src = adresse(url, dok);
      dok.head.appendChild(skript);
    } catch (fehler) {
      ende(fehler instanceof Error ? fehler : new Error(String(fehler)));
    }
  });
}

/**
 * Ein Lader für eine Shell. `apiBasis` wird bei jedem Laden gelesen, weil die Shell ihre Basis erst
 * nach dem Start kennt (`api-url`). Jedes Bündel lädt je Seite höchstens einmal; scheitert es, darf
 * ein späterer Block es neu versuchen. Ein Bündel kann nach einem Fristablauf doch noch laufen —
 * deshalb muss jedes Element sich nur definieren, wenn es noch nicht definiert ist (Element-Vertrag).
 */
export function erzeugeLader(
  apiBasis: () => string, index: NachladeIndex, optionen: LaderOptionen = {},
): (modul: string) => Promise<void> {
  return (modul: string) => {
    const eintrag = index[modul];
    if (!eintrag) return Promise.reject(new Error(`Kein Bündel für ${modul} im Index`));
    const url = modulBasis(apiBasis()) + eintrag.datei;
    let versprechen = laufend.get(url);
    if (!versprechen) {
      versprechen = lade(modul, url, eintrag, optionen);
      laufend.set(url, versprechen);
      versprechen.catch(() => laufend.delete(url));
    }
    return versprechen;
  };
}
