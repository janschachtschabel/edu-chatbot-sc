// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ApplicationRef, provideZonelessChangeDetection } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { EffectsApi } from "../core/effects-api.service";
import { STUDIO_LOCALE_STORAGE_KEY } from "../i18n/studio-language.service";
import { ArchitectureReferenceComponent } from "./architecture-reference.component";
import {
  HOST_ATTRIBUTES,
  HOST_EVENTS,
  HOST_OUTPUTS,
} from "./widget-contract-data";
import { provideRouter } from "@angular/router";

/**
 * The hull composes four section components; two of them need providers of
 * their own (the catalogue reads `/config/data/…`, the knowledge section links
 * to the Sicherung view). Both are flushed here so the hull's own assertions
 * never depend on a pending request.
 *
 * Die Sprache wird gesetzt, nicht geerbt (C1-d5a1): der Runner meldet
 * `navigator.language = en-US`, also spräche die Hülle ohne diese Zeile
 * englisch — und die deutschen Zusagen unten wären dann keine Aussage über die
 * Vorgabe, sondern ein Zufall.
 */
function mount(locale: "de" | "en" = "de"): HTMLElement {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(ArchitectureReferenceComponent);
  fixture.detectChanges();
  TestBed.inject(HttpTestingController)
    .expectOne("/studio/api/config/data/05-canvas/material-types")
    .flush({
      area: "05-canvas/material-types",
      type: "yaml",
      data: { material_types: [] },
    });
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe("ArchitectureReferenceComponent", () => {
  it("uses native disclosures, so every section is keyboard-operable", () => {
    // ALT hand-rolled `useState(open)` + a toggle button per section
    // (InfoView.tsx:22-38). `<details>` is expandable for assistive technology
    // and findable by in-page search without any of that.
    const el = mount();
    const sections = el.querySelectorAll("details");
    expect(sections.length).toBeGreaterThanOrEqual(8);
    for (const section of Array.from(sections)) {
      expect(section.querySelector(":scope > summary")).toBeTruthy();
    }
  });

  it("opens on the two engines and leaves the rest closed", () => {
    // Paket 6, S3: seit Z2 (D-15) bleiben beide Maschinen im Betrieb — der
    // Abschnitt über sie steht vorn und offen; die Pipeline darunter ist die
    // der Muster-Maschine und sagt das.
    const el = mount();
    const open = Array.from(el.querySelectorAll("details")).filter(
      (d) => d.open,
    );
    expect(open).toHaveLength(1);
    expect(open[0].textContent).toContain("Zwei Maschinen");
    expect(el.textContent).toContain("Muster-Maschine: die Verarbeitungs-Pipeline");
  });

  it("documents every host attribute the element accepts", () => {
    // This table is a specification, not decoration: an attribute missing here is
    // how `data-position` (8-5) and `inline-result-grouping` (8-7) stayed dead
    // long enough to ship. ALT's table listed 17 of the 18; `language` came
    // with C1-c, `embed-mode` with U1, `size` with U2a, `show-cards` with U2b,
    // `theme` with U4a, `ticket` with the repository-embedding mode
    // (2026-08-12), `engine` with the machine switch (2026-08-13) and
    // `result-schema` with the machine-readable result (2026-08-14), and
    // `start-replies` + `show-welcome` with the per-embed welcome the same day,
    // which makes 28.
    const el = mount();
    const rows = el.querySelectorAll(".ar-table code");
    const documented = Array.from(rows).map((c) => c.textContent?.trim());
    for (const { attr } of HOST_ATTRIBUTES) {
      expect(documented, `Attribut ${attr}`).toContain(attr);
    }
    expect(HOST_ATTRIBUTES).toHaveLength(32);  // +quick-replies-max (O-B2, 2026-08-20)
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain(
      "inline-result-grouping",
    );
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("language");
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("embed-mode");
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("size");
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("show-cards");
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("theme");
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("ticket");
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain("engine");
  });

  it("names each attribute group once instead of on every row", () => {
    // C1-d5b2: die Gruppe ist Anzeigetext UND Unterscheidungsmerkmal —
    // `isGroupStart` vergleicht sie mit der Vorzeile. Uebersetzt werden darf sie
    // deshalb nur so, dass die Zeilen weiter in fuenf Bloecke zerfallen; in
    // beiden Sprachen gepinnt, weil eine Sprache das allein nicht zeigt.
    const groupsOf = (locale: "de" | "en"): (string | undefined)[] =>
      Array.from(mount(locale).querySelectorAll(".ar-group"))
        .map((c) => c.textContent?.trim())
        .filter((label) => label !== "");
    expect(groupsOf("de")).toEqual([
      "Basis",
      "Session",
      "Kontext",
      "Anzeige",
      "Integration",
    ]);
    expect(groupsOf("en")).toEqual([
      "Basics",
      "Session",
      "Context",
      "Display",
      "Integration",
    ]);
  });

  it("lists the four window events and the four Angular outputs", () => {
    const el = mount();
    const text = el.textContent ?? "";
    for (const event of HOST_EVENTS) expect(text).toContain(event.name);
    // ALT claimed a fifth output, `(pageAction)`, which its own widget never
    // declared (widget.component.ts:119-146) — page-action is a window event.
    expect(HOST_OUTPUTS).toHaveLength(4);
    expect(HOST_OUTPUTS).not.toContain("pageAction");
    expect(text).toContain("boerdi:page-action");
    expect(text).toContain("nur als window-Event");
    // C1-d5b2: die Wann-Spalte mischt Prosa und Bezeichner. Uebersetzt wird die
    // Prosa, `emit-guide-suggestion="true"` bleibt wortgleich stehen.
    const en = mount("en").textContent ?? "";
    expect(en).toContain("always active (window event only)");
    expect(en).toContain('emit-guide-suggestion="true"');
  });

  it("describes the self-ID override as it works in NEU", () => {
    // ALT's row cited the routing rule `lookup_persona_self_id__*` two sections
    // after saying that engine was removed. NEU has `persona_overrides` in
    // classify-overrides.yaml, rendered into the classifier prompt.
    const el = mount();
    const text = el.textContent ?? "";
    expect(text).toContain("persona_overrides");
    expect(text).toContain("classify-overrides.yaml");
  });

  it("keeps wide tables inside their own scroll box", () => {
    // SC 1.4.10: the page itself must never scroll sideways at 320px.
    const el = mount();
    for (const table of Array.from(el.querySelectorAll(".ar-table"))) {
      const boxed =
        table.closest(".ar-scroll") !== null ||
        table.classList.contains("ar-table--fields");
      expect(boxed, table.querySelector("th")?.textContent ?? "?").toBe(true);
    }
  });

  it("sends the reader to the Übersicht tab for the live counts", () => {
    // The figures live in one place; repeating them here is what went stale in
    // ALT's "Anzahl" column.
    expect(mount().textContent).toContain("stehen im Tab „Übersicht“");
  });

  it("spricht englisch, wenn die Sprache englisch ist", () => {
    // Der Beleg, den der Katalog-Test nicht liefern kann: dass die Wahl die
    // Vorlage erreicht. Geprüft wird an drei Gattungen — Überschrift, Fliesstext
    // und Tabellenkopf —, weil jede einen anderen Weg durch die Vorlage nimmt.
    const text = mount("en").textContent ?? "";
    expect(text).toContain("Architecture reference");
    expect(text).toContain("Pattern engine: the processing pipeline");
    expect(text).toContain("Token behaviour");
    expect(text).not.toContain("Verarbeitungs-Pipeline");
  });

  it("übersetzt auch die Tabellenzeilen, nicht nur die Prosa um sie herum", () => {
    // C1-d5a2: die Zeilen kommen aus `reference-data.ts` und nahmen bis dahin
    // einen anderen Weg in die Vorlage als der Fliesstext. Gepinnt wird je eine
    // Zelle aus drei verschiedenen Tabellen.
    const de = mount().textContent ?? "";
    expect(de).toContain("Prompt-Zusammensetzung");
    expect(de).toContain("Wird nie entladen.");
    expect(de).toContain("Emotionale und situative Hinweise");

    const en = mount("en").textContent ?? "";
    expect(en).toContain("Prompt assembly");
    expect(en).toContain("Never unloaded.");
    expect(en).toContain("Emotional and situational cues");
    expect(en).not.toContain("Prompt-Zusammensetzung");
  });

  it("übersetzt den Fluss-Abschnitt: Karten wie Beispiel-Turn", () => {
    // C1-d5c1. Die Wirkungs-Karten und der durchgespielte Turn kommen aus
    // `reference-flow-data.ts` und nahmen bisher denselben Weg wie die
    // Architektur-Zeilen vor C1-d5a2: als fertige Saetze aus der Datendatei.
    const de = mount().textContent ?? "";
    expect(de).toContain("Wechselwirkungen");
    expect(de).toContain("Beispiel: ein kompletter Turn");
    expect(de).toContain("Risiko niedrig, keine Blockade.");

    const en = mount("en").textContent ?? "";
    expect(en).toContain("How the pieces influence each other");
    expect(en).toContain("Example: one complete turn");
    expect(en).toContain("Risk low, no block.");
    expect(en).not.toContain("Wechselwirkungen");
  });

  it("übersetzt den Wissens-Abschnitt samt seinem Verweis", () => {
    // C1-d5b1. Der Verweis auf die Sicherung trägt eine VOLLSTÄNDIGE Wortgruppe
    // (Muster aus C1-d4a) — deshalb wird er hier mitgeprüft: ein Verweis, dessen
    // Beschriftung nur ein Satzbruchstück ist, wäre in der zweiten Sprache
    // weder übersetzbar noch verständlich.
    const de = mount();
    expect(de.textContent).toContain("Wissensquellen: RAG und MCP");
    expect(de.textContent).toContain("Themenseiten-Auflösung");
    expect(de.querySelector('a[href="/sicherung"]')?.textContent?.trim()).toBe(
      "Bedient wird das alles in der Sicherung",
    );

    const en = mount("en");
    expect(en.textContent).toContain("Knowledge sources: RAG and MCP");
    expect(en.textContent).toContain("Topic-page resolution");
    expect(en.querySelector('a[href="/sicherung"]')?.textContent?.trim()).toBe(
      "All of this is operated in the backup view",
    );
  });

  it("lässt Bezeichner in Ruhe, auch wenn die Zelle übersetzt wird", () => {
    // `safety.enforced_pattern` und die Modulations-Felder sind Bezeichner aus
    // dem Code, keine Prosa: sie stehen im `<code>` und muessen in beiden
    // Sprachen wortgleich bleiben.
    for (const locale of ["de", "en"] as const) {
      const codes = Array.from(mount(locale).querySelectorAll("code")).map(
        (c) => c.textContent,
      );
      expect(codes, locale).toContain("safety.enforced_pattern");
      expect(codes, locale).toContain("format_follow_up");
    }
  });

  it("lässt den Stern in signal_*_fit stehen, statt ihn als Auszeichnung zu lesen", () => {
    // `splitRich` liest `*so*` als Hervorhebung. Der Bezeichner trägt einen
    // Stern INNERHALB eines Backtick-Paars: das Paar gewinnt, sonst verschwänden
    // die Sternchen und der Name wäre still falsch.
    const el = mount();
    const codes = Array.from(el.querySelectorAll("code")).map(
      (c) => c.textContent,
    );
    expect(codes).toContain("signal_*_fit");
  });
});

// ── Paket 6, S3: die Referenz beschreibt beide Maschinen ──────────────────
describe("ArchitectureReferenceComponent — zwei Maschinen", () => {
  it("stellt Muster-Maschine und Agent-Schleife Zeile für Zeile gegenüber", () => {
    const el = mount();
    const tabelle = el.querySelector("studio-reference-machines table")!;
    const zeilen = Array.from(tabelle.querySelectorAll("tbody th")).map(
      (th) => th.textContent!.trim());
    expect(zeilen).toEqual(["Einordnung", "Steuerung", "Werkzeuge", "Ablauf", "Schreiben"]);
    expect(tabelle.textContent).toContain("wissen_suchen");
    expect(tabelle.textContent).toContain("nur mit persönlicher Anmeldung");
  });

  it("sagt, dass Krise und Bedrohung auch im Agent-Modus die Muster-Maschine beantwortet", () => {
    const el = mount();
    expect(el.querySelector("studio-reference-machines")?.textContent)
      .toContain("auch im Agent-Modus die Muster-Maschine");
  });

  it("nennt die Vorgabe dieser Anlage, sobald sie bekannt ist — sonst nichts", () => {
    const el = mount();
    expect(el.querySelector(".rm-current")).toBeNull();
    TestBed.inject(EffectsApi).effects.set({ engine: "agent", areas: {} });
    TestBed.inject(ApplicationRef).tick();
    expect(el.querySelector(".rm-current")?.textContent).toContain("Agent-Schleife");
  });

  it("trägt keine Port-Notizen und keine feste Werkzeugzahl mehr", () => {
    // „ALT nannte …“ war eine Notiz für die Portierung, keine für die Redaktion;
    // die Zahl 12 stimmte längst nicht mehr (Werkzeugliste: Agent-Seite).
    const el = mount();
    expect(el.textContent).not.toContain("ALT nannte");
    expect(el.textContent).not.toMatch(/stellt \d+ Werkzeug/);
    expect(el.textContent).toContain("Werkzeuge und Sperren");
  });

  it("beschreibt die beiden Maschinen auch auf Englisch", () => {
    const el = mount("en");
    expect(el.textContent).toContain("Two engines: pattern and agent");
    expect(el.textContent).toContain("Pattern engine: the processing pipeline");
  });

  it("zeigt den Weg eines Zugs mit den 13 Knoten des Graphen und seinen drei frühen Ausgängen", () => {
    // Paket 6, S3 (Review): `graph/build.py` — nur tour, context_greeting und
    // preflight beenden einen Zug früh; der Seitenkontext läuft immer weiter.
    const el = mount();
    const schritte = Array.from(el.querySelectorAll(".rm-flow > li"));
    expect(schritte.map((li) => li.querySelector("code")?.textContent)).toEqual([
      "setup", "tour", "page_context_enrich", "context_greeting", "persist_user", "preflight",
      "assess", "safety_log", "merge", "route", "respond", "assemble", "persist",
    ]);
    const frueh = schritte.filter((li) => li.textContent!.includes("Kann den Zug hier beenden."));
    expect(frueh.map((li) => li.querySelector("code")?.textContent))
      .toEqual(["tour", "context_greeting", "preflight"]);
    expect(el.querySelector("studio-reference-machines")?.textContent)
      .toContain("der Seitenkontext läuft immer weiter");
  });

  it("nennt die sieben Phasen als Sicht auf die Muster-Maschine, nicht als Ablauf jeder Nachricht", () => {
    const el = mount();
    expect(el.textContent).not.toContain("durchläuft jede Nutzernachricht sieben Phasen");
  });
});
