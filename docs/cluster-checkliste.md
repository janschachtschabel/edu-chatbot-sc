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
| 1 | Session-Turns serialisiert (Advisory-Lock) | `test_pg_locks_notify.py::test_same_session_turns_serialize` + `::test_different_sessions_run_parallel` | ✅ (pg) |
| 2 | Config-Änderung propagiert < 2 s | `test_cluster_checklist.py::test_config_change_propagates_within_the_two_second_bound` | ✅ (pg) |
| 3 | Rate-Limit konsistent über den geteilten Zähler | `test_cluster_checklist.py::test_two_replicas_share_one_budget_over_a_shared_store` + `::test_a_replica_started_later_inherits_the_running_count` | ✅ (valkey) |
| 4 | SSE über den Load-Balancer stabil | Live-Protokoll unten | ❌ |
| 5 | Graceful Shutdown verliert keinen Turn | Live-Protokoll unten (Hälfte gemessen, s. u.) | ➗ |

```powershell
cd backend
docker compose -f ../deploy/compose.dev.yml up -d postgres valkey
uv run pytest tests/test_cluster_checklist.py tests/test_pg_locks_notify.py -v
```

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

Voraussetzung: `deploy/compose.prod.yml` läuft mit `BACKEND_REPLICAS=3`.

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
   gedeckelt auf `--timeout-graceful-shutdown 30`; `stop_grace_period: 40s` im
   Compose ist bewusst länger, sonst schösse Docker dazwischen).
4. Danach: neuer Turn derselben Session gegen den Cluster — die Historie muss
   den abgeschlossenen Turn enthalten.

### Lasttest-Abnahme (§8: „stabil bis ≥ 8 parallel auf 2-Kern-Referenz")

Gehört dem Nutzer (Studio → *Lasttest*, oder `POST /api/loadtest/runs`), weil
der Lauf echte LLM-Aufrufe kostet und die Pipeline mit Live-Verkehr teilt.
Deshalb ist `BOERDI_ALLOW_LOADTEST` im Prod-Compose per Default **leer** — der
Lasttest gehört auf eine Staging-Instanz.

Achtung bei der Ablesung: das Backend deckelt Profile still (Parallelität > 32,
Stufen > 6, Requests/Stufe > 60). Die Studio-Ansicht zeigt deshalb das
**effektive** Profil, nicht das getippte.

---

## Was dieses Dokument bewusst NICHT behauptet

* Kein Punkt ist „grün", weil er plausibel ist. Punkt 4 und die zweite Hälfte
  von Punkt 5 sind offen, bis jemand sie am laufenden Stack durchgeht.
* Der Cluster ist hier nie mit drei echten Replikas gelaufen — P10 liefert die
  Dateien und die Tests, nicht das Betriebsprotokoll eines echten Servers.
