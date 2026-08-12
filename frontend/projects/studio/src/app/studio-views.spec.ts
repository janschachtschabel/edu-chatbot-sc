import { describe, expect, it } from 'vitest';

import { routes } from './app.routes';
import { DEFAULT_VIEW, NAV_GROUPS, STUDIO_VIEWS } from './studio-views';

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
    const navSlugs = NAV_GROUPS.flatMap((g) => g.views.map((v) => v.slug)).sort();
    const routeSlugs = children
      .map((c) => c.path)
      .filter((p): p is string => !!p && p !== '**' && p !== BEREICH)
      .sort();
    expect(routeSlugs).toEqual(navSlugs);
  });

  it('routes the generic area editor without giving it a nav entry', () => {
    // deliberately not in the sidebar: it is reached from "Alle Bereiche", and
    // a nav item that needs an area key to mean anything would lead nowhere
    const editor = children.find((c) => c.path === BEREICH);
    expect(editor?.title).toBeTruthy();
    expect(editor?.loadComponent).toBeTypeOf('function');
    expect(NAV_GROUPS.flatMap((g) => g.views.map((v) => v.slug))).not.toContain(BEREICH);
  });

  it('uses unique, URL-safe slugs', () => {
    const slugs = STUDIO_VIEWS.map((v) => v.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const slug of slugs) expect(slug).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
  });

  it('groups the sidebar in the ALT order without empty groups', () => {
    expect(NAV_GROUPS.map((g) => g.titleKey)).toEqual([
      null, 'nav.group.konfiguration', 'nav.group.auswertung', 'nav.group.system',
    ]);
    for (const group of NAV_GROUPS) expect(group.views.length).toBeGreaterThan(0);
  });

  it('opens on a view that actually exists', () => {
    expect(STUDIO_VIEWS.map((v) => v.slug)).toContain(DEFAULT_VIEW);
    const redirect = children.find((c) => c.path === '');
    expect(redirect?.redirectTo).toBe(DEFAULT_VIEW);
    expect(redirect?.pathMatch).toBe('full');
  });

  it('names a real implementing package for every placeholder', () => {
    // `K5` steht hier neben den P9-Scheiben, weil die Kostenschau nicht aus dem
    // Port stammt. Eine Erlaubnisliste und kein `.toBeTruthy()`: ein Tippfehler
    // im Paketnamen soll auffallen, ein neues Paket bewusst eingetragen werden.
    for (const view of STUDIO_VIEWS) expect(view.paket).toMatch(/^(9-[3-6]|K5)$/);
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
      if (child.path === '') continue; // the redirect carries no title
      expect(child.title).toBeTruthy();
    }
  });

  it('catches unknown URLs inside the shell, not at the top level', () => {
    expect(children.at(-1)?.path).toBe('**');
    expect(routes.some((r) => r.path === '**')).toBe(false);
  });
});
