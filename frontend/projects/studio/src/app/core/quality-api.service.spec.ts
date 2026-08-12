import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { QualityApi } from "./quality-api.service";

const BASE = "/studio/api/quality";

function setup(): { api: QualityApi; http: HttpTestingController } {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  return {
    api: TestBed.inject(QualityApi),
    http: TestBed.inject(HttpTestingController),
  };
}

describe("QualityApi", () => {
  let api: QualityApi;
  let http: HttpTestingController;

  beforeEach(() => {
    ({ api, http } = setup());
  });

  it("reads the log window ALT used and omits filters that are not set", async () => {
    const pending = api.logs("all", {});
    const req = http.expectOne((r) => r.url === `${BASE}/logs`);

    expect(req.request.params.get("limit")).toBe("200");
    expect(req.request.params.get("scope")).toBe("all");
    // Empty filters must not be SENT as empty: `pattern_id=` is a real filter
    // value to FastAPI and would match nothing.
    expect(req.request.params.has("pattern_id")).toBe(false);
    expect(req.request.params.has("intent_id")).toBe(false);
    expect(req.request.params.has("session_id")).toBe(false);

    req.flush({ count: 0, logs: [] });
    await expect(pending).resolves.toEqual([]);
  });

  it("passes the filters that are set", () => {
    void api.logs("eval", {
      patternId: "M04",
      intentId: "I02",
      sessionId: "s-1",
    });
    const req = http.expectOne((r) => r.url === `${BASE}/logs`);

    expect(req.request.params.get("scope")).toBe("eval");
    expect(req.request.params.get("pattern_id")).toBe("M04");
    expect(req.request.params.get("intent_id")).toBe("I02");
    expect(req.request.params.get("session_id")).toBe("s-1");
    req.flush({ count: 0, logs: [] });
  });

  it("unwraps the log rows so an empty answer is distinguishable from no answer", async () => {
    const pending = api.logs("all", {});
    http
      .expectOne((r) => r.url === `${BASE}/logs`)
      .flush({ count: 1, logs: [{ id: 7 }] });
    await expect(pending).resolves.toEqual([{ id: 7 }]);
  });

  it("sends confirm=true only when clearing without any filter", () => {
    void api.clearLogs("all", {});
    const bulk = http.expectOne((r) => r.url === `${BASE}/logs/clear`);
    expect(bulk.request.method).toBe("POST");
    // The endpoint refuses an unfiltered scope='all' wipe without it (400).
    expect(bulk.request.params.get("confirm")).toBe("true");
    bulk.flush({ status: "cleared", deleted: 0 });

    void api.clearLogs("all", { patternId: "M04" });
    const filtered = http.expectOne((r) => r.url === `${BASE}/logs/clear`);
    expect(filtered.request.params.has("confirm")).toBe(false);
    expect(filtered.request.params.get("pattern_id")).toBe("M04");
    filtered.flush({ status: "cleared", deleted: 3 });
  });

  it("treats a narrowed scope as a filter, so no confirmation is demanded", () => {
    // The endpoint's own rule: scope != 'all' already counts as a filter.
    void api.clearLogs("eval", {});
    const req = http.expectOne((r) => r.url === `${BASE}/logs/clear`);
    expect(req.request.params.has("confirm")).toBe(false);
    expect(req.request.params.get("scope")).toBe("eval");
    req.flush({ status: "cleared", deleted: 2 });
  });

  it("deletes a single log by id", () => {
    void api.deleteLog(42);
    const req = http.expectOne(`${BASE}/logs/42`);
    expect(req.request.method).toBe("DELETE");
    req.flush({ status: "deleted", id: 42 });
  });

  it("carries the tuning knobs of the drill-downs", () => {
    void api.matrix("production", 5);
    const matrix = http.expectOne((r) => r.url === `${BASE}/matrix`);
    expect(matrix.request.params.get("scope")).toBe("production");
    expect(matrix.request.params.get("min_count")).toBe("5");
    matrix.flush({ scope: "production", total_turns: 0, cells: [] });

    void api.stateTransitions("all", 7, 2);
    const flow = http.expectOne((r) => r.url === `${BASE}/state-transitions`);
    expect(flow.request.params.get("days")).toBe("7");
    expect(flow.request.params.get("min_count")).toBe("2");
    flow.flush({
      scope: "all",
      days: 7,
      total_turns: 0,
      total_transitions: 0,
      state_distribution: {},
      transitions: [],
    });
  });

  it("reads the three diagnosis breakdowns with ALT's limit", () => {
    void api.degradations("all");
    const deg = http.expectOne((r) => r.url === `${BASE}/degradations`);
    expect(deg.request.params.get("limit")).toBe("30");
    deg.flush({ groups: [], total: 0, scope: "all" });

    void api.emptyEntities("all");
    const ent = http.expectOne((r) => r.url === `${BASE}/empty-entities`);
    expect(ent.request.params.get("limit")).toBe("30");
    ent.flush({ groups: [], total: 0, scope: "all" });

    void api.lowConfidence("all");
    const conf = http.expectOne((r) => r.url === `${BASE}/low-confidence`);
    expect(conf.request.params.get("limit")).toBe("30");
    conf.flush({ turns: [], total: 0, scope: "all", max_confidence: 0.6 });
  });

  it("has no way to call /tight-races, because the metric cannot fire", () => {
    // `phase2_scores` carries exactly one entry ({winner: 1.0}) since Welle E v4,
    // so `phase2_runner_up` is always '' and the endpoint's own WHERE clause
    // (`runner_up != ''`) can never match. Offering it would ship a permanently
    // empty panel. Pinned here so re-adding it is a deliberate act.
    expect("tightRaces" in api).toBe(false);
  });
});
