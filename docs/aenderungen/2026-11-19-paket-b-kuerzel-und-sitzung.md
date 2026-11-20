# Paket B: Anmelde-Kürzel und Sitzung auf Staging (2026-11-19)

Plan: `docs/plans/2026-11-19-dokument-entwurf-und-sitzung.md`, Paket B (B0–B3), Befund S3,
Entscheide E8 und E9. Dazu ein Nachtrag des Nutzers zu E8: auch „nicht angemeldet“ ist sichtbar,
und als **B4** der Name auch bei der Anmeldung von Hand und per Ticket (Abschnitt B4 unten).

## B0 — liefert `/auth/status` einen Anzeigenamen?

- **Ja, am MCP.** `src/auth/auth-status.ts:31` (Feld `displayName`) und `:69` (gesetzt, außer für das
  geteilte Dienstkonto), gebildet in `src/auth/identity.ts:90` aus Vor- und Nachname des Repositorys.
  Am Staging-MCP ohne Anmeldung gemessen: `GET /auth/status` → 200
  `{"mode":"anonymous","authenticated":false,"authority":"esguest","displayName":"ES Guest",…}`.
- **Das Widget fragt `/auth/status` nicht** (kein Treffer unter `frontend/projects/ui/src`) und
  kann es auch nicht: Der MCP schickt unter `/auth*` keinen CORS-Kopf (`src/http-app.ts:142-146`,
  `src/rest/auth-status.ts:23`; gemessen: Antwort ohne `Access-Control-Allow-Origin`). Gefragt wird
  vom Backend (`services/mcp/anmelde_endpunkte.py:52`), das den Namen verwirft
  (`services/mcp/anmeldung.py:238-242`, nur Kennung und Ablauf).
- Die Anmeldung von Hand (`session/sign-in-flow.ts`, OAuth) und das Ticket liefern keinen Namen.
- **Folge:** Einen Namen kennt nur der Weg über die Sitzung der Seite (`displayName` der
  Tauschstelle, `session/session-login.ts:248`). Von Hand und über das Ticket zeigt der Kreis das
  Personen-Symbol. Den Namen dort nachzureichen hieß, `services/mcp/**` zu ändern — nachgeholt in
  B4 (freigegeben vom Nutzer).

## B1 — das Kürzel in der Fußzeile (E8 + Nachtrag)

Ein Kreis (28 × 28 px) direkt links vom Anmelde-Knopf, nur eine Anzeige (`role="img"`, kein Knopf,
nicht fokussierbar), mit `aria-label` und `title`:

| Zustand | Inhalt | Beschriftung |
|---|---|---|
| angemeldet, Name bekannt | Initialen („Jan Schachtschabel“ → „JS“) | „Angemeldet als Jan Schachtschabel“ |
| angemeldet, ohne Namen | Personen-Symbol, getönt | „Angemeldet“ |
| nicht angemeldet | Umriss einer Person, ausgegraut, gestrichelter Rand (seit Review B) | „Nicht angemeldet“ |

- Nur, wenn die Anlage die Anmeldung anbietet (`authButton() !== 'hidden'`), nie in der Probe der
  Studio-Vorschau. Rahmenlos (`embed-mode="frameless"`) unverändert da.
- `session/initialen.ts` (neu, rein): erster Buchstabe des ersten und letzten Worts, groß, Umlaute,
  ein Wort → ein Buchstabe, leer → ''. Satzzeichen und Wörter ohne Buchstaben zählen nicht.
- Nach dem Abmelden bleibt kein Name stehen (`_angemeldetAls` wird beim Abmelden nicht geräumt;
  `kuerzel`/`kuerzelTitel` fragen deshalb zuerst den Zustand des Knopfs).
- Farben aus vorhandenen Token: angemeldet `secondary-container`/`on-secondary-container` (wie die
  Nutzer-Blase), dazu der Rand der Nachbarknöpfe — die Fläche liegt hell fast im Ton der Fußzeile
  (gemessen). Nicht angemeldet (seit Review B): ohne Füllung, `outline`, gestrichelter Rand,
  Umriss-Symbol `ICONS.person_outline`.
- Kontrast im Browser gemessen (Marke #1c4587): Initialen 10,0 : 1 hell, 10,3 : 1 dunkel (für
  #1f6feb gerechnet 6,3 / 7,8); ausgegrautes Symbol gegen die Fußzeile (seit Review B, E2E)
  3,6 : 1 hell, 5,1 : 1 dunkel.
- Personen-Symbol `ICONS.person`: auf dem Raster der Anmelde-Symbole von Hand gebaut (Kopf als Kreis,
  Schultern), kein abgetippter Material-Pfad.
- i18n de/en: `auth.signedInAs`, `auth.signedIn`, `auth.notSignedIn`.
- Umbruch der Fußzeile (WCAG 1.4.10): neue Klasse `chat-footer--anmeldung` (Kürzel da). Grenzen jetzt
  abgemeldet 356 px, angemeldet 400 px (vorher 364), mit Mikrofon je 44 px mehr (444 statt 408).
  Gemessen bei 320 px: keine waagerechte Rollleiste, Feld 250 px, Knöpfe in einer Zeile darunter.

## B2 — Chart `deploy/helm/boerdi-session-ingress` (E9)

- `Chart.yaml`, `values.yaml`, `values-staging.example.yaml`, `templates/_helpers.tpl`,
  `templates/ingress.yaml`, `templates/service-external.yaml`, `templates/NOTES.txt`.
- Ein Ingress am Repository-Host: Pfad `/edu-sharing/services/boerdi/auth/session`, `pathType:
  Exact`, kein rewrite, keine Affinität, Klasse aus `className`, TLS optional.
- Ziel A `backend.service` (Backend im Cluster, Port 8100) oder Ziel B `backend.externalName`
  (Compose-Rechner): ExternalName-Service, Annotationen `backend-protocol: HTTPS`,
  `proxy-ssl-server-name: on`, `proxy-ssl-name: <Chat-Host>`; der Host-Kopf des Repositorys bleibt.
  Seit Review B: Prüfung Pflicht (`caBundle` oder `verifySecret`), Port 8443 — siehe unten.
- Renderprüfung (`boerdi_session.pruefen`) bricht ab bei: fehlendem Host, Host mit Schema/Pfad,
  Pfad nicht unter `/edu-sharing/`, nicht auf `/auth/session` endend, anders als der Pfad des
  Backends; zwei oder keinem Ziel; ExternalName mit Schema/Pfad; Annotation mit `rewrite-target`,
  `use-regex` oder `affinity` (seit Review B mehr, siehe unten).
- `NOTES.txt` nennt `MCP_SESSION_URL` (und bei Ziel B `SESSION_HOST`, `TRAEFIK_TRUSTED_IPS`, eine
  Warnung bei `insecureSkipVerify`) und einen `curl`-Prüfpunkt mit der Bedeutung jeder Antwort.

## B3 — Compose, Variablen, Doku (E9)

- `deploy/compose.session.yml` (neu, Zusatzdatei): Router `boerdi-sitzung` =
  `Host(${SESSION_HOST}) && Path(<Tauschpfad>)`, seit Review B am eigenen Eingang `sitzung`
  (:8443, hier veröffentlicht), `tls=true` **ohne** certresolver
  (Let's Encrypt könnte für den fremden Host nicht ausstellen und versuchte es immer wieder),
  Service `boerdi`. `SESSION_HOST` ist Pflicht, sobald die Datei eingebunden ist.
- `deploy/compose.prod.yml`: Traefik-Eingang `sitzung` (`:8443`) mit
  `forwardedHeaders.trustedIPs=${TRAEFIK_TRUSTED_IPS:-127.0.0.1/32}` — seit Review B NUR dort;
  `websecure` glaubt wieder niemandem. Vorgabe = niemand. Grund: Über den Ingress des Clusters
  kämen alle Tausche von dessen Adresse; Traefik überschreibt `X-Forwarded-For`, und die Grenze je
  Adresse (10 je Minute) gälte für alle Personen zusammen.
- `deploy/.env.example`: `SESSION_HOST` (optional, leer) und `TRAEFIK_TRUSTED_IPS`.
- Doku: `deploy/README.md` (Abschnitt `MCP_SESSION_URL`, Punkt 1), `docs/uebergabe-betrieb.md` §11
  und neu **§16 „Sitzungsübernahme auf Staging einrichten“** (MCP, Ingress, Chat-Rechner, Adressen
  nachtragen, Prüfen), `docs/edu-sharing-einbindung.md` §3a, `deploy/helm/values.example.yaml`
  (Verweis aufs Chart).

## B4 — der Name auch von Hand und per Ticket (Nachtrag)

- **Weg:** `services/mcp/anmeldung._aus_stand` übernimmt bei einer bestätigten Person (`mode: user`,
  `authenticated: true`) `displayName` gesäubert in den `Befund` (`anzeigename`; Steuer- und
  Formatzeichen raus, Leerraum einfach, höchstens 120 Zeichen). `bestaetige_anmeldung` legt ihn in
  den Zugstand (`auth.merke_anzeigename`, gilt nicht nach einer Abweisung: `zug_anzeigename`).
  `api/chat._anmeldestand` setzt das neue Antwortfeld **`auth_display_name`** neben
  `auth_expires_at` — für `/api/chat` und den Strom gleich. Beim geteilten Dienstkonto gibt es
  keinen Namen (der MCP setzt ihn dort nicht, und es ist keine bestätigte Person).
- **Datenschutz:** `_anmeldestand` läuft nach `run_turn`, also nachdem der Zug gespeichert ist
  (`graph/nodes/persist` → `save_message` mit Text, Karten, Debug). Der Name steht deshalb nicht in
  der Datenbank, nicht im Verlauf (`GET /api/sessions/{id}/messages`), nicht in Debug/Spur, nicht
  im Log und nicht beim Modell. Im Prozessspeicher steht er im Befund-Speicher je Fingerabdruck,
  höchstens so lange wie die Bestätigung (5 min bzw. Gnadenfrist). Die Gastseite bekommt ihn nicht
  (die Host-Ereignisse nehmen einzelne Felder, nie die ganze Antwort).
- **Widget:** `_nameAusDemZug` (nur Arbeitsspeicher) übernimmt `auth_display_name`, wenn ein Block
  da ist, der Zug mit genau diesem Block hinausging (`letzterZugBlock`) und die Sitzung der Seite
  keinen Namen gesetzt hat; nur Text, höchstens 120 Zeichen. Ein Zug ohne Namen lässt ihn stehen
  (etwa wenn der Server gerade nicht prüfen kann). Geräumt bei Abmelden, Abweisung, Wache und jedem
  neuen Block. Kürzel und Knopf („Abmelden — angemeldet als …“) nutzen denselben Namen.
- **Vertrag:** `docs/api/openapi-v1.json` und `openapi-public.json` neu erzeugt
  (`scripts/export_openapi.py`). Der Abgleich enthält außer `auth_display_name` das Feld
  `feste_argumente` aus Paket A (anderer Agent, lag schon im Code).

## Abweichungen vom Plan

1. **Nachtrag des Nutzers:** Zustand „nicht angemeldet“ (ausgegrauter Kreis, `auth.notSignedIn`) —
   im Plan stand „nur sichtbar, wenn angemeldet“. Gewählt: nur ausgegraut, ohne Schrägstrich (das
   übliche Zeichen eines leeren Profils).
2. **Name bei der Anmeldung von Hand:** zuerst nicht umgesetzt (gesperrter Bereich), dann als B4
   nachgeholt — ohne Namen (bis zum ersten Zug, oder wenn der MCP keinen nennt) bleibt das Symbol.
3. **Renderprüfung strenger als im Plan:** zusätzlich muss der Pfad genau der des Backends sein
   (ohne rewrite nimmt `api/sitzung.py` keinen anderen an — sonst stilles 404).
4. **Der Eingang `sitzung` steht in `compose.prod.yml`, veröffentlicht wird er in der
   Zusatzdatei:** Compose ersetzt `command` beim Zusammenführen ganz; die Zusatzdatei hätte die
   ganze Befehlszeile von Traefik doppeln müssen. Ohne die Zusatzdatei ist der Eingang nicht
   erreichbar und hat keinen Router.
5. **`helm` war lokal doch vorhanden** (WinGet). Neben den Textprüfungen rendern zwei Tests echt
   (`helm template`, übersprungen ohne `helm`): Staging-Werte und sechs Abbruchfälle.
6. **E2E angepasst:** `e2e/auth-button.spec.ts` (bei 320 px bricht die Zeile jetzt auch abgemeldet
   um), `e2e/meine-vorgaenge.spec.ts` (Grenzen 400/444 px, Knopfzeile über die Mitte verglichen —
   der Kreis ist kleiner als die Knöpfe).

## Tests

- Widget: `session/initialen.spec.ts` (neu, 5), `shell/chat-shell-kuerzel.spec.ts` (neu, 10: „JS“
  aus der Sitzung, Symbol ohne Namen, ausgegraut ohne Anmeldung, nach dem Abmelden kein Name,
  fehlt ohne Anmelde-Angebot und in der Probe, direkt links vom Knopf auch rahmenlos, englisch,
  Klasse für den Umbruch). Projekt `ui`: 123 Dateien, 1537 Tests grün.
- E2E (gebautes Widget): `auth-button`, `meine-vorgaenge`, `embed` grün (28).
- Backend: `test_helm_values.py` (+9), `test_deploy_compose.py` (+2, Wächter liest auch
  `compose.session.yml`), `test_env_beispiel.py` (`_NUR_COMPOSE` + 2).
- B4 Backend: `test_anmeldung_anzeigename.py` (neu, 20: Säubern, nur Person, Speicher, neuer Zug,
  Abweisung, Antwortfeld, kein Log, nur vier Module fassen den Namen an),
  `test_anmeldung_anzeigename_ende.py` (neu, Postgres, 4: echter Zug Muster/Agent/Strom — der
  Name steht genau einmal in der Antwort, in keiner Tabelle, nicht im Verlauf, nicht im Log, nicht
  in den Aufrufen von Modell und Klassifikator; ohne Block kein Name). Gegenprobe: eine
  absichtliche Logzeile mit dem Namen macht den Test rot. `test_schemas.py` (Feldliste).
- B4 Widget: `chat-shell-kuerzel.spec.ts` +7 (Name aus dem Zug → „JS“ und Knopf, bleibt bei Zug
  ohne Namen, nicht ohne bzw. mit anderem Block, nur Text/120 Zeichen, Sitzung geht vor, nach
  Abmelden und neuem Block weg, nach Abweisung weg). Projekt `ui`: 1544 Tests grün.

## Offen

- Der Name erscheint bei der Anmeldung von Hand und per Ticket erst mit der Antwort auf den ersten
  Zug danach; vorher das Personen-Symbol.
- Abnahme auf Staging (Plan §5, S3) macht der Betrieb: Chart einspielen, `.env` am Chat-Rechner,
  `TRAEFIK_TRUSTED_IPS` nach dem ersten Tausch (`docs/uebergabe-betrieb.md` §16).

## Deploy

- Keine Migration. Neue Compose-Variablen `SESSION_HOST` (nur mit `compose.session.yml`) und
  `TRAEFIK_TRUSTED_IPS` (optional). Image neu bauen (Widget), danach Hard-Reload im Browser.

## Review behoben (19.11.)

Unabhängiges Review von Paket B: 1 MAJOR, 4 MINOR, 4 NIT — alle behoben. Je Befund der Test
zuerst, rot gesehen.

1. **MAJOR — Ziel B ohne Zertifikatsprüfung.** ingress-nginx wertet `proxy-ssl-name`,
   `-server-name` und `-verify` nur mit `proxy-ssl-secret` aus; ohne gingen weder SNI noch Prüfung
   hinaus. Jetzt Pflicht: `backend.externalName.caBundle` (PEM; das Chart legt daraus das Secret
   `<name>-ca` im Namespace des Releases an, `templates/secret-ca.yaml`) **oder** `verifySecret`
   (nur aus dem eigenen Namespace — fremde liest ingress-nginx nur mit
   `--allow-cross-namespace-resources`), nicht beides; `caBundle` muss PEM sein. Ohne beides
   bricht das Rendern ab, außer `insecureSkipVerify: true` (dann nur `backend-protocol`, Warnung in
   NOTES). Mit Prüfung: `proxy-ssl-secret`, `-verify on`, `-verify-depth 3` (auch über die
   Kreuzsignatur von ISRG Root X2), `-name`, `-server-name on`. Staging-Werte: `caBundle` per
   `--set-file` aus ISRG Root X1 + X2. Tests: `test_helm_values.py` — Rendern mit CA (Secret,
   Annotationen, Port), ohne Prüfung → Abbruch, `insecureSkipVerify`, `verifySecret` eigener und
   fremder Namespace, kein PEM, beides.
2. **MINOR — Vertrauen in `X-Forwarded-For` am ganzen `websecure`.** Eigener Traefik-Eingang
   `sitzung` (:8443, in `compose.prod.yml` angelegt, nur mit `compose.session.yml` veröffentlicht),
   `trustedIPs` nur dort; der Router `boerdi-sitzung` hängt daran, das Chart zielt auf Port 8443.
   §16 nennt die Voraussetzung am Cluster-Ingress (`X-Forwarded-For` = `$remote_addr`,
   `compute-full-forwarded-for` aus) und den Fall Load-Balancer ohne PROXY-Protokoll. Tests:
   `test_deploy_compose.py` (Eingang, Vertrauen nur dort, Port nur mit der Zusatzdatei, Router am
   Eingang). `docker compose config` mit beiden Dateien: Ports 80/443/8443, Router am Eingang.
3. **MINOR — Sperrliste zu kurz.** Dazu `upstream-vhost`, `*snippet*`, `permanent-`/
   `temporal-redirect`, `app-root`, `ssl-passthrough`; bei Ziel B auch die Schlüssel, die das Chart
   setzt (`backend-protocol`, `proxy-ssl-*`). Je ein Abbruchfall im helm-Test.
4. **MINOR — abgemeldet kaum von „angemeldet ohne Namen“ zu unterscheiden.** Andere Form: Umriss
   der Person (`ICONS.person_outline`, von Hand auf dem Raster, `evenodd`), gestrichelter Rand,
   Ton `--mat-sys-outline`. Gemessen (E2E `auth-button.spec.ts`, neu): Rand `dashed`, Symbol gegen
   die Fußzeile 3,6 : 1 hell, 5,1 : 1 dunkel. Spec: abgemeldet und angemeldet ohne Namen tragen
   verschiedene Pfade. Im Browser angesehen.
5. **MINOR — einzelnes Surrogat im Namen → 500.** `_anzeigename` wirft jetzt alle Zeichen der
   Klasse „C“ heraus (`Cc`, `Cf`, `Cs`, `Co`, `Cn`). Testfälle `'Jan \ud800'`, privat, nicht
   vergeben.
6. **NIT** — `annotations:` nur mit Inhalt (Ziel A rendert ohne; helm-Test).
7. **NIT** — Staging-Werte: ohne eigenes `tls` gilt das Zertifikat aus dem Ingress des Repositorys
   (ingress-nginx legt Ingresse desselben Hosts zusammen).
8. **NIT** — Kommentar in `_chat-footer.scss`: „ohne Anmelde-Angebot (`hidden`)“.
9. **NIT** — Name aus dem Zug nach Zeichen gekürzt (`Array.from`), kein halbes Surrogatpaar;
   Spec mit `\u{1D49C}` × 130.

Dazu berichtigt: `docs/edu-sharing-einbindung.md` (Einleitung, §3a, §10) und der Docstring von
`api/sitzung.py` nannten noch „Chart des Chatbots, `sessionIngress`“; `deploy/README.md`,
`deploy/.env.example` und `docs/uebergabe-betrieb.md` §16 auf CA-Pflicht und Eingang `sitzung`.
Deploy zusätzlich: Port 8443 am Chat-Rechner (veröffentlicht nur mit `compose.session.yml`).

## Zweites Review behoben (19.11.)

Zweites unabhängiges Review: 1 MAJOR, 2 MINOR, 3 NIT — alle behoben, Test zuerst wo testbar.

1. **MAJOR — Prüfwerte gelten für den ganzen Server-Block.** ingress-nginx übernimmt die
   `proxy-ssl-*`-Werte des ersten Ingress eines Hosts für den ganzen Server-Block, solange die
   Controller-ConfigMap `proxy-ssl-location-only` nicht `"true"` hat; andere HTTPS-/GRPCS-Ziele am
   Repository-Host prüften dann gegen den Chat-Host (502). Per Chart nicht abschaltbar.
   **Entscheid:** neuer Wert `backend.externalName.locationOnlyBestaetigt` (Vorgabe `false`); mit
   Prüf-Secret bricht das Rendern ohne ihn ab und nennt die Bedingung. Grund: Der Schaden träfe
   edu-sharing-fremde Ziele am Repository-Host und wäre am Chart nicht zu sehen — eine Zeile `true`
   nach einer dokumentierten Prüfung ist keine Schikane, ein übersehener Hinweis in NOTES wäre zu
   leise. Ohne Prüf-Secret (`insecureSkipVerify`) setzt das Chart keine `proxy-ssl-*`-Werte und
   verlangt die Bestätigung nicht. Doku: §16 neuer Schritt 2 „Vorbedingungen“ mit
   `kubectl get configmap … proxy-ssl-location-only` bzw. `kubectl get ingress -A -o json | jq …`
   (Host + `backend-protocol` HTTPS/GRPCS), `deploy/README.md`, `docs/edu-sharing-einbindung.md`
   §3a, NOTES, Kommentar in `templates/ingress.yaml` eingeschränkt. Test:
   `test_helm_mit_pruefung_nur_nach_bestaetigung_des_server_blocks` (rot: rendern lief durch).
2. **MINOR — Sperrliste Server-Ebene.** Dazu `auth-tls-*`, `server-alias`, `ssl-ciphers`,
   `ssl-prefer-server-ciphers`; je ein Abbruchfall (rot: `auth-tls-verify-client` lief durch).
3. **MINOR — Deutung 502/504 und Vorbedingungen.** NOTES und §16 Schritt 6: 502 = Prüfung
   scheitert (Controller-Log `upstream SSL certificate verify error`), 504 = nicht erreichbar;
   Gegenprobe `openssl s_client -connect <Chat-Host>:8443 -servername <Chat-Host> -CAfile
   le-wurzeln.pem` → `Verify return code: 0`. §16 Schritt 2: `annotations-risk-level` mindestens
   `High`, Port 8443 in der Firewall des Anbieters, die Annahme „Traefik liefert am Eingang
   `sitzung` per SNI das ACME-Zertifikat des Routers `boerdi`“ als zu prüfender Punkt. Test:
   `test_notes_deuten_502_und_nennen_die_pruefbefehle` (rot: „502“ fehlte).
4. **NIT** — `values.yaml` verweist für die Sperrliste auf `_helpers.tpl`; Kommentar im
   Widget-HTML: „Umriss einer Person in einem gestrichelten Kreis“.
5. **NIT** — `verifySecret` mit mehr als einem `/` bricht ab (Test, rot: lief durch).
6. **NIT** — `initialen`: nach dem Großschreiben nur das erste Zeichen („ß“ → „S“, nicht „SS“).
   Spec, rot: `expected 'SS' to be 'S'`.

Dabei: `values-staging.example.yaml` und §16 Schritt 3 zeigen den Befehl mit
`--set backend.externalName.locationOnlyBestaetigt=true` und dem Hinweis, das erst nach Schritt 2
zu setzen. Die Schritte von §16 sind dadurch um eins verschoben (jetzt 1–6).

## Drittes Review behoben (19.11.)

Drittes Review: 0 CRITICAL, 1 MAJOR, 3 MINOR, 5 NIT — alle behoben (die Fixes der Runden 1 und 2
bestätigte der Reviewer gegen die Quellen von ingress-nginx).

1. **MAJOR — Ersatzprüfung unvollständig.** Die Server-weite Vererbung der Prüfwerte trifft nicht
   nur Ingresse mit `backend-protocol: HTTPS`, sondern auch `AUTO_HTTP`, `auth-url`/`global-auth-url`
   mit https und `mirror-target`. **Entscheid (Koordinator):** Die Ersatzprüfung per `jq` entfällt;
   einziger Weg ist `proxy-ssl-location-only: "true"` in der ConfigMap des Controllers. Der Wert
   heißt jetzt `backend.externalName.proxySslLocationOnlyGesetzt`, die Abbruchmeldung nennt nur
   diese Bedingung. Die Einstellung gilt für alle Ingresse des Controllers (Prüfwerte nur noch je
   Location; Ingresse mit eigenen `proxy-ssl-*` bleiben korrekt) — mit dem Betrieb des Clusters
   abstimmen. Angepasst: `_helpers.tpl`, `values.yaml`, `values-staging.example.yaml`,
   `NOTES.txt`, `ingress.yaml` (Kommentar), §16 Schritt 2, `deploy/README.md`,
   `docs/edu-sharing-einbindung.md` §3a. Test: Abbruch ohne Bestätigung nennt
   `proxy-ssl-location-only` und nichts mehr von anderen Ingressen; alter Wert nicht mehr in
   `values.yaml` (rot: alte Meldung, `locationOnlyBestaetigt`).
2. **MINOR — Reihenfolge in §16.** Der Download der Wurzeln (`curl -fsSLO …` beider PEM,
   zusammenlegen) steht am Anfang von Schritt 3, dazu `meine-werte.yaml` als Kopie der
   Beispielwerte mit eingetragenem Chat-Host; die `openssl s_client`-Gegenprobe steht jetzt am
   Anfang von Schritt 6 (Port 8443 ist erst nach Schritt 4 offen).
3. **MINOR — ConfigMap finden, Risikostufe prüfen.** §16 Schritt 2: `kubectl get deploy -A -l
   app.kubernetes.io/name=ingress-nginx …` (Startargument `--configmap=`), Prüfbefehle für
   `proxy-ssl-location-only` und `annotations-risk-level` (leer = High).
4. **MINOR — Sperren unabhängig vom Ziel.** `mirror-*` ist immer gesperrt (schickte das
   Sitzungs-Cookie an ein zweites Ziel); `proxy-ssl-*` bei Ziel A gesperrt; `backend-protocol` bei
   Ziel A nur `HTTP`. Test `test_helm_sperrt_mirror_und_proxy_ssl_auch_im_cluster` (rot:
   `mirror-target` renderte durch).
5. **NIT** — §16 Schritt 3 verweist für die Sperrliste auf `_helpers.tpl` (auch die Meldung).
6. **NIT** — Ein Satz zu `use-regex` am Host (md-editor): unser Exact wird zu `~* "^…"` — harmlos,
   längere Pfade gehen vor, das Backend prüft exakt (`values.yaml`, `ingress.yaml`, README, §3a,
   §16).
7. **NIT** — `values-staging.example.yaml`: `-f deploy/helm/boerdi-session-ingress/…`.
8. **NIT** — `NOTES.txt`: der 502-/openssl-Block nur mit Prüf-Secret (Test auf die Bedingung).
9. **NIT** — `deploy/README.md` verweist nur noch auf das Chart, nicht auf `sessionIngress`.


## Viertes Review behoben (19.11.)

Viertes Review (Ingress-Teil): 0 CRITICAL, 0 MAJOR, 6 MINOR, 6 NIT — alle behoben.

1. §16 Schritt 2: `proxy-ssl-location-only` dauerhaft setzen — bei Helm-verwaltetem Controller
   `controller.config.proxy-ssl-location-only: "true"` (ein `kubectl patch` verschwände beim nächsten
   `helm upgrade`), sonst `kubectl patch configmap … --type merge`; wirkt ohne Neustart; nach jedem
   Controller-Upgrade erneut prüfen.
2. §16 Schritt 2: ConfigMap über `kubectl get deploy,ds -A -l app.kubernetes.io/name=ingress-nginx`
   finden (`$(POD_NAMESPACE)` = erste Spalte); ohne `--configmap` gilt false → ConfigMap anlegen;
   kein `--disable-svc-external-name`, `--watch-namespace` muss den Namespace einschließen.
3. §16: Folgen eingeschränkt („außer bei Unteranfragen wie `auth-url` …“) und Liste der
   betroffenen Ingresse (`jq` auf `proxy-ssl-secret`).
4. §11 auf das Chart umgestellt; `sessionIngress` nur für ein Gesamt-Chart ohne dieses Chart, nie
   beides zugleich — derselbe Hinweis am `sessionIngress`-Block in `deploy/helm/values.example.yaml`.
5. §16 Schritt 3: Schreibrecht für Ingress, Service und Secret; der Namespace muss vom Controller
   beobachtet werden.
6. `docs/offene-befunde-und-todo.md`, nur Abschnitt SA-16: Chart, `compose.session.yml`, Vorbedingung
   `proxy-ssl-location-only`, Verweis auf §16.
7. NOTES: die Traefik-404-Zeile nur bei Ziel B (Test).
8. NOTES: `-CAfile <CA-Datei>` mit Erklärung (bei `verifySecret` dessen `ca.crt`); die
   insecure-Warnung nennt auch `proxySslLocationOnlyGesetzt` nach §16 Schritt 2 (Test).
9. §16 und `values-staging.example.yaml`: `-n <namespace>` auch bei `helm template`, derselbe
   Release-Name `boerdi-sitzung`.
10. `_helpers.tpl`: `host` mit Port und `verifySecret` mit `/` am Anfang oder Ende brechen ab (Test,
    rot: renderte durch).
11. Kommentar in `test_helm_values.py`: zweistufig (Text überall, echtes Rendern wo `helm` da ist).
12. `deploy/README.md`: `.env`-Zeilen und Befehl getrennt; Verweis „`docs/uebergabe-betrieb.md` §16“.
