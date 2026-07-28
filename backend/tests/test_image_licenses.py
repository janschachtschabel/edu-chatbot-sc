"""C7: jedes Container-Image im Repo hat eine festgehaltene Lizenz-Entscheidung.

**Warum es das gibt.** Die beiden Lizenz-Gates in CI sehen nur *Pakete*:
``pip-licenses`` die Python-Seite, ``license-checker`` die npm-Seite. Der Redis-
**Server** kam als Docker-Image und lief an beiden vorbei — redis-py (MIT)
bestand das Gate, während das Image dahinter unter RSALv2 / SSPLv1 / AGPLv3
steht, alle drei auf der Verbotsliste der Eisernen Regel 1. Am 2026-07-27
gemessen und in P10-6 durch Valkey ersetzt; dieser Test schließt die Lücke, die
den Tausch nötig machte.

**Was geprüft wird:** die Lizenz der *Hauptkomponente* eines Images — also des
Dienstes, der das Image IST (Valkey, Postgres, traefik, der CPython-Interpreter).
**Nicht** die Systempakete der Basis-Schicht: jedes debian-slim-Image enthält
GPL-Userland (bash, coreutils), ein Gate, das daran scheitert, scheitert an allem
und wird abgeschaltet. Regel 1 zielt auf Copyleft-Pflichten für **unseren** Code,
und ein unverändert gezogenes Basis-Image erzeugt keine.

**Wo gesucht wird:** in Dockerfiles (``FROM`` und ``COPY --from=``), in
Compose-Dateien (``image:``) und in Workflow-Dateien — dort sowohl am
``image:``-Schlüssel als auch an ``docker run|pull|create`` im Shell-Block, weil
``image.yml`` seine Dienste so startet. Gesucht wird nach der Datei-Art, nicht
nach einer gepflegten Pfadliste. Beliebige YAMLs bleiben außen vor: die
Seed-Configs im Backend führen ``image:``-Schlüssel, die keine Container meinen.

**Warum eine Positivliste und keine Abfrage.** Am 2026-07-27 an den Images
gemessen, die wir wirklich ziehen: ``valkey/valkey:8-alpine`` trägt nur
``org.opencontainers.image.source``, ``pgvector/pgvector:pg17`` und
``jaegertracing/jaeger:2.19.0`` tragen **gar keine** Labels. Es gibt nichts
auszulesen — die Entscheidung muss ein Mensch festhalten, und genau das ist der
Zweck.

**Tags sind bewusst mit gepinnt.** Redis war bis 7.2 BSD-3-Clause und ist es ab 8
nicht mehr: eine Lizenz kann sich mit der Version ändern. Ein Versions-Sprung
muss deshalb an dieser Liste vorbei.

**Grenze, gemessen statt vermutet.** Im Shell-Block wird ein Image an seiner
``name:tag``-Form erkannt — ein **ungetaggter** Aufruf (``docker run alpine sh``)
hat sie nicht und bleibt ungesehen. In YAML und Dockerfiles gibt es die Lücke
nicht, dort steht die Referenz an einer festen Stelle. Aufgefangen wird sie
nicht: „jeder ``docker``-Befehl muss ein Image nennen" schlägt auf Prosa an —
in ``image.yml`` stehen zwei Kommentare, die „docker run" erwähnen (probiert).
Ungetaggt heißt ohnehin ungepinnt und gehört im Review abgelehnt; heute trifft
es nur ``docker run --rm boerdi-chat alembic …``, also unser eigenes Image, das
hier ohnehin nicht zu prüfen ist.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Eiserne Regel 1: „Nur MIT / Apache-2.0 / BSD / PSF / PostgreSQL-Lizenz."
ALLOWED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "PSF-2.0",
    "PostgreSQL",
}

# Lizenz der Hauptkomponente je Image. Jede Zeile nennt die Quelle des Belegs —
# ohne Beleg gehört hier nichts hinein, sonst segnet das Gate eine Vermutung ab.
# Alle sieben am 2026-07-27 upstream nachgelesen, nicht aus dem Gedächtnis.
IMAGE_LICENSES: dict[str, str] = {
    # LICENSE-Text ist die PostgreSQL-Form („Portions Copyright (c) 1996-…,
    # PostgreSQL Global Development Group"), dieselbe für Server und Erweiterung.
    # GitHubs API meldet dafür NOASSERTION — ihr Detektor kennt die Form nicht,
    # das ist kein fehlender Lizenz-Hinweis.
    "pgvector/pgvector:pg17": "PostgreSQL",
    # github.com/valkey-io/valkey, spdx_id BSD-3-Clause. Der Grund für P10-6.
    "valkey/valkey:8-alpine": "BSD-3-Clause",
    # github.com/traefik/traefik/LICENSE.md — MIT-Text.
    "traefik:v3.6": "MIT",
    # github.com/jaegertracing/jaeger/LICENSE — „Apache License Version 2.0".
    "jaegertracing/jaeger:2.19.0": "Apache-2.0",
    # docs.python.org/3/license.html — PSF License Version 2 für CPython.
    "python:3.12-slim": "PSF-2.0",
    # github.com/nodejs/node/LICENSE, erster Block (Node.js selbst) = MIT-Text.
    # Der Rest der Datei sind gebündelte Fremd-Lizenzen; GitHub meldet deshalb
    # NOASSERTION.
    "node:22-slim": "MIT",
    # github.com/astral-sh/uv — dual MIT ODER Apache-2.0, hier LICENSE-MIT.
    "ghcr.io/astral-sh/uv:0.7": "MIT",
}

# Unser eigenes Image: aus DIESEM Repo gebaut, hat keine fremde Lizenz. Seine
# Basis-Images stehen im Dockerfile und werden dort gescannt, es geht also nichts
# verloren. `BOERDI_IMAGE` kann beim Deploy auf eine Registry-Kopie zeigen — das
# bleibt das eigene Artefakt.
OWN_IMAGES = {"boerdi-chat"}

# Verzeichnisse ohne eigene Deploy-Dateien; ungeprüft würde der Lauf durch
# node_modules und .venv kriechen.
PRUNED_DIRS = {
    ".angular",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "htmlcov",
    "node_modules",
}

_YAML_IMAGE = re.compile(r"^\s*image:\s*(\S+)", re.MULTILINE)
# `.github/workflows/image.yml` startet seine Dienste per `docker run` in einem
# Shell-Block, nicht über einen `image:`-Schlüssel — ein Scanner, der nur YAML-
# Schlüssel liest, übersieht sie. Genau die Lückenklasse, gegen die dieser Test
# antritt, deshalb hier mit abgedeckt.
_DOCKER_CMD = re.compile(r"\bdocker\s+(?:run|pull|create)\b((?:[^\n\\]|\\\n)*)")
_IMAGE_TOKEN = re.compile(r"^([a-z0-9][a-z0-9._/-]*):([A-Za-z0-9._-]+)$")
_DOCKER_FROM = re.compile(r"^\s*FROM\s+(\S+)", re.MULTILINE | re.IGNORECASE)
_DOCKER_STAGE = re.compile(r"^\s*FROM\s+\S+\s+AS\s+(\S+)", re.MULTILINE | re.IGNORECASE)
_DOCKER_COPY_FROM = re.compile(r"^\s*COPY\s+--from=(\S+)", re.MULTILINE | re.IGNORECASE)
# Compose-Default-Form ${VAR:-wert}; ohne Default ist die Referenz nicht prüfbar.
_COMPOSE_DEFAULT = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}$")


def deploy_files() -> list[Path]:
    """Alle Dateien, aus denen heraus ein Image gezogen wird.

    Gesucht wird nach der Datei-*Art*, nicht nach einer gepflegten Pfadliste: ein
    neues ``services/foo/Dockerfile`` oder ein ``deploy/compose.staging.yml``
    wird sonst still nicht geprüft — dieselbe Lücke, die dieser Test schließt.
    Beliebige YAMLs bleiben außen vor: die Seed-Configs im Backend führen
    ``image:``-Schlüssel, die keine Container meinen.
    """
    found: list[Path] = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in PRUNED_DIRS]
        in_workflows = Path(root).name == "workflows"
        for name in files:
            is_compose = "compose" in name and name.endswith((".yml", ".yaml"))
            is_workflow = in_workflows and name.endswith((".yml", ".yaml"))
            if name.startswith("Dockerfile") or is_compose or is_workflow:
                found.append(Path(root) / name)
    return sorted(found)


def _normalize(ref: str) -> str:
    ref = ref.strip().strip("\"'")
    default = _COMPOSE_DEFAULT.match(ref)
    return default.group(1) if default else ref


def images_pulled_by_shell(text: str) -> set[str]:
    """Images aus ``docker run|pull|create``-Aufrufen in Shell-Blöcken.

    Erkannt wird an der Form ``name:tag`` statt an der Argument-Stellung: welches
    Wort das Image ist, hinge sonst davon ab, ob die vorige Option einen Wert
    nimmt (``--rm nginx:alpine`` gegen ``--name x nginx:alpine``) — eine
    Flaggen-Tabelle, die bei jeder neuen Option falsch wird. Port-Abbildungen
    (``-p 8100:8100``) haben dieselbe Form und werden am rein numerischen
    Namensteil abgewiesen; ein Image-Repository ist nie nur eine Zahl.
    """
    found: set[str] = set()
    for args in _DOCKER_CMD.findall(text):
        for raw in args.replace("\\\n", " ").split():
            token = raw.strip("\"'")
            if any(c in token for c in ("://", "$", "=", "{", ",")):
                continue
            match = _IMAGE_TOKEN.match(token)
            if match and not re.fullmatch(r"[\d.]+", match.group(1)):
                found.add(token)
    return found


def images_in(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.name.startswith("Dockerfile"):
        stages = {s.lower() for s in _DOCKER_STAGE.findall(text)}
        refs = set(_DOCKER_FROM.findall(text))
        # `COPY --from=` nennt entweder eine frühere Build-Stufe (kein Image)
        # oder ein echtes Image wie ghcr.io/astral-sh/uv:0.7.
        refs |= {r for r in _DOCKER_COPY_FROM.findall(text) if r.lower() not in stages}
    else:
        refs = set(_YAML_IMAGE.findall(text))
    return {_normalize(r) for r in refs} | images_pulled_by_shell(text)


def scan() -> dict[str, list[str]]:
    """Image-Referenz -> Dateien, die sie ziehen (repo-relative Pfade)."""
    hits: dict[str, list[str]] = {}
    for path in deploy_files():
        for image in images_in(path):
            # Beim eigenen Image zählt nur der Name: sein Tag ist eine Bau-Marke
            # (`boerdi-chat:ci`), keine fremde Version mit eigener Lizenz.
            if image.split(":")[0] in OWN_IMAGES:
                continue
            hits.setdefault(image, []).append(path.relative_to(REPO).as_posix())
    return hits


def test_shell_scan_finds_the_image_and_not_its_neighbours() -> None:
    """Form von ``.github/workflows/image.yml`` — Zeilenfortsetzung inklusive.

    Die Nachbarn sind der eigentliche Test: ``-p 8100:8100`` hat exakt dieselbe
    ``name:tag``-Form wie ein Image, und die Storage-URI enthält ebenfalls einen
    Doppelpunkt. Beide dürfen nicht als Image durchgehen.
    """
    snippet = """
          docker run -d --name valkey --network "$NET" \\
            --health-cmd "valkey-cli ping" \\
            -p 6379:6379 \\
            valkey/valkey:8-alpine valkey-server --save '' --appendonly no
          docker run -d --name boerdi -p 8100:8100 \\
            -e RATE_LIMIT_STORAGE_URI=valkey://valkey:6379/0 \\
            boerdi-chat:ci
    """
    assert images_pulled_by_shell(snippet) == {"valkey/valkey:8-alpine", "boerdi-chat:ci"}


def test_shell_scan_survives_a_flag_directly_before_the_image() -> None:
    """``--rm`` nimmt keinen Wert — an der Stellung wäre das Image hier verloren.

    Der Grund, warum die Erkennung an der Form hängt und nicht an der Position:
    eine Flaggen-Tabelle müsste für jede Option wissen, ob sie ein Argument
    schluckt, und wäre ab der ersten neuen Option still falsch.
    """
    assert images_pulled_by_shell("docker run --rm nginx:alpine") == {"nginx:alpine"}


def test_every_image_has_a_recorded_license() -> None:
    unknown = {img: files for img, files in scan().items() if img not in IMAGE_LICENSES}
    assert not unknown, (
        "Container-Image ohne festgehaltene Lizenz: "
        + "; ".join(f"{img} ({', '.join(files)})" for img, files in sorted(unknown.items()))
        + " — Lizenz upstream prüfen und in IMAGE_LICENSES eintragen (mit Beleg)."
    )


def test_no_unresolvable_image_reference() -> None:
    """``image: ${FOO}`` ohne Default kann dieses Gate nicht prüfen.

    Das laut zu sagen ist der Punkt: eine stumm übersprungene Referenz wäre
    genau die Lücke, wegen der es diesen Test gibt.
    """
    unresolved = {img: files for img, files in scan().items() if "${" in img}
    assert not unresolved, f"Image-Referenz ohne Default-Wert: {sorted(unresolved)}"


def test_allowlist_has_no_stale_entries() -> None:
    """Verwaiste Zeilen fliegen raus — und der Scanner kann nicht leer laufen.

    Fände der Scanner nichts, wäre jede Zeile verwaist und dieser Test rot. Ohne
    ihn ginge der erste Test durch, weil eine leere Menge keine Ausreißer hat.
    """
    stale = set(IMAGE_LICENSES) - set(scan())
    assert not stale, f"IMAGE_LICENSES nennt Images, die das Repo nicht mehr zieht: {sorted(stale)}"


def test_recorded_licenses_pass_iron_rule_1() -> None:
    forbidden = {img: lic for img, lic in IMAGE_LICENSES.items() if lic not in ALLOWED_LICENSES}
    assert not forbidden, (
        f"Lizenz nicht von Regel 1 gedeckt (erlaubt: {sorted(ALLOWED_LICENSES)}): {forbidden}"
    )
