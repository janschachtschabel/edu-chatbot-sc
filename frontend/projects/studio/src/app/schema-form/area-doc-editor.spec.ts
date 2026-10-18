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

  it("lässt einen nicht lesbaren Feld-Entwurf verwerfen (Paket 15)", async () => {
    // Ungültiges JSON ändert das Dokument nicht — „Verwerfen“ blieb deshalb grau, und der
    // Entwurf samt Fehler stand weiter da.
    const editor = makeEditor();
    const done = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await done;
    expect(editor.verwerfbar()).toBe(false);
    editor.setFieldErrors(["welcome.extra"]);
    expect(editor.dirty()).toBe(false);
    expect(editor.verwerfbar()).toBe(true);
    const vorher = editor.doc();
    const epoche = editor.epoche();
    editor.discard();
    expect(editor.fieldErrors()).toEqual([]);
    // Der Zähler reicht ins Formular: auch JSON-Felder mit gleichem Wert räumen (Review P15 #4).
    expect(editor.epoche()).toBe(epoche + 1);
    expect(editor.doc()).toEqual(vorher);
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

  it("behält, was während des Speicherns getippt wurde (Audit 2026-09-29)", async () => {
    // Die Antwort des Servers ist das Echo des GESENDETEN Stands. Sie als
    // neuen Inhalt zu übernehmen, setzte eine Eingabe zurück, die während
    // des Speicherns entstand — still, ohne Hinweis auf ungespeicherte Arbeit.
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    answerLoad(AREA, { welcome: { greeting: "Moin" } });
    await load;

    editor.setDoc({ welcome: { greeting: "Servus" } });
    const saved = editor.save(AREA);
    await tick();
    editor.setDoc({ welcome: { greeting: "Servus, schön dich zu sehen" } });
    http.expectOne(dataUrl(AREA)).flush({
      area: AREA, data: { welcome: { greeting: "Servus" } }, type: "yaml",
    });

    expect(await saved).toBe(true);
    expect(editor.doc()).toEqual({ welcome: { greeting: "Servus, schön dich zu sehen" } });
    expect(editor.dirty()).toBe(true);
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

  // ── ST-2e: Prüffehler je Feld ─────────────────────────────────────
  const SCHRIFT = ["display_rules", "inline_documents", "font_size_percent"];
  const MATERIAL = ["display_rules", "groups", "materialien_max"];
  const falsch = (schrift: number, material: number) => ({
    display_rules: {
      inline_documents: { font_size_percent: schrift },
      groups: { materialien_max: material },
    },
  });

  /** Ein Speicherversuch, den der Server mit zwei Feldfehlern abweist. */
  async function abgewiesen(): Promise<AreaDocEditor> {
    const editor = makeEditor();
    const load = editor.load(OTHER);
    await tick();
    answerLoad(OTHER, falsch(85, 3));
    await load;
    editor.setDoc(falsch(10, 99));
    const saved = editor.save(OTHER);
    await tick();
    http.expectOne(dataUrl(OTHER)).flush(
      {
        detail: [
          { loc: SCHRIFT, msg: "m", type: "greater_than_equal", ctx: { ge: 70 } },
          { loc: MATERIAL, msg: "m", type: "less_than_equal", ctx: { le: 8 } },
        ],
      },
      { status: 422, statusText: "Unprocessable Content" },
    );
    expect(await saved).toBe(false);
    return editor;
  }

  it("merkt sich die Prüffehler je Feld und nennt oben jedes Feld mit Grund", async () => {
    // Die Zeile oben ist die Live-Region, die ein Screenreader ansagt — die
    // Markierungen am Feld sagt er nicht von selbst an.
    const editor = await abgewiesen();
    expect(editor.problems().map((p) => p.path)).toEqual([SCHRIFT, MATERIAL]);
    expect(editor.saveError()).toContain(`${SCHRIFT.join(".")}: Mindestens 70`);
    expect(editor.saveError()).toContain(`${MATERIAL.join(".")}: Höchstens 8`);
  });

  it("vergisst einen Prüffehler, sobald sein Feld geändert ist — die anderen bleiben", async () => {
    const editor = await abgewiesen();
    editor.setDoc(falsch(80, 99));
    expect(editor.problems().map((p) => p.path)).toEqual([MATERIAL]);
  });

  it("räumt die Prüffehler beim Verwerfen", async () => {
    const editor = await abgewiesen();
    editor.discard();
    expect(editor.problems()).toEqual([]);
  });

  // ── Paket 4, D5 (externes Audit F14): Speichern mit Konfliktschutz ──────────
  // Zwei Redakteure laden denselben Stand; wer als zweites speichert, bekommt
  // 409 und entscheidet — statt still den ersten zu überschreiben.

  async function geladen(version: number | null): Promise<AreaDocEditor> {
    const editor = makeEditor();
    const load = editor.load(AREA);
    await tick();
    http.expectOne(schemaUrl(AREA)).flush(AREA_SCHEMAS[AREA]);
    http.expectOne(dataUrl(AREA)).flush({
      area: AREA, data: { welcome: { greeting: "Moin" } }, type: "yaml", version,
    });
    await load;
    editor.setDoc({ welcome: { greeting: "Mein Entwurf" } });
    return editor;
  }

  const KONFLIKT = {
    message: "Dieser Bereich wurde inzwischen geändert.",
    version: 5,
    updated_by: "studio-form",
    updated_at: "2026-10-03T20:41:00+00:00",
  };

  async function imKonflikt(): Promise<AreaDocEditor> {
    const editor = await geladen(3);
    const saved = editor.save(AREA);
    await tick();
    http.expectOne(dataUrl(AREA)).flush(
      { detail: KONFLIKT }, { status: 409, statusText: "Conflict" });
    expect(await saved).toBe(false);
    return editor;
  }

  it("speichert gegen die geladene Version und übernimmt die neue", async () => {
    const editor = await geladen(3);
    const saved = editor.save(AREA);
    await tick();
    const req = http.expectOne(dataUrl(AREA));
    expect(req.request.body).toEqual({
      data: { welcome: { greeting: "Mein Entwurf" } }, expected_version: 3,
    });
    req.flush({ area: AREA, data: req.request.body.data, type: "yaml", version: 4 });
    expect(await saved).toBe(true);
    expect(editor.version()).toBe(4);
  });

  it("legt einen Bereich ohne gespeicherte Zeile ausdrücklich an", async () => {
    // `version: null` heißt: es gibt noch keine Zeile. Wer zeitgleich anlegt,
    // soll den anderen nicht überschreiben.
    const editor = await geladen(null);
    void editor.save(AREA);
    await tick();
    expect(http.expectOne(dataUrl(AREA)).request.body).toEqual({
      data: { welcome: { greeting: "Mein Entwurf" } }, create: true,
    });
  });

  it("hält bei einem Konflikt den Entwurf und meldet, wer wann gespeichert hat", async () => {
    const editor = await imKonflikt();
    expect(editor.conflict()).toEqual({
      version: 5, updatedBy: "studio-form", updatedAt: "2026-10-03T20:41:00+00:00",
    });
    expect(editor.doc()).toEqual({ welcome: { greeting: "Mein Entwurf" } });
    expect(editor.dirty()).toBe(true);
  });

  it("speichert trotzdem — gegen genau die gemeldete Version", async () => {
    // Nicht bedingungslos: kam inzwischen noch eine Änderung, gibt es wieder 409.
    const editor = await imKonflikt();
    const saved = editor.save(AREA, { force: true });
    await tick();
    const req = http.expectOne(dataUrl(AREA));
    expect(req.request.body.expected_version).toBe(5);
    req.flush({ area: AREA, data: req.request.body.data, type: "yaml", version: 6 });
    expect(await saved).toBe(true);
    expect(editor.conflict()).toBeNull();
    expect(editor.version()).toBe(6);
  });

  it("Neu laden verwirft den Entwurf und räumt den Konflikt", async () => {
    const editor = await imKonflikt();
    const load = editor.load(AREA);
    await tick();
    http.expectOne(schemaUrl(AREA)).flush(AREA_SCHEMAS[AREA]);
    http.expectOne(dataUrl(AREA)).flush({
      area: AREA, data: { welcome: { greeting: "Vom anderen" } }, type: "yaml", version: 5,
    });
    await load;
    expect(editor.conflict()).toBeNull();
    expect(editor.doc()).toEqual({ welcome: { greeting: "Vom anderen" } });
    expect(editor.version()).toBe(5);
  });
});
