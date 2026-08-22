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
  total: 19,
  scope: "all",
};

/** Muster UND Maschinen-Marker gemischt — wie die echten quality_logs seit dem
 *  Agent-/Hybrid-Modus (Feedback 2026-08-22). */
const MIXED = {
  triples: [
    { pattern_id: "M06", intent_id: "I03", persona_id: "P-LEH", count: 10, avg_conf: 0.9 },
    { pattern_id: "M06", intent_id: "I03", persona_id: "P-AND", count: 4, avg_conf: 0.8 },
    { pattern_id: "AGENT", intent_id: "I01", persona_id: "P-AND", count: 7, avg_conf: 0.1 },
    { pattern_id: "HYBRID", intent_id: "I03", persona_id: "P-LEH", count: 3, avg_conf: null },
  ],
  total: 24,
  scope: "all",
};

/** Randwerte, wie die SQL sie wirklich liefern kann (Review-Runde 3):
 *  NULL-Kennungen aus dem GROUP BY über nullable Spalten und ein Wert, der
 *  nur wie ein Maschinen-Marker ANFÄNGT. */
const EDGE = {
  triples: [
    { pattern_id: "M06", intent_id: "I03", persona_id: "P-LEH", count: 5, avg_conf: 0.9 },
    { pattern_id: "AGENTUR", intent_id: "I01", persona_id: "P-AND", count: 3, avg_conf: null },
    { pattern_id: null, intent_id: null, persona_id: null, count: 2, avg_conf: null },
  ],
  total: 10,
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

  it("trennt die Betriebsarten: der Umschalter filtert AGENT/HYBRID aus den Mustern (Feedback 2026-08-22)", async () => {
    // AGENT/HYBRID sind keine Muster, sondern Maschinen-Marker aus den
    // quality_logs — zwischen M01–M20 einsortiert verfälschten sie das Bild.
    await mount(MIXED);
    expect(text()).toContain("AGENT");

    const select = h.el.querySelector<HTMLSelectElement>("#epu-engine")!;
    select.value = "muster";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();
    expect(text()).toContain("M06");
    expect(text()).not.toContain("AGENT");
    expect(text()).not.toContain("HYBRID");
    expect(text()).toContain("14"); // Summe nur der Muster-Turns (10 + 4)

    select.value = "agent";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();
    expect(text()).toContain("AGENT");
    expect(text()).not.toContain("M06");
    // Client-seitiger Filter — KEIN neuer Request.
    h.http.verify();
  });

  it("zeigt die Pattern-x-Persona-Matrix aus den Kombinationen (ALT-Auswertung)", async () => {
    await mount(MIXED);
    const matrix = h.el.querySelector(".epu-matrix");
    expect(matrix).toBeTruthy();
    const head = matrix!.querySelector("thead")?.textContent ?? "";
    expect(head).toContain("P-LEH");
    expect(head).toContain("P-AND");
    const rows = Array.from(matrix!.querySelectorAll("tbody tr")).map(
      (r) => r.textContent ?? "",
    );
    const m06 = rows.find((r) => r.includes("M06"))!;
    expect(m06).toContain("10"); // P-LEH-Zelle
    expect(m06).toContain("4"); // P-AND-Zelle
    expect(m06).toContain("14"); // Zeilensumme
  });

  it("Betriebsart exakt: „AGENTUR“ ist kein Agent, NULL-Kennungen laufen unter „alle“ als „(ohne)“ (Review-Runde 3)", async () => {
    await mount(EDGE);
    // NULL-Kennung erscheint unter „alle" beschriftet, nicht als leere Zelle.
    expect(text()).toContain("(ohne)");
    expect(text()).toContain("AGENTUR");

    const select = h.el.querySelector<HTMLSelectElement>("#epu-engine")!;
    select.value = "agent";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();
    // Nur der EXAKTE Kopf-Token „AGENT" zählt als Agent-Schleife — ein
    // Präfix-Vergleich hätte „AGENTUR" hier einsortiert.
    expect(text()).not.toContain("AGENTUR");
    expect(text()).toContain("Keine Turns dieser Betriebsart");

    select.value = "muster";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();
    expect(text()).toContain("M06");
    expect(text()).not.toContain("(ohne)"); // NULL-Zeile ist kein Muster
    h.http.verify();
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
    // Platzhalter — dasselbe Muster wie `overview.snapshots`. Seit dem
    // Betriebsart-Filter (2026-08-22) summiert die Zeile die KOMBINATIONEN
    // statt das Server-`total` — die Zahl muss also in den Triples stehen.
    await mount({
      ...USAGE,
      triples: [
        { ...USAGE.triples[0], count: 12338 },
        USAGE.triples[1],
        USAGE.triples[2],
      ],
    });
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
