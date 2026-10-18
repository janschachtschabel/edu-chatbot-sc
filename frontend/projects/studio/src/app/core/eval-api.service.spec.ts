import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { EvalApi } from "./eval-api.service";

const BASE = "/studio/api/eval";

describe("EvalApi", () => {
  let api: EvalApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    api = TestBed.inject(EvalApi);
    http = TestBed.inject(HttpTestingController);
  });

  it("unwraps the run list", async () => {
    const promise = api.runs();
    const req = http.expectOne((r) => r.url === `${BASE}/runs`);
    expect(req.request.params.get("limit")).toBe("50");
    req.flush({ runs: [{ id: "r1" }] });
    expect((await promise).map((r) => r.id)).toEqual(["r1"]);
  });

  it("survives a run list without the wrapper key", async () => {
    // Every list endpoint in this studio is defensive about the envelope: a 200
    // with an unexpected body must not throw inside a template.
    const promise = api.runs();
    http.expectOne((r) => r.url === `${BASE}/runs`).flush({});
    expect(await promise).toEqual([]);
  });

  it("unwraps the gold flows", async () => {
    const promise = api.goldFlows();
    http
      .expectOne((r) => r.url === `${BASE}/gold-flows`)
      .flush({ flows: [{ id: "f1", name: "Suche" }], count: 1 });
    expect((await promise).map((f) => f.id)).toEqual(["f1"]);
  });

  it("asks for an estimate with the whole form, as a body", async () => {
    void api.estimate({
      mode: "both",
      persona_ids: ["P01"],
      intent_ids: [],
      scenarios_per_combo: 2,
      turns_per_conv: 3,
    });
    const req = http.expectOne((r) => r.url === `${BASE}/estimate`);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      mode: "both",
      persona_ids: ["P01"],
      intent_ids: [],
      scenarios_per_combo: 2,
      turns_per_conv: 3,
    });
    req.flush({ est: "1.2" });
  });

  it("starts a generative run with the config slug included", async () => {
    void api.startRun({
      mode: "scenarios",
      persona_ids: [],
      intent_ids: ["I02"],
      scenarios_per_combo: 1,
      turns_per_conv: 3,
      config_slug: "wlo/v1",
    });
    const req = http.expectOne(
      (r) => r.url === `${BASE}/runs` && r.method === "POST",
    );
    expect(req.request.body.config_slug).toBe("wlo/v1");
    req.flush({ run_id: "r9" });
  });

  it("starts a golden run", async () => {
    void api.startGoldenRun({
      flow_ids: ["f1"],
      judge: false,
      config_slug: "",
      engine: "agent",
    });
    const req = http.expectOne((r) => r.url === `${BASE}/runs/golden`);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      flow_ids: ["f1"],
      judge: false,
      config_slug: "",
      engine: "agent",
    });
    req.flush({ run_id: "g1" });
  });

  it("lädt den Bericht eines Laufs als Datei (Paket 13, F7)", async () => {
    const promise = api.berichtMd("r1");
    const req = http.expectOne(`${BASE}/runs/r1/bericht.md`);
    expect(req.request.responseType).toBe("blob");
    req.flush(new Blob(["# Bericht"]));
    await expect(promise).resolves.toBeInstanceOf(Blob);
  });

  it("holt den Unterschied zweier Prompt-Fassungen (Paket 13, F8)", async () => {
    const promise = api.promptDiff("aaaaaaaaaaaa", "bbbbbbbbbbbb");
    const req = http.expectOne((r) => r.url === `${BASE}/prompt-diff`);
    expect(req.request.params.get("a")).toBe("aaaaaaaaaaaa");
    expect(req.request.params.get("b")).toBe("bbbbbbbbbbbb");
    req.flush({ diff: ["-alt", "+neu"] });
    await expect(promise).resolves.toEqual({ diff: ["-alt", "+neu"] });
  });

  it("reads one run and deletes one run", async () => {
    void api.run("r1");
    http
      .expectOne((r) => r.url === `${BASE}/runs/r1` && r.method === "GET")
      .flush({ id: "r1" });

    void api.deleteRun("r1");
    http
      .expectOne((r) => r.url === `${BASE}/runs/r1` && r.method === "DELETE")
      .flush({ deleted: "r1" });
  });

  it("stoppt einen laufenden Lauf über den Cancel-Endpunkt", async () => {
    void api.cancelRun("r1");
    http
      .expectOne((r) => r.url === `${BASE}/runs/r1/cancel` && r.method === "POST")
      .flush({ cancelled: "r1", task_stopped: true });
  });

  it("confirms a bulk delete only when nothing narrows it", async () => {
    // The endpoint refuses an unrestricted wipe without `confirm=true`; a status
    // or mode filter counts as a restriction. Mirrored so the flag is sent
    // exactly when it is required — same rule as the quality-log clear.
    void api.deleteRuns({});
    expect(
      http
        .expectOne((r) => r.url === `${BASE}/runs` && r.method === "DELETE")
        .request.params.get("confirm"),
    ).toBe("true");
    http.verify();

    void api.deleteRuns({ status: "failed" });
    const narrowed = http.expectOne(
      (r) => r.url === `${BASE}/runs` && r.method === "DELETE",
    );
    expect(narrowed.request.params.get("status")).toBe("failed");
    expect(narrowed.request.params.has("confirm")).toBe(false);
    narrowed.flush({ deleted: 2 });
  });

  it("passes the mode filter through under its own name", async () => {
    void api.deleteRuns({ mode: "golden" });
    const req = http.expectOne(
      (r) => r.url === `${BASE}/runs` && r.method === "DELETE",
    );
    expect(req.request.params.get("mode")).toBe("golden");
    expect(req.request.params.has("status")).toBe(false);
    req.flush({ deleted: 1 });
  });

  it("clears the quality logs the eval runs wrote", async () => {
    void api.clearEvalQualityLogs();
    const req = http.expectOne((r) => r.url === `${BASE}/quality-logs`);
    expect(req.request.method).toBe("DELETE");
    req.flush({ deleted: 12 });
  });

  it("reads the trends with an explicit window", async () => {
    void api.trends();
    expect(
      http
        .expectOne((r) => r.url === `${BASE}/trends`)
        .request.params.get("limit"),
    ).toBe("20");
  });

  it("filtert Liste und Verlauf nur nach Maschine, wenn eine gewählt ist (ST-7a)", async () => {
    void api.runs("agent");
    const liste = http.expectOne((r) => r.url === `${BASE}/runs`);
    expect(liste.request.params.get("engine")).toBe("agent");
    expect(liste.request.params.get("limit")).toBe("50");
    liste.flush({ runs: [] });

    void api.runs();
    const alle = http.expectOne((r) => r.url === `${BASE}/runs`);
    // Ohne Wahl bleibt die Anfrage genau die alte — auch Läufe mit unbekannter
    // Maschine gehören dann dazu.
    expect(alle.request.params.has("engine")).toBe(false);
    alle.flush({ runs: [] });

    void api.trends("pattern");
    const verlauf = http.expectOne((r) => r.url === `${BASE}/trends`);
    expect(verlauf.request.params.get("engine")).toBe("pattern");
    expect(verlauf.request.params.get("limit")).toBe("20");
  });

  it("vergleicht Läufe über eine Komma-Liste der Kennungen (ST-7c)", async () => {
    void api.compare(["eval-a", "eval-b"]);
    const req = http.expectOne((r) => r.url === `${BASE}/compare`);
    expect(req.request.method).toBe("GET");
    expect(req.request.params.get("ids")).toBe("eval-a,eval-b");
  });

  it('scopes the pattern usage and drops an empty "since"', async () => {
    void api.patternUsage("eval", "", "pattern");
    const req = http.expectOne(
      (r) => r.url === `${BASE}/analytics/pattern-usage`,
    );
    expect(req.request.params.get("scope")).toBe("eval");
    expect(req.request.params.get("engine")).toBe("pattern");
    expect(req.request.params.has("since")).toBe(false);
    req.flush({
      triples: [],
      total: 0,
      scope: "eval",
    });
  });

  it("reads the personas and intents that a run can be scoped to", async () => {
    void api.config();
    http
      .expectOne((r) => r.url === `${BASE}/config`)
      .flush({ personas: [{ id: "P01" }], intents: [{ id: "I02" }] });
  });
});
