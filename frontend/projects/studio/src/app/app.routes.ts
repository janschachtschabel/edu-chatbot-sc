/**
 * Route table (P9-2, spec §5.6 "Views NEU = Angular-Routen").
 *
 * Derived from STUDIO_VIEWS so nav and routes cannot drift (see studio-views.ts).
 * Every view is lazy — an editor who only ever opens "Begrüßung" should not pay
 * for the Lasttest charts.
 *
 * `login` sits OUTSIDE the shell: it must render without the guard, and showing
 * the nav to someone who is not signed in would be a lie.
 */
import { Type, inject } from '@angular/core';
import { Routes } from '@angular/router';

import { authGuard } from './auth/auth.guard';
import { StudioLanguageService } from './i18n/studio-language.service';
import { DEFAULT_VIEW, STUDIO_VIEWS, type StudioView } from './studio-views';
import { curatedView } from './views/curated-views';
import { unsavedChangesGuard } from './views/unsaved-changes.guard';

/**
 * Dokumenttitel „<Seite> — BOERDi Studio", in der aktiven Sprache (C1-d2).
 *
 * Als Resolver und nicht als Zeichenkette: eine Konstante würde beim Laden des
 * Moduls einmal in der damaligen Sprache gebaut und bliebe darin stehen. Läuft
 * im Injektionskontext, deshalb ist `inject()` hier erlaubt.
 */
const title = (key: string) => () => {
  const t = inject(StudioLanguageService).t;
  return `${t(key)} — ${t('studio.title')}`;
};

/**
 * Slugs with a component of their own: the 9-5 dashboards (read-only), the 9-6
 * Sicherung, which writes, and the 9-6 Vorschau, which embeds the widget. The
 * curated editors and the generic area editor are resolved below.
 */
const DASHBOARDS: Record<string, () => Promise<Type<unknown>>> = {
  uebersicht: () => import('./views/overview.component').then((m) => m.OverviewComponent),
  sicherung: () => import('./views/backup.component').then((m) => m.BackupComponent),
  vorschau: () =>
    import('./views/widget-preview.component').then((m) => m.WidgetPreviewComponent),
  sessions: () => import('./views/sessions.component').then((m) => m.SessionsComponent),
  'safety-logs': () =>
    import('./views/safety-logs.component').then((m) => m.SafetyLogsComponent),
  lasttest: () => import('./views/loadtest.component').then((m) => m.LoadtestComponent),
  analyse: () => import('./views/quality.component').then((m) => m.QualityComponent),
  evaluation: () =>
    import('./views/evaluation.component').then((m) => m.EvaluationComponent),
  kosten: () => import('./views/costs.component').then((m) => m.CostsComponent),
};

/** Which component a view slug resolves to. Everything else is a placeholder. */
function loadViewComponent(view: StudioView): Promise<Type<unknown>> {
  if (curatedView(view.slug)) {
    return import('./views/curated-view.component').then((m) => m.CuratedViewComponent);
  }
  const dashboard = DASHBOARDS[view.slug];
  if (dashboard) return dashboard();
  if (view.paket === '9-3') {
    return import('./views/areas.component').then((m) => m.AreasComponent);
  }
  return import('./views/placeholder.component').then((m) => m.PlaceholderComponent);
}

export const routes: Routes = [
  {
    path: 'login',
    title: title('route.login'),
    loadComponent: () => import('./auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./shell/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: DEFAULT_VIEW },
      ...STUDIO_VIEWS.map((view) => ({
        path: view.slug,
        title: title(view.labelKey),
        // `data.view` reaches the component as an input via
        // withComponentInputBinding(); 9-5 replaces the remaining placeholders.
        data: { view },
        // Only where something can be edited: the guard calls `dirty()`, which
        // an index or a placeholder does not have.
        canDeactivate: curatedView(view.slug) ? [unsavedChangesGuard] : [],
        loadComponent: () => loadViewComponent(view),
      })),
      {
        // A wildcard, not `:area`: an area key is `01-base/welcome-config` and
        // a route parameter cannot span a slash.
        path: 'bereich/**',
        // Ein eigener Resolver: der Titel ist hier nicht der Ansichtsname,
        // sondern der Bereichs-Pfad — 55 Bereiche unter einem Titel machen
        // Verlauf und Ansage gleichermassen nutzlos.
        title: (route) => {
          const t = inject(StudioLanguageService).t;
          const pfad = route.url.slice(1).map((s) => s.path).join('/');
          return `${pfad || t('route.area')} — ${t('studio.title')}`;
        },
        canDeactivate: [unsavedChangesGuard],
        loadComponent: () =>
          import('./views/area-editor.component').then((m) => m.AreaEditorComponent),
      },
      {
        // Inside the shell on purpose: a mistyped URL should leave the
        // navigation reachable instead of dropping the user on a bare page.
        path: '**',
        title: title('route.notFound'),
        loadComponent: () => import('./views/not-found.component').then((m) => m.NotFoundComponent),
      },
    ],
  },
];
