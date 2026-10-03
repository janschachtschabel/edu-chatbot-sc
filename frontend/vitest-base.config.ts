import { defineConfig } from 'vitest/config';

// Gilt für alle drei Test-Targets (angular.json, "runnerConfig"). Der Angular-Builder führt
// den `test`-Block mit seinen Vorgaben zusammen (jsdom, isolate: false, Setup-Dateien).
//
// Zeitzone fest auf UTC wie in der CI. Gesetzt, bevor Vitest die Worker startet, die die
// Umgebung erben; sonst rechneten datumsabhängige Specs lokal in Europe/Berlin.
process.env['TZ'] = 'UTC';

export default defineConfig({
  test: {
    // Unter voller Last (drei Projekte, viele Dateien parallel) brauchten einzelne Specs
    // länger als die Vitest-Vorgabe von 5 s und kippten (2026-09-29, 2026-10-03).
    testTimeout: 30_000,
    hookTimeout: 30_000,
    // Gestubbte Globals nach jedem Test zurücksetzen: Mit isolate: false teilen sich die
    // Dateien eines Workers sonst ein verändertes globalThis.
    unstubGlobals: true,
  },
});
