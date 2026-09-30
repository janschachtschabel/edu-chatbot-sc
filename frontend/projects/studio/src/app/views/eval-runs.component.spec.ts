// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import {
  Component,
  provideZonelessChangeDetection,
} from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { EvalRunsComponent } from "./eval-runs.component";

const RUNS_URL = "/studio/api/eval/runs";
const QLOGS_URL = "/studio/api/eval/quality-logs";

/** Mirrors the component's own constant; a test may not import a private. */
const POLL_MS = 3000;

function run(
  id: string,
  over: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id,
    created_at: "2026-07-24T10:00:00Z",
    completed_at: null,
    status: "done",
    mode: "golden",
    config_slug: "wlo/v1",
    total_turns: 12,
    avg_score: 0.83,
    personas: ["P01"],
    intents: ["I02"],
    error_message: null,
    target_turns: 12,
    current_activity: "Fertig",
    ...over,
  };
}

const RUNNING = run("r-live", {
  status: "running",
  total_turns: 4,
  target_turns: 10,
  current_activity: "Gold-Flow 2 von 5",
  avg_score: null,
});

@Component({
  selector: "studio-eval-runs-host",
  imports: [EvalRunsComponent],
  template:
    '<studio-eval-runs (runChange)="opened = $event" (deleted)="lastDeleted = $event"' +
    ' (stopped)="lastStopped = $event" (compare)="compared = $event" />',
})
class HostComponent {
  opened = "";
  compared: readonly string[] = [];
  /** `null` = Sammel-Löschung (Treffer unbekannt); `undefined` = nie gefeuert. */
  lastDeleted: string | null | undefined;
  lastStopped = "";
}

interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
  await h.fixture.whenStable();
}

async function mount(
  runs: Record<string, unknown>[] = [run("r1")],
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
    ],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne((r) => r.url === RUNS_URL).flush({ runs });
  await settle(h);
  return h;
}

const rows = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>(".er-row"));

describe("EvalRunsComponent", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads the newest runs", async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
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
    await fixture.whenStable();
    const req = http.expectOne((r) => r.url === RUNS_URL);
    expect(req.request.params.get("limit")).toBe("50");
    req.flush({ runs: [run("r1")] });
  });

  it("shows how far a running run has got, against its target", async () => {
    const h = await mount([RUNNING]);
    const row = rows(h)[0];
    expect(row.textContent).toContain("4");
    expect(row.textContent).toContain("10");
    expect(row.textContent).toContain("Gold-Flow 2 von 5");
  });

  it("re-reads while a run is in flight and stops once it is done", async () => {
    const h = await mount([RUNNING]);

    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http
      .expectOne((r) => r.url === RUNS_URL)
      .flush({ runs: [run("r-live")] });
    await settle(h);

    // Now nothing is running, so no further poll may be scheduled.
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it("pollt nach dem Verlassen der Ansicht nicht weiter (Audit 2026-09-29)", async () => {
    // Zerstört während eine Abfrage läuft: `stopPolling()` findet dann keinen
    // Timer, und die späte Antwort bewaffnete einen neuen, den niemand mehr
    // löscht — ein Zombie-GET alle drei Sekunden je unglücklicher Navigation.
    const h = await mount([RUNNING]);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    const imFlug = h.http.expectOne((r) => r.url === RUNS_URL);

    h.fixture.destroy();
    imFlug.flush({ runs: [RUNNING] });
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);

    h.http.expectNone((r) => r.url === RUNS_URL);
  });

  it("nennt je Zeile die Maschine, die den Lauf beantwortet hat (ST-7a)", async () => {
    const h = await mount([run("r1", { engine: "agent" }), run("r2", { engine: "" })]);
    expect(rows(h)[0].textContent).toContain("Agent-Schleife");
    // Vor ST-7 mit Server-Vorgabe gestartet: nicht geraten, sondern gesagt.
    expect(rows(h)[1].textContent).toContain("Maschine unbekannt");
  });

  it("filtert nach Maschine auf dem Server, auch beim Nachladen (ST-7a)", async () => {
    const h = await mount([RUNNING]);
    const select = h.el.querySelector<HTMLSelectElement>("#er-engine")!;
    select.value = "agent";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === RUNS_URL);
    expect(req.request.params.get("engine")).toBe("agent");
    req.flush({ runs: [{ ...RUNNING, engine: "agent" }] });
    await settle(h);

    // Der laufende Lauf lässt die Liste weiter nachladen — mit demselben Filter,
    // sonst stünde nach drei Sekunden wieder alles da.
    await vi.advanceTimersByTimeAsync(POLL_MS);
    const poll = h.http.expectOne((r) => r.url === RUNS_URL);
    expect(poll.request.params.get("engine")).toBe("agent");
    poll.flush({ runs: [run("r-live", { engine: "agent" })] });
    await settle(h);
  });

  it("sagt beim Sammel-Löschen, dass der Maschinen-Filter dafür nicht gilt (ST-7a)", async () => {
    const h = await mount([run("r1", { engine: "agent" })]);
    const select = h.el.querySelector<HTMLSelectElement>("#er-engine")!;
    select.value = "agent";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run("r1", { engine: "agent" })] });
    await settle(h);

    h.el.querySelector<HTMLButtonElement>(".er-bulk")!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".er-danger")!.textContent).toContain(
      "Der Maschinen-Filter gilt beim Löschen nicht",
    );
  });

  it("bietet fertige Läufe zum Vergleich an, laufende nicht (ST-7c)", async () => {
    const h = await mount([run("r1"), RUNNING]);
    const boxes = h.el.querySelectorAll<HTMLInputElement>(".er-pick input[type=checkbox]");
    expect(boxes).toHaveLength(1);
    // Das sichtbare Wort steht am Anfang des Namens (WCAG 2.5.3).
    expect(boxes[0].getAttribute("aria-label")).toBe("Vergleichen — Lauf r1");
  });

  it("vergleicht erst ab zwei Läufen und reicht die Auswahl weiter (ST-7c)", async () => {
    const h = await mount([run("r1"), run("r2"), run("r3")]);
    const box = (i: number) => h.el.querySelectorAll<HTMLInputElement>(".er-pick input")[i];
    const start = () => Array.from(h.el.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === "Gewählte vergleichen")!;

    box(0).click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".cb")!.textContent).toContain("1 Lauf zum Vergleich gewählt");
    expect(start().disabled).toBe(true);
    expect(h.el.querySelector(".cb")!.textContent).toContain("mindestens zwei Läufe");

    box(2).click();
    await h.fixture.whenStable();
    expect(start().disabled).toBe(false);
    start().click();
    expect(h.fixture.componentInstance.compared).toEqual(["r1", "r3"]);
  });

  it("behält die Auswahl über einen Wechsel des Maschinen-Filters (ST-7c)", async () => {
    // So vergleicht man: Muster-Läufe ankreuzen, Filter wechseln, Agent-Läufe ankreuzen.
    const h = await mount([run("r1", { engine: "pattern" })]);
    h.el.querySelector<HTMLInputElement>(".er-pick input")!.click();
    await h.fixture.whenStable();
    const select = h.el.querySelector<HTMLSelectElement>("#er-engine")!;
    select.value = "agent";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run("r2", { engine: "agent" })] });
    await settle(h);
    h.el.querySelector<HTMLInputElement>(".er-pick input")!.click();
    await h.fixture.whenStable();

    expect(h.el.querySelector(".cb")!.textContent).toContain("2 Läufe zum Vergleich gewählt");
  });

  it("hebt die Auswahl auf Zuruf auf", async () => {
    const h = await mount([run("r1"), run("r2")]);
    h.el.querySelectorAll<HTMLInputElement>(".er-pick input")[0].click();
    await h.fixture.whenStable();
    Array.from(h.el.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === "Auswahl aufheben")!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".cb")).toBeNull();
    expect(h.el.querySelector<HTMLInputElement>(".er-pick input")!.checked).toBe(false);
  });

  it("does not poll at all when no run is in flight", async () => {
    const h = await mount([run("r1")]);
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it("shows a failed poll and keeps the last good list", async () => {
    // ALT swallowed poll errors, so a dead backend kept claiming "läuft".
    const h = await mount([RUNNING]);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http
      .expectOne((r) => r.url === RUNS_URL)
      .flush({ detail: "Datenbank weg." }, { status: 503, statusText: "x" });
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain(
      "Datenbank weg.",
    );
    expect(rows(h)).toHaveLength(1);
  });

  it("says why a run failed, in the row", async () => {
    // "fehlgeschlagen" alone does not tell anyone what to do next. This message
    // is verbatim from the backend's stale-run sweep (`eval_service.py`, the
    // `UPDATE eval_runs SET status='failed'` on start), and a reaped run leaves
    // no other trace — the row is the only place it surfaces.
    const h = await mount([
      run("r-gen", {
        status: "failed",
        mode: "both",
        error_message: "stale running-Run beim Start-Check abgeräumt",
      }),
    ]);
    expect(rows(h)[0].textContent).toContain("fehlgeschlagen");
    expect(h.el.textContent).toContain("beim Start-Check abgeräumt");
  });

  it("opens a run as a real button", async () => {
    const h = await mount([run("r1")]);
    expect(rows(h)[0].tagName).toBe("BUTTON");
    rows(h)[0].click();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.opened).toBe("r1");
  });

  it("asks before deleting one run, then deletes it", async () => {
    const h = await mount([run("r1"), run("r2")]);
    h.el.querySelector<HTMLButtonElement>(".er-arm")!.click();
    await h.fixture.whenStable();
    h.http.verify(); // arming deletes nothing

    h.el.querySelector<HTMLButtonElement>(".er-confirm")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === `${RUNS_URL}/r1` && r.method === "DELETE")
      .flush({ deleted: "r1" });
    await settle(h);

    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run("r2")] });
    await settle(h);
    expect(rows(h)).toHaveLength(1);
    // Der Besitzer des Detail-Panels erfährt die Löschung — sonst zeigte ein
    // offenes Panel des Laufs nur noch „run not found" (Befund 2026-08-22).
    expect(h.fixture.componentInstance.lastDeleted).toBe("r1");
  });

  it("refuses to offer a delete for a run that is still going", async () => {
    // The endpoint answers 409 for a running run; an enabled button would make
    // the error message the way to find that out.
    const h = await mount([RUNNING]);
    expect(h.el.querySelector<HTMLButtonElement>(".er-arm")!.disabled).toBe(
      true,
    );
  });

  it("stoppt einen laufenden Lauf erst nach Rückfrage, mit eigenem Bestätigungswort", async () => {
    // Nutzer-Befund 2026-08-22: es gab KEINEN Weg, einen Lauf anzuhalten —
    // „Alle Läufe löschen" ließ den Hintergrund-Task sogar weiterrechnen.
    const h = await mount([RUNNING]);
    const stop = h.el.querySelector<HTMLButtonElement>(".er-stop")!;
    expect(stop.getAttribute("aria-label")).toBe("Stoppen — Lauf r-live");
    stop.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".er-question")!.textContent).toContain("stoppen");
    const confirm = h.el.querySelector<HTMLButtonElement>(".er-confirm")!;
    // NICHT „Ja, löschen": der Teilstand bleibt ja erhalten.
    expect(confirm.textContent).toContain("Ja, stoppen");
    h.http.verify(); // Armieren stoppt noch nichts

    confirm.click();
    await h.fixture.whenStable();
    h.http
      .expectOne(
        (r) => r.url === `${RUNS_URL}/r-live/cancel` && r.method === "POST",
      )
      .flush({ cancelled: "r-live", task_stopped: true });
    await settle(h);
    h.http
      .expectOne((r) => r.url === RUNS_URL)
      .flush({ runs: [run("r-live", { status: "cancelled" })] });
    await settle(h);

    expect(h.el.querySelector(".er-status")!.textContent).toContain("gestoppt");
    expect(rows(h)[0].textContent).toContain("gestoppt");
    // Wer das Detail des Laufs offen hat, muss es neu lesen können — sonst
    // stünde dort weiter „läuft" (Review-Befund 2026-08-22).
    expect(h.fixture.componentInstance.lastStopped).toBe("r-live");
    expect(h.fixture.componentInstance.lastDeleted).toBeUndefined();
  });

  it("bietet Stoppen nur an laufenden Läufen an", async () => {
    const h = await mount([run("r1")]);
    expect(h.el.querySelector(".er-stop")).toBeNull();
  });

  it("names what a bulk delete will hit and only confirms an unrestricted one", async () => {
    const h = await mount([run("r1")]);
    h.el.querySelector<HTMLButtonElement>(".er-bulk")!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".er-question")!.textContent).toContain("ALLE");

    h.el.querySelector<HTMLButtonElement>(".er-confirm")!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne(
      (r) => r.url === RUNS_URL && r.method === "DELETE",
    );
    expect(req.request.params.get("confirm")).toBe("true");
    req.flush({ deleted: 3 });
    await settle(h);

    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [] });
    await settle(h);
    expect(h.el.querySelector(".er-status")!.textContent).toContain("3");
    // Sammel-Löschung: welche Läufe es traf, weiß die Liste nicht → `null`,
    // der Panel-Besitzer schließt sicherheitshalber.
    expect(h.fixture.componentInstance.lastDeleted).toBeNull();
  });

  it("restricts the bulk delete to a status when one is chosen", async () => {
    const h = await mount([run("r1")]);
    const select = h.el.querySelector<HTMLSelectElement>("#er-status")!;
    expect(select.labels?.[0]?.textContent).toContain("Status");
    select.value = "failed";
    select.dispatchEvent(new Event("change"));
    await h.fixture.whenStable();

    h.el.querySelector<HTMLButtonElement>(".er-bulk")!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".er-question")!.textContent).toContain(
      "fehlgeschlagen",
    );

    h.el.querySelector<HTMLButtonElement>(".er-confirm")!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne(
      (r) => r.url === RUNS_URL && r.method === "DELETE",
    );
    expect(req.request.params.get("status")).toBe("failed");
    expect(req.request.params.has("confirm")).toBe(false);
    req.flush({ deleted: 1 });
    await settle(h);
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [] });
    await settle(h);
  });

  it("clears the quality logs an eval wrote, after asking", async () => {
    const h = await mount([run("r1")]);
    h.el.querySelector<HTMLButtonElement>(".er-clear-logs")!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector(".er-question")!.textContent).toContain(
      "Quality-Logs",
    );

    h.el.querySelector<HTMLButtonElement>(".er-confirm")!.click();
    await h.fixture.whenStable();
    h.http
      .expectOne((r) => r.url === QLOGS_URL && r.method === "DELETE")
      // Die ECHTE Backend-Form (`mutations.py`): bis GV5 flushte dieser Test
      // `{deleted: 40}` — ein Feld, das das Backend nie sendet — und
      // validierte damit genau den `undefined`-Anzeige-Bug, den der
      // Service-Fix behebt.
      .flush({ deleted_eval_log_rows: 40 });
    await settle(h);
    expect(h.el.querySelector(".er-status")!.textContent).toContain("40");
  });

  it("says an installation without runs is empty, and how it fills", async () => {
    const h = await mount([]);
    expect(h.el.querySelector(".as-line")!.textContent).toContain("Gold-Flow");
  });

  it("re-reads on demand", async () => {
    const h = await mount([run("r1")]);
    h.el.querySelector<HTMLButtonElement>(".er-reload")!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run("r1")] });
    await settle(h);
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
    h.el.querySelector<HTMLButtonElement>(".er-arm")!.click();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('.er-danger [role="alert"]');
    expect(alert?.textContent).toContain("löschen");
    expect(alert?.querySelector("button")).toBeNull();
  });

  it("spricht auf Englisch vollständig englisch — Leiste, Filter und Zeile", async () => {
    const h = await mount([run("r1")], "en");
    const text = h.el.textContent ?? "";
    expect(text).toContain("all statuses");
    expect(text).toContain("Delete all runs");
    expect(text).toContain("done");
    expect(text).toContain("newest first");
    expect(text).not.toMatch(/[äöüß]/);
  });

  it("beugt die Zähl-Zeile als Ganzes, nicht nur ihr Substantiv", async () => {
    // `{count} Läufe` mit einem Lauf ist auf jeder Sprache falsch; die Grenze
    // zwischen Ein- und Mehrzahl gehört der Sprache (Intl.PluralRules), nicht
    // einem `=== 1` im Template.
    const eins = await mount([run("r1")]);
    expect(eins.el.querySelector(".er-count")!.textContent).toContain(
      "1 Lauf ",
    );

    const zwei = await mount([run("r1"), run("r2")]);
    expect(zwei.el.querySelector(".er-count")!.textContent).toContain(
      "2 Läufe",
    );
  });

  it("nennt im zugänglichen Namen des Löschen-Knopfs, welchen Lauf er trifft", async () => {
    // Jede Zeile trägt denselben sichtbaren Text; ohne das Ziel sind die Knöpfe
    // für einen Screenreader nicht unterscheidbar. Der Name beginnt mit dem
    // sichtbaren Wort (WCAG 2.5.3 „Label in Name") — wie `async.retryFor`.
    const h = await mount([run("r1"), run("r2")]);
    const arm = h.el.querySelectorAll<HTMLButtonElement>(".er-arm");
    expect(arm[0].getAttribute("aria-label")).toBe("Löschen — Lauf r1");
    expect(arm[1].getAttribute("aria-label")).toBe("Löschen — Lauf r2");
    expect(arm[0].textContent?.trim()).toBe("Löschen");
  });
});
