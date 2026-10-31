# Cluster-Checkliste (Spec §8) — Abnahme-Protokoll

Spec §8 gibt fünf Zusagen für den N-Replika-Betrieb. Dieses Dokument sagt zu
jeder, **womit sie belegt ist** — und wo der Beleg ein Mensch mit einem echten
Cluster sein muss, steht das als solches da statt als Häkchen.

Stand 2026-07-27 (P10-3, Speicher-Tausch P10-6). **Drei der fünf Punkte sind
automatisiert** (1–3), zwei brauchen den laufenden Stack — bei Punkt 5 ist die
eine Hälfte gemessen. Der Grund steht in jeder Zeile; „lässt sich nicht testen"
gilt hier nicht als Begründung, „braucht zwei echte Prozesse hinter einem echten
Load-Balancer" schon.

| # | §8-Zusage | Beleg | Automatisiert |
|---|---|---|---|
| 1 | Session-Turns serialisiert | Seit Paket 7 (P1): Sperr-Eintrag je Sitzung in `session_locks` (Migration 0008), genommen von beiden Chat-Endpunkten (`api/session_locks.sitzung_sperren`); `test_sitzungssperre.py` (zweite Sperre beschäftigt, Warten, Verfall, Verlängerung). Zwei echte Repliken: Live-Protokoll offen | ✅ (pg) |
| 2 | Config-Änderung propagiert < 2 s | `test_cluster_checklist.py::test_config_change_propagates_within_the_two_second_bound` | ✅ (pg) |
| 3 | Rate-Limit konsistent über den geteilten Zähler | `test_cluster_checklist.py::test_two_replicas_share_one_budget_over_a_shared_store` + `::test_a_replica_started_later_inherits_the_running_count` | ✅ (valkey) |
| 4 | SSE über den Load-Balancer stabil | Live-Protokoll unten | ❌ |
| 5 | Graceful Shutdown verliert keinen Turn | Live-Protokoll unten (Hälfte gemessen, s. u.) | ➗ |

Seit Paket 17 (2026-10-20) kommen drei Zusagen dazu, die §8 nicht nannte, die bei N Repliken
aber genauso brechen:

| # | Zusage | Beleg | Automatisiert |
|---|---|---|---|
| 6 | Ein neuer Pod bricht keinen laufenden Lasttest einer anderen Replik ab; höchstens ein Lasttest läuft | Herzschlag `heartbeat_at` alle 15 s (`obs/herzschlag`), verwaist erst nach 90 s ohne Herzschlag; Unique-Teilindex (Migration 0014); `test_cluster_laeufe_pg.py` | ✅ (pg) |
| 7 | Ein beendeter Pod blockiert neue Eval-Läufe nicht | Herzschlag wie 6, verwaist nach 3 min (vorher 2 h nach dem Start); `test_cluster_laeufe_pg.py` | ✅ (pg) |
| 8 | Master-Skill: eine Abfrage je Takt im Cluster, „Neu laden“ wirkt überall, alle Repliken legen dieselbe Fassung in den Prompt | Stand in `master_skill_stand` (Migration 0015), Abfrage nur unter der Sperre `__lauf:master-skill`, Signal über `config_changed`; `test_master_skill_cluster.py` | ✅ (pg) |

```powershell
cd backend
docker compose -f ../deploy/compose.dev.yml up -d postgres valkey
uv run pytest tests/test_cluster_checklist.py tests/test_pg_locks_notify.py tests/test_cluster_laeufe_pg.py tests/test_master_skill_cluster.py -v
```

**Ohne Besitzer-Spalte.** Eine Zeile merkt sich nicht, welcher Pod den Lauf trägt. Geht ein
Pod geordnet, schließt er zu Beginn des Herunterfahrens selbst ab, was in seiner Lauf-Registry
steht (`services/laeufe_beenden`: Zeile auf `failed` „abgebrochen: Pod beendet“, dann den Task
abbrechen) — sonst sammelte ein Eval-Lauf bis zum Ende der Gnadenfrist nur Verbindungsfehler
über die geschlossene Loopback-Adresse. Stürzt er ab oder verliert das Netz, gibt der
ausbleibende Herzschlag den Weg frei.

**Grenze von Zusage 6/7.** Verliert ein lebender Läufer nur den Herzschlag (etwa weil der Pool
seines Pods unter der Last des eigenen Lasttests leerläuft) und wird abgeräumt, schreibt er
danach nichts mehr — weder Zwischen- noch Endstand — und hält am nächsten Prüfpunkt an (beim
Lasttest nach der laufenden Stufe). Bis dahin können sich zwei Läufe überlappen.

**Umstieg auf Migration 0014:** währenddessen keinen Lasttest und keinen Eval-Lauf starten. Alte
Pods schreiben keinen Herzschlag; ihre laufenden Läufe gelten bei neuen Pods nach 90 s bzw.
3 min (gezählt ab dem Start) als verwaist.

## Was der Betrieb einstellen muss

Werte, ohne die ein Cluster zwar startet, aber unter Last oder beim Rollout Züge verliert.
Die Helm-Vorlage (`deploy/helm/values.example.yaml`) trägt sie bereits; hier steht, warum.

* **DB-Verbindungen:** je Pod ein Pool von `DB_POOL_SIZE` + `DB_MAX_OVERFLOW` (Vorgabe 5 + 10),
  bis zu 4 der Sitzungssperre (eigener kleiner Pool, Paket 19), eine LISTEN-Verbindung und
  kurzzeitig eine für die Bereitschaftsprobe (`/ready`, ohne Pool).
  Also `max_connections ≥ N × (DB_POOL_SIZE + DB_MAX_OVERFLOW + 6) + Reserve` (die 6: Sitzungssperre 4, LISTEN 1, `/ready` 1;
  Reserve für Migration, psql, Sicherung), mit den Vorgaben N × 21 — beim Rolling Update
  zählen die Surge-Pods mit (N = Repliken + `maxSurge`). Oder PgBouncer im
  Session-Modus (LISTEN braucht ihn). Seit Paket 19 hält ein Zug seine Verbindung nur während
  der Abfragen, nicht über LLM und MCP; jede Verbindung trägt Fristen (`DB_*_TIMEOUT_S`). Die
  Server-Fristen setzt die App per `SET` nach dem Verbindungsaufbau, nicht als Startparameter —
  PgBouncer lehnt unbekannte Startparameter ab.
* **Gnadenfrist ≥ 75 s:** bis 5 s schließt der Pod seine Läufe, Uvicorn wartet bis 30 s auf
  offene Anfragen, danach der Lebenszyklus bis 25 s auf nachlaufende Züge, plus Abbruch und
  Abbau (5 + 5 + 2 s). Compose: `stop_grace_period: 75s`. Kubernetes:
  `terminationGracePeriodSeconds: 85` — die preStop-Zeit zählt mit, dazu 5 s Luft.
* **preStop 5 s:** der Pod bekommt SIGTERM erst, wenn sein Endpunkt aus dem Service genommen
  ist; sonst landen in den ersten Sekunden noch neue Anfragen auf einem gehenden Pod.
* **SSE ohne Pufferung:** die Ströme senden `X-Accel-Buffering: no` und
  `Cache-Control: no-cache, no-transform`. Ein Proxy, der das übergeht, liefert die Antwort
  erst am Ende (Punkt 4).
* **Lese-Timeout am Proxy > 10 s:** ein laufender Strom sendet alle 10 s ein Keepalive
  (`api/sse.KEEPALIVE_SECONDS`). Ein kürzerer Lese-Timeout trennt jeden Zug, der länger
  rechnet; die Vorlage setzt 120 s.
* **Rate-Limit geteilt:** `RATE_LIMIT_STORAGE_URI` auf Valkey (Punkt 3). Mit `memory://` zählt
  jede Replik für sich; in Kubernetes warnt der Start (`KUBERNETES_SERVICE_HOST`).

**Punkt 2 war vor P10-3 ungeprüft.** `test_pg_locks_notify.py` prüft den *Inhalt*
der Benachrichtigung und lässt dafür bewusst bis zu 5 s Wartezeit zu — die
§8-Schranke ist aber eine Zeit, und 5 s > 2 s. Der neue Test misst die Spanne
zwischen Schreiben und Eintreffen; bei der Abnahme am 2026-07-27 lag sie bei
**0,02 s** (im Umkehr-Lauf mit künstlich enger Schranke abgelesen).

**Punkt 3 war vor P10-2 gar nicht baubar.** `limits` braucht für einen geteilten
Zähler einen Client; der fehlte, ein Compose mit gesetzter Storage-URI hätte einen
Container erzeugt, der beim Import stirbt. Seit P10-2 ist die Abhängigkeit da —
seit **P10-6** ist es `valkey` statt `redis`, weil Redis 8 unter RSALv2/SSPLv1/
AGPLv3 steht und alle drei auf der Verbotsliste der Eisernen Regel 1 stehen.
Am Protokoll ändert der Tausch nichts. Beide Tests prüfen die Eigenschaft, auf
die es ankommt: **zwei** Limiter-Instanzen
(= zwei Replikas) teilen sich *ein* Kontingent, und eine später gestartete
Replika erbt den laufenden Zählerstand, statt ihn zurückzusetzen.

---

## Live-Protokoll (braucht den laufenden Prod-Stack)

Voraussetzung: `deploy/compose.prod.yml` läuft mit `BACKEND_REPLICAS=3`. Das
ist bewusst gesetzt: die Vorgabe ist 1 (Paket 4, L4). Seit Paket 7 (P1) sperrt
Postgres die Züge einer Sitzung über alle Repliken — die Protokolle hier prüfen
den Mehr-Replika-Betrieb, bevor man ihn einschaltet.

```powershell
cd deploy
docker compose -f compose.prod.yml --env-file .env up -d
docker compose -f compose.prod.yml ps          # 3 backend-Container, alle healthy
```

### Punkt 4 — SSE über den Load-Balancer

Nicht automatisiert, weil dafür ein echter Reverse-Proxy zwischen Client und
Server stehen muss: der Fehler, den dieser Punkt sucht, ist *Pufferung* im
Proxy — der Stream kommt dann erst am Ende an, und genau das sieht ein
In-Process-Testclient nie.

1. Chat-Stream anstoßen und die Ereignisse **einzeln eintrudeln** sehen:
   ```powershell
   curl -N -H "Content-Type: application/json" `
     -d '{\"message\":\"Hallo\",\"session_id\":\"lb-check\"}' `
     https://<PUBLIC_HOST>/api/chat/stream
   ```
   Erwartung: die `data:`-Zeilen erscheinen nach und nach. Kommt alles auf
   einmal am Schluss, puffert der Proxy.
2. Denselben Aufruf 5× wiederholen. Erwartung: jedes Mal vollständig — die
   Session liegt in Postgres, es ist also egal, welche Replika antwortet
   (deshalb sind auch **keine Sticky-Sessions** konfiguriert).
3. Während ein Stream läuft: `docker compose -f compose.prod.yml logs -f backend`
   — die Antwort darf von einer anderen Replika kommen als der vorige Turn.

### Punkt 5 — Graceful Shutdown

**Gemessen ist die eine Hälfte** (P10-1, wiederholbar): auf `docker stop`
beendet sich der Container in ~3 s mit ExitCode 0 und der Log-Zeile
„Application shutdown complete" — kein SIGKILL, kein Timeout.

Die andere Hälfte — *verliert keinen Turn* — braucht einen Turn, der im Flug
ist, während die Replika geht:

1. Langen Stream starten (Frage, die Werkzeuge auslöst).
2. Währenddessen **genau die Replika** stoppen, die ihn bedient:
   ```powershell
   docker stop <container-id-der-replika>
   ```
3. Erwartung: der laufende Stream wird **zu Ende geliefert** (uvicorn wartet,
   gedeckelt auf `--timeout-graceful-shutdown 30`; danach wartet der Lifespan bis
   25 s auf nachlaufende Züge — `stop_grace_period: 75s` im Compose deckt beides,
   sonst schösse Docker dazwischen).
4. Danach: neuer Turn derselben Session gegen den Cluster — die Historie muss
   den abgeschlossenen Turn enthalten.

### Lasttest-Abnahme (§8: „stabil bis ≥ 8 parallel auf 2-Kern-Referenz")

Gehört dem Nutzer (Studio → *Lasttest*, oder `POST /api/loadtest/runs`), weil
der Lauf echte LLM-Aufrufe kostet und die Pipeline mit Live-Verkehr teilt.
Deshalb ist `BOERDI_ALLOW_LOADTEST` im Prod-Compose per Default **`false`** — der
Lasttest gehört auf eine Staging-Instanz. (Bis 2026-09-29 stand dort ein leerer
Wert; `settings.py` liest leer als „nicht gesetzt" = Code-Default `true`.)

Achtung bei der Ablesung: das Backend deckelt Profile still (Parallelität > 32,
Stufen > 6, Requests/Stufe > 60). Die Studio-Ansicht zeigt deshalb das
**effektive** Profil, nicht das getippte.

Läuft ein Lauf aus dem Ruder, hält ihn der *Stoppen*-Knopf an (Lauf-Liste oder
offenes Lauf-Panel; `POST /api/loadtest/runs/{run_id}/cancel`). Die bis dahin
gemessenen Stufen bleiben als Status `gestoppt` stehen — löschen lässt sich ein
laufender Lauf weiterhin nicht, ein gestoppter schon.

---

## Was dieses Dokument bewusst NICHT behauptet

* Kein Punkt ist „grün", weil er plausibel ist. Punkt 4 und die zweite Hälfte
  von Punkt 5 sind offen, bis jemand sie am laufenden Stack durchgeht.
* Der Cluster ist hier nie mit drei echten Replikas gelaufen — P10 liefert die
  Dateien und die Tests, nicht das Betriebsprotokoll eines echten Servers.
* Die Punkte 6–8 prüfen die Datenbank-Seite mit einem Prozess, der seinen Speicher leert;
  zwei echte Pods während eines Rollouts hat niemand beobachtet.
