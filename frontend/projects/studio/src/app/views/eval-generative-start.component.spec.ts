// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { EvalGenerativeStartComponent } from "./eval-generative-start.component";

const CONFIG_URL = "/studio/api/eval/config";
const ESTIMATE_URL = "/studio/api/eval/estimate";
const RUNS_URL = "/studio/api/eval/runs";

const CONFIG = {
  personas: [
    { id: "P-LEH", label: "Lehrkraft" },
    { id: "P-SUS", label: "Schülerin" },
  ],
  intents: [
    { id: "I01", label: "Suche" },
    { id: "I03", label: "Wissen" },
  ],
};

const ESTIMATE = {
  scenarios: 8,
  conversations: 4,
  total_turns: 20,
  chat_calls: 20,
  judge_calls: 20,
  simulator_calls: 16,
  est_usd: 0.14,
  est_usd_min: 0.08,
  est_usd_max: 0.28,
};

interface Harness {
  fixture: ComponentFixture<EvalGenerativeStartComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let h: Harness;

async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

/** jsdom meldet `navigator.language === 'en-US'`; ohne die gemerkte Wahl liefe
 *  die deutsche Oberfläche unter diesen Prüfungen auf Englisch. */
async function mount(
  config: Record<string, unknown> | null = CONFIG,
  locale = "de",
): Promise<void> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(EvalGenerativeStartComponent);
  const http = TestBed.inject(HttpTestingController);
  h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === CONFIG_URL);
  if (config === null)
    req.flush({ detail: "weg" }, { status: 503, statusText: "x" });
  else req.flush(config);
  await settle();
}

const text = (): string => h.el.textContent ?? "";
const button = (label: string): HTMLButtonElement | null =>
  (Array.from(h.el.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").includes(label),
  ) as HTMLButtonElement) ?? null;
const checkbox = (id: string): HTMLInputElement =>
  h.el.querySelector<HTMLInputElement>(`#egs-${id}`)!;

/** Click "Kosten prüfen" and answer the estimate request. */
async function check(
  payload: Record<string, unknown> | null = ESTIMATE,
): Promise<Record<string, unknown>> {
  button("Kosten prüfen")!.click();
  await h.fixture.whenStable();
  const req = h.http.expectOne((r) => r.url === ESTIMATE_URL);
  const sent = req.request.body as Record<string, unknown>;
  if (payload === null)
    req.flush({ detail: "kaputt" }, { status: 500, statusText: "x" });
  else req.flush(payload);
  await settle();
  return sent;
}

describe("EvalGenerativeStartComponent", () => {
  beforeEach(() => {
    h = undefined as unknown as Harness;
  });

  it("offers every configured persona and intent", async () => {
    await mount();
    expect(checkbox("persona-P-LEH")).toBeTruthy();
    expect(checkbox("intent-I03")).toBeTruthy();
    expect(text()).toContain("Lehrkraft");
    // Empty means all — a guess the user should not have to make.
    expect(text()).toContain("Nichts ausgewählt = alle");
  });

  it("says how many combinations the current selection produces", async () => {
    await mount();
    expect(text()).toContain("4 Kombinationen"); // 2 personas × 2 intents

    checkbox("persona-P-LEH").click();
    await h.fixture.whenStable();
    expect(text()).toContain("2 Kombinationen"); // 1 × 2
  });

  it("shows the config load failure instead of an empty form", async () => {
    await mount(null);
    expect(text()).toContain("weg");
    expect(button("Kosten prüfen")!.disabled).toBe(true);
  });

  it("says why nothing can run when the config has no combinations", async () => {
    await mount({
      personas: [{ id: "P-LEH", label: "Lehrkraft" }],
      intents: [],
    });

    expect(text()).toContain("keine Personas oder keine Intents");
    expect(button("Kosten prüfen")!.disabled).toBe(true);
  });

  it("estimates with the values on screen, not the defaults", async () => {
    await mount();
    checkbox("persona-P-SUS").click();
    h.el.querySelector<HTMLInputElement>("#egs-mode-scenarios")!.click();
    await h.fixture.whenStable();

    const sent = await check();

    expect(sent).toEqual({
      mode: "scenarios",
      persona_ids: ["P-SUS"],
      intent_ids: [], // nothing chosen = every intent
      scenarios_per_combo: 2,
      turns_per_conv: 3,
    });
  });

  it("shows the cost band and that it is an estimate", async () => {
    await mount();
    await check();

    expect(text()).toContain("20 Chat-Aufrufe");
    expect(text()).toContain("20 Judge-Aufrufe");
    expect(text()).toContain("0,08"); // band floor, de-DE
    expect(text()).toContain("0,28"); // band ceiling
    expect(text()).toContain("Schätzung");
  });

  it("spends no money on the first click — the run needs a second yes", async () => {
    await mount();
    await check();

    // The estimate is in, nothing has started.
    h.http.verify();
    expect(button("Ja, Lauf starten")).toBeTruthy();
  });

  it("starts the run with the checked values and reports it", async () => {
    await mount();
    const started: string[] = [];
    h.fixture.componentInstance.started.subscribe((id: string) =>
      started.push(id),
    );
    const estimated = await check();

    button("Ja, Lauf starten")!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne(
      (r) => r.url === RUNS_URL && r.method === "POST",
    );
    expect(req.request.body).toEqual({ ...estimated, config_slug: "" });
    req.flush({ run_id: "eval-abc", status: "running", warnings: [] });
    await settle();

    expect(started).toEqual(["eval-abc"]);
    expect(text()).toContain("eval-abc");
    // The confirmation is spent — a second run needs a fresh estimate.
    expect(button("Ja, Lauf starten")).toBeNull();
  });

  it("surfaces warnings the backend attached to the start", async () => {
    await mount();
    await check();
    button("Ja, Lauf starten")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === RUNS_URL && r.method === "POST")
      .flush({
        run_id: "eval-abc",
        status: "running",
        warnings: ["Unknown persona IDs ignored: ['P-XX']"],
      });
    await settle();

    expect(text()).toContain("P-XX");
  });

  it("keeps the form and shows why a start failed", async () => {
    await mount();
    checkbox("persona-P-SUS").click();
    await h.fixture.whenStable();
    await check();

    button("Ja, Lauf starten")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === RUNS_URL && r.method === "POST")
      .flush(
        { detail: "Es läuft bereits ein Eval-Lauf." },
        { status: 409, statusText: "x" },
      );
    await settle();

    expect(text()).toContain("Es läuft bereits ein Eval-Lauf.");
    expect(checkbox("persona-P-SUS").checked).toBe(true); // selection preserved
  });

  it("names a failed estimate instead of pretending the run is free", async () => {
    await mount();
    await check(null);

    expect(text()).toContain("kaputt");
    // Still startable: the operator, not the estimate, authorises the spend —
    // but the confirmation must not imply a price it does not have.
    expect(button("Ja, Lauf starten")!.disabled).toBe(false);
    expect(text()).toContain("ohne Kostenschätzung");
  });

  it("blocks the start while another run is in flight", async () => {
    await mount();
    h.fixture.componentRef.setInput("busy", true);
    await h.fixture.whenStable();

    expect(button("Kosten prüfen")!.disabled).toBe(true);
    expect(text()).toContain("Es läuft schon ein Lauf");
  });

  it("holds the numeric fields inside the range the backend accepts", async () => {
    await mount();
    const field = h.el.querySelector<HTMLInputElement>("#egs-scenarios")!;
    expect(field.min).toBe("1");
    expect(field.max).toBe("10");

    field.value = "99";
    field.dispatchEvent(new Event("input"));
    await h.fixture.whenStable();
    // Clamped locally: 99 would come back as a 422 with no field to point at.
    expect(await check()).toMatchObject({ scenarios_per_combo: 10 });
  });

  /**
   * The eighth confirmation of B6 needed nothing: A3 already put the prose in a
   * live region, and deliberately left the buttons OUT of it — their labels flip
   * to "Startet …" and would re-announce the whole cost paragraph. `polite`
   * rather than `role="alert"` here because this text is a cost estimate that
   * arrives from the server, not an answer to a click.
   */
  it("keeps the cost prose live and the buttons out of it", async () => {
    await mount();
    await check();
    const live = h.el.querySelector(".egs-confirm [aria-live]");
    expect(live?.getAttribute("aria-live")).toBe("polite");
    expect(live?.textContent).toContain("Chat-Aufrufe");
    expect(live?.querySelector("button")).toBeNull();
  });

  // ── C1-d4c ──────────────────────────────────────────────────────────
  //
  // Vier Anzahlen in einem Satz, jede mit eigener Mehrzahl. Eine
  // Schlüssel-Matrix aus 2⁴ Sätzen wäre die falsche Antwort — die vier
  // Wortgruppen entstehen einzeln und werden eingesetzt.
  it("setzt jede der vier Anzahlen der Kostenzeile in ihre eigene Mehrzahl", async () => {
    await mount({
      personas: [{ id: "P-LEH", label: "Lehrkraft" }],
      intents: [{ id: "I01", label: "Suche" }],
    });
    await check({
      scenarios: 1,
      conversations: 1,
      total_turns: 1,
      chat_calls: 1,
      judge_calls: 1,
      simulator_calls: 1,
      est_usd: 0.01,
      est_usd_min: 0.01,
      est_usd_max: 0.02,
    });
    expect(
      h.el.querySelector(".egs-cost")!.textContent!.replace(/\s+/g, " ").trim(),
    ).toBe(
      "Dieser Lauf feuert 1 Chat-Aufruf durch die echte Pipeline, " +
        "1 Judge-Aufruf und 1 Simulator-Aufruf — 1 bewerteter Turn.",
    );
  });

  it("zählt auch die Kombinationen in der Mehrzahl der Sprache", async () => {
    await mount({
      personas: [{ id: "P-LEH", label: "Lehrkraft" }],
      intents: [{ id: "I01", label: "Suche" }],
    });
    expect(
      h.el
        .querySelector(".egs-combos")!
        .textContent!.replace(/\s+/g, " ")
        .trim(),
    ).toBe("Auswahl ergibt 1 Kombination.");
  });

  it("spricht das ganze Panel in der aktiven Sprache", async () => {
    await mount(CONFIG, "en");
    expect(text()).toContain("Start generative run");
    expect(text()).toContain("4 combinations");
    expect(text()).toContain("Nothing selected = all.");
    expect(button("Check cost")).toBeTruthy();
    expect(text()).not.toMatch(/Kombinationen|Nichts ausgewählt/);
  });
});
