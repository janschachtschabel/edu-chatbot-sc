"""Paket 17 (D7): ``deploy/helm/values.example.yaml`` — das Mapping für Team 6 (Helm).

Leitfaden „Übergabe an Team 6“: T4 liefert eine Beispiel-Values-Struktur, die auf die
Env-Variablen abgebildet wird; Secrets getrennt; optionale Bestandteile (Datenbank, Valkey)
abschaltbar; Ressourcen, Skalierung und Proben, die Compose nicht enthält. T6 baut das Chart
(Nutzer-Entscheid 2026-10-20). Der Wächter hält die Datei mit ``Settings`` und Compose gleich.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
_VALUES = _REPO / "deploy" / "helm" / "values.example.yaml"
_COMPOSE = _REPO / "deploy" / "compose.prod.yml"


def _env_modul():
    pfad = Path(__file__).with_name("test_env_beispiel.py")
    spec = importlib.util.spec_from_file_location("test_env_beispiel", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _values() -> dict:
    return yaml.safe_load(_VALUES.read_text(encoding="utf-8"))


def test_jede_einstellung_ist_abgebildet() -> None:
    v = _values()
    abgebildet = set(v["env"]) | set(v["secretEnv"]["keys"]) | set(v["imageEnv"])
    fehlt = sorted(set(_env_modul()._einstellungen()) - abgebildet)
    assert not fehlt, f"in values.example.yaml ergänzen: {fehlt}"


def test_geheimnisse_nur_als_secret() -> None:
    v = _values()
    geheim = {n for n, g in _env_modul()._einstellungen().items() if g}
    assert geheim <= set(v["secretEnv"]["keys"])
    assert not geheim & set(v["env"]), "Geheimnis im Klartext-Block"


def test_proben_am_internen_port_und_ingress_nur_oeffentlich() -> None:
    v = _values()
    assert v["ports"] == {"public": 8100, "internal": 8101}
    assert v["probes"]["liveness"]["path"] == "/health"
    assert v["probes"]["readiness"]["path"] == "/ready"
    assert {v["probes"][p]["port"] for p in ("liveness", "readiness", "startup")} == {"internal"}
    assert v["ingress"]["port"] == "public"
    assert "/metrics" not in str(v["ingress"])


def test_die_gnadenfrist_deckt_das_herunterfahren() -> None:
    """Uvicorn 30 s + Nachlauf der Züge + Abbruch + Aufräumen (wie ``stop_grace_period``)."""
    from boerdi.api.sse import NACHLAUF_FRIST_S
    from boerdi.obs.tasks import ABBRUCH_FRIST_S

    v = _values()
    # Kubernetes zieht preStop von der Gnadenfrist ab (Review Phase D, K3).
    pre_stop = v["lifecycle"]["preStopSleepSeconds"]
    assert pre_stop >= 5
    from boerdi.services.laeufe_beenden import _FRIST_S as abschluss_s

    assert (v["terminationGracePeriodSeconds"]
            >= abschluss_s + 30 + NACHLAUF_FRIST_S + 2 * ABBRUCH_FRIST_S + 2 + pre_stop)


def test_proben_haben_eine_frist_ueber_der_datenbank_probe() -> None:
    v = _values()
    assert all(v["probes"][p]["timeoutSeconds"] >= 3 for p in ("liveness", "readiness", "startup"))


def test_forwarded_for_nur_mit_bedingung() -> None:
    """Review Phase D (K1): ohne überschreibenden Ingress fälschte jeder Client seine IP."""
    assert _values()["env"]["TRUST_FORWARDED_FOR"] == "false"


def test_cluster_pflichten() -> None:
    v = _values()
    assert v["env"]["RATE_LIMIT_STORAGE_URI"].startswith("valkey://")
    assert v["env"]["LOG_FORMAT"] == "json"
    assert v["postgresql"]["enabled"] is False and v["postgresql"]["external"]["host"]
    assert "enabled" in v["valkey"]


def test_migration_wie_in_compose() -> None:
    compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert _values()["migrateJob"]["command"] == compose["services"]["migrate"]["command"]


def test_image_mit_versions_tag() -> None:
    tag = _values()["image"]["tag"]
    assert tag != "latest" and tag.count(".") == 2  # SemVer für Produktion


# ── Plan 2026-11-19 (E9, Paket B2): das Chart für den Tauschpfad am Repository-Host ──────────────
# Zweistufig: die Vorlagen als Text bzw. YAML (läuft überall, auch in der CI ohne `helm`) — die Form
# des Ingress und die Prüfregeln —, und wo `helm` installiert ist, echtes Rendern samt aller
# Abbruchfälle (`_helm`, sonst übersprungen). Die Abnahme auf Staging macht der Betrieb (S3).

_CHART = _REPO / "deploy" / "helm" / "boerdi-session-ingress"


def _chart_datei(name: str) -> str:
    return (_CHART / name).read_text(encoding="utf-8")


def _chart_werte(name: str = "values.yaml") -> dict:
    return yaml.safe_load(_chart_datei(name))


def test_das_chart_ist_vollstaendig() -> None:
    for name in ("Chart.yaml", "values.yaml", "values-staging.example.yaml",
                 "templates/_helpers.tpl", "templates/ingress.yaml",
                 "templates/service-external.yaml", "templates/secret-ca.yaml",
                 "templates/NOTES.txt"):
        assert (_CHART / name).is_file(), name
    chart = yaml.safe_load(_chart_datei("Chart.yaml"))
    assert chart["apiVersion"] == "v2" and chart["name"] == "boerdi-session-ingress"


def test_der_pfad_ist_der_des_backends() -> None:
    """Ohne rewrite kommt der Pfad unverändert an — das Backend nimmt nur diesen an."""
    from boerdi.api.sitzung import PFAD_AM_REPOSITORY

    assert _chart_werte()["path"] == PFAD_AM_REPOSITORY
    staging = _chart_werte("values-staging.example.yaml")
    assert staging.get("path", PFAD_AM_REPOSITORY) == PFAD_AM_REPOSITORY
    assert _values()["sessionIngress"]["path"] == PFAD_AM_REPOSITORY
    assert f'"{PFAD_AM_REPOSITORY}"' in _chart_datei("templates/_helpers.tpl")


def test_genau_ein_ingress_exact_ohne_rewrite_und_ohne_affinitaet() -> None:
    text = _chart_datei("templates/ingress.yaml")
    assert text.count("kind: Ingress") == 1
    assert "pathType: Exact" in text
    for verboten in ("rewrite-target", "use-regex", "affinity", "ImplementationSpecific",
                     "pathType: Prefix", "upstream-vhost"):
        assert verboten not in text, verboten
    # Pfad und Prüfung hängen am selben Helfer — sonst prüfte die Regel einen anderen Wert.
    assert 'include "boerdi_session.pruefen"' in text
    assert 'include "boerdi_session.pfad"' in text


def test_die_renderpruefung_bricht_bei_falschem_pfad_und_falschem_ziel_ab() -> None:
    helfer = _chart_datei("templates/_helpers.tpl")
    pruefen = helfer[helfer.index('define "boerdi_session.pruefen"'):]
    for regel in ('hasPrefix "/edu-sharing/"', 'hasSuffix "/auth/session"',
                  "rewrite-target", "use-regex", "affinity"):
        assert regel in pruefen, regel
    # Je Regel ein Abbruch: Host fehlt, Pfad (3), Ziel (keins/beide), ExternalName-Form,
    # verbotene Annotationen.
    assert pruefen.count("fail ") >= 7


def test_externalname_spricht_https_mit_pruefung_und_behaelt_den_host() -> None:
    ingress = _chart_datei("templates/ingress.yaml")
    for schluessel in ("backend-protocol", "proxy-ssl-secret", "proxy-ssl-verify",
                       "proxy-ssl-name", "proxy-ssl-server-name"):
        assert f"nginx.ingress.kubernetes.io/{schluessel}" in ingress, schluessel
    dienst = _chart_datei("templates/service-external.yaml")
    assert "type: ExternalName" in dienst and ".Values.backend.externalName.host" in dienst
    ca = _chart_datei("templates/secret-ca.yaml")
    assert "ca.crt" in ca and ".Values.backend.externalName.caBundle" in ca


def test_vorgaben_rendern_nichts_von_selbst() -> None:
    """Ohne Host und Ziel bricht das Rendern ab — ein halb gesetztes Chart geht nie still durch."""
    v = _chart_werte()
    assert v["host"] == ""
    extern = v["backend"]["externalName"]
    assert v["backend"]["service"]["name"] == "" and extern["host"] == ""
    # Review B (1, 2): Prüfung ab Werk Pflicht, eigener Eingang des Chat-Rechners
    assert extern["caBundle"] == "" and extern["verifySecret"] == ""
    assert extern["insecureSkipVerify"] is False and extern["port"] == 8443
    assert v["className"] == "nginx"


def test_die_staging_werte_zeigen_auf_den_chat_rechner() -> None:
    v = _chart_werte("values-staging.example.yaml")
    assert v["host"] == "repository.staging.openeduhub.net"
    extern = v["backend"]["externalName"]
    assert extern["host"] and "://" not in extern["host"] and extern["port"] == 8443
    assert not v["backend"].get("service", {}).get("name")
    assert "caBundle" in extern and not extern.get("insecureSkipVerify")
    assert "isrgrootx1.pem" in _chart_datei("values-staging.example.yaml")


def _helm(*argumente: str):
    import shutil
    import subprocess

    import pytest

    helm = shutil.which("helm")
    if not helm:
        pytest.skip("helm nicht installiert — die Textprüfungen oben gelten trotzdem")
    return subprocess.run([helm, "template", "s", str(_CHART), *argumente],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


_STAGING = ("-f", str(_CHART / "values-staging.example.yaml"))
#: Zweites Review B (1): ohne diese Bestätigung bricht das Rendern mit Prüf-Secret ab.
_BESTAETIGT = ("--set", "backend.externalName.proxySslLocationOnlyGesetzt=true")
_PEM = "-----BEGIN CERTIFICATE-----\nTUlJQmFzZTY0LVRlc3Q=\n-----END CERTIFICATE-----\n"


def _mit_ca(tmp_path) -> tuple[str, ...]:
    datei = tmp_path / "ca.pem"
    datei.write_bytes(_PEM.encode("ascii"))   # ohne die Zeilenenden von Windows
    # helm liest Rückstriche im Wert als Escape — unter Windows also Schrägstriche
    return (*_STAGING, "--set-file", f"backend.externalName.caBundle={datei.as_posix()}",
            *_BESTAETIGT)


def _objekte(ergebnis) -> dict[str, dict]:
    assert ergebnis.returncode == 0, ergebnis.stderr
    return {o["kind"]: o for o in yaml.safe_load_all(ergebnis.stdout) if o}


def test_helm_rendert_die_staging_werte_mit_ca_zu_einem_geprueften_ingress(tmp_path) -> None:
    """Wo ``helm`` da ist, wird echt gerendert (Abnahme S3)."""
    objekte = _objekte(_helm(*_mit_ca(tmp_path)))
    regel = objekte["Ingress"]["spec"]["rules"][0]
    assert regel["host"] == "repository.staging.openeduhub.net"
    pfad = regel["http"]["paths"][0]
    assert pfad["pathType"] == "Exact"
    assert pfad["path"] == "/edu-sharing/services/boerdi/auth/session"
    assert pfad["backend"]["service"]["port"]["number"] == 8443
    assert objekte["Service"]["spec"]["type"] == "ExternalName"
    # Review B (1): das CA-Secret liegt im Namespace des Ingress, und der Ingress prüft damit
    geheimnis = objekte["Secret"]
    assert geheimnis["stringData"]["ca.crt"] == _PEM
    a = objekte["Ingress"]["metadata"]["annotations"]
    assert a["nginx.ingress.kubernetes.io/backend-protocol"] == "HTTPS"
    assert a["nginx.ingress.kubernetes.io/proxy-ssl-secret"] == \
        f"default/{geheimnis['metadata']['name']}"
    assert a["nginx.ingress.kubernetes.io/proxy-ssl-verify"] == "on"
    assert a["nginx.ingress.kubernetes.io/proxy-ssl-server-name"] == "on"
    assert a["nginx.ingress.kubernetes.io/proxy-ssl-name"] == "87.106.127.225.nip.io"
    assert not [k for k in a if "rewrite" in k or "affinity" in k or "regex" in k]


def test_helm_ohne_pruefung_bricht_ab_ausser_ausdruecklich() -> None:
    """Review B (1): ohne ``proxy-ssl-secret`` wertet ingress-nginx weder SNI noch Prüfung aus —
    das Sitzungs-Cookie ginge ungeprüft über das Netz."""
    ohne = _helm(*_STAGING)
    assert ohne.returncode != 0 and "caBundle" in ohne.stderr, ohne.stderr
    objekte = _objekte(_helm(*_STAGING, "--set", "backend.externalName.insecureSkipVerify=true"))
    a = objekte["Ingress"]["metadata"]["annotations"]
    assert a == {"nginx.ingress.kubernetes.io/backend-protocol": "HTTPS"}
    assert "Secret" not in objekte
    assert "insecureSkipVerify" in _chart_datei("templates/NOTES.txt")


def test_helm_nimmt_ein_vorhandenes_secret_nur_aus_dem_eigenen_namespace() -> None:
    for wert, erwartet in (("default/le-ca", "default/le-ca"), ("le-ca", "default/le-ca")):
        objekte = _objekte(_helm(*_STAGING, *_BESTAETIGT,
                                 "--set", f"backend.externalName.verifySecret={wert}"))
        a = objekte["Ingress"]["metadata"]["annotations"]
        assert a["nginx.ingress.kubernetes.io/proxy-ssl-secret"] == erwartet
        assert "Secret" not in objekte
    fremd = _helm(*_STAGING, *_BESTAETIGT,
                  "--set", "backend.externalName.verifySecret=edu-sharing/le-ca")
    assert fremd.returncode != 0 and "Namespace" in fremd.stderr, fremd.stderr
    # Zweites Review B (5): mehr als ein Schrägstrich ist keine Angabe „<namespace>/<secret>“
    zwei = _helm(*_STAGING, *_BESTAETIGT, "--set", "backend.externalName.verifySecret=default/a/b")
    assert zwei.returncode != 0 and "<namespace>/<secret>" in zwei.stderr, zwei.stderr


def test_helm_prueft_die_form_der_ca(tmp_path) -> None:
    kaputt = _helm(*_STAGING, "--set-string", "backend.externalName.caBundle=kein-zertifikat")
    assert kaputt.returncode != 0 and "PEM" in kaputt.stderr, kaputt.stderr
    beides = _helm(*_mit_ca(tmp_path), "--set", "backend.externalName.verifySecret=le-ca")
    assert beides.returncode != 0 and "nicht beides" in beides.stderr, beides.stderr


def test_helm_ziel_im_cluster_ohne_leere_annotationen() -> None:
    """Review B (NIT 6): ohne Inhalt kein ``annotations:``."""
    objekte = _objekte(_helm("--set", "host=r.example.org", "--set", "backend.service.name=boerdi"))
    assert "annotations" not in objekte["Ingress"]["metadata"]
    assert objekte["Ingress"]["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"] == \
        {"name": "boerdi", "port": {"number": 8100}}


def test_helm_bricht_bei_falschem_pfad_und_verbotener_annotation_ab(tmp_path) -> None:
    ca = _mit_ca(tmp_path)
    anm = r"annotations.nginx\.ingress\.kubernetes\.io/"
    for setzen, meldung in (
        ("path=/services/boerdi/auth/session", "unter /edu-sharing/"),
        ("path=/edu-sharing/services/boerdi/session", "auf /auth/session enden"),
        ("path=/edu-sharing/services/x/auth/session", "nimmt ohne rewrite nur"),
        ("host=", "host fehlt"),
        ("backend.service.name=boerdi", "nicht beides"),
        (f"{anm}rewrite-target=/x", "verboten"),
        # Review B (3): weitere Schlüssel, die den Repository-Host oder den Weg verbiegen
        (f"{anm}upstream-vhost=x", "verboten"),
        (f"{anm}configuration-snippet=x", "verboten"),
        (f"{anm}server-snippet=x", "verboten"),
        (f"{anm}permanent-redirect=https://x", "verboten"),
        (f"{anm}app-root=/x", "verboten"),
        (f"{anm}ssl-passthrough=true", "verboten"),
        # Zweites Review B (2): Schlüssel der Server-Ebene — gälten für den ganzen Repository-Host
        (f"{anm}auth-tls-verify-client=on", "verboten"),
        (f"{anm}server-alias=x.example.org", "verboten"),
        (f"{anm}ssl-ciphers=ALL", "verboten"),
        (f"{anm}ssl-prefer-server-ciphers=true", "verboten"),
        # … und die das Chart bei Ziel B selbst setzt (sonst doppelte YAML-Schlüssel)
        (f"{anm}backend-protocol=HTTP", "setzt das Chart"),
        (f"{anm}proxy-ssl-verify=off", "setzt das Chart"),
    ):
        ergebnis = _helm(*ca, "--set-string", setzen)
        assert ergebnis.returncode != 0, setzen
        assert meldung in ergebnis.stderr, (setzen, ergebnis.stderr)


def test_helm_mit_pruefung_nur_nach_bestaetigung_des_server_blocks(tmp_path) -> None:
    """Zweites Review B (1): ingress-nginx übernimmt die proxy-ssl-Werte des ersten Ingress eines
    Hosts für den ganzen Server-Block, solange ``proxy-ssl-location-only`` nicht ``"true"`` ist —
    andere HTTPS-Ziele am Repository-Host prüften dann gegen den Chat-Host (502). Das Chart kann
    es nicht abschalten; der Betrieb bestätigt es ausdrücklich."""
    datei = tmp_path / "ca.pem"
    datei.write_bytes(_PEM.encode("ascii"))
    ohne = _helm(*_STAGING, "--set-file", f"backend.externalName.caBundle={datei.as_posix()}")
    assert ohne.returncode != 0 and "proxy-ssl-location-only" in ohne.stderr, ohne.stderr
    # Drittes Review B (1): die Ersatzprüfung „kein anderes HTTPS-Ziel am Host“ gibt es nicht mehr
    assert "GRPCS" not in ohne.stderr and "anderer Ingress" not in ohne.stderr, ohne.stderr
    # ohne Prüf-Secret setzt das Chart keine proxy-ssl-Werte — dort braucht es keine Bestätigung
    _objekte(_helm(*_STAGING, "--set", "backend.externalName.insecureSkipVerify=true"))
    extern = _chart_werte()["backend"]["externalName"]
    assert extern["proxySslLocationOnlyGesetzt"] is False and "locationOnlyBestaetigt" not in extern


def test_notes_deuten_502_und_nennen_die_pruefbefehle() -> None:
    """Zweites Review B (3)."""
    notes = _chart_datei("templates/NOTES.txt")
    for stelle in ("502", "openssl s_client", "Verify return code: 0",
                   "upstream SSL certificate verify error", "proxy-ssl-location-only"):
        assert stelle in notes, stelle
    # Drittes Review B (8): der Block nur mit Prüf-Secret
    assert '{{- if include "boerdi_session.pruefSecret" . }}\n502' in notes



def test_helm_sperrt_mirror_und_proxy_ssl_auch_im_cluster(tmp_path) -> None:
    """Drittes Review B (4): ``mirror-*`` schickte das Sitzungs-Cookie an ein zweites Ziel;
    ``proxy-ssl-*`` gehört nicht zu Ziel A (HTTP auf 8100), ``backend-protocol`` dort nur HTTP."""
    anm = r"annotations.nginx\.ingress\.kubernetes\.io/"
    cluster = ("--set", "host=r.example.org", "--set", "backend.service.name=boerdi")
    for setzen in (f"{anm}mirror-target=https://x.example.org/m",
                   f"{anm}proxy-ssl-verify=on",
                   f"{anm}backend-protocol=HTTPS"):
        ergebnis = _helm(*cluster, "--set-string", setzen)
        assert ergebnis.returncode != 0, setzen
        assert "annotations:" in ergebnis.stderr, (setzen, ergebnis.stderr)
    ergebnis = _helm(*_mit_ca(tmp_path), "--set-string", f"{anm}mirror-request-body=on")
    assert ergebnis.returncode != 0 and "verboten" in ergebnis.stderr, ergebnis.stderr
    erlaubt = _objekte(_helm(*cluster, "--set-string", f"{anm}backend-protocol=HTTP"))
    assert erlaubt["Ingress"]["metadata"]["annotations"] == {
        "nginx.ingress.kubernetes.io/backend-protocol": "HTTP"}


def test_helm_weist_host_mit_port_und_secret_mit_schraegstrich_am_ende_ab(tmp_path) -> None:
    """Viertes Review B (10): ``host`` mit Port träfe nie den Host-Kopf; ``<secret>/`` ist keine
    Angabe."""
    mit_port = _helm(*_mit_ca(tmp_path), "--set", "host=r.example.org:443")
    assert mit_port.returncode != 0 and "ohne Port" in mit_port.stderr, mit_port.stderr
    schraeg = _helm(*_STAGING, *_BESTAETIGT, "--set", "backend.externalName.verifySecret=le-ca/")
    assert schraeg.returncode != 0 and "<namespace>/<secret>" in schraeg.stderr, schraeg.stderr


def test_notes_nennen_traefik_nur_bei_ziel_b_und_die_richtige_ca() -> None:
    """Viertes Review B (7, 8)."""
    notes = _chart_datei("templates/NOTES.txt")
    zeile_traefik = next(z for z in notes.splitlines() if "page not found" in z)
    davor = notes[:notes.index(zeile_traefik)]
    assert davor.rfind("{{- if .Values.backend.externalName.host }}") > davor.rfind("{{- end }}")
    assert "<CA-Datei>" in notes and "verifySecret: dessen ca.crt" in notes
    assert "proxySslLocationOnlyGesetzt" in notes

