
---

**Nachtrag X1 (2026-08-20) — Tour-Abschluss kollidierte mit der Kontext-Begrüßung.**
Live auf wp-test.wirlernenonline.de: direkt hinter dem letzten Tour-Schritt („Fast
geschafft" auf /mitmachen/) erschien „Du bist auf wp-test… — das gehört nicht zu
WLO". Zwei Ursachen, beide gefixt: (1) `own_hosts` führte `wirlernenonline.de` nur
als exakten Host — Subdomains galten als fremd; der Seed trägt jetzt zusätzlich
`*.wirlernenonline.de` (Wächter-Test pinnt die Einstufung gegen die echte
Seed-Datei). (2) `_afterResume` prüfte das Tour-Flag erst NACH dem Tick — der
Abschluss-Tick löscht es, der Kontext-Ping feuerte im selben Load; der Besitz des
Loads wird jetzt VOR dem Tick entschieden, und `onSpaContextChange` schweigt
während einer laufenden Tour ebenfalls (der Kontext selbst bleibt aktuell, die
Ankunftserkennung braucht ihn). Der Abschluss-TEXT ist wortgleich mit ALT — dort
war nichts zu fixen; die Störung war die external-Begrüßung, die es in ALT nicht
gab. Tore: Backend 30 passed (page_host + enrich), Frontend ui 826 passed.


## Z2-Nachtrag (2026-08-20): Gescheiterte Auflösung verschluckt die Node-ID nicht mehr

Live-Befund (edu-sharing, 2×: Qualitätscheck neues Material + Prüftisch
`editorial-desk?nodeId=…`): Die Seite reicht die `node_id` korrekt herein
(Handover-Log bestätigt), der **anonyme** Bot darf den unveröffentlichten
Knoten aber nicht lesen — `get_node_details` scheitert (403). Der finale
Fallback in `resolve_page_context` verlangte einen `document_title`; ohne ihn
kam `None` zurück und `render_for_prompt` verwarf den GANZEN Seitenblock. Das
Modell fragte den Nutzer nach der Node-ID, die längst vorlag, und suchte
chancenlos nach dem Titel (Index kennt nur Öffentliches).

Fix (backend-only, `services/page_context.py`):
1. Finaler Fallback baut auch OHNE Titel ein Meta, sobald eine adressierbare
   ID da ist (`source: "unresolved_node"`, `node_id` im Meta, synthetischer
   Titel). Kurze TTL für unresolved-Metas galt schon (Retry nach Anmeldung).
2. `render_for_prompt` hängt bei `unresolved` + ID eine ehrliche Ansage an:
   Auflösung gescheitert (vermutlich Leserechte/anonym), ID liegt vor — NICHT
   danach fragen, keine Titelsuche; Text/Transkript erbitten oder auf die
   Anmeldung (Ticket) verweisen.

Tests: 4 neue in `tests/test_page_context.py` (Resolve mit/ohne document_title,
Render-Hinweis, Gegenprobe aufgelöstes Meta ohne Hinweis); 3 davon rot gesehen.
Verbraucher-Suiten (enrich, classify_prompt, response_prompt_builder,
respond_agent) unverändert grün. Der KONZIPIERTE Weg für den Anwendungsfall
bleibt das `ticket`-Attribut (edu-sharing-einbindung.md §3) — dieser Fix macht
den anonymen Fall ehrlich, er ersetzt die Anmeldung nicht.
