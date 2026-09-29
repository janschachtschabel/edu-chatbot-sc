# Maschinen-Messung (K0)

| Kriterium | pattern | agent | hybrid |
|---|---|---|---|
| Läufe | 3 | 3 | 3 |
| Harte Quote (Spanne der Läufe) | 0,98 (0,97–0,99) | 0,89 (0,87–0,90) | 0,93 (0,91–0,96) |
| Judge intent_fit (0–2) | 1,83 | 1,74 | 1,73 |
| Judge persona_tone (0–2) | 1,23 | 1,00 | 1,05 |
| Judge pattern_match (0–2) | 1,85 | 2,00 | 1,68 |
| Judge safety (0–2) | 2,00 | 2,00 | 2,00 |
| Judge info_quality (0–2) | 1,28 | 1,33 | 1,23 |
| Judge auftrag_erfuellt (0–2) | 1,09 | 0,98 | 0,87 |
| Übereinstimmung der Checks | 0,64 | 0,64 | 0,74 |
| Werkzeug-Jaccard | 0,86 | 0,78 | 0,87 |
| Textnähe | 0,58 | 0,51 | 0,50 |
| Streuung auftrag_erfuellt | 0,40 | 0,47 | 0,45 |
| p50 / p95 (s) | 14,7 / 33,5 | 13,0 / 50,6 | 13,7 / 35,7 |
| Anteil über 30 s | 0,08 | 0,10 | 0,09 |
| Züge über 90 s | 0 | 0 | 1 |
| Token je Zug (Prompt / gecacht / Ausgabe) | 52863 / 27077 / 1137 | 63262 / 55045 / 919 | 75363 / 62595 / 962 |
| Kosten je Zug (USD) | 0,00342 | 0,00183 | 0,00238 |
| Chat-Fehler / Judge-Ausfall / leer / Ersatz | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 2 | 0 / 0 / 0 / 3 |
| SAFE: harte Quote | 1,00 | 1,00 | 1,00 |
| FREI: harte Quote / auftrag_erfuellt | 0,97 / 0,56 | 0,95 / 0,74 | 0,95 / 0,33 |

## Regeln (Plan §5.4)

- **R1 Hybrid: fällt.** Δ auftrag_erfuellt -0,11, Δ harte Quote 0,04, Kosten ×1,30, p50 ×1,06.
- **R2(a) Muster: nicht erfüllt.** Δ Übereinstimmung 0,00, Kosten ×1,87, p50 ×1,13. R2(b) — braucht eine Einbettung genau diesen Vorteil? — beantwortet keine Zahl.
- **R3:** Liegen Unterschiede innerhalb der Spanne der Läufe, gewinnt die einfachere Architektur.

## Messbedingungen

- k0-pattern-r1, k0-agent-r1, k0-hybrid-r1, k0-pattern-r2, k0-agent-r2, k0-hybrid-r2, k0-pattern-r3, k0-agent-r3, k0-hybrid-r3: openai · gpt-6-luna · Judge gpt-4o-mini · Master-Skill an (8bbf014fa385) · Deckel 20 Runden, 300 s, 400000 Token
