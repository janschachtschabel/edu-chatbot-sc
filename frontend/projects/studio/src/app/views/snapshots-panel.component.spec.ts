// @vitest-environment jsdom
import { provideHttpClient, withXhr } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideZonelessChangeDetection } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  STUDIO_LOCALE_STORAGE_KEY,
  StudioLanguageService,
} from "../i18n/studio-language.service";
import { SnapshotsPanelComponent } from "./snapshots-panel.component";

const LIST = "/studio/api/config/snapshots";

interface Harness {
  fixture: ComponentFixture<SnapshotsPanelComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const ROW = {
  id: "snap-abc",
  created_at: "2026-07-20T09:30:00Z",
  label: "vor dem Umbau",
  include_db: false,
};

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(rows: readonly unknown[] = [ROW]): Promise<Harness> {
  TestBed.resetTestingModule();
  // Siehe backup.component.spec.ts: jsdom meldet `en-US`, der Browser ist die
  // zweitstärkste Quelle — deutsche Zusagen brauchen die oberste.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, "de");
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(SnapshotsPanelComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne(LIST).flush(rows);
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

describe("SnapshotsPanelComponent", () => {
  beforeEach(() => {
    Object.assign(URL, {
      createObjectURL: vi.fn(() => "blob:x"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("holt die Liste, sobald das Panel steht", async () => {
    const h = await mount();
    expect(text(h)).toContain("vor dem Umbau");
    expect(text(h)).toContain("snap-abc");
    h.http.verify();
  });

  it("sagt im Leerzustand, was ein Snapshot überhaupt sichert", async () => {
    const h = await mount([]);
    expect(text(h)).toContain("Noch keine Snapshots");
    expect(text(h)).toMatch(/Konfiguration|Bereich/);
  });

  it("verspricht nirgends eine Datenbank-Sicherung", async () => {
    // NEU packt nur Config-Bereiche (services/snapshots.py: `include_db` wird nie
    // gesetzt, der Dump ist auf P10 vertagt). ALT sicherte wirklich die DB und
    // hatte deshalb Checkbox, „+ DB"-Badge und Warnungen über Sessions/Memory/
    // RAG-Chunks. Wörtlich portiert wären das drei falsche Zusagen.
    //
    // Beide Zustände, nicht nur der gefüllte: der Leertext beschreibt, WAS ein
    // Snapshot sichert, und ist damit genau die Stelle, an der die Zusage später
    // wieder einziehen würde.
    const filled = await mount([{ ...ROW, include_db: true }]);
    await click(filled, "Wiederherstellen");
    expect(text(filled)).not.toMatch(/Datenbank|\+ ?DB\b/);
    expect(filled.el.querySelector('input[type="checkbox"]')).toBeNull();

    const empty = await mount([]);
    expect(text(empty)).not.toMatch(/Datenbank|\+ ?DB\b/);
  });

  it("legt an, leert das Feld und liest die Liste neu", async () => {
    const h = await mount([]);
    const input = h.el.querySelector<HTMLInputElement>('input[type="text"]')!;
    input.value = "vor dem Remix";
    input.dispatchEvent(new Event("input"));
    await settle(h);

    await click(h, "Snapshot anlegen");
    const create = h.http.expectOne(LIST);
    expect(create.request.method).toBe("POST");
    expect(create.request.body).toEqual({ label: "vor dem Remix" });
    create.flush({ id: "snap-neu", label: "vor dem Remix" });
    await settle(h);

    h.http
      .expectOne(LIST)
      .flush([{ ...ROW, id: "snap-neu", label: "vor dem Remix" }]);
    await settle(h);
    expect(input.value).toBe("");
    expect(text(h)).toContain("vor dem Remix");
  });

  it("fragt vor dem Wiederherstellen zurück und nennt den Snapshot", async () => {
    const h = await mount();
    await click(h, "Wiederherstellen");
    // Armed, not fired: no request may go out before the second click.
    h.http.expectNone(`${LIST}/snap-abc/restore`);
    expect(text(h)).toContain("vor dem Umbau");
    // The confirmation appears below the button that armed it, so focus does not
    // move and nothing else changes on screen. Without a live region a screen
    // reader would announce nothing at all and the second click would fire an
    // action its user never heard about (WCAG 2.2 SC 4.1.3).
    expect(h.el.querySelector(".op-confirm")!.getAttribute("role")).toBe(
      "alert",
    );

    await click(h, "Ja, wiederherstellen");
    const req = h.http.expectOne(`${LIST}/snap-abc/restore`);
    expect(req.request.method).toBe("POST");
    req.flush({ status: "restored", areas: 35 });
    await settle(h);
    expect(text(h)).toContain("35");
  });

  it("fragt vor dem Löschen zurück und liest danach neu", async () => {
    const h = await mount();
    await click(h, "Löschen");
    h.http.expectNone(`${LIST}/snap-abc`);

    await click(h, "Ja, löschen");
    const req = h.http.expectOne(`${LIST}/snap-abc`);
    expect(req.request.method).toBe("DELETE");
    req.flush({ status: "deleted", id: "snap-abc" });
    await settle(h);
    h.http.expectOne(LIST).flush([]);
    await settle(h);
    expect(text(h)).toContain("Noch keine Snapshots");
  });

  it("lädt als Datei herunter statt die Seite zu wechseln", async () => {
    const h = await mount();
    await click(h, "Herunterladen");
    const req = h.http.expectOne(`${LIST}/snap-abc/download`);
    expect(req.request.responseType).toBe("blob");
    req.flush(new Blob(["PK"]));
    await settle(h);
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("nennt die Server-Grenze mit dem gemessenen Stand", async () => {
    const h = await mount([ROW, { ...ROW, id: "snap-2" }]);
    // The limit is enforced in create_snapshot (MAX_SNAPSHOTS = 50) and only
    // announces itself as a 400 — worth knowing before the button is pressed.
    expect(text(h)).toContain("2 von 50");
  });

  it("beugt den Stand-Satz nach der Regel der aktiven Sprache", async () => {
    // Auf Deutsch unterscheidet nur das Substantiv, auf Englisch auch das Verb
    // („1 snapshot of 50 is saved" ↔ „2 … are saved"). Ein `=== 1` im Template
    // wäre die deutsche Regel, fest verdrahtet.
    const eins = await mount([ROW]);
    expect(text(eins)).toContain("1 von 50");

    TestBed.inject(StudioLanguageService).toggle();
    await settle(eins);
    expect(text(eins)).toContain("1 of 50");
    expect(text(eins)).toMatch(/\bis saved\b/);

    const zwei = await mount([ROW, { ...ROW, id: "snap-2" }]);
    TestBed.inject(StudioLanguageService).toggle();
    await settle(zwei);
    expect(text(zwei)).toMatch(/\bare saved\b/);
  });

  it("zeigt den Satz des Backends, wenn das Anlegen scheitert", async () => {
    const h = await mount([]);
    await click(h, "Snapshot anlegen");
    h.http
      .expectOne(LIST)
      .flush(
        {
          detail: "Snapshot-Limit erreicht (max 50) — alte Snapshots löschen.",
        },
        { status: 400, statusText: "Bad Request" },
      );
    await settle(h);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain(
      "Snapshot-Limit erreicht",
    );
  });
});
