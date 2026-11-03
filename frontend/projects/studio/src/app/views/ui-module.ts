/**
 * Die Seite „UI-Module“ (Paket U1-f, Plan §16) — die reinen Regeln, ohne DOM prüfbar.
 *
 * Die Schalter stehen im Bereich `01-base/display-rules` unter `display_rules.ui_module` als
 * Ausschalt-Listen (`aus`, `agent_aus`); fehlt ein Name, ist das Modul an. Das Backend liest sie
 * in `config_loader/ui_module.py` und wendet sie in `ui_module/schalter.py` an — hier wird nur
 * das Dokument gelesen und geändert. Gespeichert wird das GANZE Dokument (`/config/data`).
 */
import type { ModulKontext, UiModulManifest } from '@boerdi/ui-module';

import type { UiModulEintrag } from '../core/ui-module-api.service';

export type { UiModulEintrag, UiModulKatalog } from '../core/ui-module-api.service';

export interface Schalter {
  readonly aus: readonly string[];
  readonly agent_aus: readonly string[];
}

type Dokument = Readonly<Record<string, unknown>>;

function objekt(wert: unknown): Record<string, unknown> {
  return wert && typeof wert === 'object' && !Array.isArray(wert) ? wert as Record<string, unknown> : {};
}

function namen(wert: unknown): string[] {
  return Array.isArray(wert) ? wert.filter((n): n is string => typeof n === 'string') : [];
}

/** Die Ausschalt-Listen aus dem Bereichsdokument; Bestand in falscher Form zählt als leer. */
export function schalterAus(doc: Dokument | null): Schalter {
  const roh = objekt(objekt(objekt(doc)['display_rules'])['ui_module']);
  return { aus: namen(roh['aus']), agent_aus: namen(roh['agent_aus']) };
}

/** Ein neues Dokument mit einem umgelegten Schalter; alles Übrige bleibt, wie es kam. */
export function mitSchalter(doc: Dokument, name: string, art: 'aktiv' | 'agent', an: boolean): Dokument {
  const regeln = objekt(doc['display_rules']);
  const schalter = schalterAus(doc);
  const liste = art === 'aktiv' ? 'aus' : 'agent_aus';
  const menge = new Set(schalter[liste]);
  if (an) menge.delete(name);
  else menge.add(name);
  return {
    ...doc,
    display_rules: {
      ...regeln,
      ui_module: { ...objekt(regeln['ui_module']), ...schalter, [liste]: [...menge].sort() },
    },
  };
}

/**
 * Nach einem Konflikt (Review U1-f, #2): nur die Umschaltungen des Entwurfs gegenüber dem
 * geladenen Stand auf das neue Dokument setzen. Ein Modul, das inzwischen jemand anderes
 * umgelegt hat und das hier unberührt blieb, behält den neuen Stand; alles Übrige auch.
 */
export function mitUmschaltungen(neu: Dokument, geladen: Schalter, entwurf: Schalter): Dokument {
  const regeln = objekt(neu['display_rules']);
  const frisch = schalterAus(neu);
  const liste = (art: keyof Schalter): string[] => {
    const menge = new Set(frisch[art]);
    for (const name of entwurf[art]) if (!geladen[art].includes(name)) menge.add(name);
    for (const name of geladen[art]) if (!entwurf[art].includes(name)) menge.delete(name);
    return [...menge].sort();
  };
  return {
    ...neu,
    display_rules: {
      ...regeln,
      ui_module: { ...objekt(regeln['ui_module']), aus: liste('aus'), agent_aus: liste('agent_aus') },
    },
  };
}

/** Wie das Modul gerade steht: `agent` ist `null`, wo es keinen Agent-Schalter gibt; ein festes
 *  Modul ist immer aktiv (das Backend ignoriert es in den Listen, `ui_module/schalter.py`). */
export function zustand(
  eintrag: UiModulEintrag, schalter: Schalter,
): { readonly aktiv: boolean; readonly agent: boolean | null } {
  const aktiv = !eintrag.schaltbar.aktiv || !schalter.aus.includes(eintrag.name);
  if (!eintrag.schaltbar.agent) return { aktiv, agent: null };
  return { aktiv, agent: aktiv && !schalter.agent_aus.includes(eintrag.name) };
}

/** Eine Zeile der Feldübersicht (Eingabe oder Antwort eines Moduls). */
export interface Feld {
  readonly name: string;
  /** JSON-Typ (`string`, `array<object>`, `integer | null`) oder `enum`. */
  readonly typ: string;
  readonly pflicht: boolean;
  readonly beschreibung: string;
  /** Zulässige Werte einer Aufzählung. */
  readonly werte: readonly string[];
  /** Werte, die nur das System setzt (`x-nur-system`) — die KI bekommt sie nicht angeboten. */
  readonly nurSystem: readonly string[];
}

function typVon(schema: Record<string, unknown>): string {
  if (Array.isArray(schema['enum'])) return 'enum';
  const typ = schema['type'];
  if (Array.isArray(typ)) return typ.join(' | ');
  if (typ === 'array') {
    const innen = objekt(schema['items'])['type'];
    return typeof innen === 'string' ? `array<${innen}>` : 'array';
  }
  return typeof typ === 'string' ? typ : '';
}

/** Die oberste Ebene eines JSON Schemas als Liste, in der Reihenfolge des Manifests. */
export function feldUebersicht(schema: Readonly<Record<string, unknown>> | undefined): readonly Feld[] {
  const eigenschaften = objekt(schema?.['properties']);
  const pflicht = new Set(namen(schema?.['required']));
  return Object.entries(eigenschaften).map(([name, roh]) => {
    const feld = objekt(roh);
    return {
      name,
      typ: typVon(feld),
      pflicht: pflicht.has(name),
      beschreibung: typeof feld['description'] === 'string' ? feld['description'] : '',
      werte: Array.isArray(feld['enum']) ? feld['enum'].map(String) : [],
      nurSystem: namen(feld['x-nur-system']),
    };
  });
}

/** Ein Beispiel des Manifests. */
export type Beispiel = UiModulManifest['beispiele'][number];

/** Der Kontext, mit dem die Vorschau ein Beispiel zeigt: wie im Widget, aber ohne Nachricht.
 *  `beantwortet` zeigt ein Beispiel mit `antwort` nur lesend mit dieser Antwort — so zeigt das
 *  Widget eine beantwortete Frage; sonst ist es offen und lässt sich ausprobieren. */
export function vorschauKontext(
  name: string, index: number, sprache: 'de' | 'en', beispiel: Beispiel, beantwortet: boolean,
): ModulKontext {
  const antwort = beantwortet ? beispiel.antwort ?? null : null;
  return {
    blockId: `vorschau-${name.replace(/_/g, '-')}-${index}`,
    sprache,
    nurLesen: !!antwort,
    antwort,
    schriftSkala: 0.85,
    anzeigeRegeln: null,
  };
}
