// @vitest-environment jsdom
import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
  withXhr,
} from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { Router } from "@angular/router";
import { firstValueFrom } from "rxjs";
import { describe, expect, it, vi } from "vitest";

import { SessionState, SessionStore } from "../auth/session-store";
import { authErrorInterceptor } from "./auth-error.interceptor";

/**
 * Audit 2026-09-29. Abgemeldet antwortet `GET /studio/api/auth/session` mit
 * 401 (backend api/studio_bff.py) — das ist die Frage des Guards, keine
 * abgelaufene Sitzung. Der Interceptor nahm nur den Login-Pfad aus: jeder
 * abgemeldete Besuch sah „Sitzung abgelaufen", und seine Umleitung mitten in
 * der ersten Navigation (`router.url` noch `/`) überstimmte das Ziel des
 * Guards — Deep-Links überlebten die Anmeldung nie.
 */
function setUp(state: SessionState) {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr(), withInterceptors([authErrorInterceptor])),
      provideHttpClientTesting(),
    ],
  });
  const router = TestBed.inject(Router);
  const navigate = vi.spyOn(router, "navigate").mockResolvedValue(true);
  const session = TestBed.inject(SessionStore);
  session.set(state);
  return {
    http: TestBed.inject(HttpClient),
    ctrl: TestBed.inject(HttpTestingController),
    navigate,
    session,
  };
}

async function answer401(
  s: ReturnType<typeof setUp>,
  url: string,
): Promise<void> {
  const pending = firstValueFrom(s.http.get(url)).catch(() => undefined);
  s.ctrl.expectOne(url).flush(null, { status: 401, statusText: "Unauthorized" });
  await pending;
}

describe("authErrorInterceptor", () => {
  it("lässt die Sitzungs-Frage des Guards in Ruhe", async () => {
    const s = setUp("unknown");
    await answer401(s, "/studio/api/auth/session");
    expect(s.navigate).not.toHaveBeenCalled();
  });

  it("leitet ohne Anmeldung nicht als „abgelaufen“ um", async () => {
    // z. B. der Health-Poll der Statusanzeige nach dem Abmelden
    const s = setUp("signed-out");
    await answer401(s, "/studio/api/health");
    expect(s.navigate).not.toHaveBeenCalled();
  });

  it("schickt eine abgelaufene Sitzung zur Anmeldung", async () => {
    const s = setUp("signed-in");
    await answer401(s, "/studio/api/config/areas");
    expect(s.session.state()).toBe("signed-out");
    expect(s.navigate).toHaveBeenCalledWith(["/login"], {
      queryParams: expect.objectContaining({ abgelaufen: 1 }),
    });
  });
});
