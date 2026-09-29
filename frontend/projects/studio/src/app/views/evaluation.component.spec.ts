// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { describe, expect, it } from "vitest";

import { routes } from "../app.routes";
import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { AREA_SCHEMAS } from "../schema-form/area-schemas.fixture";
import { EvaluationComponent } from "./evaluation.component";

const RUNS_URL = "/studio/api/eval/runs";
const TRENDS_URL = "/studio/api/eval/trends";
/** The start panel (A3) sits in the same tab and loads its own choices. */
const CONFIG_URL = "/studio/api/eval/config";
/** The gold-flow start panel (A2) reads its own choices. */
const FLOWS_URL = "/studio/api/eval/gold-flows";

interface Harness {
  fixture: ComponentFixture<EvaluationComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

/** One list row, only the fields the list itself renders. */
function runRow(over: Record<string, unknown> = {}) {
  return {
    id: "eval-abc",
    created_at: "2026-07-26T10:00:00Z",
    completed_at: null,
    status: "done",
    mode: "golden",
    config_slug: "",
    total_turns: 3,
    avg_score: 0.83,
    personas: [],
    intents: [],
    error_message: null,
    target_turns: 3,
    current_activity: "",
    ...over,
  };
}

async function mount(
  runs: readonly Record<string, unknown>[] = [],
  locale = "de",
): Promise<Harness> {
  // jsdom meldet `navigator.language === 'en-US'`; ohne diese Zeile liefe eine
  // Prüfung auf deutschen Wortlaut gegen die englische Oberfläche (C1-d4a).
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      // ST-9: der Gold-Flow-Abschnitt verlinkt auf den Rohtext
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(EvaluationComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http
    .expectOne((r) => r.url === RUNS_URL)
    .flush({ runs: runs.map((r) => runRow(r)) });
  http
    .expectOne((r) => r.url === CONFIG_URL)
    .flush({ personas: [], intents: [] });
  http.expectOne((r) => r.url === FLOWS_URL).flush({ flows: [], count: 0 });
  await settle(h);
  return h;
}

const tabs = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]'));

describe("EvaluationComponent", () => {
  it("is what the evaluation route actually loads", async () => {
    // A view nobody can navigate to is not built. 9-5c shipped four finished
    // panels that were unreachable until the route entry landed.
    const children = routes.find((r) => r.path === "")!.children!;
    const route = children.find((r) => r.path === "evaluation")!;
    const loaded = await (route.loadComponent as () => Promise<unknown>)();
    expect(loaded).toBe(EvaluationComponent);
  });

  it("opens on the run list and loads only that panel", async () => {
    const h = await mount();
    expect(tabs(h).map((t) => t.textContent?.trim())).toEqual([
      "Läufe",
      "Trends",
      "Pattern-Nutzung",
      "Gold-Flows",
    ]);
    // Trends must not fetch before it is opened.
    h.http.verify();
    expect(h.el.querySelector("#panel-trends")!.hasAttribute("hidden")).toBe(
      true,
    );
  });

  it("beschriftet die Reiter in der aktiven Sprache", async () => {
    // Bis C1-d4b standen die drei Beschriftungen als fertige Sätze in einer
    // Modul-Konstante `TABS` — dem siebten eingefrorenen Fall dieser Art. Auf
    // Englisch blieben sie deutsch, obwohl die Seite sonst wechselte.
    const h = await mount([], "en");
    expect(tabs(h).map((t) => t.textContent?.trim())).toEqual([
      "Runs",
      "Trends",
      "Pattern usage",
      "Gold flows",
    ]);
  });

  it("opens the detail of the run the list points at, and closes it again", async () => {
    // The list has emitted `runChange` since 9-5d; until this listener existed
    // nothing happened when a row was opened.
    const h = await mount([{ id: "eval-abc" }]);
    const row = h.el.querySelector<HTMLButtonElement>("#panel-laeufe .er-row")!;
    row.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === "/studio/api/eval/runs/eval-abc")
      .flush({
        id: "eval-abc",
        created_at: "2026-07-26T10:00:00Z",
        completed_at: null,
        status: "done",
        mode: "golden",
        config_slug: "",
        personas: [],
        intents: [],
        turns_per_conv: 0,
        judge_model: "",
        simulator_model: "",
        total_turns: 0,
        avg_score: null,
        error_message: null,
        summary: {},
        conversations: [],
      });
    await settle(h);

    expect(h.el.querySelector("studio-eval-run-detail")).toBeTruthy();

    const close = Array.from(h.el.querySelectorAll("button")).find((b) =>
      (b.textContent ?? "").includes("Schließen"),
    ) as HTMLButtonElement;
    close.click();
    await settle(h);

    expect(h.el.querySelector("studio-eval-run-detail")).toBeNull();
  });

  it("bringt den Fokus beim Schließen des Details zur Zeile des Laufs zurück", async () => {
    // Das Detail steht unter der Liste; ohne Rücksprung landete man nach dem
    // Schließen irgendwo unten auf der Seite.
    const h = await mount([{ id: "eval-abc" }, { id: "eval-def" }]);
    const rows = h.el.querySelectorAll<HTMLButtonElement>("#panel-laeufe .er-row");
    rows[1].click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === "/studio/api/eval/runs/eval-def").flush({
      id: "eval-def", created_at: "2026-07-26T10:00:00Z", completed_at: null,
      status: "done", mode: "golden", engine: "", config_slug: "", personas: [],
      intents: [], turns_per_conv: 0, judge_model: "", simulator_model: "",
      total_turns: 0, avg_score: null, error_message: null, summary: {},
      conversations: [],
    });
    await settle(h);

    Array.from(h.el.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === "Schließen")!.click();
    await settle(h);

    expect(document.activeElement).toBe(
      h.el.querySelectorAll<HTMLButtonElement>("#panel-laeufe .er-row")[1]);
  });

  it("öffnet den Vergleich der Läufe, die die Liste gewählt hat (ST-7c)", async () => {
    const h = await mount([{ id: "eval-a" }, { id: "eval-b" }]);
    const boxes = h.el.querySelectorAll<HTMLInputElement>("#panel-laeufe .er-pick input");
    boxes[0].click();
    boxes[1].click();
    await h.fixture.whenStable();
    Array.from(h.el.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === "Gewählte vergleichen")!.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === "/studio/api/eval/compare");
    expect(req.request.params.get("ids")).toBe("eval-a,eval-b");
    req.flush({ engines: {}, rules: {}, currency: null, conditions: [], runs: [],
                warnings: [] });
    await settle(h);
    expect(h.el.querySelector("studio-eval-compare")).toBeTruthy();

    Array.from(h.el.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === "Vergleich schließen")!.click();
    await settle(h);
    expect(h.el.querySelector("studio-eval-compare")).toBeNull();
  });

  it("schließt das Detail eines Laufs, den die Liste gelöscht hat (Befund 2026-08-22)", async () => {
    // Gemessen auf Prod: nach dem Löschen blieb das Panel offen und zeigte nur
    // noch das rohe „run not found" mit einem Erneut-versuchen-Knopf ins Leere.
    const h = await mount([{ id: "eval-abc" }]);
    h.el.querySelector<HTMLButtonElement>("#panel-laeufe .er-row")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === "/studio/api/eval/runs/eval-abc")
      .flush({
        id: "eval-abc",
        created_at: "2026-07-26T10:00:00Z",
        completed_at: null,
        status: "done",
        mode: "golden",
        config_slug: "",
        personas: [],
        intents: [],
        turns_per_conv: 0,
        judge_model: "",
        simulator_model: "",
        total_turns: 0,
        avg_score: null,
        error_message: null,
        summary: {},
        conversations: [],
      });
    await settle(h);
    expect(h.el.querySelector("studio-eval-run-detail")).toBeTruthy();

    h.el.querySelector<HTMLButtonElement>(".er-arm")!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".er-confirm")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne(
        (r) =>
          r.url === "/studio/api/eval/runs/eval-abc" && r.method === "DELETE",
      )
      .flush({ deleted: "eval-abc" });
    await settle(h);
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [] });
    await settle(h);

    expect(h.el.querySelector("studio-eval-run-detail")).toBeNull();
  });

  it("liest das offene Detail neu, wenn die Liste seinen Lauf stoppt", async () => {
    // Ohne das stünde im Panel weiter „läuft" samt Aktivitätszeile, obwohl der
    // Lauf gestoppt ist (Review-Befund 2026-08-22). Schließen wäre falsch: ein
    // gestoppter Lauf behält seinen Teilstand und bleibt lesenswert.
    const laufend = {
      id: "eval-abc",
      status: "running",
      total_turns: 5,
      target_turns: 39,
      current_activity: "Judge bewertet 39 Züge …",
      avg_score: null,
    };
    const detail = (status: string) => ({
      id: "eval-abc",
      created_at: "2026-07-26T10:00:00Z",
      completed_at: null,
      status,
      mode: "golden",
      config_slug: "",
      personas: [],
      intents: [],
      turns_per_conv: 0,
      judge_model: "",
      simulator_model: "",
      total_turns: 5,
      avg_score: null,
      error_message: null,
      summary: { current_activity: "Judge bewertet 39 Züge …" },
      conversations: [],
    });

    const h = await mount([laufend]);
    h.el.querySelector<HTMLButtonElement>("#panel-laeufe .er-row")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === "/studio/api/eval/runs/eval-abc")
      .flush(detail("running"));
    await settle(h);
    expect(h.el.querySelector("studio-eval-run-detail")!.textContent).toContain(
      "läuft",
    );

    h.el.querySelector<HTMLButtonElement>(".er-stop")!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".er-confirm")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne(
        (r) =>
          r.url === "/studio/api/eval/runs/eval-abc/cancel" &&
          r.method === "POST",
      )
      .flush({ cancelled: "eval-abc", task_stopped: true });
    await settle(h);

    h.http
      .expectOne((r) => r.url === RUNS_URL)
      .flush({ runs: [runRow({ ...laufend, status: "cancelled" })] });
    // Das Panel liest sich selbst neu — das ist der Kern dieser Prüfung.
    h.http
      .expectOne(
        (r) => r.url === "/studio/api/eval/runs/eval-abc" && r.method === "GET",
      )
      .flush(detail("cancelled"));
    await settle(h);

    const panel = h.el.querySelector("studio-eval-run-detail")!;
    expect(panel).toBeTruthy();
    expect(panel.textContent).toContain("gestoppt");
  });

  it("puts both start forms in the same panel as the list they feed", async () => {
    // A run takes minutes and the list is its only progress display — a start
    // button on another tab would report nothing after the click.
    const h = await mount();
    const panel = h.el.querySelector("#panel-laeufe")!;
    expect(panel.querySelector("studio-eval-golden-start")).toBeTruthy();
    expect(panel.querySelector("studio-eval-generative-start")).toBeTruthy();
    expect(panel.querySelector("studio-eval-runs")).toBeTruthy();
  });

  it("zeigt die Lauf-Liste zuerst und klappt die Start-Formulare zu (Feedback 2026-08-22)", async () => {
    // Vorher standen beide Start-Panels ÜBER der Liste — aktive Läufe waren
    // erst nach langem Scrollen sichtbar.
    const h = await mount();
    const panel = h.el.querySelector("#panel-laeufe")!;
    expect(panel.children[0]?.tagName.toLowerCase()).toBe("studio-eval-runs");
    const disclosures = Array.from(
      panel.querySelectorAll<HTMLDetailsElement>("details.ev-start"),
    );
    expect(disclosures.length).toBe(2);
    for (const details of disclosures) expect(details.open).toBe(false);
    // Die Formulare bleiben MONTIERT (laden ihre Daten), nur zugeklappt.
    expect(disclosures[0].querySelector("studio-eval-golden-start")).toBeTruthy();
    expect(disclosures[1].querySelector("studio-eval-generative-start")).toBeTruthy();
  });

  it("loads the trends panel on its first visit", async () => {
    const h = await mount();
    tabs(h)[1].click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === TRENDS_URL)
      .flush({
        runs: [],
        pattern_trend: {},
        cache_hit_trend: [],
        llm_engine_match_trend: [],
        persona_correct_trend: [],
        intent_correct_trend: [],
      });
    await settle(h);
    expect(h.el.querySelector("#panel-trends")!.hasAttribute("hidden")).toBe(
      false,
    );
    expect(h.el.querySelector("#panel-laeufe")!.hasAttribute("hidden")).toBe(
      true,
    );
  });

  it("keeps a visited panel mounted so switching back does not refetch", async () => {
    const h = await mount();
    tabs(h)[1].click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === TRENDS_URL)
      .flush({
        runs: [],
        pattern_trend: {},
        cache_hit_trend: [],
        llm_engine_match_trend: [],
        persona_correct_trend: [],
        intent_correct_trend: [],
      });
    await settle(h);

    tabs(h)[0].click();
    await settle(h);
    tabs(h)[1].click();
    await settle(h);
    // Neither panel re-fetches — both are still mounted, just hidden.
    h.http.verify();
  });

  it("loads the pattern usage on its first visit", async () => {
    const h = await mount();
    tabs(h)[2].click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === "/studio/api/eval/analytics/pattern-usage")
      .flush({
        triples: [],
        by_pattern: [],
        by_intent: [],
        total: 0,
        scope: "all",
      });
    await settle(h);

    expect(h.el.querySelector("#panel-pattern")!.hasAttribute("hidden")).toBe(
      false,
    );
  });

  it("wires each panel to its tab for assistive technology", async () => {
    const h = await mount();
    for (const id of ["laeufe", "trends", "pattern", "goldflows"]) {
      const panel = h.el.querySelector(`#panel-${id}`)!;
      expect(panel.getAttribute("role")).toBe("tabpanel");
      expect(panel.getAttribute("aria-labelledby")).toBe(`tab-${id}`);
      expect(panel.getAttribute("tabindex")).toBe("0");
    }
  });

  // ── ST-9: die Gold-Flows neben den Läufen, die sie abspielen ──────────

  async function goldFlowsOeffnen(h: Harness): Promise<void> {
    tabs(h)[3].click();
    await settle(h);
    h.http.expectOne("/studio/api/config/schema/eval/gold-flows")
      .flush(AREA_SCHEMAS["eval/gold-flows"]);
    h.http.expectOne("/studio/api/config/data/eval/gold-flows")
      .flush({ area: "eval/gold-flows", data: { version: 1, flows: [] }, type: "yaml" });
    await settle(h);
  }

  it("bearbeitet die Gold-Flows im vierten Reiter (ST-9)", async () => {
    // Bis ST-9 nur als Dateiname unter „Alle Bereiche“ — neben einer Seite,
    // die genau diese Flows startet.
    const h = await mount();
    await goldFlowsOeffnen(h);
    const panel = h.el.querySelector("#panel-goldflows")!;
    expect(panel.hasAttribute("hidden")).toBe(false);
    expect(panel.querySelector("studio-area-section .cs-title")?.textContent).toContain(
      "Gold-Flows",
    );
  });

  it("liest die Flow-Liste des Starts neu, wenn man von den Gold-Flows zurückkommt", async () => {
    // Sonst stünde nach dem Speichern eines neuen Flows die alte Liste im
    // Start-Formular — auf derselben Seite.
    const h = await mount();
    await goldFlowsOeffnen(h);
    tabs(h)[0].click();
    await settle(h);
    h.http.expectOne((r) => r.url === FLOWS_URL).flush({ flows: [], count: 0 });
    await settle(h);
  });

  it("meldet ungespeicherte Änderungen der Gold-Flows", async () => {
    const h = await mount();
    await goldFlowsOeffnen(h);
    const ev = h.fixture.componentInstance;
    expect(ev.dirty()).toBe(false);
    ev.goldFlows()!.editor.setDoc({ version: 2, flows: [] });
    await settle(h);
    expect(ev.dirty()).toBe(true);
  });
});
