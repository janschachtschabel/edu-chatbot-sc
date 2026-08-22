import { describe, expect, it } from "vitest";

// Direkter JSON-Import statt node:fs — der Spec-tsconfig kennt keine
// Node-Typen, und esbuild bündelt die Datei so zur Bauzeit ein: geprüft
// wird exakt der Stand, mit dem auch `ng serve` starten würde.
import proxy from "../../../../proxy.conf.json";

/**
 * Wächter für die Dev-Verdrahtung (Review 2026-08-22): `proxy.conf.json`
 * zeigte auf :8000, das NEU-Dev-Backend läuft dokumentiert auf :8100
 * (backend/README.md `--port 8100`, deploy/compose.dev.yml „8100: ALT belegt
 * lokal 8000"). Jeder dokumentierte Dev-Weg (`npm run start:studio` bzw.
 * `npm start`) lief damit gegen eine tote Tür — dieselbe Fehlerklasse wie
 * der EVAL_CHAT_URL-Prod-Befund am selben Tag (test_deploy_compose.py).
 *
 * Bewusst ein Test über eine DATEI statt über Code: die Verdrahtung ist
 * Konfiguration, und nur ein Leser der Datei merkt, wenn sie driftet.
 */
describe("Dev-Proxy-Verdrahtung", () => {
  it("alle Proxy-Ziele zeigen auf das Dev-Backend :8100", () => {
    const routen = Object.entries(
      proxy as Record<string, { target: string }>,
    );
    expect(routen.length).toBeGreaterThan(0);
    for (const [route, cfg] of routen) {
      expect(cfg.target, `${route} → ${cfg.target}`).toBe(
        "http://localhost:8100",
      );
    }
    // Die drei Wege, die Studio und Widget im Dev wirklich nutzen.
    expect(Object.keys(proxy)).toEqual(
      expect.arrayContaining(["/api", "/widget", "/studio/api"]),
    );
  });
});
