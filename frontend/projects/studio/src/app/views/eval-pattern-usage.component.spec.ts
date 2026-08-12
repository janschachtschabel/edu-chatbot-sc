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
import { EvalPatternUsageComponent } from "./eval-pattern-usage.component";

const USAGE_URL = "/studio/api/eval/analytics/pattern-usage";

const USAGE = {
  triples: [
    {
      pattern_id: "M04",
      intent_id: "I01",
      persona_id: "P-LEH",
      count: 12,
      avg_conf: 0.91,
    },
    {
      pattern_id: "M15",
      intent_id: "I03",
      persona_id: "P-AND",
      count: 5,
      avg_conf: 0.62,
    },
    { pattern_id: "", intent_id: "", persona_id: "", count: 2, avg_conf: null },
  ],
  by_pattern: [
    { pattern_id: "M04", count: 12 },
    { pattern_id: "M15", count: 5 },
  ],
  by_intent: [
    { intent_id: "I01", count: 12 },
    { intent_id: "I03", count: 5 },
  ],
  total: 19,
  scope: "all",
};

interface Harness {
  fixture: ComponentFixture<EvalPatternUsageComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let h: Harness;

async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(
  payload: Record<string, unknown> | null = USAGE,
  locale = "de",
): Promise<void> {
  // jsdom meldet `navigator.language === 'en-US'`; ohne die gemerkte Wahl liefe
  // die deutsche Oberfläche unter diesen Prüfungen auf Englisch.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(EvalPatternUsageComponent);
  const http = TestBed.inject(HttpTestingController);
  h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === USAGE_URL);
  if (payload === null)
    req.flush({ detail: "kaputt" }, { status: 500, statusText: "x" });
  else req.flush(payload);
  await settle();
}

const text = (): string => h.el.textContent ?? "";
const lastQuery = (): URLSearchParams =>
  new URLSearchParams(
    h.http
      .match(() => true)
      .at(-1)
      ?.request.params.toString() ?? "",
  );

describe("EvalPatternUsageComponent", () => {
  beforeEach(() => {
    h = undefined as unknown as Harness;
  });

  it("reads the whole window for every scope by default", async () => {
    await mount();
    expect(text()).toContain("19"); // total turns
    expect(text()).toContain("M04");
    expect(text()).toContain("I01");
  });

  it("feeds both distributions to the shared bar table", async () => {
    await mount();
    const captions = Array.from(h.el.querySelectorAll("caption")).map(
      (c) => c.textContent?.trim() ?? "",
    );

    // Reused rather than re-drawn: `QualityBarsComponent` already renders "a key
    // with a number" as a table with a hidden bar.
    expect(captions.some((c) => c.includes("Pattern"))).toBe(true);
    expect(captions.some((c) => c.includes("Intent"))).toBe(true);
  });

  it("re-reads when the scope changes, and sends it", async () => {
    await mount();
    const select = h.el.querySelector<HTMLSelectElement>("#epu-scope")!;
    select.value = "eval";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === USAGE_URL);
    expect(req.request.params.get("scope")).toBe("eval");
    req.flush({ ...USAGE, scope: "eval" });
    await settle();
    h.http.verify();
  });

  it("sends a since floor only once one is set", async () => {
    await mount();
    expect(lastQuery().has("since")).toBe(false);

    const field = h.el.querySelector<HTMLInputElement>("#epu-since")!;
    expect(field.type).toBe("date"); // platform native, no datepicker dependency
    field.value = "2026-07-01";
    field.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === USAGE_URL);
    expect(req.request.params.get("since")).toBe("2026-07-01");
    req.flush(USAGE);
    await settle();
  });

  it("names an unclassified triple instead of showing a blank row", async () => {
    await mount();
    // The third triple has empty ids — a blank row reads as a rendering fault.
    expect(text()).toContain("(ohne)");
  });

  it("leaves out a confidence it does not have", async () => {
    await mount();
    expect(text()).toContain("0,91");
    // `avg_conf: null` means no turn carried one, not 0.
    const cells = Array.from(h.el.querySelectorAll("tbody td")).map(
      (c) => c.textContent?.trim() ?? "",
    );
    expect(cells).toContain("–");
  });

  it("says the log is empty rather than drawing empty tables", async () => {
    await mount({
      triples: [],
      by_pattern: [],
      by_intent: [],
      total: 0,
      scope: "all",
    });

    expect(text()).toContain("Noch keine Turns");
  });

  it("shows why the numbers could not be read", async () => {
    await mount(null);
    expect(text()).toContain("kaputt");
  });

  // ── C1-d4b3 ─────────────────────────────────────────────────────────

  it("spricht auf Englisch durchgehend Englisch", async () => {
    await mount(USAGE, "en");

    expect(text()).toContain("Pattern usage"); // Überschrift, aus der Hülle
    expect(text()).toContain("Scope"); // Filter-Beschriftung
    expect(text()).toContain("eval runs only"); // Bereich aus der Konstante
    expect(text()).toContain("From date"); // Datums-Feld
    expect(text()).toContain("Turns per pattern"); // Beschriftung der Balken
    expect(text()).toContain("Avg confidence"); // Spaltenkopf
    expect(text()).toContain("(none)"); // aus der Balken-Tabelle
    // Kein deutscher Rest — der Fall, den ein Blick auf die Seite übersieht.
    expect(text()).not.toMatch(/[äöüß]/);
  });

  it("setzt die Auszeichnung als Element, nicht als sichtbaren Stern", async () => {
    await mount();

    expect(h.el.querySelector(".epu-intro code")?.textContent).toBe(
      "quality_logs",
    );
    expect(h.el.querySelector(".epu-total strong")?.textContent).toBe(
      "19 Turns",
    );
    expect(text()).not.toContain("*");
    expect(text()).not.toContain("`");
  });

  it("fügt den Summen-Satz ohne eingestreute Leerzeichen zusammen", async () => {
    // Angular behält den Leerraum innerhalb der `@`-Blöcke von `<studio-rich>`;
    // in C1-d4b2 hat genau das aus „83 %" ein „83 % " gemacht.
    await mount();
    expect(
      h.el
        .querySelector(".epu-total")
        ?.textContent?.replace(/\s+/g, " ")
        .trim(),
    ).toBe("19 Turns in 3 Kombinationen aus Pattern, Intent und Persona.");
  });

  it("trennt die Tausender auch im Summen-Satz", async () => {
    // Die Zahl wählt die Mehrzahlform, der FORMATIERTE Text füllt den
    // Platzhalter — dasselbe Muster wie `overview.snapshots`.
    await mount({ ...USAGE, total: 12345 });
    expect(h.el.querySelector(".epu-total strong")?.textContent).toBe(
      "12.345 Turns",
    );
  });

  it("zählt Turn und Kombination in der Einzahl, wenn es nur eine gibt", async () => {
    await mount({
      triples: [
        {
          pattern_id: "M04",
          intent_id: "I01",
          persona_id: "P-LEH",
          count: 1,
          avg_conf: 0.5,
        },
      ],
      by_pattern: [{ pattern_id: "M04", count: 1 }],
      by_intent: [{ intent_id: "I01", count: 1 }],
      total: 1,
      scope: "all",
    });
    expect(
      h.el
        .querySelector(".epu-total")
        ?.textContent?.replace(/\s+/g, " ")
        .trim(),
    ).toBe("1 Turn in 1 Kombination aus Pattern, Intent und Persona.");
  });
});
