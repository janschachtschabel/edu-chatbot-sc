"""P1-3: security response headers + CORS semantics — port of ALT
tests/test_security_headers.py (+ CORS credentials rule from ALT main.py:188-195).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from boerdi.main import create_app


def test_security_headers_present(monkeypatch):
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "referrer-policy" in r.headers


def test_cors_wildcard_disables_credentials(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)  # default "*"
    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": "https://embedder.example"})
    assert r.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in r.headers


def test_cors_explicit_origin_enables_credentials(monkeypatch):
    # Seit dem Offen-Schalter (2026-08-18) braucht dieser Bestandsfall das
    # ausdrueckliche Zumachen: die Vorgabe ist '*', und dort sind Anmeldedaten
    # per Regel aus. Die geprüfte Zusage ist unveraendert — nur ihre Voraussetzung
    # steht jetzt sichtbar da.
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://embedder.example,https://two.example")
    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": "https://embedder.example"})
    assert r.headers.get("access-control-allow-origin") == "https://embedder.example"
    assert r.headers.get("access-control-allow-credentials") == "true"


# ── Browser-Erweiterungen als Ursprung (Safari-Befund 2026-08-18) ──────────
#
# Gemeldet von den Plugin-Entwicklern, Safari-Konsole: „Preflight response is
# not successful. Status code: 400" auf `/api/chat/stream` und daneben
# „Origin safari-web-extension://<UUID> is not allowed by
# Access-Control-Allow-Origin. Status code: 200" auf den einfachen GETs.
#
# EINE Ursache, zwei Gesichter: der Ursprung stand nicht in der Erlaubnisliste.
# Die 400 ist woertlich Starlette (`PlainTextResponse("Disallowed CORS origin",
# status_code=400)`), die 200 ist die Antwort auf eine einfache Anfrage, deren
# Kopf der Browser dann verweigert.
#
# Der Kern: Safari vergibt die UUID JE INSTALLATION. Eine statische Liste kann
# den Fall grundsaetzlich nicht loesen — Chrome hat eine feste Kennung, deshalb
# ist es dort nie aufgefallen.

_SAFARI = "safari-web-extension://72c621e2-eb2a-46f5-a136-2030bade7892"
_CHROME = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


def test_abgeschaltet_kehrt_der_gemeldete_zustand_zurueck(monkeypatch):
    """Der gemeldete Zustand, festgehalten — damit die Regel einen belegten
    Gegenspieler hat und nicht bloss eine Behauptung ist.

    Die Vorgabe des Schalters ist **an**: eine Einbindung per Browser-Plugin ist
    ein unterstuetzter Weg (``docs/browser-plugin-einbindung.md``), und ihr
    Ausfall sieht aus wie dieser Befund — eine 400 ohne Zusammenhang, an der die
    Entwickler einen halben Tag suchen. Wer enger fahren will, schaltet ihn aus;
    dann gilt wieder genau das hier."""
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")   # sonst misst der Test den Schalter
    monkeypatch.setenv("CORS_ALLOW_EXTENSIONS", "false")
    client = TestClient(create_app())
    r = client.options("/api/chat", headers={
        "Origin": _SAFARI,
        "Access-Control-Request-Method": "POST",
    })
    assert r.status_code == 400                       # Starlette: Disallowed CORS origin
    assert "access-control-allow-origin" not in r.headers


def test_safari_erweiterung_darf_mit_der_regel(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")   # sonst misst der Test den Schalter
    monkeypatch.setenv("CORS_ALLOW_EXTENSIONS", "true")
    client = TestClient(create_app())
    r = client.options("/api/chat", headers={
        "Origin": _SAFARI,
        "Access-Control-Request-Method": "POST",
    })
    assert r.status_code == 200
    # Der KONKRETE Ursprung wird zurueckgegeben, nicht `*` — nur so bleiben
    # Anmeldedaten ueberhaupt moeglich.
    assert r.headers.get("access-control-allow-origin") == _SAFARI
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_auch_chrome_erweiterungen_fallen_darunter(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")   # sonst misst der Test den Schalter
    monkeypatch.setenv("CORS_ALLOW_EXTENSIONS", "true")
    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": _CHROME})
    assert r.headers.get("access-control-allow-origin") == _CHROME


def test_die_liste_bleibt_daneben_gueltig(monkeypatch):
    """Die Regel ERWEITERT, sie ersetzt nicht: eine gewoehnliche Webseite
    kommt weiterhin nur ueber die Liste herein."""
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")   # sonst misst der Test den Schalter
    monkeypatch.setenv("CORS_ALLOW_EXTENSIONS", "true")
    client = TestClient(create_app())
    erlaubt = client.get("/health", headers={"Origin": "https://redaktion.example"})
    fremd = client.get("/health", headers={"Origin": "https://fremde.example"})
    assert erlaubt.headers.get("access-control-allow-origin") == "https://redaktion.example"
    assert "access-control-allow-origin" not in fremd.headers


def test_kein_beliebiges_schema_und_kein_praefix_trick(monkeypatch):
    """`fullmatch` statt `search`: `https://boese.example/safari-web-extension://x`
    ist ein gewoehnlicher Web-Ursprung und darf nicht durchrutschen."""
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")   # sonst misst der Test den Schalter
    monkeypatch.setenv("CORS_ALLOW_EXTENSIONS", "true")
    client = TestClient(create_app())
    for boese in (
        "https://boese.example/safari-web-extension://72c621e2",
        "safari-web-extension://72c621e2-eb2a-46f5-a136-2030bade7892.boese.example",
        "moz-extension://72c621e2-eb2a-46f5-a136-2030bade7892",
    ):
        r = client.get("/health", headers={"Origin": boese})
        assert "access-control-allow-origin" not in r.headers, boese


# ── Der Offen-Schalter (Nutzer-Entscheid 2026-08-18) ───────────────────────
#
# Vorgabe: alle Ursprünge erlaubt. Die Anlage soll ohne Zutun einbettbar sein —
# ein Einbau, der an einer vergessenen Liste scheitert, kostet ein fremdes Team
# einen halben Tag (genau der Safari-Fall von heute). Zumachen ist eine
# ausdrückliche Handlung: CORS_ALLOW_ALL=false.
#
# Der Preis ist benannt und LAUT: wer eine Liste pflegt und den Schalter nicht
# kennt, sähe sie sonst still übergangen. Deshalb die Warnzeile.


def test_offen_ist_die_vorgabe_auch_mit_gesetzter_liste(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.delenv("CORS_ALLOW_ALL", raising=False)
    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": "https://irgendwer.example"})
    assert r.headers.get("access-control-allow-origin") == "*"
    # Mit '*' sind Anmeldedaten aus — die Regel daneben bleibt unberührt.
    assert "access-control-allow-credentials" not in r.headers


def test_die_uebersteuerte_liste_wird_beim_start_gemeldet(monkeypatch, caplog):
    """Eine still übergangene Konfiguration ist schlimmer als eine offene:
    der Betreiber glaubt, er habe zugemacht."""
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.delenv("CORS_ALLOW_ALL", raising=False)
    with caplog.at_level("WARNING"):
        create_app()
    zeilen = [r.message for r in caplog.records if "CORS_ALLOW_ALL" in r.message]
    assert zeilen, "keine Warnung über die übersteuerte Liste"
    assert "https://redaktion.example" in zeilen[0] or "CORS_ORIGINS" in zeilen[0]


def test_zugemacht_gilt_die_liste_wieder(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://redaktion.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")
    client = TestClient(create_app())
    erlaubt = client.get("/health", headers={"Origin": "https://redaktion.example"})
    fremd = client.get("/health", headers={"Origin": "https://irgendwer.example"})
    assert erlaubt.headers.get("access-control-allow-origin") == "https://redaktion.example"
    assert erlaubt.headers.get("access-control-allow-credentials") == "true"
    assert "access-control-allow-origin" not in fremd.headers


def test_leerzeichen_nach_dem_komma_toeten_den_eintrag_nicht_mehr(monkeypatch):
    """Der gemessene Fall: `"https://a.example, https://b.example"` — der
    zweite Eintrag trug ein führendes Leerzeichen und traf nie einen Ursprung."""
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("CORS_ALLOW_ALL", "false")
    client = TestClient(create_app())
    for o in ("https://a.example", "https://b.example"):
        r = client.get("/health", headers={"Origin": o})
        assert r.headers.get("access-control-allow-origin") == o, o
