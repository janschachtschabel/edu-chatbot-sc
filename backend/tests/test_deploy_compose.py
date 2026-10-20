"""Der Weg von der ``.env`` in den Container — die Luecke, die K2 offenliess.

**Gemessen am 2026-08-18:** ``CORS_ALLOW_ALL=false`` in ``deploy/.env`` blieb in
Produktion wirkungslos. ``docker compose`` liest die ``.env`` nur zur Ersetzung
IN der Compose-Datei; was nicht unter ``environment:`` steht, erreicht den
Container nie. Der Schalter war gebaut, getestet und dokumentiert — und genau
auf dem Weg, den ``deploy/INSTALL-schnellstart.md`` beschreibt, tot. Der
Betreiber haette geglaubt, er habe zugemacht: dieselbe stille Uebersteuerung,
gegen die K2 die Warnzeile eingezogen hat, nur eine Ebene hoeher.

Der Fehler ist eine KLASSE, kein Einzelfall — jeder kuenftige Schalter kann so
verschwinden. Deshalb prueft der erste Test alle dokumentierten Schluessel.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
_ENV_BEISPIEL = _DEPLOY / ".env.example"
_COMPOSE = _DEPLOY / "compose.prod.yml"


def _dokumentierte_schluessel() -> list[str]:
    """Die Namen, die ``deploy/.env.example`` einem Betreiber anbietet — auch die
    auskommentierten (``# CHAT_TOKEN_STREAMING=``): Paket 7 (L6) fand genau so
    einen Schalter, dokumentiert und doch nie im Container."""
    return re.findall(r"^#?\s*([A-Z_][A-Z0-9_]*)=", _ENV_BEISPIEL.read_text("utf-8"), re.M)


def test_jeder_dokumentierte_schluessel_steht_in_compose() -> None:
    """Was die Beispiel-``.env`` anbietet, muss in ``compose.prod.yml`` vorkommen.

    Die Zusage ist bewusst schwach — sie prueft nur, dass der Name ueberhaupt
    auftaucht, nicht an welcher Stelle. Genau das reicht gegen den gemessenen
    Fehler (Name kommt NIRGENDS vor => erreicht niemanden) und erzeugt keine
    Fehlalarme fuer Werte, die zurecht woanders stehen: ``PUBLIC_HOST`` in den
    traefik-Labels, ``BOERDI_IMAGE`` unter ``image:``, ``POSTGRES_*`` beim
    Datenbank-Dienst. Wo es genau stehen muss, prueft der Test darunter.
    """
    text = _COMPOSE.read_text("utf-8")
    fehlend = [k for k in _dokumentierte_schluessel() if not re.search(rf"\b{k}\b", text)]
    assert fehlend == [], (
        f"in deploy/.env.example dokumentiert, in compose.prod.yml nirgends "
        f"verdrahtet: {fehlend} — diese Werte erreichen den Container nie"
    )


def test_dockerfile_liefert_den_gold_runner_mit() -> None:
    """Der Gold-Runner ist eine framework-freie DATEI (kein Paket-Modul) und
    wird zur Laufzeit per Pfad geladen. Prod-Befund 2026-08-22: das Image
    kopierte sie nicht, und die Quellbaum-Arithmetik zeigte in der
    installierten venv auf ``/app/.venv/lib/evals/…`` — jeder Gold-Lauf starb
    sofort mit Errno 2 (generative Läufe waren nie betroffen: ihr Runner ist
    ein normales Paket-Modul in der venv). Das Image muss die Datei mitführen
    UND ``EVAL_RUNNER_PATH`` darauf zeigen lassen.
    """
    text = (_DEPLOY.parent / "Dockerfile").read_text("utf-8")
    assert "COPY evals/run_golden.py" in text, "evals/run_golden.py fehlt im Image"
    assert "EVAL_RUNNER_PATH=/app/evals/run_golden.py" in text, (
        "EVAL_RUNNER_PATH zeigt im Image nicht auf die mitkopierte Datei"
    )
    # Paket 15 (A2): ohne Compose gestartet (Testcontainer) fragte der Runner Port 8000 —
    # jeder Lauf brach mit 502 ab. Das Image trägt den Selbstaufruf selbst.
    assert "EVAL_CHAT_URL=http://127.0.0.1:8100/api/chat" in text, (
        "EVAL_CHAT_URL fehlt im Image — ein Container ohne Compose startet keinen Eval-Lauf"
    )
    # CI-Befund 2026-08-22 (zweite Hälfte): das Dockerfile ALLEIN reicht nicht —
    # ein pauschales `evals` in der .dockerignore hielt die Datei aus dem
    # Build-Kontext, und der COPY brach mit „not found" ab.
    ignore = (_DEPLOY.parent / ".dockerignore").read_text("utf-8")
    zeilen = {
        z.strip() for z in ignore.splitlines()
        if z.strip() and not z.strip().startswith("#")
    }
    verboten = sorted(zeilen & {
        "evals", "evals/", "evals/*", "evals/**", "**/evals",
        "evals/run_golden.py",
    })
    assert verboten == [], (
        f".dockerignore hält den Gold-Runner aus dem Build-Kontext: {verboten} "
        "— der COPY im Dockerfile findet die Datei dann nicht"
    )


def test_eval_chat_url_hat_einen_container_tauglichen_default() -> None:
    """``EVAL_CHAT_URL`` muss im Container auf den EIGENEN Port zeigen.

    Gemessen auf Prod am 2026-08-22: die Compose reichte den Wert nur leer
    durch (``${EVAL_CHAT_URL:-}``), der Code-Default zeigt auf ALT-Port 8000 —
    das Image lauscht aber auf 8100. Jeder Eval-Start brach damit im Preflight
    mit „Chat-Backend nicht erreichbar" ab, bis ein Betreiber die Variable von
    Hand setzte. Der Default ist der Selbstaufruf im Container (kein Umweg
    ueber traefik/TLS); die ``.env`` darf weiterhin uebersteuern.
    """
    for compose in (_COMPOSE, _DEPLOY / "compose.dev.yml"):
        dienste = yaml.safe_load(compose.read_text("utf-8"))["services"]
        umgebung = dienste["backend"]["environment"]
        wert = str(umgebung.get("EVAL_CHAT_URL", ""))
        assert "http://127.0.0.1:8100/api/chat" in wert, (
            f"{compose.name}: EVAL_CHAT_URL ohne Selbstaufruf-Default — "
            f"Eval-Starts laufen im Container gegen ALT-Port 8000 (Wert: {wert!r})"
        )


def test_die_cors_schalter_erreichen_den_backend_dienst() -> None:
    """Die drei CORS-Namen muessen in der Umgebung des Backends stehen.

    Nicht irgendwo in der Datei: ``environment:`` des Dienstes ``backend`` ist
    der einzige Ort, von dem aus ``settings.py`` sie liest.
    """
    dienste = yaml.safe_load(_COMPOSE.read_text("utf-8"))["services"]
    umgebung = dienste["backend"]["environment"]
    assert isinstance(umgebung, dict), "environment als Liste — Test anpassen"
    for name in ("CORS_ORIGINS", "CORS_ALLOW_ALL", "CORS_ALLOW_EXTENSIONS"):
        assert name in umgebung, f"{name} erreicht den Backend-Container nicht"


# ── Audit 2026-09-29: drei Befunde auf demselben Weg ─────────────────────

def _dienste() -> dict:
    return yaml.safe_load(_COMPOSE.read_text("utf-8"))["services"]


def test_der_lasttest_ist_auf_prod_ohne_eintrag_aus() -> None:
    """Kommentar, ``.env.example``, Runbook und Cluster-Checkliste sagen: leer
    = auf Prod abgelehnt. ``${VAR:-}`` liefert aber einen LEEREN String, und
    ``env_ignore_empty`` macht daraus „nicht gesetzt" — also den Code-Default
    ``True``. Der Lasttest (bis 32 parallele echte Züge im LLM-Pool der
    Live-Nutzer) lief damit auf Prod."""
    wert = _dienste()["backend"]["environment"]["BOERDI_ALLOW_LOADTEST"]
    assert wert == "${BOERDI_ALLOW_LOADTEST:-false}"


def test_migrate_kennt_die_embedding_dimension_des_backends() -> None:
    """Migration 0001 legt ``vector(dim)`` aus ``get_embed_dim()`` an — das
    liest ``EMBED_DIM``, ``LLM_EMBED_MODEL`` und ``LLM_PROVIDER``. ``migrate``
    bekam nur ``DATABASE_URL`` und legte bei jedem anderen Anbieter 1536 an,
    während das Backend mit einer anderen Dimension einbettete: jede
    RAG-Abfrage schlug fehl."""
    dienste = _dienste()
    for name in ("LLM_PROVIDER", "LLM_EMBED_MODEL", "EMBED_DIM"):
        assert dienste["migrate"]["environment"].get(name) == \
            dienste["backend"]["environment"][name], name


def test_alte_sicherungen_verschwinden_nur_nach_einer_neuen() -> None:
    """Das ``find … -delete`` lief auch nach einem gescheiterten ``pg_dump``:
    nach ``BACKUP_KEEP_DAYS`` stiller Fehlschläge war jede gute Sicherung
    gelöscht. Aufgeräumt wird nur im Erfolgszweig."""
    skript = _dienste()["pg-backup"]["command"][0]
    erfolg = skript.index("then")
    fehler = skript.index("else")
    aufraeumen = skript.index("-delete")
    assert erfolg < aufraeumen < fehler


def test_ohne_eintrag_laeuft_genau_eine_replik() -> None:
    """Paket 4, L4 (externes Audit F01, Zwischenmaßnahme): Züge derselben Sitzung
    sperrt heute nur ein prozessinterner Lock (Befundliste C-H1). Über Repliken
    hinweg können sie parallel laufen — die Vorgabe darf also nicht 3 sein.
    Mehr Repliken bleiben möglich, aber nur als bewusster Eintrag."""
    text = _COMPOSE.read_text("utf-8")
    assert "replicas: ${BACKEND_REPLICAS:-1}" in text
    # Die Beispiel-`.env` nennt dieselbe Vorgabe, nicht mehr „3 (= Default)“.
    assert "# BACKEND_REPLICAS=1" in _ENV_BEISPIEL.read_text("utf-8")


def test_hsts_und_studio_csp_erreichen_den_backend_dienst() -> None:
    """Paket 8 (P1/P2): beide Schalter stehen in der Umgebung des Backends und in
    der Beispiel-``.env`` — leer heißt Code-Vorgabe (1 Tag HSTS, CSP durchgesetzt)."""
    umgebung = _dienste()["backend"]["environment"]
    beispiel = _ENV_BEISPIEL.read_text("utf-8")
    for name in ("HSTS_MAX_AGE", "STUDIO_CSP"):
        assert umgebung.get(name) == f"${{{name}:-}}", f"{name} erreicht den Container nicht"
        assert re.search(rf"^#?\s*{name}=", beispiel, re.M), f"{name} fehlt in .env.example"


def test_das_herunterfahren_passt_in_die_gnadenfrist() -> None:
    """Review Paket 9: uvicorn wartet zuerst bis ``--timeout-graceful-shutdown`` auf
    offene Verbindungen, erst danach wartet der Lifespan ``NACHLAUF_FRIST_S`` auf
    nachlaufende Züge (und 5 s auf ihren Abbruch). Lag die Summe über
    ``stop_grace_period``, kam SIGKILL mitten im Warten — ohne Warnung im Log, ohne
    ``store.stop`` und ``engine.dispose``."""
    from fastapi import FastAPI

    from boerdi import serve
    from boerdi.api.sse import NACHLAUF_FRIST_S

    # Paket 17 (D1): die Frist steht seit ``boerdi.serve`` im Einstieg, nicht mehr in der
    # Dockerfile-CMD — gelesen wird sie dort, wo sie wirkt.
    dockerfile = (_DEPLOY.parent / "Dockerfile").read_text("utf-8")
    assert 'CMD ["python", "-m", "boerdi.serve"]' in dockerfile
    uvicorn_s = serve.baue_server(FastAPI(), FastAPI())[0].config.timeout_graceful_shutdown
    gnade = re.search(r"stop_grace_period:\s*(\d+)s", _COMPOSE.read_text("utf-8"))
    from boerdi.services.laeufe_beenden import _FRIST_S as abschluss_s  # vor dem Schließen

    abbruch_s, aufraeumen_s = 5, 5     # hängende Züge abbrechen; Takt, Store, Engine
    assert (abschluss_s + uvicorn_s + NACHLAUF_FRIST_S + abbruch_s + aufraeumen_s
            <= int(gnade.group(1)))


def test_das_reranker_modell_hat_ein_beschreibbares_volume() -> None:
    """Paket 11 (Nutzer 2026-10-15): eingeschaltet bezieht das Backend das Modell selbst —
    dafür muss ``/models`` beschreibbar sein. Vorgabe ist ein benanntes Volume (Docker übernimmt
    die Rechte aus dem Image); ``RERANK_MODEL_HOST_DIR`` kann weiter einen Ordner einhängen."""
    backend = _dienste()["backend"]
    mount = next(v for v in backend["volumes"] if str(v).endswith(":/models")
                 or ":/models:" in str(v))
    assert not str(mount).endswith(":ro"), mount
    assert "reranker_models" in str(mount)
    assert "reranker_models" in yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))["volumes"]
    dockerfile = (_DEPLOY.parent / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"mkdir -p /models && chown boerdi(:boerdi)? /models", dockerfile), \
        "ohne Verzeichnis im Image gehört ein neues Volume root — der Bezug scheitert"


def test_die_reranker_schalter_erreichen_den_backend_dienst() -> None:
    """Paket 11: ohne Eintrag unter ``environment:`` käme ``RAG_RERANKER_ENABLED`` aus der
    ``.env`` nie im Container an — der Schalter wäre wirkungslos (Befund 2026-10-15)."""
    umgebung = _dienste()["backend"]["environment"]
    for schluessel in ("RAG_RERANKER_ENABLED", "RERANK_AUTO_DOWNLOAD",
                       "RERANK_INTRA_OP_THREADS", "RERANK_MAX_CONCURRENCY"):
        assert schluessel in umgebung, schluessel


def test_migrate_zieht_die_werksfassung_nach() -> None:
    """Paket 12: beim Hochfahren der Werksabgleich, nicht mehr nur das Fehlende — unberührte
    Bereiche kommen so ohne Handgriff auf die neue Werksfassung, Angepasstes bleibt."""
    befehl = " ".join(_dienste()["migrate"]["command"])
    assert "boerdi import-config --werksabgleich" in befehl
    assert "--only-missing" not in befehl


def test_das_image_kennt_version_und_commit() -> None:
    """Paket 13 (A7): Eval-Läufe nennen den Stand des Abbilds (``messbedingungen.app``). Das
    Dockerfile reicht beide Build-Argumente als Umgebung durch, der Image-Bau befüllt sie."""
    text = (_DEPLOY.parent / "Dockerfile").read_text("utf-8")
    runtime = text.split("AS runtime", 1)[1]
    for name in ("BOERDI_VERSION", "GIT_SHA"):
        assert f"ARG {name}" in runtime, name
        assert f"{name}=${{{name}}}" in runtime, name
    workflow = (_DEPLOY.parent / ".github" / "workflows" / "image.yml").read_text("utf-8")
    assert "BOERDI_VERSION=${{ needs.stand.outputs.name }}" in workflow
    assert "GIT_SHA=${{ needs.stand.outputs.sha }}" in workflow
