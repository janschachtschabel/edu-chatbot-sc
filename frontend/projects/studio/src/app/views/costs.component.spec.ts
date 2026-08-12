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
import { CostsComponent, dayEnd, dayStart, isoDay } from "./costs.component";

const URL = "/studio/api/usage/period";

/** Eine gepflegte Preistafel, zwei Modelle, eine Sitzungsliste. */
const REPORT = {
  empty: false,
  calls: 7,
  prompt_tokens: 1_234_567,
  cached_tokens: 400_000,
  completion_tokens: 89_000,
  reasoning_tokens: 12_000,
  currency: "EUR",
  amount: "4.92",
  price_unavailable: [] as string[],
  models: [
    {
      model: "gpt-5.4-mini",
      calls: 5,
      prompt_tokens: 1_000_000,
      cached_tokens: 400_000,
      completion_tokens: 80_000,
      reasoning_tokens: 12_000,
      amount: "4.50",
    },
    {
      model: "gpt-4o-mini",
      calls: 2,
      prompt_tokens: 234_567,
      cached_tokens: 0,
      completion_tokens: 9_000,
      reasoning_tokens: 0,
      amount: "0.42",
    },
  ],
  sessions: [
    {
      session_id: "bb-teuer",
      calls: 4,
      prompt_tokens: 900_000,
      cached_tokens: 0,
      completion_tokens: 50_000,
      reasoning_tokens: 0,
      amount: "3.10",
      price_unavailable: [] as string[],
    },
  ],
};

const LEER = {
  empty: true,
  calls: 0,
  prompt_tokens: 0,
  cached_tokens: 0,
  completion_tokens: 0,
  reasoning_tokens: 0,
  currency: "EUR",
  amount: null,
  price_unavailable: [] as string[],
  models: [],
  sessions: [],
};

interface Harness {
  fixture: ComponentFixture<CostsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
  /** Die Parameter der zuletzt abgesetzten Anfrage — nach `flush` ist sie aus
   *  der Warteschlange verschwunden, also beim Abfangen gemerkt. */
  query: URLSearchParams;
}

let h: Harness;

async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(
  payload: Record<string, unknown> | null = REPORT,
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
  const fixture = TestBed.createComponent(CostsComponent);
  const http = TestBed.inject(HttpTestingController);
  h = {
    fixture,
    el: fixture.nativeElement as HTMLElement,
    http,
    query: new URLSearchParams(),
  };
  await fixture.whenStable();
  await answer(payload);
}

/** Die offene Anfrage abfangen, ihre Parameter merken, sie beantworten. */
async function answer(payload: Record<string, unknown> | null): Promise<void> {
  const req = h.http.expectOne((r) => r.url === URL);
  h.query = new URLSearchParams(req.request.params.toString());
  if (payload === null)
    req.flush({ detail: "Datenbank weg" }, { status: 500, statusText: "x" });
  else req.flush(payload);
  await settle();
}

const text = (): string => h.el.textContent ?? "";

// ── Die reinen Helfer ───────────────────────────────────────────────────

describe("Tagesgrenzen", () => {
  it("macht aus einem Zeitpunkt den Tag der Bedienung, nicht den UTC-Tag", () => {
    // 22:30 UTC ist in Berlin schon der Folgetag. Läse der Helfer den UTC-Tag,
    // stünde zwischen 00:00 und 02:00 Ortszeit im Feld „Bis" gestern.
    const moment = Date.UTC(2026, 7, 11, 22, 30);
    const lokal = new Date(moment);
    const erwartet = [
      lokal.getFullYear(),
      String(lokal.getMonth() + 1).padStart(2, "0"),
      String(lokal.getDate()).padStart(2, "0"),
    ].join("-");

    expect(isoDay(moment)).toBe(erwartet);
  });

  it("legt Anfang und Ende auf den Tag der Bedienung, nicht auf den UTC-Tag", () => {
    // Der Grund für dieses Paar: der Server liest ein blosses Datum als
    // Mitternacht. „bis heute" verlöre sonst den ganzen heutigen Tag — stumm,
    // denn eine kleinere Summe sieht aus wie eine kleinere Summe.
    //
    // Dieselbe Falle noch einmal, eine Ebene tiefer: hängt man ein „Z" an, ist
    // die Grenze um den Zonen-Versatz verschoben. In Berlin (+02:00) fiele ein
    // Zug um 00:30 Ortszeit aus dem eigenen Tag heraus, und das Fenster reichte
    // zwei Stunden in den Folgetag hinein. Deshalb wird gegen die ORTS-Getter
    // geprüft: die Zusicherung gilt in jeder Zeitzone.
    const start = new Date(dayStart("2026-08-11"));
    const ende = new Date(dayEnd("2026-08-11"));

    expect([start.getDate(), start.getHours(), start.getMinutes()]).toEqual([
      11, 0, 0,
    ]);
    expect([ende.getDate(), ende.getHours(), ende.getMinutes()]).toEqual([
      11, 23, 59,
    ]);
    expect(ende.getSeconds()).toBe(59);
    expect(ende.getMilliseconds()).toBe(999);
  });

  it("gibt Unlesbares unverändert zurück, statt zu werfen", () => {
    // `toISOString()` wirft bei einem ungültigen Datum einen `RangeError` —
    // aus der Ansicht heraus wäre das eine leere Seite. So weist der Server
    // den Parameter mit 422 ab und nennt ihn.
    expect(dayStart("kein Datum")).toBe("kein Datum");
    expect(dayEnd("")).toBe("");
  });
});

// ── Zeitraum ────────────────────────────────────────────────────────────

describe("Kostenschau — Zeitraum", () => {
  beforeEach(async () => {
    await mount();
  });

  it("macht mit dem zurückliegenden Monat auf und fragt sofort", () => {
    // Gegen die ORTS-Getter, nicht gegen eine UTC-Schreibweise: die Grenzen
    // sind Mitternacht und der letzte Augenblick des Tages BEI DER BEDIENUNG.
    const von = new Date(h.query.get("from")!);
    const bis = new Date(h.query.get("to")!);
    expect([von.getHours(), von.getMinutes(), von.getSeconds()]).toEqual([
      0, 0, 0,
    ]);
    expect([bis.getHours(), bis.getMinutes(), bis.getSeconds()]).toEqual([
      23, 59, 59,
    ]);

    const tage = (bis.getTime() - von.getTime()) / 86_400_000;
    expect(tage).toBeGreaterThan(29);
    expect(tage).toBeLessThan(31);
  });

  it("fragt beim Ändern einer Grenze neu", async () => {
    const feld = h.el.querySelector<HTMLInputElement>("#cst-from")!;
    feld.value = "2026-01-01";
    feld.dispatchEvent(new Event("change"));
    await settle();

    await answer(REPORT);
    // Bewusst das Datum über den Jahreswechsel: dort steht Berlin auf +01:00,
    // im August auf +02:00. Ein festgeschriebenes „Z" wäre also nicht einmal
    // um einen KONSTANTEN Betrag falsch, sondern je nach Jahreszeit anders.
    const von = new Date(h.query.get("from")!);
    expect([von.getFullYear(), von.getMonth(), von.getDate()]).toEqual([
      2026, 0, 1,
    ]);
    expect([von.getHours(), von.getMinutes()]).toEqual([0, 0]);
  });

  it("fragt gar nicht erst, wenn eine Grenze geleert wurde", async () => {
    const feld = h.el.querySelector<HTMLInputElement>("#cst-to")!;
    feld.value = "";
    feld.dispatchEvent(new Event("change"));
    await settle();

    // Kein Abruf: daraus entstünde eine Fehlermeldung über einen Tippfehler,
    // den die Bedienung selbst sieht.
    h.http.expectNone((r) => r.url === URL);
    const knopf = h.el.querySelector<HTMLButtonElement>(".cst-btn")!;
    expect(knopf.disabled).toBe(true);
  });
});

// ── Zahlen ──────────────────────────────────────────────────────────────

describe("Kostenschau — Zahlen", () => {
  it("zeigt den Betrag in der Typografie der Oberfläche", async () => {
    await mount();
    expect(h.el.querySelector(".cst-amount-value")?.textContent?.trim()).toBe(
      "4,92 €",
    );
  });

  it("trennt Tausender im Summenband", async () => {
    await mount();
    const band = h.el.querySelector(".cst-band")?.textContent ?? "";
    expect(band).toContain("1.234.567");
    expect(band).toContain("400.000");
    expect(band).toContain("89.000");
    expect(band).toContain("12.000");
  });

  it("sagt am Band, dass Cache und Reasoning schon enthalten sind", async () => {
    await mount();
    // Die häufigste Falle der ganzen Rechnung: wer die vier Zahlen addiert,
    // zählt Cache und Reasoning doppelt.
    const band = h.el.querySelector(".cst-band")?.textContent ?? "";
    expect(band).toContain("davon Cache");
    expect(band).toContain("davon Reasoning");
  });

  it("führt beide Tabellen mit ihren Zeilen", async () => {
    await mount();
    const kopfzeilen = Array.from(h.el.querySelectorAll("tbody th"), (el) =>
      el.textContent?.trim(),
    );
    expect(kopfzeilen).toEqual(["gpt-5.4-mini", "gpt-4o-mini", "bb-teuer"]);
  });

  it("lässt die Sitzungstabelle weg, wenn es keine gibt", async () => {
    await mount({ ...REPORT, sessions: [] });
    expect(text()).not.toContain("Teuerste Sitzungen");
  });
});

// ── Betrag und Lücke — die Auflage aus K4 ───────────────────────────────

describe("Kostenschau — Teilsumme", () => {
  it("nennt neben dem Betrag die Modelle ohne Preis", async () => {
    // Ohne diesen Satz läse sich eine Teilsumme als Gesamtsumme, und zwar umso
    // überzeugender, je gepflegter die Tafel wirkt.
    await mount({ ...REPORT, price_unavailable: ["whisper-1", "tts-1"] });

    const hinweis = h.el.querySelector(".cst-amount-note")?.textContent ?? "";
    expect(hinweis).toContain("Teilsumme");
    expect(hinweis).toContain("whisper-1");
    expect(hinweis).toContain("tts-1");
  });

  it("zeigt ohne jeden Preis einen Strich und seinen Grund — keine Null", async () => {
    await mount({
      ...REPORT,
      amount: null,
      price_unavailable: ["gpt-5.4-mini"],
      models: [{ ...REPORT.models[0], amount: null }],
      sessions: [],
    });

    expect(h.el.querySelector(".cst-amount-value")?.textContent?.trim()).toBe(
      "—",
    );
    expect(text()).toContain("Für kein Modell ist ein Preis gepflegt.");
    expect(text()).not.toContain("0,00");
  });

  it("unterscheidet eine kaputte Preistafel von einer ungepflegten", async () => {
    // Beide enden ohne Betrag. Sähen sie gleich aus, pflegte die Redaktion
    // nach einem YAML-Tippfehler nach und wunderte sich — der Grund stünde
    // nur im Server-Log.
    await mount({
      ...REPORT,
      amount: null,
      price_config_broken: true,
      price_unavailable: ["gpt-5.4-mini"],
      models: [{ ...REPORT.models[0], amount: null }],
      sessions: [],
    });

    expect(text()).toContain("nicht lesbar");
    expect(text()).not.toContain("Für kein Modell ist ein Preis gepflegt.");
  });

  it("schreibt in eine Zeile ohne Preis den Grund statt einer leeren Zelle", async () => {
    await mount({
      ...REPORT,
      amount: "4.50",
      price_unavailable: ["gpt-4o-mini"],
      models: [REPORT.models[0], { ...REPORT.models[1], amount: null }],
      sessions: [],
    });
    expect(text()).toContain("kein Preis");
  });

  it("sagt bei der Sitzungsliste, wonach sie ohne Preise ordnet", async () => {
    await mount({
      ...REPORT,
      amount: null,
      price_unavailable: ["gpt-5.4-mini"],
      sessions: [
        {
          ...REPORT.sessions[0],
          amount: null,
          price_unavailable: ["gpt-5.4-mini"],
        },
      ],
    });
    expect(text()).toContain("nach Token geordnet");
  });
});

// ── Zustände ────────────────────────────────────────────────────────────

describe("Kostenschau — Zustände", () => {
  it("sagt bei leerem Zeitraum, was hier stünde", async () => {
    await mount(LEER);
    expect(text()).toContain("Zahlen entstehen mit dem ersten Chat-Zug");
    expect(h.el.querySelector(".cst-band")).toBeNull();
  });

  it("zeigt den Satz des Endpunkts, nicht einen eigenen", async () => {
    // Vertauschte Grenzen weist der Server mit 422 und einem übersetzten Satz
    // ab (C1-e). Die Ansicht wiederholt die Regel nicht — sie zeigt die Absage.
    await mount(null);
    expect(text()).toContain("Datenbank weg");
  });

  it("sagt einen neuen Betrag an, statt ihn nur zu zeigen", async () => {
    // Beim Wechsel des Zeitraums ändert sich genau diese Zahl. Am Bildschirm
    // sieht man das; ohne ihn hörte man ohne Live-Bereich gar nichts.
    await mount();
    const block = h.el.querySelector(".cst-amount")!;
    expect(block.getAttribute("aria-live")).toBe("polite");
    // Ohne `aria-atomic` käme „4,92 €" ohne das Wort „Betrag" davor.
    expect(block.getAttribute("aria-atomic")).toBe("true");
  });

  it("spricht Englisch, wenn das Studio Englisch spricht", async () => {
    await mount(REPORT, "en");
    expect(text()).toContain("of which cached");
    expect(text()).toContain("Most expensive sessions");
    expect(h.el.querySelector(".cst-amount-value")?.textContent?.trim()).toBe(
      "€4.92",
    );
  });
});
