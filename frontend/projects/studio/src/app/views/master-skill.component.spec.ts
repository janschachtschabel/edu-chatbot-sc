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
import {
  MasterSkillComponent,
  type MasterSkillStatus,
} from "./master-skill.component";

const tick = (): Promise<unknown> =>
  new Promise((resolve) => setTimeout(resolve, 0));

const SUM = "8bbf014fa385d526".padEnd(64, "0");

const STATUS: MasterSkillStatus = {
  enabled: true,
  node_id: "knoten-1",
  cached: true,
  fetched_at: "2026-09-26T18:38:28+00:00",
  length: 27928,
  sha256: SUM,
  last_error: null,
  ttl_seconds: 300,
  text: "# Chatbot Masterskill\n\n## Aktivierung",
  edit_url: "https://repo.example/edu-sharing/services/md-editor/?nodeId=knoten-1&field=file",
  view_url: "https://repo.example/edu-sharing/components/render/knoten-1",
};

interface Harness {
  fixture: ComponentFixture<MasterSkillComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(status: object = STATUS): Promise<Harness> {
  TestBed.resetTestingModule();
  // Siehe rag-ingest.component.spec.ts — jsdom meldet `en-US`.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(MasterSkillComponent);
  fixture.componentRef.setInput("section", {
    panel: "master-skill",
    labelKey: "curated.agent.masterSkill.label",
    hintKey: "curated.agent.masterSkill.hint",
  });
  fixture.componentRef.setInput("open", true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne("/studio/api/master-skill").flush(status);
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

describe("MasterSkillComponent", () => {
  it("zeigt Zustand, Kennung, Länge und eine kurze Prüfsumme", async () => {
    const { el } = await mount();
    const facts = el.querySelector(".ms-facts")?.textContent ?? "";
    expect(facts).toContain("Aktiv");
    expect(facts).toContain("knoten-1");
    expect(facts).toContain("27.928");
    expect(facts).toContain("8bbf014fa385");
    expect(facts).not.toContain(SUM);
  });

  it("öffnet den Master-Skill zum Bearbeiten im md-editor, in einem neuen Tab", async () => {
    // Paket F (Nutzer 2026-09-29): der Editor des Repositoriums lässt sich auch
    // außerhalb von edu-sharing öffnen — bis dahin führte der Knopf nur auf die
    // Render-Seite.
    const { el } = await mount();
    const link = el.querySelector<HTMLAnchorElement>("a.ms-edit");
    expect(link?.getAttribute("href")).toBe(STATUS.edit_url);
    expect(link?.textContent).toContain("Im Editor bearbeiten");
    expect(link?.target).toBe("_blank");
    expect(link?.rel).toContain("noopener");
    expect(link?.rel).toContain("noreferrer");
    // Review 2026-09-29: der Linkname nennt, WAS bearbeitet wird — in der
    // Linkliste eines Screenreaders fehlt sonst der Gegenstand.
    expect(link?.querySelector(".sr")?.textContent).toContain("Master-Skill");
    expect(link?.querySelector(".sr")?.textContent).toContain("neuen Tab");
    const hinweis = el.querySelector(".ms-edit-hint");
    expect(hinweis?.textContent).toContain("edu-sharing-Anmeldung");
    // Wer per Tab zum Link springt, hört die Voraussetzung mit.
    expect(link?.getAttribute("aria-describedby")).toBe(hinweis?.id);
  });

  it("zeigt den Knoten zusätzlich im Repositorium, ebenfalls in einem neuen Tab", async () => {
    const { el } = await mount();
    const link = el.querySelector<HTMLAnchorElement>("a.ms-view");
    expect(link?.getAttribute("href")).toBe(STATUS.view_url);
    expect(link?.textContent).toContain("Im Repositorium ansehen");
    expect(link?.target).toBe("_blank");
    expect(link?.rel).toContain("noopener");
    expect(link?.rel).toContain("noreferrer");
    expect(link?.querySelector(".sr")?.textContent).toContain("Master-Skill");
    expect(link?.querySelector(".sr")?.textContent).toContain("neuen Tab");
  });

  it("mit Kennung, aber ohne Adressen: kein toter Link", async () => {
    // Review 2026-09-29: der einzige Fall ohne Adresse hatte auch keine Kennung —
    // die Wächter an den Links liefen so nie für sich.
    const ohne = await mount({ ...STATUS, edit_url: null, view_url: "" });
    expect(ohne.el.querySelector("a.ms-edit")).toBeNull();
    expect(ohne.el.querySelector("a.ms-view")).toBeNull();
    expect(ohne.el.querySelector(".ms-edit-hint")).toBeNull();
    expect(ohne.el.querySelector(".ms-reload")).not.toBeNull();
    const nurAnsehen = await mount({ ...STATUS, edit_url: null });
    expect(nurAnsehen.el.querySelector("a.ms-edit")).toBeNull();
    expect(nurAnsehen.el.querySelector("a.ms-view")).not.toBeNull();
  });

  it("zeigt den Wortlaut als reinen Text, nie als HTML", async () => {
    const { el } = await mount({ ...STATUS, text: "# A\n<img src=x onerror=alert(1)>" });
    const pre = el.querySelector(".ms-pre");
    expect(pre?.textContent).toBe("# A\n<img src=x onerror=alert(1)>");
    expect(el.querySelector(".ms-pre img")).toBeNull();
  });

  it("„Neu laden“ ruft den POST und meldet das Ergebnis", async () => {
    const { el, http, fixture } = await mount();
    el.querySelector<HTMLButtonElement>(".ms-reload")?.click();
    await fixture.whenStable();
    expect(el.querySelector<HTMLButtonElement>(".ms-reload")?.disabled).toBe(true);

    const req = http.expectOne("/studio/api/master-skill/reload");
    expect(req.request.method).toBe("POST");
    req.flush({ ...STATUS, sha256: "ffff".padEnd(64, "0") });
    await tick();
    await fixture.whenStable();

    expect(el.querySelector(".ms-facts")?.textContent).toContain("ffff00000000");
    expect(el.querySelector(".cs-status")?.textContent).toContain("Neu geladen");
  });

  it("ein gescheitertes „Neu laden“ ist ein Fehler, keine Erfolgsmeldung", async () => {
    // Review-Befund 2026-09-26: das Backend antwortet auch dann mit 200 und
    // nennt den Grund in `last_error` — der Knopf meldete trotzdem Erfolg.
    const { el, http, fixture } = await mount();
    el.querySelector<HTMLButtonElement>(".ms-reload")?.click();
    await fixture.whenStable();
    http.expectOne("/studio/api/master-skill/reload")
      .flush({ ...STATUS, last_error: "TimeoutError: MCP weg" });
    await tick();
    await fixture.whenStable();

    expect(el.querySelector(".cs-status")?.textContent).not.toContain("Neu geladen");
    expect(el.querySelector(".ms-reload-error")?.getAttribute("role")).toBe("alert");
    expect(el.querySelector(".ms-reload-error")?.textContent).toContain("MCP weg");
  });

  it("abgeschaltet: sagt, dass der Wortlaut nur zeigt, was gelten würde", async () => {
    const { el } = await mount({ ...STATUS, enabled: false });
    expect(el.querySelector(".ms-facts")?.textContent).toContain("Abgeschaltet");
    expect(el.querySelector(".ms-off-note")?.textContent).toContain("MASTER_SKILL_ENABLED");
  });

  it("eingeschaltet: kein Abschalt-Hinweis", async () => {
    const { el } = await mount();
    expect(el.querySelector(".ms-off-note")).toBeNull();
  });

  it("ohne Kennung: Hinweis statt Link und Wortlaut", async () => {
    const { el } = await mount({
      ...STATUS, node_id: "", cached: false, text: null, edit_url: null, view_url: null,
      sha256: null, length: null, fetched_at: null,
    });
    expect(el.querySelector(".ms-empty")?.textContent).toContain("MASTER_SKILL_NODE_ID");
    expect(el.querySelector("a.ms-edit")).toBeNull();
    expect(el.querySelector("a.ms-view")).toBeNull();
    expect(el.querySelector(".ms-edit-hint")).toBeNull();
    expect(el.querySelector(".ms-pre")).toBeNull();
  });

  it("ein gescheiterter Abruf im Backend steht als Warnung da", async () => {
    const { el } = await mount({
      ...STATUS, cached: false, text: null, sha256: null, length: null,
      last_error: "TimeoutError: MCP weg",
    });
    expect(el.querySelector(".ms-error")?.textContent).toContain("MCP weg");
  });

  it("HTTP-Fehler: Fehlerzustand mit Erneut-Versuchen", async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    const fixture = TestBed.createComponent(MasterSkillComponent);
    fixture.componentRef.setInput("section", {
      panel: "master-skill",
      labelKey: "curated.agent.masterSkill.label",
      hintKey: "curated.agent.masterSkill.hint",
    });
    fixture.componentRef.setInput("open", true);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.expectOne("/studio/api/master-skill")
      .flush("kaputt", { status: 502, statusText: "Bad Gateway" });
    await tick();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector("[role=alert]")).not.toBeNull();
    expect(el.querySelector("[role=alert] button")).not.toBeNull();
  });
});
