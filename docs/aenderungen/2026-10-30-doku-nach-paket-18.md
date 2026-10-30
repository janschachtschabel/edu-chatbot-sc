# Änderungsnotiz — Doku nach Paket 18

Stand 2026-10-30 · Basis `main` `924662a` (Paket 18 komplett)

**Warum:** Die zentrale Liste der offenen Punkte (`docs/offene-befunde-und-todo.md`) stand noch vor
Paket 18. Sie nennt jetzt, was Paket 18 erledigt hat, und was danach offen bleibt.

| Abschnitt | Neu |
|---|---|
| Pläne | Paket 18 mit seinen drei Plänen und der Rückmeldung an die Audit-Personen |
| §2 Entscheidungen | E5 (Agent-Deckel für Anonyme: erst Kosten messen), `MODERATION_FAILURE_MODE` festlegen |
| §4 Beim nächsten Deploy | Image, Migration `0016`, Plugin-Bündel, `STUDIO_API_KEY`, **`RATE_LIMIT_CHAT` vorher prüfen**, Zähler und Alarmregeln, `LLM_SLOT_WAIT_S` |
| §6 Zurückgestellt | Circuit-Breaker, 2000-Zeichen-Grenze der Rechtsprüfung, „Testnachricht“ → `quiz`, Zähler für Warteschlange/DB-Pool, die in 18E bewusst gelassenen Stellen, die ungeklärte Laufzeit der GitHub-Runner |

Kein Code, kein Deploy.
