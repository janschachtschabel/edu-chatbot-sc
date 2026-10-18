import { describe, expect, it } from 'vitest';

import { routes } from './app.routes';
import { STUDIO_VIEWS, navGroups, startView } from './studio-views';

/**
 * The invariant these tests exist for: ALT kept the nav list and the render
 * switch as two separate structures, and they DID diverge — `Layer` declared
 * `'info'`, which no nav entry and no render branch ever referenced (dead view).
 * Here both sides derive from STUDIO_VIEWS, and that is checked, not assumed.
 */
/** The generic area editor's wildcard route — not a view, so not in the nav. */
const BEREICH = 'bereich/**';

/**
 * The 16 views spec §5.6 ports from ALT — §5.6 itself counts 18, including the
 * Architektur sub-tab, which is a tab of "Übersicht" here.
 *
 * Its own list since K5, not one flat array of everything: this one carries the
 * ALT-fidelity promise, and folding a newly invented view into it would quietly
 * raise the very number that states the promise. Same discipline as
 * `SPEC_AREAS` / `NEUE_BEREICHE` in `backend/tests/test_config_models.py`.
 *
 * Named by slug since C1-d2: the labels are catalogue entries now, and their
 * German wording is pinned where it lives — `i18n/views-i18n.spec.ts`.
 */
const PORTIERT: readonly string[] = [
  'uebersicht', 'begruessung', 'kontext-aktionen', 'identitaet', 'domain-wissen',
  'patterns', 'dimensionen', 'material-formate', 'wissen', 'anzeige', 'datenschutz',
  'sessions', 'analyse', 'evaluation', 'lasttest', 'safety-logs',
];

/** Views with no ALT counterpart — each with the reason it exists anyway. */
const OHNE_ALT_VORBILD: Readonly<Record<string, string>> = {
  bereiche: 'Einstieg in den generischen Editor, macht V3 prüfbar (9-3f)',
  sicherung:
    'ALTs Snapshots/Backup/Restore hingen im Header, weshalb 9-2 sie als Chrome '
    + 'zählte; 9-6 macht eine Ansicht daraus — backup.component.ts hält fest, '
    + 'warum das Modal nicht nachgebaut wurde',
  vorschau:
    'Verbesserung V8: ALT konnte eine Änderung nur auf einer echten Host-Seite '
    + 'ansehen (widget-preview.component.ts)',
  kosten:
    'K5: ALT rechnete überhaupt nicht ab, hat also kein Gegenstück — die Ansicht '
    + 'kommt mit der Kostenüberwachung, nicht aus dem P9-Port',
  // Paket 14: der Agent-Arbeitsbereich — ALT kannte nur EINEN Weg, einen Zug zu beantworten.
  'agent-uebersicht':
    'Paket 14: Startseite des Agent-Arbeitsbereichs — Master-Skill mit Zustand, NodeID und '
    + 'Links ins Repositorium, dazu die Vorgabe-Maschine des Servers',
  'agent-rolle':
    'Paket 14: Rolle, Schutzregeln, Leitplanken, Anrede je Zielgruppe und die beiden '
    + 'Schutzantworten — alles, was der Agent-Kopf liest',
  'agent-prompt':
    'Paket 14: Prompt-Kette, Master-Skill-Wortlaut und die beiden Probeläufe (Chat-Weg und '
    + 'POST /api/agent)',
  fuehrung:
    'Paket 14: Website-Tour und Lotse wirken in beiden Maschinen — vorher auf „Domänenwissen“, '
    + 'das im Agent-Arbeitsbereich fehlt',
  betrieb:
    'Paket 14: Vorgabe-Maschine und Betriebsschalter (Streaming …) — vorher auf der Seite '
    + '„Agent“; sie gelten für beide Arbeitsbereiche',
  // Paket 15: Nutzer-Rundgang 2026-10-17 — Werkzeuge, Skills und Anrede gelten in beiden Modi.
  werkzeuge:
    'Paket 15: alle Werkzeuge aller MCP-Server und die eingebauten, mit Herkunft, Sperrgrund und '
    + 'Schalter — vorher doppelt (MCP-Panel unter Wissen und Agent-Seite)',
  skills:
    'Paket 15: Master-Skill mit Vorschau, Skill-Register und Skill-Brücke an einem Ort — vorher '
    + 'auf der Agent-Seite und der Patterns-Seite doppelt',
  zielgruppen:
    'Paket 15: die Anrede je Zielgruppe samt Rückfall gilt in beiden Modi — vorher unter „Rolle & '
    + 'Grenzen“ und „Anzeige“ verteilt',
};

/** Paket 14: was die Navigation je Arbeitsbereich in ihrem eigenen Block zeigt. */
const BLOCK: Readonly<Record<'agent' | 'pattern', readonly string[]>> = {
  agent: ['agent-uebersicht', 'agent-rolle', 'agent-prompt'],
  pattern: ['uebersicht', 'identitaet', 'domain-wissen', 'patterns', 'dimensionen',
    'material-formate'],
};

describe('studio view registry', () => {
  const shell = routes.find((r) => r.path === '');
  const children = shell?.children ?? [];

  it('covers the §5.6 view list', () => {
    expect(PORTIERT).toHaveLength(16);
    const slugs = STUDIO_VIEWS.map((v) => v.slug);
    for (const expected of PORTIERT) expect(slugs).toContain(expected);
  });

  it('führt jede Ansicht ohne ALT-Vorbild mit ihrem Grund', () => {
    // Die Gegenrichtung: eine Ansicht, die weder portiert noch begründet ist,
    // fällt hier auf — sonst wüchse die Registry lautlos.
    const slugs = STUDIO_VIEWS.map((v) => v.slug);
    expect(slugs.filter((s) => !PORTIERT.includes(s)).sort())
      .toEqual(Object.keys(OHNE_ALT_VORBILD).sort());
    for (const [slug, grund] of Object.entries(OHNE_ALT_VORBILD)) {
      expect(slugs, `nicht in der Registry: ${slug}`).toContain(slug);
      expect(grund.length, `Grund zu knapp: ${slug}`).toBeGreaterThan(40);
    }
  });

  it('leitet beide Katalog-Schlüssel aus dem Slug ab', () => {
    // Die Schlüssel stehen als Literale in der Registry — ein zur Laufzeit
    // zusammengesetzter Schlüssel gäbe bei einem Tippfehler den Schlüssel selbst
    // als Beschriftung aus. Dass sie der Konvention folgen, prüft dieser Test.
    for (const view of STUDIO_VIEWS) {
      expect(view.labelKey).toBe(`view.${view.slug}.label`);
      expect(view.descKey).toBe(`view.${view.slug}.desc`);
    }
  });

  it('has a route for every nav entry and a nav entry for every route', () => {
    const navSlugs = [...new Set([...navGroups('agent'), ...navGroups('pattern')]
      .flatMap((g) => g.views.map((v) => v.slug)))].sort();
    const routeSlugs = children
      .filter((c) => !c.redirectTo)
      .map((c) => c.path)
      .filter((p): p is string => !!p && p !== '**' && p !== BEREICH)
      .sort();
    expect(routeSlugs).toEqual(navSlugs);
  });

  it('zeigt je Arbeitsbereich nur dessen Block und die gemeinsamen Gruppen (Paket 14)', () => {
    for (const ansicht of ['agent', 'pattern'] as const) {
      const [eigener, ...rest] = navGroups(ansicht);
      expect(eigener.views.map((v) => v.slug)).toEqual(BLOCK[ansicht]);
      const fremd = BLOCK[ansicht === 'agent' ? 'pattern' : 'agent'];
      const alle = [eigener, ...rest].flatMap((g) => g.views.map((v) => v.slug));
      for (const slug of fremd) expect(alle, `${slug} in ${ansicht}`).not.toContain(slug);
    }
  });

  it('leitet die alte Agent-Seite auf die Agent-Übersicht um (Lesezeichen, Paket 14)', () => {
    const alt = children.find((c) => c.path === 'agent');
    expect(alt?.redirectTo).toBe('agent-uebersicht');
  });

  it('führt Werkzeuge, Skills und Zielgruppen unter „Gemeinsam“ (Paket 15)', () => {
    const gemeinsam = navGroups('agent').find((g) => g.titleKey === 'nav.group.gemeinsam')!;
    expect(gemeinsam.views.map((v) => v.slug)).toEqual([
      'begruessung', 'kontext-aktionen', 'fuehrung', 'zielgruppen', 'wissen', 'werkzeuge',
      'skills', 'anzeige', 'datenschutz',
    ]);
    // Lesezeichen auf die alte Agent-Seite „Werkzeuge & Skills“
    expect(children.find((c) => c.path === 'agent-werkzeuge')?.redirectTo).toBe('werkzeuge');
  });

  it('routes the generic area editor without giving it a nav entry', () => {
    // deliberately not in the sidebar: it is reached from "Alle Bereiche", and
    // a nav item that needs an area key to mean anything would lead nowhere
    const editor = children.find((c) => c.path === BEREICH);
    expect(editor?.title).toBeTruthy();
    expect(editor?.loadComponent).toBeTypeOf('function');
    const alle = [...navGroups('agent'), ...navGroups('pattern')];
    expect(alle.flatMap((g) => g.views.map((v) => v.slug))).not.toContain(BEREICH);
  });

  it('uses unique, URL-safe slugs', () => {
    const slugs = STUDIO_VIEWS.map((v) => v.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const slug of slugs) expect(slug).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
  });

  it('ordnet die Navigation: eigener Block, Gemeinsam, Auswertung, System (Paket 14)', () => {
    expect(navGroups('agent').map((g) => g.titleKey)).toEqual([
      'nav.group.agent', 'nav.group.gemeinsam', 'nav.group.auswertung', 'nav.group.system',
    ]);
    expect(navGroups('pattern').map((g) => g.titleKey)).toEqual([
      'nav.group.muster', 'nav.group.gemeinsam', 'nav.group.auswertung', 'nav.group.system',
    ]);
    for (const group of [...navGroups('agent'), ...navGroups('pattern')]) {
      expect(group.views.length).toBeGreaterThan(0);
    }
  });

  it('öffnet je Arbeitsbereich auf dessen Startseite', () => {
    expect(startView('agent')).toBe('agent-uebersicht');
    expect(startView('pattern')).toBe('uebersicht');
    const redirect = children.find((c) => c.path === '');
    expect(redirect?.redirectTo).toBeTypeOf('function');
    expect(redirect?.pathMatch).toBe('full');
  });

  it('names a real implementing package for every placeholder', () => {
    // `K5` steht hier neben den P9-Scheiben, weil die Kostenschau nicht aus dem
    // Port stammt. Eine Erlaubnisliste und kein `.toBeTruthy()`: ein Tippfehler
    // im Paketnamen soll auffallen, ein neues Paket bewusst eingetragen werden.
    // `D2` steht seit 2026-08-13 neben `K5`: „Agent & Maschine" stammt so wenig
    // aus dem P9-Port wie die Kostenschau.
    for (const view of STUDIO_VIEWS) expect(view.paket).toMatch(/^(9-[3-6]|K5|P14|P15)$/);
  });

  it('guards the shell and leaves /login open', () => {
    expect(shell?.canActivate).toHaveLength(1);
    const login = routes.find((r) => r.path === 'login');
    expect(login).toBeDefined();
    expect(login?.canActivate).toBeUndefined();
  });

  it('gives every view a document title', () => {
    // The title change is what a screen reader announces on route change; a
    // missing one leaves the previous view's title standing.
    for (const child of children) {
      if (child.redirectTo) continue; // a redirect carries no title
      expect(child.title).toBeTruthy();
    }
  });

  it('catches unknown URLs inside the shell, not at the top level', () => {
    expect(children.at(-1)?.path).toBe('**');
    expect(routes.some((r) => r.path === '**')).toBe(false);
  });
});
