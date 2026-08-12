// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import {
  STUDIO_LOCALE_STORAGE_KEY,
  StudioLanguageService,
} from "../i18n/studio-language.service";
import {
  compareToolsets,
  McpRegistryComponent,
} from "./mcp-registry.component";

const tick = (): Promise<unknown> =>
  new Promise((resolve) => setTimeout(resolve, 0));

const SERVERS = [
  {
    id: "wlo-mcp",
    name: "WLO",
    url: "http://intern:8080/mcp",
    description: "Primär",
    enabled: true,
    tools: ["search_wlo_all"],
    tool_descriptions: { search_wlo_all: "Sucht alles" },
    url_source: "env",
    url_env_var: "MCP_SERVER_URL",
    url_readonly: true,
  },
  {
    id: "extra",
    name: "Extra",
    url: "https://extra.example/mcp",
    description: "",
    enabled: false,
    tools: [],
  },
];

interface Harness {
  fixture: ComponentFixture<McpRegistryComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(servers: unknown[] = SERVERS): Promise<Harness> {
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
  const fixture = TestBed.createComponent(McpRegistryComponent);
  fixture.componentRef.setInput("section", {
    panel: "mcp-registry",
    labelKey: "curated.wissen.mcp.label",
    hintKey: "curated.wissen.mcp.hint",
  });
  fixture.componentRef.setInput("open", true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne("/studio/api/config/mcp-servers").flush(servers);
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

describe("McpRegistryComponent", () => {
  it("lists every registered server", async () => {
    // Über die Feldwerte und nicht über `textContent`: die Namen stehen in
    // `<input [value]>`, wo sie kein Textknoten sind. Bis C1-d3c ging der Test
    // dennoch durch — das `sr`-Bruchstück am Entfernen-Knopf trug den Namen
    // zufällig in den Text. Mit dem Knopfnamen in `aria-label` ist dieser
    // Umweg weg, und die Prüfung sieht jetzt hin, wo der Wert wirklich steht.
    const { el } = await mount();
    expect(el.querySelectorAll(".mr-row")).toHaveLength(2);
    expect(
      Array.from(el.querySelectorAll<HTMLInputElement>(".mr-name")).map(
        (i) => i.value,
      ),
    ).toEqual(["WLO", "Extra"]);
  });

  it("shows each tool with the description the live server reported", async () => {
    // `get_node_details` and `get_nodes_details` differ by one letter; the
    // description is the only thing that tells them apart.
    const { el } = await mount();
    const tag = el.querySelector(".mr-tool");
    expect(tag?.textContent).toContain("search_wlo_all");
    expect(tag?.getAttribute("title")).toBe("Sucht alles");
  });

  it("locks the primary server’s URL and says where it comes from", async () => {
    const { el } = await mount();
    const url = el.querySelectorAll<HTMLInputElement>(".mr-url")[0];
    expect(url.disabled).toBe(true);
    expect(el.textContent).toContain("MCP_SERVER_URL");
    expect(el.querySelectorAll<HTMLButtonElement>(".mr-del")[0].disabled).toBe(
      true,
    );
  });

  it("trägt den Namen der Umgebungsvariablen als Wert im Satz, nicht als Auszeichnung", async () => {
    // Muster von `login.passwordEnv`: der Satz bleibt als Ganzes übersetzbar,
    // der Wert reist als Platzhalter. Das kostet die `<code>`-Auszeichnung —
    // wo im Satz sie steht, ist je Sprache verschieden, und Markup im Katalog
    // hat bislang kein einziger Eintrag.
    const { el, fixture } = await mount();
    const hilfe = el.querySelectorAll(".mr-row")[0].querySelector(".mr-help");
    expect(hilfe?.textContent).toContain("Umgebungsvariable MCP_SERVER_URL");
    expect(hilfe?.querySelector("code")).toBeNull();

    TestBed.inject(StudioLanguageService).toggle();
    await fixture.whenStable();
    expect(
      el.querySelectorAll(".mr-row")[0].querySelector(".mr-help")?.textContent,
    ).toContain("MCP_SERVER_URL");
  });

  it("gibt dem Entfernen-Knopf einen zugänglichen Namen mit seinem Server", async () => {
    // Zwei Zeilen, zweimal „Entfernen" — bis C1-d3c stand das Ziel in einem
    // `sr`-Bruchstück, das sich nicht übersetzen liess (C1-d3a).
    const { el } = await mount();
    expect(el.querySelector(".mr-row .sr")).toBeNull();
    expect(
      el
        .querySelectorAll<HTMLButtonElement>(".mr-del")[1]
        .getAttribute("aria-label"),
    ).toBe("Entfernen — Extra");
  });

  it("marks itself unsaved as soon as something is changed", async () => {
    const { el, fixture } = await mount();
    expect(fixture.componentInstance.dirty()).toBe(false);
    const toggle = el.querySelectorAll<HTMLInputElement>(".mr-enabled")[1];
    toggle.checked = true;
    toggle.dispatchEvent(new Event("change"));
    await fixture.whenStable();
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it("saves the whole registry, because the endpoint replaces it", async () => {
    const { el, fixture, http } = await mount();
    const toggle = el.querySelectorAll<HTMLInputElement>(".mr-enabled")[1];
    toggle.checked = true;
    toggle.dispatchEvent(new Event("change"));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>(".mr-save")?.click();
    await fixture.whenStable();

    const req = http.expectOne("/studio/api/config/mcp-servers");
    expect(req.request.method).toBe("PUT");
    const sent = req.request.body as {
      servers: { id: string; enabled: boolean }[];
    };
    expect(sent.servers.map((s) => s.id)).toEqual(["wlo-mcp", "extra"]);
    expect(sent.servers[1].enabled).toBe(true);
  });

  it("surfaces the server’s reason when a save is refused", async () => {
    // An internal URL is rejected by the SSRF gate; "gespeichert" would be a lie.
    const { el, fixture, http } = await mount();
    const url = el.querySelectorAll<HTMLInputElement>(".mr-url")[1];
    url.value = "http://10.1.2.3/mcp";
    url.dispatchEvent(new Event("input"));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>(".mr-save")?.click();
    await fixture.whenStable();

    http
      .expectOne("/studio/api/config/mcp-servers")
      .flush(
        { detail: "MCP-Server 'extra': private Adresse" },
        { status: 400, statusText: "Bad Request" },
      );
    await tick();
    await fixture.whenStable();

    expect(el.querySelector('[role="alert"]')?.textContent?.trim()).toBe(
      "MCP-Server 'extra': private Adresse",
    );
    expect(fixture.componentInstance.dirty()).toBe(true); // still unsaved, honestly
  });

  it("adds a server locally and only writes it on save", async () => {
    const { el, fixture, http } = await mount();
    el.querySelector<HTMLButtonElement>(".mr-add")?.click();
    await fixture.whenStable();
    expect(el.querySelectorAll(".mr-row")).toHaveLength(3);
    http.verify(); // nothing written yet
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it("refuses to save a server without a kennung, which the store drops silently", async () => {
    // `save_mcp_servers` skips every entry without an id (config_loader/mcp.py),
    // so a filled-in row with no kennung would just be gone after saving.
    const { el, fixture, http } = await mount();
    el.querySelector<HTMLButtonElement>(".mr-add")?.click();
    await fixture.whenStable();

    const save = el.querySelector<HTMLButtonElement>(".mr-save");
    expect(save?.disabled).toBe(true);
    expect(el.textContent).toContain("Kennung");
    save?.click();
    await fixture.whenStable();
    http.verify(); // nothing written

    const id = el.querySelectorAll<HTMLInputElement>(".mr-id")[2];
    id.value = "neu";
    id.dispatchEvent(new Event("input"));
    await fixture.whenStable();
    expect(el.querySelector<HTMLButtonElement>(".mr-save")?.disabled).toBe(
      false,
    );
  });

  it("removes a server from the list it is about to save", async () => {
    const { el, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>(".mr-del")[1].click();
    await fixture.whenStable();
    expect(el.querySelectorAll(".mr-row")).toHaveLength(1);
    expect(fixture.componentInstance.servers().map((s) => s.id)).toEqual([
      "wlo-mcp",
    ]);
  });

  it("discovers the tools of an address without registering it", async () => {
    const { el, fixture, http } = await mount();
    const field = el.querySelector<HTMLInputElement>(".mr-discover-url");
    field!.value = "https://neu.example/mcp";
    field!.dispatchEvent(new Event("input"));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>(".mr-discover-go")?.click();
    await fixture.whenStable();

    const req = http.expectOne(
      (r) => r.url === "/studio/api/config/mcp-servers/discover",
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.params.get("url")).toBe("https://neu.example/mcp");
    req.flush({
      url: "https://neu.example/mcp",
      tools: [{ name: "t", description: "d" }],
    });
    await tick();
    await fixture.whenStable();

    expect(el.querySelector(".mr-found")?.textContent).toContain("t");
    expect(fixture.componentInstance.servers()).toHaveLength(2); // not registered
  });

  it("shows a failed handshake instead of an empty tool list", async () => {
    const { el, fixture, http } = await mount();
    const field = el.querySelector<HTMLInputElement>(".mr-discover-url");
    field!.value = "https://tot.example/mcp";
    field!.dispatchEvent(new Event("input"));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>(".mr-discover-go")?.click();
    await fixture.whenStable();
    http
      .expectOne((r) => r.url === "/studio/api/config/mcp-servers/discover")
      .flush(
        { detail: "Verbindung fehlgeschlagen: timeout" },
        { status: 502, statusText: "Bad Gateway" },
      );
    await tick();
    await fixture.whenStable();

    expect(el.textContent).toContain("Verbindung fehlgeschlagen");
  });
});

describe("compareToolsets", () => {
  it("nennt beide Richtungen getrennt", () => {
    expect(compareToolsets(["a", "b", "c"], ["b", "c", "d"])).toEqual({
      missing: ["a"],
      extra: ["d"],
    });
  });

  it("meldet nichts, wenn beide Seiten dasselbe führen — Reihenfolge zählt nicht", () => {
    expect(compareToolsets(["a", "b"], ["b", "a"])).toEqual({
      missing: [],
      extra: [],
    });
  });
});

describe("McpRegistryComponent — Abgleich mit der Registry", () => {
  /** Eine Adresse prüfen und die Antwort des Servers einspielen. */
  async function pruefe(
    harness: Harness,
    url: string,
    tools: { name: string; description: string }[],
  ): Promise<void> {
    const { el, fixture, http } = harness;
    const field = el.querySelector<HTMLInputElement>(".mr-discover-url");
    field!.value = url;
    field!.dispatchEvent(new Event("input"));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>(".mr-discover-go")?.click();
    await fixture.whenStable();
    http
      .expectOne((r) => r.url === "/studio/api/config/mcp-servers/discover")
      .flush({ url, tools });
    await tick();
    await fixture.whenStable();
  }

  it("benennt das erwartete Werkzeug, das der Server gar nicht führt", async () => {
    // Der Zweck der Ansicht: gemessen 2026-08-11 kannte ein laufender
    // MCP-Betrieb ``get_skill_registry`` nicht, während drei Muster es nennen.
    // Dem Modell angeboten, vom Server nicht geführt — jeder Aufruf ein Fehler.
    const harness = await mount();
    await pruefe(harness, "http://intern:8080/mcp", [
      { name: "get_skill", description: "" },
    ]);
    expect(
      harness.el.querySelector(".mr-compare-missing")?.textContent,
    ).toContain("search_wlo_all");
  });

  it("greift auch bei nachgestelltem Schrägstrich — sonst vergleicht es still nichts", async () => {
    const harness = await mount();
    await pruefe(harness, "http://intern:8080/mcp/", [
      { name: "get_skill", description: "" },
    ]);
    expect(
      harness.el.querySelector(".mr-compare-missing")?.textContent,
    ).toContain("search_wlo_all");
  });

  it("bestätigt ausdrücklich, wenn nichts fehlt — Schweigen wäre nicht dasselbe", async () => {
    const harness = await mount();
    await pruefe(harness, "http://intern:8080/mcp", [
      { name: "search_wlo_all", description: "" },
      { name: "get_skill", description: "" },
    ]);
    expect(harness.el.querySelector(".mr-compare-missing")).toBeNull();
    // Das Zusatzwerkzeug ist kein Mangel, wird aber genannt.
    expect(harness.el.querySelector(".mr-compare")?.textContent).toContain(
      "get_skill",
    );
  });

  it("sagt bei einer unbekannten Adresse, dass es nichts zu vergleichen gibt", async () => {
    const harness = await mount();
    await pruefe(harness, "https://neu.example/mcp", [
      { name: "t", description: "d" },
    ]);
    expect(harness.el.querySelector(".mr-compare-missing")).toBeNull();
    expect(harness.el.querySelector(".mr-compare")?.textContent).toContain(
      "nicht in der Liste",
    );
  });
});
