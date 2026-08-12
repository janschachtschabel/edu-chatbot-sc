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
import { SessionsComponent } from "./sessions.component";

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

const SESSIONS = [
  {
    session_id: "abc-123",
    persona_id: "lehrkraft",
    state_id: "S3",
    turn_count: 7,
    created_at: "2026-07-20T10:00:00Z",
    updated_at: "2026-07-24T18:30:00Z",
  },
  {
    session_id: "def-456",
    persona_id: "",
    state_id: "S1",
    turn_count: 1,
    created_at: "2026-07-24T09:00:00Z",
    updated_at: "2026-07-24T09:01:00Z",
  },
];

interface Harness {
  fixture: ComponentFixture<SessionsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(
  sessions: unknown[] = SESSIONS,
  locale = "de",
): Promise<Harness> {
  // jsdom meldet `navigator.language === 'en-US'` — ohne die gemerkte Wahl
  // stünde die Oberfläche ab C1-d4e2 auf Englisch.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(SessionsComponent);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne("/studio/api/sessions/").flush(sessions);
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

async function select(h: Harness, index: number): Promise<void> {
  h.el.querySelectorAll<HTMLButtonElement>(".sv-pick")[index].click();
  await h.fixture.whenStable();
}

describe("SessionsComponent", () => {
  it("asks for the list WITH the trailing slash the route needs", async () => {
    // Without it FastAPI answers 307 and the browser would follow the Location
    // straight past the BFF.
    const { http } = await mount();
    http.verify();
  });

  it("shows each session with its turns, persona and state", async () => {
    const { el } = await mount();
    const rows = el.querySelectorAll(".sv-row");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("abc-123");
    expect(rows[0].textContent).toContain("7");
    expect(rows[0].textContent).toContain("lehrkraft");
    expect(rows[0].textContent).toContain("S3");
  });

  it("names a session without a persona instead of showing a gap", async () => {
    const { el } = await mount();
    expect(el.querySelectorAll(".sv-row")[1].textContent).toContain(
      "unbekannt",
    );
  });

  it("makes each session a real button — ALT used a div with onClick", async () => {
    // A div is not focusable and not operable with Enter or Space.
    const { el } = await mount();
    const picks = el.querySelectorAll(".sv-pick");
    expect(picks).toHaveLength(2);
    for (const pick of Array.from(picks)) expect(pick.tagName).toBe("BUTTON");
  });

  it("says an empty studio is empty, and why that is normal", async () => {
    const { el } = await mount([]);
    expect(el.textContent).toContain("Noch keine Sessions");
  });

  it("reports a failed list instead of showing zero sessions", async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    const fixture = TestBed.createComponent(SessionsComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http
      .expectOne("/studio/api/sessions/")
      .flush("x", { status: 503, statusText: "Unavailable" });
    await tick();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role="alert"]')).not.toBeNull();
    expect(el.textContent).not.toContain("Noch keine Sessions");
  });

  it("loads the transcript of the chosen session, capped at the endpoint limit", async () => {
    const h = await mount();
    await select(h, 0);
    const req = h.http.expectOne(
      (r) => r.url === "/studio/api/sessions/abc-123/messages",
    );
    expect(req.request.params.get("limit")).toBe("200");
  });

  it("asks before deleting a session and does nothing when cancelled", async () => {
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>(".sv-del")[0].click();
    await h.fixture.whenStable();
    expect(h.el.textContent).toContain("Wirklich löschen");

    h.el.querySelector<HTMLButtonElement>(".sv-del-no")?.click();
    await h.fixture.whenStable();
    h.http.verify();
  });

  it("deletes the confirmed session and re-reads the list", async () => {
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>(".sv-del")[0].click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".sv-del-yes")?.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne("/studio/api/sessions/abc-123");
    expect(req.request.method).toBe("DELETE");
    req.flush({ status: "deleted" });
    await tick();
    await h.fixture.whenStable();
    h.http.expectOne("/studio/api/sessions/").flush([SESSIONS[1]]);
  });

  it("clears only the transcript, keeping the session row", async () => {
    // Two different destructive actions on one row; sending the wrong one
    // destroys analytics that "Verlauf leeren" promises to keep.
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>(".sv-clear")[0].click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".sv-clear-yes")?.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne("/studio/api/sessions/abc-123/messages");
    expect(req.request.method).toBe("DELETE");
  });

  it("stays on the session whose history was cleared, and re-reads it", async () => {
    // Clearing the history of the conversation you are reading must not close
    // the panel — it should show that it is now empty.
    const h = await mount();
    await select(h, 0);
    h.http
      .expectOne((r) => r.url === "/studio/api/sessions/abc-123/messages")
      .flush([{ role: "user", content: "hallo" }]);
    await tick();
    await h.fixture.whenStable();

    h.el.querySelectorAll<HTMLButtonElement>(".sv-clear")[0].click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>(".sv-clear-yes")?.click();
    await h.fixture.whenStable();
    h.http
      .expectOne("/studio/api/sessions/abc-123/messages")
      .flush({ status: "cleared" });
    await tick();
    await h.fixture.whenStable();

    expect(h.fixture.componentInstance.selected()).toBe("abc-123");
    h.http.expectOne("/studio/api/sessions/").flush(SESSIONS);
    await tick();
    await h.fixture.whenStable();
    // the transcript asked again, and now gets nothing
    h.http
      .expectOne((r) => r.url === "/studio/api/sessions/abc-123/messages")
      .flush([]);
    await tick();
    await h.fixture.whenStable();
    expect(h.el.textContent).toContain("keine Nachrichten gespeichert");
  });

  it("arms the confirmation on one row only", async () => {
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>(".sv-del")[1].click();
    await h.fixture.whenStable();
    expect(h.el.querySelectorAll(".sv-del-yes")).toHaveLength(1);
  });

  it("re-reads the list on demand", async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>(".sv-reload")?.click();
    await h.fixture.whenStable();
    h.http.expectOne("/studio/api/sessions/").flush(SESSIONS);
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
    h.el.querySelectorAll<HTMLButtonElement>(".sv-del")[0].click();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('.sv-confirm [role="alert"]');
    expect(alert?.textContent).toContain("Wirklich löschen?");
    expect(alert?.querySelector("button")).toBeNull();
  });

  /**
   * C1-d4e2 — vierter und fünfter Fall derselben Sache (nach C1-d4b1, C1-d4d2
   * und C1-d4e1). Hier stehen ZWEI zerstörende Knöpfe nebeneinander, deren
   * sichtbare Namen sich nicht unterscheiden lassen, wenn man nur die Zeile
   * hört: „Verlauf leeren" behält die Auswertungsdaten, „Löschen" nimmt alles.
   */
  it("gibt beiden Knöpfen EINEN Namen, der mit dem sichtbaren Wort beginnt", async () => {
    const h = await mount();
    const clear = h.el.querySelectorAll<HTMLButtonElement>(".sv-clear")[0];
    const remove = h.el.querySelectorAll<HTMLButtonElement>(".sv-del")[0];

    expect(clear.getAttribute("aria-label")).toBe(
      "Verlauf leeren — Session abc-123",
    );
    expect(remove.getAttribute("aria-label")).toBe("Löschen — Session abc-123");
    expect(clear.textContent!.trim()).toBe("Verlauf leeren");
    expect(remove.textContent!.trim()).toBe("Löschen");
    expect(h.el.querySelector(".sv-row .sr")).toBeNull();
  });

  it("spricht Englisch, wenn Englisch eingestellt ist", async () => {
    const h = await mount(SESSIONS, "en");
    const rows = h.el.querySelectorAll(".sv-row");

    expect(rows[0].textContent).toContain("7 turns");
    expect(rows[1].textContent).toContain("1 turn");
    expect(rows[1].textContent).toContain("unknown");
    expect(h.el.textContent).not.toContain("Verlauf leeren");
  });
});
