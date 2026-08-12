// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { LoadtestComponent } from "./loadtest.component";

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

const RUNS_URL = "/studio/api/loadtest/runs";
const MIX_URL = "/studio/api/loadtest/mix-options";

const MIX = [
  { key: "wissen", label: "Wissensfragen", prompt: "Was ist ein Erklärvideo?" },
  { key: "lernpfad", label: "Lernpfade", prompt: "Baue mir einen Lernpfad." },
];

// Exactly what `_summary` in services/loadtest.py returns. Seit C5 (2026-07-31)
// gehoeren die zwei Spitzenwerte wieder dazu: psutil ist Abhaengigkeit, der
// Runner tastet CPU/RSS alle 0,5 s ab — die Felder haben also einen echten
// Produzenten. VOR C5 hatte eine Fixture sie *erfunden*, ohne dass irgendein
// Backend-Pfad sie schrieb; genau so kam "Spitze NaN MB" ins echte Studio (B5).
// Der NaN-Schutz unten bleibt deshalb stehen.
const SUMMARY = {
  stable_concurrency: 4,
  p95_threshold_s: 20,
  total_requests: 32,
  total_errors: 0,
  peak_rss_mb: 512.5,
  peak_proc_cpu_pct: 87.5,
};

const PROFILE = {
  stages: [1, 2, 4, 8],
  requests_per_stage: 8,
  mix: { wissen: 2 },
  p95_threshold_s: 20,
  total_requests: 32,
};

const DONE_RUN = {
  id: "lt-abc123",
  status: "completed",
  created_at: "2026-07-24T18:00:00Z",
  summary: SUMMARY,
  profile: PROFILE,
  error: null,
};

const RUNNING_RUN = {
  ...DONE_RUN,
  id: "lt-live99",
  status: "running",
  summary: null,
};

interface Harness {
  fixture: ComponentFixture<LoadtestComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

function create(locale = "de"): Harness {
  // jsdom meldet `navigator.language === 'en-US'`; ohne die gemerkte Wahl
  // stünde die Oberfläche auf Englisch und jede deutsche Zusicherung unten
  // wäre ab C1-d4e1 rot.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(LoadtestComponent);
  return {
    fixture,
    el: fixture.nativeElement as HTMLElement,
    http: TestBed.inject(HttpTestingController),
  };
}

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

async function mount(
  runs: unknown[] = [DONE_RUN],
  locale = "de",
): Promise<Harness> {
  const h = create(locale);
  await h.fixture.whenStable();
  h.http.expectOne(RUNS_URL).flush({ runs });
  h.http.expectOne(MIX_URL).flush({ options: MIX });
  await settle(h);
  return h;
}

function startButton(h: Harness): HTMLButtonElement {
  return h.el.querySelector<HTMLButtonElement>(".lt-btn--go")!;
}

async function typeStages(h: Harness, value: string): Promise<void> {
  const input = h.el.querySelector<HTMLInputElement>("#lt-stages")!;
  input.value = value;
  input.dispatchEvent(new Event("input"));
  await h.fixture.whenStable();
}

describe("LoadtestComponent", () => {
  it("names the real cost of the profile before the button is pressed", async () => {
    const h = await mount();
    expect(h.el.querySelector(".lt-cost")!.textContent).toContain(
      "32 echte Chat-Anfragen",
    );
  });

  it("shows what the backend will actually run, not what was typed", async () => {
    // ALT multiplied the typed stage count by requests-per-stage; the backend
    // then dropped everything past the sixth stage and capped 64 at 32.
    const h = await mount();
    await typeStages(h, "1, 2, 4, 8, 16, 32, 64");

    const cost = h.el.querySelector(".lt-cost")!.textContent!;
    expect(cost).toContain("48 echte Chat-Anfragen"); // 6 stages × 8, not 7 × 8
    expect(cost).toContain("1 → 2 → 4 → 8 → 16 → 32");
    expect(h.el.querySelector(".lt-adjust")!.textContent).toContain("6 Stufen");
  });

  it("blocks the start and says why when the profile is too big", async () => {
    const h = await mount();
    await typeStages(h, "1,2,4,8,16,32");
    const rps = h.el.querySelector<HTMLInputElement>("#lt-rps")!;
    rps.value = "60";
    rps.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();

    expect(startButton(h).disabled).toBe(true);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain("200");
  });

  it("blocks the start while any run is in flight, not just the open one", async () => {
    // The backend permits one run at a time and answers 409; ALT only looked at
    // the run it had open, so the usual way to find out was the error message.
    const h = await mount([RUNNING_RUN]);
    expect(startButton(h).disabled).toBe(true);
    expect(h.el.querySelector(".lt-busy")!.textContent).toContain("lt-live99");
  });

  it("posts the effective profile and opens the new run", async () => {
    const h = await mount([]);
    startButton(h).click();
    await h.fixture.whenStable();

    const req = h.http.expectOne(RUNS_URL);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      stages: [1, 2, 4, 8],
      requests_per_stage: 8,
      // The zero-weight category is dropped, not sent as 0.
      mix: { wissen: 2, suche: 2, orientierung: 1 },
      p95_threshold_s: 20,
    });
    req.flush({ id: "lt-new001", status: "running", profile: PROFILE });
    await settle(h);

    h.http
      .expectOne(RUNS_URL)
      .flush({ runs: [{ ...RUNNING_RUN, id: "lt-new001" }] });
    await settle(h);
    // the detail panel asks for the run it just started
    h.http.expectOne("/studio/api/loadtest/runs/lt-new001").flush({
      ...DONE_RUN,
      id: "lt-new001",
      status: "running",
      stages: [],
      resource_samples: [],
      summary: null,
      finished_at: null,
    });
    await settle(h);
    expect(h.fixture.componentInstance.selected()).toBe("lt-new001");
  });

  it("reports a refused start in the backend words", async () => {
    const h = await mount([]);
    startButton(h).click();
    await h.fixture.whenStable();
    h.http
      .expectOne(RUNS_URL)
      .flush(
        {
          detail:
            "Lasttest ist auf dieser Instanz deaktiviert (BOERDI_ALLOW_LOADTEST).",
        },
        { status: 403, statusText: "Forbidden" },
      );
    await settle(h);

    const error = h.el.querySelector(".lt-error")!;
    expect(error.textContent).toContain("BOERDI_ALLOW_LOADTEST");
    expect(error.textContent).not.toContain("HTTP 403"); // never the transport envelope
  });

  it("asks before deleting a run and does nothing when cancelled", async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>(".lt-del")!.click();
    await h.fixture.whenStable();
    expect(h.el.textContent).toContain(
      "Diesen Lauf mit allen Messwerten löschen",
    );

    h.el.querySelectorAll<HTMLButtonElement>(".lt-confirm .lt-btn")[1].click();
    await h.fixture.whenStable();
    h.http.verify();
  });

  it("deletes the confirmed run and re-reads the list", async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>(".lt-del")!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".lt-del-yes")!.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne(`${RUNS_URL}/lt-abc123`);
    expect(req.request.method).toBe("DELETE");
    req.flush({ deleted: "lt-abc123" });
    await settle(h);
    h.http.expectOne(RUNS_URL).flush({ runs: [] });
  });

  it("keeps a running run from being deleted at all", async () => {
    // The endpoint answers 409; offering the button anyway is an invitation to
    // an error message.
    const h = await mount([RUNNING_RUN]);
    expect(h.el.querySelector<HTMLButtonElement>(".lt-del")!.disabled).toBe(
      true,
    );
  });

  it("says an empty list is empty, and how something gets into it", async () => {
    const h = await mount([]);
    expect(h.el.textContent).toContain("Noch kein Lasttest gelaufen");
  });

  it("keeps the form usable when only the mix categories fail to load", async () => {
    const h = create();
    await h.fixture.whenStable();
    h.http.expectOne(RUNS_URL).flush({ runs: [] });
    h.http
      .expectOne(MIX_URL)
      .flush("x", { status: 500, statusText: "Server Error" });
    await settle(h);

    expect(h.el.querySelector('.lt-mix-state [role="alert"]')).not.toBeNull();
    expect(h.el.querySelector("#lt-stages")).not.toBeNull();
  });

  it("labels every mix weight with its category", async () => {
    const h = await mount();
    for (const option of MIX) {
      const input = h.el.querySelector<HTMLInputElement>(
        `#lt-mix-${option.key}`,
      )!;
      const label = h.el.querySelector(`label[for="lt-mix-${option.key}"]`)!;
      expect(input).not.toBeNull();
      expect(label.textContent).toContain(option.label);
    }
  });

  /**
   * B6: the confirmation appears under the button that armed it and the focus does
   * not move, so without a live region a screen reader learns nothing before the
   * second click. `role="alert"` carries the QUESTION only — a container that also
   * held the buttons would re-announce the whole thing every time a button label
   * flips to "Wird gelöscht …" (the trap A3 documented for the cost paragraph).
   */
  it("announces the confirmation question", async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>(".lt-del")!.click();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('.lt-confirm [role="alert"]');
    expect(alert?.textContent).toContain("nicht rückgängig");
    expect(alert?.querySelector("button")).toBeNull();
  });

  /**
   * B5 pinnte hier „nie eine Spitze zeigen", weil das Backend keine erhob — die
   * Fixture erfand die Felder, und die Zeile rendete „Spitze NaN MB".
   * **C5 kehrt die Voraussetzung um** (psutil-Abtastung gebaut), also pinnt der
   * Test jetzt das neue Soll. Der eigentliche B5-Schutz — **niemals NaN** —
   * bleibt wortwoertlich: er galt dem Rechenfehler, nicht dem Feature.
   */
  it("zeigt die gemessene Speicher-Spitze und nie NaN", async () => {
    const h = await mount();
    const line =
      h.el.querySelector(".lt-run-meta, .lt-summary, li")!.textContent ?? "";
    expect(h.el.textContent).not.toContain("NaN");
    expect(h.el.textContent).toContain("512,5");
    expect(line + (h.el.textContent ?? "")).toContain("stabil bis 4 parallel");
  });

  /**
   * C1-d4e1: derselbe Fehler wie in der Lauf-Liste (C1-d4b1) und in den
   * Quality-Logs (C1-d4d2) — der Knopf trug seinen Namen in zwei Bruchstücken
   * (`Löschen` + `<span class="sr">`). Ein Screenreader las beide, aber der
   * zugängliche Name entstand aus zwei Knoten statt aus einem Attribut.
   */
  it("gibt dem Löschen-Knopf EINEN Namen, der mit dem sichtbaren Wort beginnt", async () => {
    const h = await mount();
    const button = h.el.querySelector<HTMLButtonElement>(".lt-del")!;

    expect(button.getAttribute("aria-label")).toBe("Löschen — Lauf lt-abc123");
    expect(button.textContent!.trim()).toBe("Löschen");
    expect(button.querySelector(".sr")).toBeNull();
  });

  it("zählt Requests und Fehler in der Zusammenfassung nach der Mehrzahl-Regel", async () => {
    const h = await mount([
      {
        ...DONE_RUN,
        summary: {
          ...SUMMARY,
          stable_concurrency: 1,
          total_requests: 1,
          total_errors: 1,
        },
      },
    ]);
    expect(h.el.querySelector(".lt-summary")!.textContent).toContain(
      "stabil bis 1 parallel · 1 Request · 1 Fehler",
    );
  });

  it("spricht Englisch, wenn Englisch eingestellt ist", async () => {
    const h = await mount([DONE_RUN], "en");
    expect(h.el.querySelector(".lt-cost")!.textContent).toContain(
      "32 real chat requests",
    );
    expect(h.el.querySelector(".lt-btn--go")!.textContent!.trim()).toBe(
      "Start load test",
    );
    expect(h.el.textContent).not.toContain("Lasttest starten");
  });
});
