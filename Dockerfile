# syntax=docker/dockerfile:1.7
#
# Production image (P10-1). ONE image serves all three surfaces: the API
# (/api), the widget bundle (/widget) and the studio SPA (/studio) — ALT needed
# three images because its studio was a separate Next.js server and its chat
# page a separate nginx.
#
# **Why the frontend is built HERE instead of copied in.** ALT's most frequent
# deploy failure is the first section of its own CLAUDE.md: `widget_dist` is
# built by hand outside the image, so a forgotten `npm run build:widget` ships a
# stale bundle while studio and backend already serve the new config ("studio
# new, widget old"). Building both Angular apps inside the image removes the
# step that can be forgotten — the bundle can only be the one built from this
# commit. It costs build time; it cannot drift.
#
# Build context is the repo root (backend/ + frontend/ are both needed):
#     docker build -t boerdi-chat .
#
# The image runs the web process. Migrations run from the SAME image as a
# one-shot job — see deploy/compose.prod.yml — never from the web process,
# which would have N replicas racing on `alembic upgrade head`.


# ── Stage 1: the two Angular apps ────────────────────────────────────
FROM node:22-slim AS frontend
WORKDIR /build

# Manifest-only layer first: dependencies change far less often than source, so
# a source edit re-runs the build but not the install.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# build:widget is the §5.5 single-file build (the budget gate runs in CI);
# build:studio emits the SPA that studio_static.py mounts.
RUN npm run build:widget && npm run build:studio


# ── Stage 2: python dependencies ─────────────────────────────────────
FROM python:3.12-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1
WORKDIR /app

# README.md is not documentation here — pyproject declares `readme`, so the
# wheel build fails without it.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/src ./src
# --no-editable: install a real wheel instead of a .pth pointing at ./src, so
# the runtime stage needs the source tree only inside site-packages. One copy of
# the code in the image, not two that could disagree.
RUN uv sync --locked --no-dev --no-editable


# ── Stage 3: runtime ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# V12 (Audit-Erbe T-9), and here it is actually reachable: ALT shipped this
# block commented out because its container wrote to bind-mounted host paths
# (the SQLite file plus the chatbots/ config tree the studio edits), which a
# non-root uid could not own. In this build the config lives in Postgres (V2)
# and the only runtime write is a tempfile under /tmp during RAG file ingest —
# so the process needs no writable application directory at all.
RUN useradd --create-home --uid 1000 boerdi

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WIDGET_DIST_DIR=/app/widget_dist \
    STUDIO_DIST_DIR=/app/studio_dist

COPY --from=deps /app/.venv /app/.venv

# alembic is deliberately outside the wheel (it is an ops tool, not app code),
# so it is copied as files and run by the migrate job.
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

# The config seed tree (W6). A fresh install has no ALT tree beside it, so the
# last editorial state ships inside the image and `boerdi import-config` fills an
# empty database from here. Afterwards the DB is the source of truth and the
# studio the way to change things — this is the starting point, not a runtime
# dependency.
COPY backend/seeds ./seeds

COPY --from=frontend /build/dist/widget/browser ./widget_dist
COPY --from=frontend /build/dist/studio/browser ./studio_dist

USER boerdi
EXPOSE 8100

# python instead of curl: the base image already has an interpreter, so the
# probe costs no extra package (ALT installed curl AND build-essential into its
# runtime image for this). /health is deliberately DB-free — a warming instance
# that cannot reach Postgres yet is still a live process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=4).status == 200 else 1)"]

# One uvicorn process per container: the cluster scales by replicas (spec §4).
# --workers here would give each worker its own in-process config cache while
# the health check only ever observes one of them.
# --timeout-graceful-shutdown caps the wait for open connections. Without it a
# single SSE stream that never ends blocks a rolling restart forever, which is
# the opposite of the graceful shutdown V12 asks for; 30 s is longer than any
# turn and shorter than compose's stop_grace_period.
#
# --proxy-headers makes uvicorn read X-Forwarded-Proto/-For from traefik.
# Without it every ABSOLUTE redirect the app emits carries the scheme uvicorn
# sees itself — plain http, because traefik terminates TLS and forwards
# unencrypted. Measured on the live server: GET /studio answered
# `Location: http://<host>/studio/`, and only traefik's own 80->443 rule
# repaired it, one needless plaintext hop later.
#
# --forwarded-allow-ips "*" is safe HERE for the same reason TRUST_FORWARDED_FOR
# is (compose.prod.yml): no application service publishes a port, so these
# headers cannot come from a client — only from traefik on the internal network.
CMD ["uvicorn", "boerdi.main:app", "--host", "0.0.0.0", "--port", "8100", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "30"]
