
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
