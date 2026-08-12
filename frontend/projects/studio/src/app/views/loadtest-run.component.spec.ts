// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import {
  Component,
  provideZonelessChangeDetection,
  signal,
} from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { LoadtestRunComponent } from "./loadtest-run.component";

const POLL_MS = 2000;
const url = (id: string): string => `/studio/api/loadtest/runs/${id}`;

const PROFILE = {
  stages: [1, 2],
  requests_per_stage: 4,
  mix: { wissen: 1 },
  p95_threshold_s: 20,
  total_requests: 8,
};

function stage(concurrency: number, errors = 0) {
  return {
    concurrency,
    requests: 4,
    ok: 4 - errors,
    errors,
    error_kinds: errors ? ["timeout"] : [],
    p50_s: 2.1,
    p95_s: 4.2,
    max_s: 5,
    mean_s: 2.5,
    duration_s: 9,
    rps: 0.45,
    by_kind: { wissen: { n: 4, ok: 4, p50_s: 2.1, p95_s: 4.2 } },
  };
}

const RUNNING = {
  id: "lt-1",
  status: "running",
  created_at: "2026-07-24T18:00:00Z",
  finished_at: null,
  profile: PROFILE,
  stages: [stage(1)],
  resource_samples: [],
  summary: null,
  error: null,
};

const COMPLETED = {
  ...RUNNING,
  status: "completed",
  finished_at: "2026-07-24T18:05:00Z",
  stages: [stage(1), stage(2, 1)],
  // Die echte Form von `_summary` — seit C5 mit den zwei Ressourcen-Spitzen,
  // die jetzt einen Produzenten haben (psutil-Abtastung im Runner).
  resource_samples: [
    { t: 0.0, proc_cpu: 12.0, rss_mb: 180.0 },
    { t: 0.5, proc_cpu: 63.5, rss_mb: 244.5 },
  ],
  summary: {
    stable_concurrency: 1,
    p95_threshold_s: 20,
    total_requests: 8,
    total_errors: 1,
    peak_rss_mb: 244.5,
    peak_proc_cpu_pct: 63.5,
  },
};

/** A host so the required `runId` input can change like it does in the view. */
@Component({
  selector: "studio-run-host",
  imports: [LoadtestRunComponent],
  template:
    '<studio-loadtest-run [runId]="id()" (finished)="finishes = finishes + 1" />',
})
class HostComponent {
  readonly id = signal("lt-1");
  finishes = 0;
}

interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

/** Flushes microtasks; a real `setTimeout(0)` would never fire under fake timers. */
async function settle(h: Harness): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
  await h.fixture.whenStable();
}

async function mount(
  first: object = COMPLETED,
  locale = "de",
): Promise<Harness> {
  // jsdom meldet `navigator.language === 'en-US'` — ohne die gemerkte Wahl
  // stünde die Oberfläche ab C1-d4e1 auf Englisch.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne(url("lt-1")).flush(first);
  await settle(h);
  return h;
}

describe("LoadtestRunComponent", () => {
  beforeEach(() => {
    // Real timers would make the polling tests wait two seconds each.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the verdict, the profile and every finished stage", async () => {
    const h = await mount();
    const text = h.el.textContent!;
    // C1-d4e1: die Einzahl beugt mit — „bis 1 gleichzeitigen Nutzer" gegen
    // „bis 4 gleichzeitige Nutzer". Bis hierher stand die Mehrzahlform fest im
    // Template und dieser Test hat sie mit `stable_concurrency: 1` gepinnt.
    expect(text).toContain("Stabil bis 1 gleichzeitigen Nutzer");
    expect(text).not.toContain("NaN");
    expect(h.el.querySelectorAll(".lr-table tbody tr")).toHaveLength(2);
  });

  it("marks a stage that produced errors with more than a colour", async () => {
    const h = await mount();
    const bad = h.el.querySelector(".lr-bad")!;
    expect(bad.textContent).toContain("1");
    expect(bad.textContent).toContain("timeout");
  });

  it("says plainly when not even the first stage held the threshold", async () => {
    const h = await mount({
      ...COMPLETED,
      summary: { ...COMPLETED.summary, stable_concurrency: null },
    });
    expect(h.el.textContent).toContain(
      "Schon die erste Stufe verfehlte die Schwelle",
    );
  });

  it("draws the latency curve from the finished stages", async () => {
    const h = await mount();
    const line = h.el.querySelector(".lr-line--p95")!;
    expect(line.getAttribute("points")).not.toContain("NaN");
    expect(h.el.querySelectorAll(".lr-dot--p95")).toHaveLength(2);
  });

  it("re-reads a running run until it stops, then tells the parent once", async () => {
    const h = await mount(RUNNING);
    expect(h.el.textContent).toContain("Stufe 1 von 2 fertig");

    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http.expectOne(url("lt-1")).flush(RUNNING);
    await settle(h);
    expect(h.fixture.componentInstance.finishes).toBe(0);

    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http.expectOne(url("lt-1")).flush(COMPLETED);
    await settle(h);

    expect(h.fixture.componentInstance.finishes).toBe(1);
    // and it stops: no further request is scheduled
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it("does not poll a run that was already finished when opened", async () => {
    const h = await mount(COMPLETED);
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it("keeps the last state on screen when a poll fails, and says so", async () => {
    // ALT swallowed poll errors with an empty catch, so a backend that died
    // mid-run left the page claiming "läuft" for as long as it was open.
    const h = await mount(RUNNING);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http
      .expectOne(url("lt-1"))
      .flush("x", { status: 503, statusText: "Unavailable" });
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')).not.toBeNull();
    expect(h.el.querySelector(".lr-table")).not.toBeNull(); // the stage table survived
  });

  it("stops polling when the run panel goes away", async () => {
    const h = await mount(RUNNING);
    h.fixture.destroy();
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it("follows the selection to another run", async () => {
    const h = await mount(COMPLETED);
    h.fixture.componentInstance.id.set("lt-2");
    await h.fixture.whenStable();
    await vi.advanceTimersByTimeAsync(0);
    h.http.expectOne(url("lt-2")).flush({ ...COMPLETED, id: "lt-2" });
    await settle(h);
    expect(h.el.textContent).toContain("lt-2");
  });

  /**
   * B5 pinnte hier, dass die Ansicht die FEHLENDE Messung benennt statt „NaN"
   * zu drucken. **C5 liefert die Messung** (psutil-Abtastung), also pinnt der
   * Test jetzt die Werte — der NaN-Schutz bleibt, er galt dem Rechenfehler.
   */
  it("zeigt die gemessenen Spitzen samt Anzahl der Messpunkte, nie NaN", async () => {
    const h = await mount();
    const verdict = h.el.querySelector(".lr-verdict")!.textContent ?? "";
    expect(verdict).not.toContain("NaN");
    expect(verdict).toContain("244,5"); // Speicher-Spitze, deutsch getrennt
    expect(verdict).toContain("63,5"); // CPU-Spitze
    expect(verdict).toContain("2 Messpunkte");
  });

  it("benennt einen Lauf ohne Messpunkte, statt 0 als Messwert auszugeben", async () => {
    // Ein Lauf, der kürzer war als ein Abtast-Intervall: 0-Spitzen sind dann
    // KEINE Aussage über den Ressourcenbedarf.
    const h = await mount({
      ...COMPLETED,
      resource_samples: [],
      summary: { ...COMPLETED.summary, peak_rss_mb: 0, peak_proc_cpu_pct: 0 },
    });
    const verdict = h.el.querySelector(".lr-verdict")!.textContent ?? "";
    expect(verdict).toContain("Keine Messpunkte");
    expect(verdict).not.toContain("0 MB Speicher");
  });

  /**
   * C1-d4e1 — vier Anzahlen, die bis hierher fest in der Mehrzahl standen. Der
   * Lauf mit genau einem von allem ist kein Sonderfall: das Backend deckelt
   * nichts nach unten, und der Abtast-Takt von 0,5 s liefert bei einem kurzen
   * Lauf genau einen Messpunkt.
   */
  it("beugt Requests, Fehler und Messpunkte nach ihrer Anzahl", async () => {
    const h = await mount({
      ...COMPLETED,
      stages: [stage(1)],
      resource_samples: [{ t: 0.0, proc_cpu: 12.0, rss_mb: 180.0 }],
      summary: { ...COMPLETED.summary, total_requests: 1, total_errors: 1 },
    });
    const verdict = h.el.querySelector(".lr-verdict")!.textContent ?? "";

    expect(verdict).toContain("1 Request, 1 Fehler.");
    expect(verdict).toContain("1 Messpunkt,");
  });

  it("beugt auch die Stufenzahl im zugänglichen Namen des Diagramms", async () => {
    const h = await mount({ ...COMPLETED, stages: [stage(1)] });
    expect(
      h.el.querySelector(".lr-chart")!.getAttribute("aria-label"),
    ).toContain("über 1 Stufe;");
  });

  it("spricht Englisch, wenn Englisch eingestellt ist", async () => {
    const h = await mount(COMPLETED, "en");
    const text = h.el.textContent!;

    expect(text).toContain("Stable up to 1 concurrent user");
    expect(text).toContain("8 requests, 1 error.");
    expect(text).not.toContain("Stabil bis");
  });
});
