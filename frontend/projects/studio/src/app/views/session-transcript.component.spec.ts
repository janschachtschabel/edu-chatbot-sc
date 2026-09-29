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
import { SessionTranscriptComponent } from "./session-transcript.component";

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

interface Harness {
  fixture: ComponentFixture<SessionTranscriptComponent>;
  el: HTMLElement;
  component: SessionTranscriptComponent;
}

async function mount(messages: unknown[], locale = "de"): Promise<Harness> {
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
  const fixture = TestBed.createComponent(SessionTranscriptComponent);
  fixture.componentRef.setInput("sessionId", "abc-123");
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http
    .expectOne((r) => r.url === "/studio/api/sessions/abc-123/messages")
    .flush(messages);
  await tick();
  await fixture.whenStable();
  return {
    fixture,
    el: fixture.nativeElement as HTMLElement,
    component: fixture.componentInstance,
  };
}

describe("SessionTranscriptComponent — Zeitstempel", () => {
  it("renders a timestamp in German order", async () => {
    const h = await mount([
      {
        id: 1,
        role: "user",
        content: "Hallo",
        created_at: "2026-07-24T10:00:00Z",
      },
    ]);
    expect(h.el.querySelector(".st-time")?.textContent).toContain("24.7.2026");
  });

  // The template guards with `@if (formatTime(…); as time)`, so an empty return
  // is what removes the element — a message the backend stored without a
  // timestamp must not render an empty grey span next to the role.
  it("drops the time element when the message carries no timestamp", async () => {
    const h = await mount([{ id: 1, role: "user", content: "Hallo" }]);
    expect(h.el.querySelector(".st-time")).toBeNull();
    expect(h.el.textContent).toContain("Hallo");
  });

  /**
   * B2: aligned with the shared `germanDateTime`, which shows what it was given
   * rather than nothing. Before B2 this view swallowed an unparseable timestamp
   * exactly like a missing one — so a corrupt row looked like a row the backend
   * had never stamped, and nobody could tell the two apart.
   */
  it("shows an unparseable timestamp as it came in", async () => {
    const h = await mount([
      { id: 1, role: "user", content: "Hallo", created_at: "kein-datum" },
    ]);
    expect(h.el.querySelector(".st-time")?.textContent).toContain("kein-datum");
  });
});

describe("SessionTranscriptComponent — Sprache (C1-d4e2)", () => {
  const TURN = {
    id: 1,
    role: "assistant",
    content: "Hier sind Materialien.",
    debug: {
      pattern: "M06",
      intent: "I02",
      persona: "lehrkraft",
      state: "S3",
      tools_called: ["wlo_search"],
      signals: ["rag_hit"],
    },
  };

  it("benennt Rollen und Entscheidungs-Fakten auf Deutsch", async () => {
    const h = await mount([TURN, { id: 2, role: "user", content: "Danke" }]);
    expect(h.el.textContent).toContain("BOERDi");
    expect(h.el.textContent).toContain("Nutzerin/Nutzer");
    expect(h.el.querySelector(".st-facts")!.textContent).toContain("Muster");
    expect(h.el.querySelector(".st-facts")!.textContent).toContain("Werkzeuge");
  });

  it("benennt eine leere Rolle, statt eine Lücke zu lassen", async () => {
    const h = await mount([{ id: 1, role: "", content: "x" }]);
    expect(h.el.querySelector(".st-role")!.textContent!.trim()).toBe(
      "unbekannt",
    );
  });

  it("spricht Englisch, wenn Englisch eingestellt ist", async () => {
    const h = await mount([TURN], "en");
    expect(h.el.textContent).toContain("BOERDi"); // Produktname, unübersetzt
    expect(h.el.querySelector(".st-facts")!.textContent).toContain("Pattern");
    expect(h.el.querySelector(".st-facts")!.textContent).toContain("Tools");
    expect(h.el.textContent).not.toContain("Werkzeuge");
  });
});

describe("SessionTranscriptComponent — Spur (ST-8a)", () => {
  const AGENT_TURN = {
    id: 1,
    role: "assistant",
    content: "Hier sind drei Materialien.",
    debug: {
      pattern: "AGENT",
      engine: "agent",
      token_usage: { prompt_tokens: 1200, cached_tokens: 0, completion_tokens: 90 },
      trace: [
        {
          step: "agent_round",
          duration_ms: 800,
          data: { runde: 1, dauer_ms: 800, werkzeuge: [{ name: "search_wlo_content", argumente: ["query"] }] },
        },
        { step: "agent_stop", duration_ms: 800, data: { stop_reason: "text", runden: 1 } },
      ],
    },
  };

  it("zeigt unter einer Antwort Maschine und Runden des Zugs", async () => {
    const h = await mount([AGENT_TURN]);
    const spur = h.el.querySelector(".st-turn--bot studio-agent-trace .atr");
    expect(spur).not.toBeNull();
    expect(spur!.textContent).toContain("Agent-Schleife");
    expect(spur!.querySelector(".atr-table tbody tr")!.textContent).toContain("search_wlo_content");
  });

  it("zeigt unter einer Frage der Person keine Spur", async () => {
    const h = await mount([{ id: 2, role: "user", content: "Hallo", debug: {} }]);
    expect(h.el.querySelector("studio-agent-trace")).toBeNull();
  });
});
