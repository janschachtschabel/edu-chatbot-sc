# Dritte Antwort an den MCP-Entwickler: Anmeldung aus der WLO-Sitzung (2026-11-15)

Zu deiner zweiten Antwort (Version 1.3.0). Danke, beides passt zu unserem Weiterreicher. Zwei
Fragen, bevor wir die Grenze bei uns anheben. Bis dahin bleibt sie bei 20 Tauschen je Minute.

## 1. Kommt unser `X-Forwarded-For` durch dein Traefik?

Du liest mit `TRUST_PROXY=1` den Eintrag vor dem deines Proxys (`forwardedClientKey`:
`hops.pop()`, dann der letzte). Das klappt nur, wenn Traefik unseren Eintrag stehen lässt.
Traefik wirft `X-Forwarded-*` von Quellen weg, die nicht in `forwardedHeaders.trustedIPs`
stehen, und schreibt nur die Adresse der Verbindung. Dann bleibt nach dem `pop()` nichts
übrig, und unser ganzer Client zählt als eine Adresse: 200 verschiedene Sitzungen in 10 Minuten
für alle Personen zusammen.

Bitte:

- Sag uns, ob dein Traefik auf Staging die Ausgangsadresse unseres Backends in `trustedIPs`
  führt (oder wie er sonst eingestellt ist). Die Adresse nennt dir unser Betrieb.
- Nach unserem ersten Test im Browser: Schau, ob dein Log für Tausche von verschiedenen
  Anschlüssen verschiedene Adressen nennt.

Wir schicken die Adresse als einzigen Eintrag (eine gültige IP, ohne Port). Was der Browser
selbst behauptet hat, reichen wir nicht weiter.

## 2. Ein Werkzeugaufruf kostet uns drei POSTs

Deine Rechnung geht von bis zu 300 POSTs an `/mcp` je Minute aus; dann blieben rund 780 für
Tausch, Abmelden und Status. Unser Transport öffnet aber je Werkzeugaufruf eine eigene Sitzung:
`initialize`, `notifications/initialized`, `tools/call`. Das sind drei POSTs. Bei 300
Werkzeugaufrufen je Minute wären es also rund 900 von 1080, und für den Rest blieben rund 180.

Wir setzen die Grenze deshalb auf 100 Tausche je Minute, nicht auf 200. Das reicht uns für den
Anfang. Falls du lieber mehr Luft gibst, sind beide Wege für uns gleich gut: rpm für unseren
Schlüssel höher, oder die beiden Benachrichtigungen nicht ins Protokoll-Budget zählen.

## 3. Zur Information: was bei uns gilt

- Neue Einstellung `MCP_SESSION_EXCHANGE_RPM`, Vorgabe 20. Der Betrieb setzt sie auf 100,
  sobald 1.3.0 mit unserem Schlüssel auf Staging läuft und Punkt 1 geklärt ist. Ohne
  Client-Schlüssel gilt bei uns höchstens 20.
- Je Adresse lassen wir 10 Tausche je Minute zu, bei einer Gesamtgrenze über 20 dann 60.
- Der Schlüssel liegt nur im Backend, nie im Widget.
- Widerrufen wird nur, wenn die Person sich abmeldet. Dazu kommt ein Block, der danach noch aus
  einem laufenden Tausch zurückkommt. Einen veralteten Block widerruft das Backend nicht von
  selbst.
