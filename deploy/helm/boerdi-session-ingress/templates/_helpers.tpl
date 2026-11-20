{{/*
Helfer des Charts boerdi-session-ingress (Plan 2026-11-19, E9). Eigenständig wie die Helfer des
md-editors (helm/md-collab-editor/templates/_helpers.tpl): keine Abhängigkeit auf eine Bibliothek.
*/}}

{{/* Name der Objekte — nameOverride gewinnt, sonst <release>-<chart>. */}}
{{- define "boerdi_session.name" -}}
{{- default (printf "%s-%s" .Release.Name .Chart.Name) .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "boerdi_session.labels" -}}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/name: {{ include "boerdi_session.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/* Der Pfad mit genau einem Schrägstrich vorn und keinem am Ende. */}}
{{- define "boerdi_session.pfad" -}}
{{- printf "/%s" (trimAll "/" .Values.path) -}}
{{- end -}}

{{/* Der Service, an den der Ingress leitet: der eigene ExternalName-Service oder der des Backends. */}}
{{- define "boerdi_session.ziel" -}}
{{- if .Values.backend.externalName.host -}}
{{- include "boerdi_session.name" . -}}
{{- else -}}
{{- .Values.backend.service.name -}}
{{- end -}}
{{- end -}}

{{- define "boerdi_session.zielPort" -}}
{{- if .Values.backend.externalName.host -}}
{{- .Values.backend.externalName.port | int -}}
{{- else -}}
{{- .Values.backend.service.port | int -}}
{{- end -}}
{{- end -}}

{{/* Name des CA-Secrets, das das Chart aus backend.externalName.caBundle anlegt. */}}
{{- define "boerdi_session.caSecretName" -}}
{{- printf "%s-ca" (include "boerdi_session.name" . | trunc 60 | trimSuffix "-") -}}
{{- end -}}

{{/*
Das Secret für proxy-ssl-secret als „<namespace>/<name>“ — aus caBundle (vom Chart angelegt) oder
verifySecret (ohne Namespace: der dieses Releases). Leer: keine Prüfung (nur mit insecureSkipVerify).
*/}}
{{- define "boerdi_session.pruefSecret" -}}
{{- $e := .Values.backend.externalName -}}
{{- if $e.caBundle -}}
{{- printf "%s/%s" .Release.Namespace (include "boerdi_session.caSecretName" .) -}}
{{- else if $e.verifySecret -}}
{{- if contains "/" $e.verifySecret -}}
{{- $e.verifySecret -}}
{{- else -}}
{{- printf "%s/%s" .Release.Namespace $e.verifySecret -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Prüfungen beim Rendern — brechen mit einer Meldung ab statt ein Objekt zu liefern, das still
404 antwortet, dem Repository-Host schadet oder das Sitzungs-Cookie ungeprüft weiterreicht:
- host gesetzt, ohne Schema und Pfad;
- path unter /edu-sharing/ (nur dorthin schickt der Browser das Sitzungs-Cookie), endet auf
  /auth/session (so prüfen Backend und Widget MCP_SESSION_URL) und ist der Pfad, den das Backend
  annimmt (api/sitzung.py, PFAD_AM_REPOSITORY) — ohne rewrite kommt er unverändert an;
- genau ein Ziel: backend.service.name ODER backend.externalName.host (ohne Schema und Pfad);
- Ziel B nur mit Prüfung des Zertifikats (Review B, 1): caBundle (PEM) oder verifySecret im eigenen
  Namespace als „<secret>“ oder „<namespace>/<secret>“, nicht beides — oder ausdrücklich
  insecureSkipVerify. ingress-nginx wertet die proxy-ssl-Annotationen ohne proxy-ssl-secret gar
  nicht aus (kein SNI, keine Prüfung);
- mit Prüfung nur nach proxySslLocationOnlyGesetzt (zweites/drittes Review B, 1): ingress-nginx
  übernimmt die proxy-ssl-Werte des ersten Ingress eines Hosts für den GANZEN Server-Block,
  solange die Controller-ConfigMap proxy-ssl-location-only nicht "true" hat. Was dort sonst
  HTTPS spricht (andere Ziele, auch AUTO_HTTP, auth-url, global-auth-url, mirror-target), prüfte
  dann gegen den Chat-Host (502). Eine Ersatzprüfung über die Ingresse des Hosts deckt das nicht
  ab — einziger Weg ist die ConfigMap; der Betrieb bestätigt sie ausdrücklich (§16);
- keine Annotation, die den Weg oder den Repository-Host verbiegt (Review B, 3): rewrite-target und
  use-regex (stellten alle Pfade des Repository-Hosts auf Regex um), affinity (ein eigenes
  INGRESSCOOKIE mit längerem Pfad ginge vor dem des Repositorys an den Server), upstream-vhost
  (der Host-Kopf muss bleiben), *-snippet (freies nginx), permanent-/temporal-redirect, app-root,
  ssl-passthrough, und die der Server-Ebene, die für den ganzen Repository-Host gälten
  (auth-tls-*, server-alias, ssl-ciphers, ssl-prefer-server-ciphers — zweites Review B, 2) und
  mirror-* (schickte das Sitzungs-Cookie an ein zweites Ziel — drittes Review B, 4). Bei Ziel B
  keine, die das Chart selbst setzt (backend-protocol, proxy-ssl-*; sonst stünde der Schlüssel
  doppelt im YAML); bei Ziel A (HTTP auf 8100) kein proxy-ssl-* und backend-protocol nur HTTP.
*/}}
{{- define "boerdi_session.pruefen" -}}
{{- if not .Values.host }}
{{- fail "host fehlt: der Host des Repositorys, so wie die Redaktion ihn aufruft (ohne https://)" }}
{{- end }}
{{- if or (contains "/" .Values.host) (contains ":" .Values.host) }}
{{- fail "host ohne Schema, Pfad und ohne Port angeben, z. B. repository.example.org" }}
{{- end }}
{{- $pfad := include "boerdi_session.pfad" . }}
{{- if not (hasPrefix "/edu-sharing/" $pfad) }}
{{- fail "path muss unter /edu-sharing/ liegen: nur dorthin schickt der Browser das Sitzungs-Cookie" }}
{{- end }}
{{- if not (hasSuffix "/auth/session" $pfad) }}
{{- fail "path muss auf /auth/session enden: so prüfen Backend und Widget MCP_SESSION_URL" }}
{{- end }}
{{- if ne $pfad "/edu-sharing/services/boerdi/auth/session" }}
{{- fail "path: das Backend nimmt ohne rewrite nur /edu-sharing/services/boerdi/auth/session an (api/sitzung.py)" }}
{{- end }}
{{- $service := .Values.backend.service.name }}
{{- $e := .Values.backend.externalName }}
{{- $extern := $e.host }}
{{- if and $service $extern }}
{{- fail "backend: entweder service.name (im Cluster) oder externalName.host (eigener Rechner), nicht beides" }}
{{- end }}
{{- if not (or $service $extern) }}
{{- fail "backend: service.name (im Cluster) oder externalName.host (eigener Rechner) setzen" }}
{{- end }}
{{- if $extern }}
{{- if contains "/" $extern }}
{{- fail "backend.externalName.host ohne https:// und ohne Pfad angeben, z. B. chat.example.org" }}
{{- end }}
{{- if and $e.caBundle $e.verifySecret }}
{{- fail "backend.externalName: caBundle oder verifySecret, nicht beides" }}
{{- end }}
{{- if and $e.caBundle (not (contains "BEGIN CERTIFICATE" $e.caBundle)) }}
{{- fail "backend.externalName.caBundle ist kein PEM-Zertifikat (-----BEGIN CERTIFICATE-----)" }}
{{- end }}
{{- if or (gt (len (splitList "/" (toString $e.verifySecret))) 2) (hasSuffix "/" (toString $e.verifySecret)) (hasPrefix "/" (toString $e.verifySecret)) }}
{{- fail "backend.externalName.verifySecret: „<secret>“ oder „<namespace>/<secret>“ — ein Schrägstrich, beide Teile gefüllt" }}
{{- end }}
{{- if and $e.verifySecret (contains "/" $e.verifySecret) (ne (first (splitList "/" $e.verifySecret)) .Release.Namespace) }}
{{- fail (printf "backend.externalName.verifySecret muss im Namespace des Ingress (%s) liegen: ingress-nginx liest fremde Namespaces nur mit --allow-cross-namespace-resources" .Release.Namespace) }}
{{- end }}
{{- if and (or $e.caBundle $e.verifySecret) (not $e.proxySslLocationOnlyGesetzt) }}
{{- fail "backend.externalName.proxySslLocationOnlyGesetzt: erst bestätigen, dass die ConfigMap des Controllers proxy-ssl-location-only: \"true\" hat — sonst übernimmt ingress-nginx die Prüfung des Chat-Hosts für den ganzen Server-Block des Repository-Hosts (502 für alles, was dort HTTPS spricht). Prüfbefehl: docs/uebergabe-betrieb.md §16" }}
{{- end }}
{{- if not (or $e.caBundle $e.verifySecret $e.insecureSkipVerify) }}
{{- fail "backend.externalName: caBundle (PEM, z. B. ISRG Root X1/X2) oder verifySecret setzen — ohne proxy-ssl-secret prüft ingress-nginx das Zertifikat des Chat-Hosts nicht, und das Sitzungs-Cookie reiste ungeprüft. Nur bewusst: insecureSkipVerify=true" }}
{{- end }}
{{- end }}
{{- $verboten := list "rewrite-target" "use-regex" "affinity" "upstream-vhost" "snippet" "permanent-redirect" "temporal-redirect" "app-root" "ssl-passthrough" "auth-tls-" "server-alias" "ssl-ciphers" "ssl-prefer-server-ciphers" "mirror-" }}
{{- range $schluessel, $wert := .Values.annotations }}
{{- range $wort := $verboten }}
{{- if contains $wort $schluessel }}
{{- fail (printf "annotations: %s ist hier verboten (siehe templates/_helpers.tpl)" $schluessel) }}
{{- end }}
{{- end }}
{{- if and $extern (or (hasSuffix "/backend-protocol" $schluessel) (contains "/proxy-ssl-" $schluessel)) }}
{{- fail (printf "annotations: %s setzt das Chart bei backend.externalName selbst" $schluessel) }}
{{- end }}
{{- if and (not $extern) (contains "/proxy-ssl-" $schluessel) }}
{{- fail (printf "annotations: %s gehört nicht zu backend.service (HTTP auf 8100)" $schluessel) }}
{{- end }}
{{- if and (not $extern) (hasSuffix "/backend-protocol" $schluessel) (ne (upper (toString $wert)) "HTTP") }}
{{- fail (printf "annotations: %s bei backend.service nur HTTP (das Backend spricht HTTP auf 8100)" $schluessel) }}
{{- end }}
{{- end }}
{{- end -}}
