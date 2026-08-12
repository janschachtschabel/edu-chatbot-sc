// @vitest-environment jsdom
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideHttpClient, withXhr } from "@angular/common/http";
import { TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { StudioApiError } from "./studio-api-error";
import { StudioApi } from "./studio-api.service";

describe("StudioApi", () => {
  let api: StudioApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
        StudioApi,
      ],
    });
    api = TestBed.inject(StudioApi);
    http = TestBed.inject(HttpTestingController);
  });

  it("prefixes every path with the BFF base", async () => {
    const done = api.get<{ ok: boolean }>("/config/welcome");
    http.expectOne("/studio/api/config/welcome").flush({ ok: true });
    expect(await done).toEqual({ ok: true });
  });

  it("keeps a trailing slash — /api/sessions/ only exists WITH one", async () => {
    // ALT needed a special case in its proxy for exactly this (route.ts:27-35):
    // dropping the slash makes FastAPI answer 307 instead of data.
    const done = api.get("/sessions/");
    http.expectOne("/studio/api/sessions/").flush([]);
    await done;
  });

  it("serializes query params and skips null/undefined", async () => {
    const done = api.get("/quality/logs", {
      limit: 50,
      scope: "prod",
      persona: null,
    });
    const req = http.expectOne((r) => r.url === "/studio/api/quality/logs");
    expect(req.request.params.get("limit")).toBe("50");
    expect(req.request.params.get("scope")).toBe("prod");
    expect(req.request.params.has("persona")).toBe(false);
    req.flush({});
    await done;
  });

  it("exposes the status CODE on failure, not just a message", async () => {
    // ALT's fetchJson threw `new Error("HTTP 403 /url — body")`, so callers could
    // only string-match to tell 401 from 500 (studio/src/lib/api.ts:15-19).
    const done = api.get("/config/patterns");
    http
      .expectOne("/studio/api/config/patterns")
      .flush(
        { detail: "Studio login required" },
        { status: 401, statusText: "Unauthorized" },
      );

    const err = await done.then(
      () => null,
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(StudioApiError);
    expect((err as StudioApiError).status).toBe(401);
    expect((err as StudioApiError).detail).toBe("Studio login required");
  });

  it("turns a network failure into status 0 with a readable German message", async () => {
    const done = api.get("/health");
    http.expectOne("/studio/api/health").error(new ProgressEvent("error"));

    const err = (await done.then(
      () => null,
      (e: unknown) => e,
    )) as StudioApiError;
    expect(err.status).toBe(0);
    expect(err.detail).toContain("nicht erreichbar");
  });

  it("falls back to a readable detail when the body is not the usual shape", async () => {
    const done = api.get("/config/patterns");
    http
      .expectOne("/studio/api/config/patterns")
      .flush("<html>Gateway</html>", {
        status: 502,
        statusText: "Bad Gateway",
      });

    const err = (await done.then(
      () => null,
      (e: unknown) => e,
    )) as StudioApiError;
    expect(err.status).toBe(502);
    expect(err.detail.length).toBeGreaterThan(0);
    expect(err.detail.length).toBeLessThanOrEqual(200); // no unbounded body in the UI
  });

  it('names the fields of a validation failure instead of "Unprocessable Content"', async () => {
    const done = api.put("/config/data/01-base/welcome-config", { data: {} });
    http.expectOne("/studio/api/config/data/01-base/welcome-config").flush(
      {
        detail: [
          {
            loc: ["body", "welcome", "quick_replies"],
            msg: "Input should be a valid list",
          },
          {
            loc: ["body", "welcome", "tour_reply"],
            msg: "Input should be a valid string",
          },
        ],
      },
      { status: 422, statusText: "Unprocessable Content" },
    );
    const err = (await done.then(
      () => null,
      (e: unknown) => e,
    )) as StudioApiError;
    expect(err.detail).toContain(
      "welcome.quick_replies: Input should be a valid list",
    );
    // both entries, separated — a single-entry test would not notice a lost join
    expect(err.detail).toContain("; ");
    expect(err.detail).toContain("welcome.tour_reply");
  });

  it("strips only the LEADING body segment — `body` is a real config key", async () => {
    // every layer doc and every pattern stores its markdown under `body`;
    // filtering it everywhere left those errors with no field name at all
    const done = api.put("/config/data/01-base/base-persona", { data: {} });
    http
      .expectOne("/studio/api/config/data/01-base/base-persona")
      .flush(
        {
          detail: [
            { loc: ["body", "body"], msg: "Input should be a valid string" },
          ],
        },
        { status: 422, statusText: "Unprocessable Content" },
      );
    const err = (await done.then(
      () => null,
      (e: unknown) => e,
    )) as StudioApiError;
    expect(err.detail).toBe("body: Input should be a valid string");
  });

  it("sends put/post/delete to the same base", async () => {
    const put = api.put("/config/welcome", { greeting: "Moin" });
    const putReq = http.expectOne("/studio/api/config/welcome");
    expect(putReq.request.method).toBe("PUT");
    expect(putReq.request.body).toEqual({ greeting: "Moin" });
    putReq.flush({});
    await put;

    const post = api.post("/config/snapshots", null);
    expect(http.expectOne("/studio/api/config/snapshots").request.method).toBe(
      "POST",
    );
    http.verify();
    void post.catch(() => undefined);
  });
});
