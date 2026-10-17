// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app.routes";
import {
  STUDIO_LOCALE_STORAGE_KEY,
  StudioLanguageService,
} from "../i18n/studio-language.service";
import { BackupComponent } from "./backup.component";

const BASE = "/studio/api/config";

interface Harness {
  fixture: ComponentFixture<BackupComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'`, und der Browser ist im Studio
  // die zweitstärkste Quelle. Ohne die oberste Quelle liefe diese Suite auf
  // Englisch — deutsche Zusagen wären dann zufällig rot.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(BackupComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  // The two children load on their own; the hull reads nothing.
  http.expectOne(`${BASE}/factory`).flush({ exists: false });
  http.expectOne(`${BASE}/snapshots`).flush([]);
  await settle(h);
  return h;
}

const text = (h: Harness): string => h.el.textContent ?? "";

function button(h: Harness, label: string): HTMLButtonElement {
  const match = Array.from(h.el.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").trim().startsWith(label),
  );
  if (!match)
    throw new Error(
      `Kein Knopf "${label}" — vorhanden: ${Array.from(
        h.el.querySelectorAll("button"),
      )
        .map((b) => b.textContent?.trim())
        .join(" | ")}`,
    );
  return match;
}

async function click(h: Harness, label: string): Promise<void> {
  button(h, label).click();
  await settle(h);
}

describe("BackupComponent", () => {
  beforeEach(() => {
    Object.assign(URL, {
      createObjectURL: vi.fn(() => "blob:x"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("hängt an der Route `sicherung`", async () => {
    // A finished view nobody can reach is not built (the 9-5c lesson).
    const children = routes.find((r) => r.path === "")!.children!;
    const route = children.find((r) => r.path === "sicherung")!;
    const loaded = await (route.loadComponent as () => Promise<unknown>)();
    expect(loaded).toBe(BackupComponent);
  });

  it("zeigt beide Werkzeuge auf einer Seite", async () => {
    const h = await mount();
    expect(h.el.querySelector("studio-snapshots-panel")).toBeTruthy();
    expect(h.el.querySelector("studio-factory-panel")).toBeTruthy();
  });

  it("trägt die Sprungziele der Kopfzeile (ST-9)", async () => {
    // „Backup einspielen …" und „Zu den Snapshots" führen hierher; ohne die
    // Ziele landete man am Seitenanfang.
    const h = await mount();
    expect(h.el.querySelector("#voll-backup #bk-file")).not.toBeNull();
    expect(h.el.querySelector("#snapshots")).not.toBeNull();
  });

  it("sagt, was in einem Backup steckt und was nicht", async () => {
    const h = await mount();
    // Config areas only — the Postgres dump is deferred to P10. Without this
    // sentence an operator would reasonably read "Backup" as "everything".
    expect(text(h)).toContain("Konfigurationsbereiche");
    expect(text(h)).toMatch(/keine Sessions|ohne Sessions/);
  });

  it("lädt das Backup als Datei statt die Seite zu verlassen", async () => {
    const h = await mount();
    await click(h, "Backup herunterladen");
    const req = h.http.expectOne(`${BASE}/backup`);
    expect(req.request.responseType).toBe("blob");
    req.flush(new Blob(["PK"]));
    await settle(h);
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("spielt eine ZIP erst nach Rückfrage ein", async () => {
    const h = await mount();
    expect(button(h, "Backup einspielen").disabled).toBe(true);

    const file = new File(["PK"], "boerdi-config-backup.zip");
    h.fixture.componentInstance.onFile({
      target: { files: [file] },
    } as unknown as Event);
    await settle(h);

    await click(h, "Backup einspielen");
    h.http.expectNone((r) => r.url === `${BASE}/restore`);
    // The confirmation names the file — the chosen name itself is shown by the
    // native file input, which jsdom does not render.
    expect(text(h)).toContain("boerdi-config-backup.zip");

    await click(h, "Ja, einspielen");
    const req = h.http.expectOne(`${BASE}/restore?mode=merge`);
    expect((req.request.body as FormData).get("file")).toBe(file);
    req.flush({ status: "restored", areas: 35, deleted: 0, snapshot_id: null });
    await settle(h);
    expect(text(h)).toContain("35");
    // The chosen file STAYS chosen. Clearing the signal alone would leave the
    // native picker showing a file name next to a button that refuses to use
    // it, and clearing the input element too needs a DOM reach-around for no
    // gain — re-applying the same ZIP writes the same areas.
    expect(button(h, "Backup einspielen").disabled).toBe(false);
  });

  // Paket 7 (P5-5): „exakt" löscht, was nicht in der ZIP liegt — nur auf
  // ausdrückliche Wahl, und die Meldung nennt den Rückweg.
  it("spielt „exakt“ nur auf ausdrückliche Wahl ein und nennt den Rückweg", async () => {
    const h = await mount();
    h.fixture.componentInstance.onFile({
      target: { files: [new File(["PK"], "alt.zip")] },
    } as unknown as Event);
    await settle(h);
    await click(h, "Backup einspielen");
    const wahl = (wert: string) =>
      h.el.querySelector<HTMLInputElement>(`.op-confirm input[value="${wert}"]`)!;
    expect(wahl("merge").checked).toBe(true);
    wahl("exact").click();
    await settle(h);

    await click(h, "Ja, einspielen");
    h.http
      .expectOne(`${BASE}/restore?mode=exact`)
      .flush({ status: "restored", areas: 30, deleted: 2, snapshot_id: "snap-9" });
    await settle(h);
    expect(text(h)).toContain("2 Bereiche gelöscht");
    expect(text(h)).toContain("snap-9");
    // Die Snapshot-Liste darunter liest neu: der Rückweg steht sofort darin.
    h.http.expectOne(`${BASE}/snapshots`).flush([]);

    // Die nächste Rückfrage beginnt wieder bei der Vorgabe.
    await click(h, "Backup einspielen");
    expect(wahl("merge").checked).toBe(true);
  });

  it("nennt die Datei in einem GANZEN Satz, in beiden Sprachen", async () => {
    // Bis C1-d3b stand der Dateiname zwischen zwei Template-Bruchstücken
    // (`„{{ file()?.name }}" einspielen? Jeder Bereich …`). Ein Satz, dessen
    // Mitte aus einer anderen Datei kommt, lässt sich nicht übersetzen: im
    // Englischen steht das Objekt hinter dem Verb, nicht davor.
    const h = await mount();
    h.fixture.componentInstance.onFile({
      target: { files: [new File(["PK"], "stand.zip")] },
    } as unknown as Event);
    await settle(h);
    await click(h, "Backup einspielen");
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain(
      "„stand.zip“ einspielen?",
    );

    TestBed.inject(StudioLanguageService).toggle();
    await settle(h);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain(
      "Restore “stand.zip”?",
    );
  });

  it("zählt die eingespielten Bereiche in der Form der aktiven Sprache", async () => {
    const h = await mount();
    // Paket 4b, B3: die Rückmeldung steht leer bereit.
    const region = h.el.querySelector<HTMLElement>(".op-msg[role='status']");
    expect(region?.textContent).toBe("");
    h.fixture.componentInstance.onFile({
      target: { files: [new File(["PK"], "eins.zip")] },
    } as unknown as Event);
    await settle(h);
    await click(h, "Backup einspielen");
    await click(h, "Ja, einspielen");
    h.http
      .expectOne(`${BASE}/restore?mode=merge`)
      .flush({ status: "restored", areas: 1, deleted: 0, snapshot_id: null });
    await settle(h);
    // Einzahl, nicht „1 Konfigurationsbereiche" — die Grenze zwischen den
    // Formen entscheidet die Sprache, nicht ein `=== 1` im Code.
    expect(text(h)).toContain("1 Konfigurationsbereich aus");
    expect(region!.textContent).toContain("1 Konfigurationsbereich aus");
  });

  it("zeigt den Satz des Backends, wenn die ZIP abgelehnt wird", async () => {
    const h = await mount();
    const region = h.el.querySelector<HTMLElement>(".op-msg[role='status']");
    h.fixture.componentInstance.onFile({
      target: { files: [new File(["x"], "kaputt.zip")] },
    } as unknown as Event);
    await settle(h);
    await click(h, "Backup einspielen");
    await click(h, "Ja, einspielen");
    h.http
      .expectOne(`${BASE}/restore?mode=merge`)
      .flush(
        { detail: "Keine gültige ZIP-Datei." },
        { status: 413, statusText: "Payload Too Large" },
      );
    await settle(h);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain(
      "Keine gültige ZIP-Datei.",
    );
    // Zweites Review 4b: der Fehler steht nur im Alarm, die Status-Region
    // bleibt leer — sonst wird er doppelt angesagt.
    expect(h.el.querySelector(".op-msg[role='status']")).toBe(region);
    expect(region!.textContent).toBe("");
  });

  it("führt den Fokus in die Rückfrage und zurück zum Knopf (Paket 9, V8)", async () => {
    const h = await mount();
    h.fixture.componentInstance.onFile({
      target: { files: [new File(["PK"], "b.zip")] },
    } as unknown as Event);
    await settle(h);
    await click(h, "Backup einspielen");
    expect(document.activeElement?.textContent?.trim()).toBe("Abbrechen");
    await click(h, "Abbrechen");
    expect(document.activeElement).toBe(button(h, "Backup einspielen"));

    await click(h, "Backup einspielen");
    await click(h, "Ja, einspielen");
    h.http
      .expectOne(`${BASE}/restore?mode=merge`)
      .flush({ status: "restored", areas: 3, deleted: 0, snapshot_id: null });
    await settle(h);
    expect(document.activeElement).toBe(button(h, "Backup einspielen"));
  });

  it("trägt keine Kennung doppelt — sonst benennt aria-labelledby das falsche Panel (Paket 9)", async () => {
    // Snapshots und Auslieferungsstand hießen beide `sp-title`; das zweite Panel
    // trug damit den Namen des ersten.
    const h = await mount();
    const ids = Array.from(h.el.querySelectorAll("[id]"), (e) => e.id);
    expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([]);
  });
});
