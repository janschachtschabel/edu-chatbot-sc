# Zweite Antwort an den MCP-Entwickler: Anmeldung aus der WLO-Sitzung (2026-11-15)

Zu deiner Antwort „Antwort an das Chatbot-Team: Anmeldung aus der WLO-Sitzung“
(`docs/plans/2026-11-15-antwort-chatbot-sitzung.md`). Danke für 1b und 1c.

**Kurz: Weg B braucht den MCP nicht im Cluster. Von dir brauchen wir nur Abschnitt 1.**

> **Stand:** Beantwortet am selben Tag. Der MCP-Entwickler hat 1a.2 (Budget) und 1b
> (Ticket-Bindung) in Version 1.3.0 gebaut und spielt sie mit `WLO_SESSION_EXCHANGE=1` auf
> Staging ein. Unsere Grenzen sind darauf angepasst (Plan SA-17).

## 1. Was wir von dir brauchen

### 1a. Weg B geht ohne den MCP im Cluster

Du schreibst, Weg B gehe nur, wenn der MCP im Cluster des Repositorys läuft. Das gilt, wenn der
Browser deinen Server direkt ruft. Wir haben es anders gelöst, darum ist es keine Voraussetzung
mehr:

- **Unser** Chart legt den Pfad am Repository-Host an (`sessionIngress`, eigenes Ingress-Objekt,
  `/edu-sharing/services/boerdi/auth/session`, `pathType: Exact`, unverändert, ohne
  `rewrite-target`, wie bei dir und beim md-editor).
- Der Pfad führt zu **unserem** Backend. Das prüft die Anfrage und reicht den Tausch
  server-zu-server an dein `POST /auth/session` weiter, also an deinen Server auf
  `wlo-mcp.87.106.195.152.nip.io`, so wie er heute läuft.

Bei dir kommt an:

- `Cookie`: genau eine `JSESSIONID`, höchstens ein `INGRESSCOOKIE`;
- `Origin`: die Herkunft der Repository-Seite (nur, wenn der Browser genau sie geschickt hat);
- `Content-Type: application/json`, Rumpf `{}`, kein `Authorization`;
- `X-WLO-Client-Key` (unser Schlüssel) und `X-Forwarded-For` mit der Adresse der Person.

Bitte:

1. **`WLO_SESSION_EXCHANGE=1` an deinem Staging-Server**, nur die Variable: ohne Chart, ohne
   `WLO_SESSION_MOUNT_PATH`. Wir rufen `/auth/session` an der Wurzel. Deine Herkunftsprüfung
   lässt ohne `WLO_SESSION_ALLOWED_ORIGINS` die Herkunft aus `WLO_REPOSITORY_URL` zu. Das genügt,
   wenn sie dieselbe ist wie die Adresse im Browser (Staging: der Host des Repositorys).
2. **Budget, die Bedingung für den Betrieb mit vielen Personen. Diese Frage hast du noch nicht
   beantwortet.** Alle Tausche kommen von der Adresse unseres Backends. An `/auth/session` und
   `/auth/revoke` teilen sie sich bei dir je Adresse einen Topf (`API_RATE_LIMIT_RPM`, Vorgabe 30
   je Minute). Dazu kommen 200 verschiedene Sitzungen in 10 Minuten (`TICKET_CREDENTIAL_LIMIT`).
   Wir begrenzen deshalb auf 20 Tausche je Minute für die ganze Anlage, damit 10 für das
   Abmelden bleiben. Für eine Redaktion reicht das. Für eine Schulklasse, die gleichzeitig lädt,
   reicht es nicht.
   `TRUST_PROXY` hochzusetzen löst das nicht: Dann zählte dein Server das `X-Forwarded-For`
   jeder Anfrage, und jeder könnte sich eine Adresse ausdenken.
   Bitte: Für einen vertrauten Client-Schlüssel an `/auth/session` die Grenzen je
   weitergereichter Adresse zählen (unser `X-Forwarded-For`, nur bei gültigem Schlüssel), oder
   ihm einen eigenen, größeren Topf geben.
3. **Optional, für deine Doku:** Deine Startmeldung und die Chart-README nennen als Weg nur „auf
   dem Repository-Host eingehängt“. Ein Weiterreicher wie unserer ist eine zweite Form. Für ihn
   gilt: Das Budget hängt an der Adresse des Weiterreichers, nicht an `TRUST_PROXY` (siehe 2).

Dein `sessionIngress` bleibt nützlich. Läuft der MCP eines Tages im Cluster, zeigt unsere
Adresse (`MCP_SESSION_URL`) direkt auf deinen Pfad (`/edu-sharing/services/wlo-mcp/auth/session`),
und unser eigener Pfad bleibt aus. Das Widget merkt keinen Unterschied.

### 1b. Bindung auch für Ticket-Blöcke: ja, bitte

Gleiche Regel für beide Arten ist einfacher zu erklären, und ein abgegriffener Ticket-Block
bleibt dann nach dem Abmelden ebenso wertlos. Es eilt nicht. Die einmalige 401 beim Einspielen
nehmen wir hin: Wer betroffen ist, meldet sich einmal neu an.

## 2. Zur Information: nachgelesen an deinem Stand

- **1b:** Der Block trägt den Zeitpunkt seiner Eintragung, die Prüfung vergleicht ihn
  (`credential.ts`, `payload.iat` gegen `listedAt`). Die Eintragung geschieht in einem
  geordneten Schreibvorgang (`listUnlessListed`). Damit sind beide Fälle aus unserer ersten
  Antwort geschlossen. An unserem Widget ändert sich nichts.
- **1c:** Unser Backend liest eine 401 an `/auth/status` schon heute als „Block gilt nicht mehr“.
  Es liest `authenticated: false` mit `upstream: "ok"` als Abmeldung und nimmt `expiresAt` für
  das stille Erneuern nach 12 Stunden. Auch hier ist nichts zu ändern.
- **Bindung an den Client-Schlüssel:** Dass du sie notiert hast, genügt uns. Kein Muss für den
  Start.

## 3. Was danach kommt

Sobald `WLO_SESSION_EXCHANGE=1` gesetzt ist und unser Pfad auf Staging steht, prüfen wir den
Tausch einer angemeldeten Sitzung im Browser und melden das Ergebnis.
