// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { describe, expect, it, vi } from "vitest";

import { EffectsApi } from "../core/effects-api.service";
import { StudioAnsicht } from "../core/studio-ansicht.service";
import { STUDIO_DE } from "../i18n/de";
import { STUDIO_EN } from "../i18n/en";
import {
  STUDIO_LOCALE_STORAGE_KEY,
  StudioLanguageService,
} from "../i18n/studio-language.service";
import { AREA_KEYS, AREA_SCHEMAS } from "../schema-form/area-schemas.fixture";
import { STUDIO_VIEWS, type StudioView, navGroups } from "../studio-views";
import { DASHBOARD_SECTIONS, PANEL_AREAS, PANEL_FELDER, areasWithPage } from "./area-homes";
import { fieldPaths } from "../schema-form/pick-fields";
import { rootField } from "../schema-form/schema-to-fields";
import {
  CURATED_VIEWS, type CuratedAreaSection, curatedView, isAreaSection,
} from "./curated-views";
import { CuratedViewComponent } from "./curated-view.component";
import { By } from "@angular/platform-browser";
import { SchemaFormComponent } from "../schema-form/schema-form.component";

/** Only the config-area sections — panels have no area key (9-4e). */
const AREA_SECTIONS = CURATED_VIEWS.map((view) => ({
  slug: view.slug,
  sections: view.sections.filter(isAreaSection),
}));

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<CuratedViewComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

function viewFor(slug: string): StudioView {
  const view = STUDIO_VIEWS.find((v) => v.slug === slug);
  if (!view) throw new Error(`no such view: ${slug}`);
  return view;
}

/** A schema the fixture may not carry under this key (areas share models). */
function schemaFor(area: string): object {
  return AREA_SCHEMAS[area] ?? AREA_SCHEMAS["01-base/base-persona"];
}

async function mount(slug: string, ansicht?: "agent" | "pattern"): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `en-US`; die Wortlaute unten sind deutsch (C1-d3b).
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  localStorage.clear(); // Paket 13: keine gemerkte Ansicht aus einem anderen Test
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  if (ansicht) TestBed.inject(StudioAnsicht).waehle(ansicht);
  const fixture = TestBed.createComponent(CuratedViewComponent);
  fixture.componentRef.setInput("view", viewFor(slug));
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

/** Answer the pair of requests one section makes when it opens. */
function answer(
  http: HttpTestingController,
  area: string,
  data: Record<string, unknown>,
): void {
  http.expectOne(`/studio/api/config/schema/${area}`).flush(schemaFor(area));
  http
    .expectOne(`/studio/api/config/data/${area}`)
    .flush({ area, data, type: "yaml" });
}

describe("CURATED_VIEWS declaration", () => {
  it("names only real config areas", () => {
    // A typo here is invisible until someone opens the page and reads
    // "Diesen Konfigurationsbereich gibt es nicht."
    const unknown = AREA_SECTIONS.flatMap((view) =>
      view.sections
        .map((s) => s.area)
        .filter((area) => !AREA_KEYS.includes(area)),
    );
    expect(unknown).toEqual([]);
  });

  it("gibt jedem Bereich eine Seite außer „Alle Bereiche“ (ST-9)", () => {
    // Gemessen vor ST-9: acht Bereiche — darunter Preistafel, Gold-Flows und
    // Karten-Pipeline — standen nur als Dateiname unter „Alle Bereiche“.
    const ohneSeite = AREA_KEYS.filter((area) => !areasWithPage().has(area));
    expect(ohneSeite).toEqual([]);
  });

  it("renders every declared panel — no silently empty section", () => {
    // A panel id with no `@case` in the template renders nothing at all: the
    // heading and hint would be gone too, so the page just looks shorter.
    const RENDERED = [
      "rag-areas", "rag-ingest", "mcp-registry", "agent-tester", "master-skill",
      "privacy-purge", "retention", "agent-tools", "agent-skills", "agent-prompt", "agent-probe",
      "anrede", "material-typen",
    ];
    const declared = CURATED_VIEWS.flatMap((view) =>
      view.sections.flatMap((s) => (isAreaSection(s) ? [] : [s.panel])),
    );
    expect(declared.filter((panel) => !RENDERED.includes(panel))).toEqual([]);
  });

  it("führt auf „Prompt & Probelauf“ die Kette entlang, dann die beiden Probeläufe (ST-8, P14)", () => {
    const panels = (slug: string) => CURATED_VIEWS.find((view) => view.slug === slug)!
      .sections.flatMap((s) => (isAreaSection(s) ? [] : [s.panel]));
    expect(panels("agent-prompt")).toEqual(["agent-prompt", "agent-probe", "agent-tester"]);
    // Paket 15: Werkzeuge, Skills und Anrede gelten in beiden Modi — eigene gemeinsame Seiten.
    expect(panels("werkzeuge")).toEqual(["agent-tools"]);
    expect(panels("skills")).toEqual(["master-skill", "agent-skills"]);
    expect(panels("zielgruppen")).toEqual(["anrede"]);
    expect(panels("patterns")).toEqual([]);
  });

  it("names only slugs the view registry actually routes here", () => {
    // Der Kern bleibt: jeder kuratierte Schnitt MUSS in der Registry stehen —
    // sonst gibt es keine Route und die Seite ist unerreichbar.
    //
    // Die Paket-Zusage stand bis 2026-08-13 auf genau `9-4`. Das war so lange
    // richtig, wie alle kuratierten Ansichten aus dem P9-Port stammten; „Agent
    // & Maschine" (D2) ist die erste, die es nicht tut. Eine Erlaubnisliste
    // statt einer gelöschten Zusicherung: ein Tippfehler im Paketnamen soll
    // weiterhin auffallen.
    const ERLAUBT = ["9-4", "P14", "P15"];
    for (const view of CURATED_VIEWS) {
      const registered = STUDIO_VIEWS.find((v) => v.slug === view.slug);
      expect(registered, `slug ${view.slug}`).toBeDefined();
      expect(ERLAUBT, `slug ${view.slug}`).toContain(registered?.paket);
    }
  });

  it("marks the two folder areas as groups, and nothing else", () => {
    // `03-patterns` and `04-personas` hold many documents; GET /config/data
    // answers 404 for them, so an unmarked one renders a dead panel. The
    // reverse is just as wrong: a file key rendered as a group asks
    // /config/elements for a list that does not exist.
    const FOLDERS = new Set(["03-patterns", "04-personas"]);
    for (const view of AREA_SECTIONS) {
      for (const section of view.sections) {
        expect(section.kind === "group", `${view.slug} → ${section.area}`).toBe(
          FOLDERS.has(section.area),
        );
      }
    }
  });

  it("lists every area at most once per view", () => {
    for (const view of AREA_SECTIONS) {
      const areas = view.sections.map((s) => s.area);
      expect(new Set(areas).size, `view ${view.slug}`).toBe(areas.length);
    }
  });

  // ── Paket 14: Heimat je Arbeitsbereich ─────────────────────────────────
  // Zwei Seiten, die dasselbe Dokument bearbeiten, sind zwei Stände — innerhalb EINES
  // Arbeitsbereichs darf ein Bereich deshalb nur eine Heimat haben (bei Feld-Ausschnitten:
  // überschneidungsfrei). Über die Arbeitsbereiche hinweg darf er zweimal stehen (Leitplanken
  // in „Rolle & Grenzen“ und in „Identität“): man ist immer nur in einem, und das Speichern
  // ist versioniert (409 bei fremdem Stand).
  const sichtbar = (ansicht: "agent" | "pattern") => new Set(
    navGroups(ansicht).flatMap((g) => g.views.map((v) => v.slug)));

  /** Paket 15: `ohneFelder` = alle Felder des Schemas außer diesen (Personas ohne Anrede). */
  function ausschnitt(section: CuratedAreaSection): readonly string[] | null {
    if (section.felder) return section.felder;
    if (!section.ohneFelder) return null;
    return fieldPaths(rootField(AREA_SCHEMAS[section.area]))
      .filter((p) => !section.ohneFelder!.includes(p));
  }

  /** Bereich → Feld-Ausschnitte seiner Abschnitte im Arbeitsbereich (`null` = alle Felder). */
  function heimaten(ansicht: "agent" | "pattern"): Map<string, (readonly string[] | null)[]> {
    const slugs = sichtbar(ansicht);
    const map = new Map<string, (readonly string[] | null)[]>();
    for (const view of AREA_SECTIONS.filter((v) => slugs.has(v.slug))) {
      for (const section of view.sections) {
        map.set(section.area, [...(map.get(section.area) ?? []), ausschnitt(section)]);
      }
    }
    for (const [slug, sections] of Object.entries(DASHBOARD_SECTIONS)) {
      if (!slugs.has(slug)) continue;
      for (const section of sections) map.set(section.area, [...(map.get(section.area) ?? []), null]);
    }
    for (const view of CURATED_VIEWS.filter((v) => slugs.has(v.slug))) {
      for (const section of view.sections) {
        const area = isAreaSection(section) ? undefined : PANEL_AREAS[section.panel];
        const felder = isAreaSection(section) ? undefined : PANEL_FELDER[section.panel];
        if (area) map.set(area, [...(map.get(area) ?? []), felder ?? ["(panel)"]]);
      }
    }
    return map;
  }

  /** Bereiche ohne Heimat im Agent-Arbeitsbereich — je mit Grund (Code-Lesart 2026-10-17). */
  const NUR_MUSTER: Readonly<Record<string, string>> = {
    "01-base/base-persona": "Agent: nur Krisen-Züge, die der Muster-Weg beantwortet",
    "02-domain/domain-rules": "Agent: nur Krisen-Züge",
    "02-domain/wlo-plattform-wissen": "Agent: nur Krisen-Züge",
    "01-base/tone-modifiers": "Agent: nur Krisen-Züge",
    "01-base/classify-overrides": "Agent: kein Klassifikator",
    "04-intents/intents": "Agent: kein Klassifikator",
    "04-entities/entities": "Agent: keine Entitäten-Erkennung",
    "04-signals/signal-modulations": "Agent: keine Signale",
    "01-base/placeholder-topics": "Agent: keine Entitäten-Erkennung",
    "04-states/states": "Agent: nur die Zustands-Direktive, Zustand bleibt meist S1",
    "05-canvas/material-types": "Agent: nur der Canvas-Schnellweg, der dort aus ist",
    "05-canvas/type-aliases": "Agent: nur Randwirkung (Typ des Zugs)",
    "05-canvas/persona-priorities": "Agent: nur Randwirkung (Chip-Hinweise)",
  };

  it("gibt jedem Bereich je Arbeitsbereich höchstens eine Heimat, Ausschnitte ohne Überschneidung (P14)", () => {
    for (const ansicht of ["agent", "pattern"] as const) {
      for (const [area, ausschnitte] of heimaten(ansicht)) {
        if (ausschnitte.length === 1) continue;
        expect(ausschnitte.includes(null), `${ansicht}: ${area} ganz und im Ausschnitt`).toBe(false);
        const felder = ausschnitte.flat();
        expect(new Set(felder).size, `${ansicht}: ${area} Felder doppelt`).toBe(felder.length);
      }
    }
  });

  it("kennt beide Schreiber der Server-Liste: MCP-Server und Werkzeuge (Review-Runde 2)", () => {
    // „Werkzeuge“ schreibt `werkzeuge_aus` derselben Liste — ohne Erklärung sähe der Wächter
    // eine spätere Überschneidung (Schalter zurück ins MCP-Panel) nicht.
    for (const ansicht of ["agent", "pattern"] as const) {
      const schreiber = heimaten(ansicht).get("05-knowledge/mcp-servers") ?? [];
      expect(schreiber, ansicht).toHaveLength(2);
      expect(schreiber.flat(), ansicht).toContain("werkzeuge_aus");
    }
  });

  it("gibt jedem Bereich in jedem Arbeitsbereich eine Heimat — außer begründet (P14)", () => {
    const agent = heimaten("agent");
    const muster = heimaten("pattern");
    expect(AREA_KEYS.filter((area) => !agent.has(area) && !(area in NUR_MUSTER))).toEqual([]);
    expect(AREA_KEYS.filter((area) => !muster.has(area))).toEqual([]);
    // Die Ausnahmen stimmen noch: keine steht doch im Agent-Arbeitsbereich.
    expect(Object.keys(NUR_MUSTER).filter((area) => agent.has(area))).toEqual([]);
  });

  it("verteilt 01-base/engine auf Agent, Muster und Betrieb (P14)", () => {
    const felder = (slug: string) => AREA_SECTIONS.find((v) => v.slug === slug)!
      .sections.filter((s) => s.area === "01-base/engine").map((s) => s.felder);
    expect(felder("agent-rolle")).toEqual([["agent_rolle", "agent"]]);
    // Paket 15: die Skill-Brücke steht bei den Skills, nicht mehr bei den Patterns.
    expect(felder("skills")).toEqual([["muster_skills"]]);
    expect(felder("patterns")).toEqual([]);
    expect(felder("betrieb")).toEqual([["mode", "betrieb"]]);
  });

  it("zeigt im Agent-Arbeitsbereich nur die beiden Schutzantworten (P14)", () => {
    const rolle = AREA_SECTIONS.find((v) => v.slug === "agent-rolle")!;
    const patterns = rolle.sections.find((s) => s.area === "03-patterns")!;
    expect(patterns.dokumente).toEqual(["M01", "M02"]);
    // Paket 15: was eine Schutzantwort ausmacht — ohne Routing-Felder (die wirken hier nicht,
    // das Sicherheits-Tor erzwingt M01/M02) und ohne Reiter.
    expect(patterns.feature).toBeUndefined();
    expect(patterns.felder).toEqual([
      "body", "frontmatter.core_rule", "frontmatter.default_tone", "frontmatter.default_length",
      "frontmatter.quick_replies_mode", "frontmatter.forbidden_phrases",
    ]);
  });

  it("leaves no 9-4 view without a definition", () => {
    // Not a wish list: a new 9-4 view added to the registry without an entry
    // here would render the placeholder page and look finished from the nav.
    const missing = STUDIO_VIEWS.filter((v) => v.paket === "9-4")
      .map((v) => v.slug)
      .filter((slug) => !curatedView(slug));
    expect(missing).toEqual([]);
  });

  it("nennt nur Katalog-Schlüssel, die es in beiden Sprachen gibt", () => {
    // Bis C1-d3d standen hier 70 fertige deutsche Texte auf Modulebene — sie
    // frören in der Sprache ein, die beim Laden des Moduls galt. Jetzt sind es
    // Schlüssel, und ein Tippfehler darin wäre unsichtbar bis jemand die Seite
    // öffnet: `t()` gibt den Schlüssel selbst als Überschrift aus. Dieselbe
    // Prüfung wie `views-i18n.spec.ts` für die Ansichts-Registry.
    const keys = [
      ...CURATED_VIEWS.flatMap((view) => [
        view.introKey,
        ...view.sections.flatMap((section) => [
          section.labelKey,
          section.hintKey,
        ]),
      ]),
      // ST-9: die auf Kosten und Evaluation eingebetteten Abschnitte
      ...Object.values(DASHBOARD_SECTIONS).flatMap((sections) =>
        sections.flatMap((section) => [section.labelKey, section.hintKey]),
      ),
    ];
    expect(
      keys.filter((key) => !(key in STUDIO_DE)),
      "fehlt auf Deutsch",
    ).toEqual([]);
    expect(
      keys.filter((key) => !(key in STUDIO_EN)),
      "fehlt auf Englisch",
    ).toEqual([]);
  });

  it("gibt keinem Abschnitt denselben Schlüssel wie einem anderen", () => {
    // Zwei Abschnitte mit demselben Schlüssel tragen dieselbe Überschrift —
    // aus dem Katalog heraus nicht erkennbar, weil beide Sprachen ihn brav
    // führen. Die Sichtprüfung fiele erst auf der Seite auf.
    const keys = CURATED_VIEWS.flatMap((view) =>
      view.sections.map((section) => section.labelKey),
    );
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("ordnet auf Seiten mit Reitern jeden Abschnitt einem Reiter zu (Paket 15)", () => {
    for (const view of CURATED_VIEWS.filter((v) => v.reiter)) {
      const ids = view.reiter!.map((r) => r.id);
      for (const section of view.sections) {
        expect(ids, `${view.slug}: ${section.labelKey}`).toContain(section.reiter);
      }
      for (const id of ids) {
        expect(view.sections.some((s) => s.reiter === id), `${view.slug}: Reiter ${id} leer`)
          .toBe(true);
      }
    }
    expect(curatedView("wissen")?.reiter?.map((r) => r.id)).toEqual(["rag", "mcp"]);
    expect(curatedView("anzeige")?.reiter?.map((r) => r.id))
      .toEqual(["chat", "karten", "kopfzeile", "geraete"]);
    expect(curatedView("fuehrung")?.reiter?.map((r) => r.id)).toEqual(["tour", "lotse", "regeln"]);
    // Rundgang 3: die Sicherheit zuerst — auf beiden Seiten, die sie tragen.
    expect(curatedView("agent-rolle")?.reiter?.map((r) => r.id))
      .toEqual(["sicherheit", "rolle", "regeln", "schutz"]);
    expect(curatedView("identitaet")?.reiter?.map((r) => r.id))
      .toEqual(["sicherheit", "persona", "regeln"]);
  });

  it("springt von der Sicherheitsstufe zu den Safety-Logs (Rundgang 3)", () => {
    for (const slug of ["agent-rolle", "identitaet"]) {
      const sicherheit = curatedView(slug)!.sections.filter(isAreaSection)
        .find((s) => s.area === "01-base/safety-config")!;
      expect(sicherheit.reiter, slug).toBe("sicherheit");
      expect(sicherheit.sprung?.slug, slug).toBe("safety-logs");
    }
  });

  it("keeps the MCP registry off the generic form, which has no SSRF gate", () => {
    // `PUT /config/data/…` validates the model; only `PUT /config/mcp-servers`
    // knows what a server URL means. Listing the area here would put a second,
    // weaker write path for it on the very page that manages MCP.
    const areas = AREA_SECTIONS.flatMap((view) =>
      view.sections.map((s) => s.area),
    );
    expect(areas).not.toContain("05-knowledge/mcp-servers");
  });
});

describe("CuratedViewComponent", () => {
  it("shows one section per configured area, in the declared order", async () => {
    const { el, http } = await mount("anzeige");
    answer(http, "01-base/display-rules", { display_rules: {} });

    const headings = Array.from(el.querySelectorAll("summary .cs-title")).map(
      (h) => h.textContent?.trim(),
    );
    expect(headings).toEqual([
      "Darstellungsregeln",
      "Trefferauswahl und Links",
      "Trefferliste im Text",
      "Kopfzeilen-Navigation",
      "Geräte & Anrede",
    ]);
  });

  it("nimmt Einleitung und Abschnitts-Überschriften aus dem Katalog", async () => {
    // Die Erwartung steht ausgeschrieben und wird NICHT aus derselben Quelle
    // gezogen, gegen die geprüft wird — sonst bestünde der Test auch dann,
    // wenn überall der Schlüssel statt des Textes erschiene.
    const { el, http, fixture } = await mount("anzeige");
    answer(http, "01-base/display-rules", { display_rules: {} });
    expect(el.querySelector(".cv-intro")?.textContent).toContain(
      "Wie Ergebnisse im Widget",
    );

    TestBed.inject(StudioLanguageService).toggle();
    await fixture.whenStable();
    expect(el.querySelector(".cv-intro")?.textContent).toContain(
      "How results appear",
    );
    expect(
      Array.from(el.querySelectorAll("summary .cs-title")).map((h) =>
        h.textContent?.trim(),
      ),
    ).toEqual([
      "Display rules", "Result selection and links", "Result list in the text",
      "Header navigation",
      "Devices & form of address",
    ]);
  });

  it("loads only the section that is open", async () => {
    // Three areas mean six requests on arrival if every section loads eagerly.
    const { http } = await mount("anzeige");
    answer(http, "01-base/display-rules", { display_rules: {} });
    http.verify(); // nothing for the other four sections yet
  });

  it("loads a section the first time it is opened, and not again", async () => {
    const { el, http, fixture } = await mount("anzeige");
    answer(http, "01-base/display-rules", { display_rules: {} });

    const second = el.querySelectorAll("details")[1];
    second.open = true;
    second.dispatchEvent(new Event("toggle"));
    await fixture.whenStable();
    answer(http, "01-base/card-pipeline", { card_pipeline: {} });

    second.open = false;
    second.dispatchEvent(new Event("toggle"));
    second.open = true;
    second.dispatchEvent(new Event("toggle"));
    await fixture.whenStable();
    http.verify(); // reopening must not refetch and discard the edits in it
  });

  it("reports unsaved changes in ANY section, so the leave guard sees them", async () => {
    const { el, http, fixture } = await mount("anzeige");
    answer(http, "01-base/display-rules", { display_rules: {} });

    const second = el.querySelectorAll("details")[1];
    second.open = true;
    second.dispatchEvent(new Event("toggle"));
    await fixture.whenStable();
    answer(http, "01-base/card-pipeline", { card_pipeline: { pool_size: 20 } });
    await tick();
    await fixture.whenStable();

    expect(fixture.componentInstance.dirty()).toBe(false);
    fixture.componentInstance
      .sections()[1]
      .editor.setDoc({ card_pipeline: { pool_size: 30 } });
    await fixture.whenStable();
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it("zeigt im Kopf jedes Abschnitts, wo er wirkt (ST-5)", async () => {
    const { el, http, fixture } = await mount("datenschutz");
    answer(http, "01-base/privacy-config", { logging: {} });
    TestBed.inject(EffectsApi).effects.set({
      engine: "pattern",
      areas: {
        "01-base/privacy-config": { pattern: "voll", agent: "teilweise" },
        "01-base/quality-log-config": { pattern: "voll", agent: "voll" },
      },
    });
    await tick();
    await fixture.whenStable();
    const koepfe = Array.from(el.querySelectorAll("studio-area-section summary"))
      .map((s) => s.textContent?.replace(/\s+/g, " ") ?? "");
    expect(koepfe[0]).toContain("Wirkt in: Muster-Maschine · Agent-Schleife (teilweise)");
    expect(koepfe[1]).toContain("Wirkt in: Muster-Maschine · Agent-Schleife");
  });

  it("warnt, wenn die Vorgabe-Maschine keine Einstellung der Seite nutzt (ST-5)", async () => {
    const { el, fixture } = await mount("material-formate");
    const nurMuster = Object.fromEntries(
      curatedView("material-formate")!.sections.filter(isAreaSection)
        .map((s) => [s.area, { pattern: "voll" as const, agent: "keine" as const }]),
    );
    const effects = TestBed.inject(EffectsApi).effects;
    effects.set({ engine: "agent", areas: nurMuster });
    await fixture.whenStable();
    expect(el.querySelector(".cv-banner")?.textContent).toContain("Agent-Schleife");

    effects.set({ engine: "pattern", areas: nurMuster });
    await fixture.whenStable();
    expect(el.querySelector(".cv-banner")).toBeNull();
  });

  it("sagt im Banner, wenn eine Seite unter der Agent-Schleife nur Krisen-Züge trägt (ST-5)", async () => {
    // Domänenwissen: unter der Agent-Schleife beantwortet der Muster-Weg nur Krisen- und
    // Drohungs-Züge (SF-1). „Wirkt nicht" wäre dort falsch. Seit Paket 14 trägt die
    // Muster-Seite auch die Skill-Brücke (teilweise in beiden) — dort schweigt das Banner.
    const { el, fixture } = await mount("domain-wissen");
    TestBed.inject(EffectsApi).effects.set({
      engine: "agent",
      areas: {
        "02-domain/domain-rules": { pattern: "voll", agent: "krise" },
        "02-domain/wlo-plattform-wissen": { pattern: "voll", agent: "krise" },
      },
    });
    await fixture.whenStable();
    const banner = el.querySelector(".cv-banner")?.textContent ?? "";
    expect(banner).toContain("Krisen");
    expect(banner).not.toContain("keine Einstellung");
  });

  it("lädt nach dem Speichern des Maschinen-Umschalters die Wirkungen neu (Paket 13, E6)",
    async () => {
      const { fixture, http } = await mount("betrieb");
      http.match(() => true); // die Anfragen des offenen ersten Abschnitts
      fixture.componentInstance.sections()[0].changed.emit();
      http.expectOne("/studio/api/config/effects");
    });

  it("lädt die Wirkungen nach anderen Speicherungen nicht neu", async () => {
    const { fixture, http } = await mount("anzeige");
    http.match(() => true);
    fixture.componentInstance.sections()[0].changed.emit();
    http.expectNone("/studio/api/config/effects");
  });

  // Review PR #18 (C6): jede Panelart mit eigenem Speichern zählt für den Verlassen-Schutz —
  // fehlt eine in `dirty`, verlässt ein Entwurf die Seite ohne Rückfrage.
  it("zählt einen Materialtyp-Entwurf als ungespeichert", async () => {
    const { fixture, http } = await mount("material-formate");
    http.match(() => true);
    expect(fixture.componentInstance.dirty()).toBe(false);
    fixture.componentInstance.materialTypen()[0].entwurf.set(
      { id: "neu", label: "Neu", label_en: "", emoji: "", category: "", structure: "" });
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it("zählt eine geänderte Anrede als ungespeichert", async () => {
    const { fixture, http } = await mount("zielgruppen");
    http.match(() => true);
    expect(fixture.componentInstance.dirty()).toBe(false);
    fixture.componentInstance.anreden()[0].zeilen.set([{
      area: "01-base/persona-x", kennung: "P-X", name: "X", doc: null, gewaehlt: "du",
      busy: false, gespeichert: false, fehler: "", konflikt: null,
    }]);
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it("zählt einen umgelegten Werkzeug-Schalter als ungespeichert", async () => {
    const { fixture, http } = await mount("werkzeuge");
    http.match(() => true);
    expect(fixture.componentInstance.dirty()).toBe(false);
    fixture.componentInstance.werkzeuge()[0].reg.servers.set(
      [{ name: "wlo", url: "https://example.org/mcp" } as never]);
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it("liest nach dem Speichern der Aliase die Materialtyp-Liste neu (Review PR #18, C5)", async () => {
    const { fixture, http } = await mount("material-formate");
    http.match(() => true);
    const neu = vi.spyOn(fixture.componentInstance.materialTypen()[0], "nebenbereicheNeu")
      .mockResolvedValue();
    const aliase = fixture.componentInstance.sections()
      .find((s) => s.section().area === "05-canvas/type-aliases")!;
    aliase.changed.emit();
    expect(neu).toHaveBeenCalledTimes(1);
  });

  it("klappt auf Kontext-Aktionen und Tour & Lotse alle Formularabschnitte zu (Rundgang)", () => {
    for (const slug of ["kontext-aktionen", "fuehrung"]) {
      const bereiche = curatedView(slug)!.sections.filter(isAreaSection);
      expect(bereiche.length).toBeGreaterThan(0);
      expect(bereiche.every((s) => s.zugeklappt === true)).toBe(true);
    }
  });

  it("reicht „zugeklappt“ bis ins Formular durch", async () => {
    const { fixture, http } = await mount("kontext-aktionen");
    answer(http, "01-base/context-actions", { context_actions: {} });
    await tick();
    await fixture.whenStable();
    const formular = fixture.debugElement.query(By.directive(SchemaFormComponent));
    expect((formular.componentInstance as SchemaFormComponent).alleZu()).toBe(true);
  });

  it("hält Speichern und Verwerfen beim Scrollen sichtbar (ST-4)", async () => {
    // Bis ST-4 saß die Leiste am Ende langer Formulare — wer oben änderte,
    // musste zum Speichern ans Ende scrollen und sah dabei die Änderung nicht mehr.
    const { el, http, fixture } = await mount("datenschutz");
    answer(http, "01-base/privacy-config", { logging: {} });
    await tick();
    await fixture.whenStable();
    const leiste = el.querySelector<HTMLElement>(".cs-actions")!;
    expect(getComputedStyle(leiste).position).toBe("sticky");
  });

  it("saves one area at a time — a section never writes its neighbour", async () => {
    const { el, http, fixture } = await mount("datenschutz");
    answer(http, "01-base/privacy-config", {
      privacy: { store_messages: true },
    });
    await tick();
    await fixture.whenStable();

    const section = fixture.componentInstance.sections()[0];
    section.editor.setDoc({ privacy: { store_messages: false } });
    await fixture.whenStable();

    const save = el.querySelector<HTMLButtonElement>(".cs-save");
    save?.click();
    await fixture.whenStable();

    const req = http.expectOne(
      "/studio/api/config/data/01-base/privacy-config",
    );
    expect(req.request.method).toBe("PUT");
    expect(req.request.body).toEqual({
      data: { privacy: { store_messages: false } },
    });
    req.flush({
      area: "01-base/privacy-config",
      data: { privacy: { store_messages: false } },
      type: "yaml",
    });
    await fixture.whenStable();
    http.verify(); // quality-log-config was never touched
  });

  it("zeigt eine Abweisung des Servers am Feld, nicht nur als Zeile (ST-2e)", async () => {
    const { el, http, fixture } = await mount("anzeige");
    const schrift = (wert: number) => ({
      display_rules: { inline_documents: { font_size_percent: wert } },
    });
    answer(http, "01-base/display-rules", schrift(85));
    await tick();
    await fixture.whenStable();

    fixture.componentInstance.sections()[0].editor.setDoc(schrift(10));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>(".cs-save")?.click();
    await fixture.whenStable();
    http.expectOne("/studio/api/config/data/01-base/display-rules").flush(
      {
        detail: [{
          loc: ["display_rules", "inline_documents", "font_size_percent"],
          msg: "Input should be greater than or equal to 70",
          type: "greater_than_equal",
          ctx: { ge: 70 },
        }],
      },
      { status: 422, statusText: "Unprocessable Content" },
    );
    await tick();
    await fixture.whenStable();

    const feld = el.querySelector<HTMLInputElement>('input[id$="font_size_percent"]')!;
    expect(feld.getAttribute("aria-invalid")).toBe("true");
    expect(el.textContent).toContain("Mindestens 70.");
  });

  it("offers the raw source of each area, because the form cannot reach every key", async () => {
    const { el, http, fixture } = await mount("begruessung");
    answer(http, "01-base/welcome-config", { welcome: {} });
    await tick();
    await fixture.whenStable();

    const link = el.querySelector<HTMLAnchorElement>(".cs-raw-link");
    expect(link?.getAttribute("href")).toBe("/bereich/01-base/welcome-config");
  });
});

describe("CuratedViewComponent — Reiter (Paket 15)", () => {
  it("trennt Wissensbereiche und MCP-Server in Reiter; Abschnitte bleiben eingehängt", async () => {
    const { el, fixture } = await mount("wissen");
    const reiter = Array.from(el.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    expect(reiter.map((r) => r.textContent?.trim())).toEqual(["Wissensbereiche", "MCP-Server"]);
    // Review-Runde 2: je Reiter ein eigenes Panel — verborgen wird das Panel, nicht der Abschnitt.
    const mcp = () => el.querySelector("studio-mcp-registry")!.closest<HTMLElement>('[role="tabpanel"]')!;
    const rag = () => el.querySelector("studio-rag-areas")!.closest<HTMLElement>('[role="tabpanel"]')!;
    expect(mcp().hidden).toBe(true);
    expect(rag().hidden).toBe(false);
    reiter[1].click();
    await fixture.whenStable();
    expect(mcp().hidden).toBe(false);
    expect(rag().hidden).toBe(true);
    expect(mcp().getAttribute("aria-labelledby")).toBe("tab-mcp");
  });

  it("jedes aria-controls zeigt auf ein vorhandenes Panel, auch beim inaktiven Reiter (Review-Runde 2)", async () => {
    const { el } = await mount("wissen");
    for (const tab of Array.from(el.querySelectorAll('[role="tab"]'))) {
      const ziel = el.querySelector(`[id="${tab.getAttribute("aria-controls")}"]`);
      expect(ziel?.getAttribute("role"), tab.textContent ?? "").toBe("tabpanel");
    }
  });
});

describe("CuratedViewComponent — Skills je Arbeitsbereich (Paket 16, C8)", () => {
  const abschnitte = (el: HTMLElement) => Array.from(el.querySelectorAll<HTMLDetailsElement>("details.cs"));
  const titel = (d: HTMLDetailsElement) => d.querySelector(".cs-title")?.textContent?.trim();

  it("stellt im Muster-Arbeitsbereich die Skill-Brücke zuerst und offen", async () => {
    const { el } = await mount("skills", "pattern");
    const [erster, ...rest] = abschnitte(el);
    expect(titel(erster)).toBe("Skill-Brücke");
    expect(erster.open).toBe(true);
    expect(erster.textContent).toContain("nur im Muster-Modus");
    expect(rest.some((d) => d.open)).toBe(false);
  });

  it("lässt im Agent-Arbeitsbereich den Master-Skill vorn — mit „Wirkt in: Agent-Schleife“", async () => {
    const { el } = await mount("skills", "agent");
    const [erster] = abschnitte(el);
    expect(titel(erster)).toBe("Master-Skill");
    expect(erster.open).toBe(true);
    expect(erster.querySelector("summary")?.textContent).toContain("Wirkt in: Agent-Schleife");
  });
});
