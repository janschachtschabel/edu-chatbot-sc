# Maschinen-Messung (K0)

| Kriterium | pattern | agent |
|---|---|---|
| Läufe | 3 | 3 |
| Harte Quote (Spanne der Läufe) | 0,98 (0,97–1,00) | 0,92 (0,88–0,96) |
| Judge intent_fit (0–2) | 1,94 | 1,72 |
| Judge persona_tone (0–2) | 1,21 | 1,02 |
| Judge pattern_match (0–2) | 1,89 | 2,00 |
| Judge safety (0–2) | 2,00 | 2,00 |
| Judge info_quality (0–2) | 1,30 | 1,29 |
| Judge auftrag_erfuellt (0–2) | 1,06 | 0,92 |
| Übereinstimmung der Checks | 0,67 | 0,60 |
| Werkzeug-Jaccard | 0,83 | 0,77 |
| Textnähe | 0,55 | 0,50 |
| Streuung auftrag_erfuellt | 0,42 | 0,43 |
| p50 / p95 (s) | 15,4 / 30,4 | 12,4 / 37,4 |
| Anteil über 30 s | 0,06 | 0,11 |
| Züge über 90 s | 0 | 0 |
| Token je Zug (Prompt / gecacht / Ausgabe) | 51725 / 30285 / 1155 | 61995 / 54747 / 910 |
| Kosten je Zug (USD) | 0,00303 | 0,00173 |
| Chat-Fehler / Judge-Ausfall / leer / Ersatz | 0 / 0 / 0 / 1 | 0 / 0 / 0 / 1 |
| SAFE: harte Quote | 1,00 | 1,00 |
| FREI: harte Quote / auftrag_erfuellt | 0,97 / 0,44 | 1,00 / 0,70 |

## Regeln (Plan §5.4)

- **R2(a) Muster: nicht erfüllt.** Δ Übereinstimmung 0,07, Kosten ×1,75, p50 ×1,25. R2(b) — braucht eine Einbettung genau diesen Vorteil? — beantwortet keine Zahl.
- **R3:** Liegen Unterschiede innerhalb der Spanne der Läufe, gewinnt die einfachere Architektur.

## Messbedingungen

- k1-tor-pattern-r1, k1-tor-agent-r1, k1-tor-pattern-r2, k1-tor-agent-r2, k1-tor-pattern-r3, k1-tor-agent-r3: openai · gpt-6-luna · Judge gpt-4o-mini · Master-Skill an (8bbf014fa385) · Deckel 20 Runden, 300 s, 400000 Token
