// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { ConfigApi } from "../core/config-api.service";
import {
  STUDIO_LOCALE_STORAGE_KEY,
  StudioLanguageService,
} from "../i18n/studio-language.service";
import { AREA_SCHEMAS } from "./area-schemas.fixture";
import { AreaDocEditor } from "./area-doc-editor";

const AREA = "01-base/welcome-config";
const OTHER = "01-base/display-rules";
const schemaUrl = (area: string) => `/studio/api/config/schema/${area}`;
const dataUrl = (area: string) => `/studio/api/config/data/${area}`;

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

let http: HttpTestingController;

function makeEditor(): AreaDocEditor {
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund) — die Zusagen
  // unten nennen deutsche Sätze, also wird die oberste Quelle gesetzt.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  http = TestBed.inject(HttpTestingController);
  // Der Übersetzer kommt durch den Konstruktor: `AreaDocEditor` ist bewusst
  // nicht injizierbar und kann `inject()` daher nicht selbst aufrufen.
  return new AreaDocEditor(
    TestBed.inject(ConfigApi),
    TestBed.inject(StudioLanguageService).t,
  );
}

/** Answer one load(area) with the given document. */
function answerLoad(
  area: string,
  data: Record<string, unknown>,
  type = "yaml",
): void {
  http.expectOne(schemaUrl(area)).flush(AREA_SCHEMAS[area]);
  http.expectOne(dataUrl(area)).flush({ area, data, type });
}

describe("AreaDocEditor", () => {
  beforeEach(() => {
    // each test builds its own editor via makeEditor()
  });

  it("installs schema and document, and starts clean", async () => {
    const editor = makeEditor();
    const done = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await done;

    expect(editor.schema()).not.toBeNull();
    expect(editor.doc()).toEqual({ welcome: { greeting: "Moin" } });
    expect(editor.docType()).toBe("yaml");
    expect(editor.dirty()).toBe(false);
    expect(editor.loading()).toBe(false);
  });

  it("ignores a load that finished after a newer one started", async () => {
    // Without the generation guard area A's document lands under area B's
    // schema, is marked clean, and the next save REPLACES B with A.
    const editor = makeEditor();
    const stale = editor.load(AREA);
    await tick();
    const fresh = editor.load(OTHER);
    await tick();

    answerLoad(OTHER, { display_rules: { boxes: {} } });
    answerLoad(AREA, { welcome: { greeting: "alt" } });

    // the return value is what callers chain follow-up requests on: a stale
    // load that reported success would let its caller fetch the raw text of
    // the wrong area — and start a generation that voids the fresh load
    expect(await stale).toBe(false);
    expect(await fresh).toBe(true);
    expect(editor.doc()).toEqual({ display_rules: { boxes: {} } });
  });

  it("sends the WHOLE document on save and adopts what came back", async () => {
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" }, eigener_schluessel: 42 });
    await load;

    editor.setDoc({ welcome: { greeting: "Servus" }, eigener_schluessel: 42 });
    expect(editor.dirty()).toBe(true);

    const saved = editor.save(AREA);
    await tick();
    const req = http.expectOne(dataUrl(AREA));
    expect(req.request.method).toBe("PUT");
    // the unpinned key must travel with the save, or it is deleted
    expect(req.request.body).toEqual({
      data: { welcome: { greeting: "Servus" }, eigener_schluessel: 42 },
    });
    req.flush({
      area: AREA,
      data: { welcome: { greeting: "Servus" }, eigener_schluessel: 42 },
      type: "yaml",
    });

    expect(await saved).toBe(true);
    expect(editor.dirty()).toBe(false);
    expect(editor.status()).toContain("espeichert");
  });

  it("refuses to save while a field holds unparseable input", async () => {
    // Saving anyway would PUT the last parseable value and report success —
    // the edit would be gone with nothing saying so.
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await load;

    editor.setDoc({ welcome: { greeting: "Servus" } });
    editor.setFieldErrors(["welcome.quick_replies"]);
    expect(editor.blocked()).toBe(true);

    expect(await editor.save(AREA)).toBe(false);
    http.expectNone(dataUrl(AREA));
    expect(editor.saveError()).toContain("welcome.quick_replies");
  });

  it("does not adopt a save answer that a newer request has overtaken", async () => {
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await load;

    editor.setDoc({ welcome: { greeting: "eins" } });
    const stale = editor.save(AREA);
    await tick();
    const staleReq = http.expectOne(dataUrl(AREA));

    const reload = editor.load(OTHER);
    await tick();
    answerLoad(OTHER, { display_rules: { boxes: {} } });
    staleReq.flush({
      area: AREA,
      data: { welcome: { greeting: "eins" } },
      type: "yaml",
    });
    await Promise.all([stale, reload]);

    expect(editor.doc()).toEqual({ display_rules: { boxes: {} } });
  });

  it("restores the last saved document on discard", async () => {
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await load;

    editor.setDoc({ welcome: { greeting: "weg damit" } });
    editor.discard();

    expect(editor.doc()).toEqual({ welcome: { greeting: "Moin" } });
    expect(editor.dirty()).toBe(false);
  });

  it("reports an unknown area in words an editor can act on", async () => {
    const editor = makeEditor();
    const done = editor.load("01-base/gibt-es-nicht");
    await tick();
    http
      .expectOne(schemaUrl("01-base/gibt-es-nicht"))
      .flush(
        { detail: "unknown config area" },
        { status: 404, statusText: "Not Found" },
      );
    http
      .expectOne(dataUrl("01-base/gibt-es-nicht"))
      .flush(
        { detail: "unknown config area" },
        { status: 404, statusText: "Not Found" },
      );
    await done;

    expect(editor.loadError()).toContain("gibt es nicht");
    expect(editor.loading()).toBe(false);
  });

  it("keeps the edit when the save is rejected", async () => {
    // Never clear the form on error — the editor would lose what they typed.
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await load;

    editor.setDoc({ welcome: { greeting: "" } });
    const saved = editor.save(AREA);
    await tick();
    http
      .expectOne(dataUrl(AREA))
      .flush(
        {
          detail: [
            {
              loc: ["body", "welcome", "greeting"],
              msg: "darf nicht leer sein",
            },
          ],
        },
        { status: 422, statusText: "Unprocessable Content" },
      );

    expect(await saved).toBe(false);
    expect(editor.doc()).toEqual({ welcome: { greeting: "" } });
    expect(editor.dirty()).toBe(true);
    expect(editor.saveError()).toContain("greeting");
  });
});
