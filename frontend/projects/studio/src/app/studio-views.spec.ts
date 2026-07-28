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

describe('studio view registry', () => {
  const shell = routes.find((r) => r.path === '');
  const children = shell?.children ?? [];

  it('covers the §5.6 view list', () => {
    // 16 ported views (spec §5.6 counts 18 including the Architektur sub-tab,
    // which is a tab of "Übersicht" here) plus three with no ALT counterpart as
    // a view: "Alle Bereiche", the entry point to the generic editor that makes
    // V3 checkable (9-3f), "Sicherung" — ALT's Snapshots/Backup/Restore hung in
    // the header, which is why 9-2 counted it as chrome; 9-6 made it a view
    // instead (backup.component.ts records why the modal was not rebuilt) — and
    // "Vorschau", improvement V8: ALT could only check a change on a real host
    // page (widget-preview.component.ts).
    expect(STUDIO_VIEWS).toHaveLength(19);
    const labels = STUDIO_VIEWS.map((v) => v.label);
    for (const expected of [
      'Übersicht', 'Begrüßung', 'Kontext-Aktionen', 'Identität & Schutz', 'Domain-Wissen',
      'Patterns', 'Dimensionen', 'Material-Formate', 'Wissen', 'Anzeige', 'Datenschutz',
      'Sessions', 'Analyse', 'Evaluation', 'Lasttest', 'Safety-Logs', 'Alle Bereiche',
      'Sicherung', 'Vorschau',
    ]) {
      expect(labels).toContain(expected);
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
    expect(NAV_GROUPS.map((g) => g.title)).toEqual([
      null, 'Konfiguration', 'Auswertung', 'System',
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
    for (const view of STUDIO_VIEWS) expect(view.paket).toMatch(/^9-[3-6]$/);
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
