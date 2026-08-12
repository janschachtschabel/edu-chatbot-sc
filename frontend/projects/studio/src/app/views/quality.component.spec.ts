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
import { QualityComponent } from "./quality.component";

const STATS_URL = "/studio/api/quality/stats";
const MATRIX_URL = "/studio/api/quality/matrix";
const FLOW_URL = "/studio/api/quality/state-transitions";
const LOGS_URL = "/studio/api/quality/logs";

const STATS = {
  scope: "all",
  total_turns: 120,
  pattern_distribution: { M04: 60 },
  intent_distribution: { I02: 70 },
  avg_confidence: 0.8,
  degradation_rate: 0.01,
  empty_entity_rate: 0.1,
  avg_response_length: 400,
};

const BREAKDOWN = {
  scope: "all",
  total: 0,
  groups: [],
  turns: [],
  max_confidence: 0.6,
};

interface Harness {
  fixture: ComponentFixture<QualityComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

/**
 * The overview and its three diagnosis breakdowns — what the first tab costs.
 *
 * Two steps, because the diagnosis blocks live inside the overview's
 * `@if (value())`: they are created only once the stats have arrived, so their
 * requests do not exist before that.
 */
async function flushOverview(h: Harness): Promise<void> {
  h.http.expectOne((r) => r.url === STATS_URL).flush(STATS);
  await settle(h);
  for (const path of ["degradations", "empty-entities", "low-confidence"]) {
    h.http
      .expectOne((r) => r.url === `/studio/api/quality/${path}`)
      .flush(BREAKDOWN);
  }
}

/** jsdom meldet `navigator.language === 'en-US'`; ohne gesetzte Wahl liefe die
 *  deutsche Oberfläche auf Englisch. */
async function mount(locale = "de"): Promise<Harness> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(QualityComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  await flushOverview(h);
  await settle(h);
  return h;
}

const tabs = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]'));

async function openTab(h: Harness, label: string): Promise<void> {
  tabs(h)
    .find((t) => t.textContent!.includes(label))!
    .click();
  await h.fixture.whenStable();
}

describe("QualityComponent", () => {
  it("offers four tabs, each pointing at a panel that exists", async () => {
    const h = await mount();
    const labels = tabs(h).map((t) => t.textContent!.trim());
    expect(labels).toEqual([
      "Übersicht",
      "Routing-Matrix",
      "Gesprächs-Flow",
      "Logs",
    ]);

    for (const tab of tabs(h)) {
      const panel = h.el.querySelector(`#${tab.getAttribute("aria-controls")}`);
      expect(panel).not.toBeNull();
      expect(panel!.getAttribute("aria-labelledby")).toBe(tab.id);
    }
  });

  it("opens on the overview and hides the other three panels", async () => {
    const h = await mount();
    expect(tabs(h)[0].getAttribute("aria-selected")).toBe("true");
    expect(
      h.el.querySelector("#panel-uebersicht")!.hasAttribute("hidden"),
    ).toBe(false);
    expect(h.el.querySelector("#panel-matrix")!.hasAttribute("hidden")).toBe(
      true,
    );
  });

  it("fetches a panel only once its tab has been opened", async () => {
    // ALT loaded the matrix and the flow lazily too; this keeps that and pins it.
    const h = await mount();
    h.http.verify(); // no matrix, no flow, no logs yet

    await openTab(h, "Routing-Matrix");
    h.http
      .expectOne((r) => r.url === MATRIX_URL)
      .flush({ scope: "all", total_turns: 5, cells: [] });
    await settle(h);
  });

  it("keeps a visited panel loaded instead of re-fetching on every tab switch", async () => {
    // ALT re-ran the matrix query on each `tab === 'matrix'` effect run.
    const h = await mount();
    await openTab(h, "Routing-Matrix");
    h.http
      .expectOne((r) => r.url === MATRIX_URL)
      .flush({ scope: "all", total_turns: 5, cells: [] });
    await settle(h);

    await openTab(h, "Übersicht");
    await openTab(h, "Routing-Matrix");
    await settle(h);
    h.http.verify();
  });

  it("switches the scope with real radios, and every open panel follows", async () => {
    const h = await mount();
    await openTab(h, "Gesprächs-Flow");
    h.http
      .expectOne((r) => r.url === FLOW_URL)
      .flush({
        scope: "all",
        days: 30,
        total_turns: 0,
        total_transitions: 0,
        state_distribution: {},
        transitions: [],
      });
    await settle(h);

    const radios = Array.from(
      h.el.querySelectorAll<HTMLInputElement>('input[type="radio"]'),
    );
    expect(radios).toHaveLength(3);
    expect(radios[0].checked).toBe(true);

    radios[2].checked = true;
    radios[2].dispatchEvent(new Event("change"));
    await h.fixture.whenStable();

    // Both the loaded panels re-read for the new scope; the unvisited ones do not.
    expect(
      h.http.expectOne((r) => r.url === FLOW_URL).request.params.get("scope"),
    ).toBe("eval");
    await flushOverview(h);
    await settle(h);
  });

  it("sends a drill-down to the log tab and applies it as a filter", async () => {
    const h = await mount();
    await openTab(h, "Routing-Matrix");
    h.http
      .expectOne((r) => r.url === MATRIX_URL)
      .flush({
        scope: "all",
        total_turns: 10,
        cells: [
          {
            persona_id: "P01",
            intent_id: "I05",
            top_pattern: "M15",
            top_pattern_count: 4,
            total_count: 5,
            share: 0.8,
            alternatives: [],
          },
        ],
      });
    await settle(h);

    h.el.querySelector<HTMLButtonElement>(".qm-cell")!.click();
    await h.fixture.whenStable();

    // The logs tab is now the selected one …
    const selected = tabs(h).find(
      (t) => t.getAttribute("aria-selected") === "true",
    );
    expect(selected!.textContent).toContain("Logs");
    // … and it asks for exactly the intent that was clicked.
    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get("intent_id")).toBe("I05");
    req.flush({ count: 0, logs: [] });
    await settle(h);
  });

  it("names the view and says what the scope switch does", async () => {
    const h = await mount();
    expect(h.el.querySelector("h2")!.textContent).toContain("Analyse");
    expect(h.el.querySelector("fieldset legend")!.textContent).toContain(
      "Datenbasis",
    );
  });

  it("nimmt Reiter, Datenbasis und deren Erklärungen aus dem Katalog", async () => {
    // Die vier Reiter und die drei Datenbasis-Wahlen standen als eingefrorene
    // Konstanten im Bauteil — beides ist Oberfläche, nicht Struktur.
    const h = await mount("en");
    expect(tabs(h).map((t) => t.textContent!.trim())).toEqual([
      "Overview",
      "Routing matrix",
      "Conversation flow",
      "Logs",
    ]);
    expect(h.el.querySelector("h2")!.textContent).toContain("Analysis");
    expect(h.el.querySelector("fieldset legend")!.textContent).toContain(
      "Data basis",
    );
    const hints = Array.from(h.el.querySelectorAll(".qv-scope-hint")).map(
      (s) => s.textContent,
    );
    expect(hints).toEqual([
      "Real conversations and eval runs together",
      "Real conversations only",
      "Simulated eval turns only",
    ]);
  });
});
