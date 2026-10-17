import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { FassungenApi } from "./fassungen-api.service";

const BASE = "/studio/api/config/fassungen";

describe("FassungenApi", () => {
  let api: FassungenApi;
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
    api = TestBed.inject(FassungenApi);
    http = TestBed.inject(HttpTestingController);
  });

  it("liest die Liste", async () => {
    const antwort = api.list();
    http.expectOne(BASE).flush({ available: true, bereiche: [] });
    expect(await antwort).toEqual({ available: true, bereiche: [] });
  });

  it("schaltet mit Bereich, Ziel und Version im Body um — Bereichsnamen enthalten /", () => {
    void api.umschalten("03-patterns/m05-suche", "werk", 4);
    const req = http.expectOne(`${BASE}/umschalten`);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      area: "03-patterns/m05-suche", ziel: "werk", expected_version: 4,
    });
    req.flush({ status: "ok", area: "03-patterns/m05-suche", version: 5 });
  });

  it("holt den Vergleich mit dem Bereich als Abfrage", () => {
    void api.vergleich("01-base/welcome-config");
    const req = http.expectOne(
      (r) => r.url === `${BASE}/vergleich` && r.params.get("area") === "01-base/welcome-config");
    expect(req.request.method).toBe("GET");
    req.flush({ area: "x", werk: "", gelebt: "", eigene: null, zeilen: [] });
  });

  it("startet den Werksabgleich", () => {
    void api.werksabgleich();
    const req = http.expectOne(`${BASE}/werksabgleich`);
    expect(req.request.method).toBe("POST");
    req.flush({ neu: 0, aktualisiert: 0, zugeordnet: 0, neues_werk: 0, uebersprungen: 0, konflikt: 0 });
  });
});
