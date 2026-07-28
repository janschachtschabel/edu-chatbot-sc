"""Pure card domain (P5-4) — the ALT ``card_pipeline.py`` monolith (1285 L) split
by responsibility per the NEU layering rule (``domain/`` = framework-free logic).

Sub-modules:
- ``normalize`` — Phase-2 normalization (node_type inference, host-rewrite, dedup,
  priority sort, wlo_url repair) + the shared repo-URL builders. [5-4a]
- ``select`` — Pipeline-v2 final selection (relevance scoring, deterministic
  type-mix, LLM re-rank merge, type-focus filter, log summary). [5-4b]
- ``links`` — final URL resolution (``build_card_link`` lookup table + guide-mode
  routing), allow-list ``validate_card_link``, ``annotate_cards_with_link``. [5-4c]

Reranker/gate: ``services/card_reranker.py`` [5-5]. Async I/O orchestration:
``services/card_pipeline.py`` (``fetch_card_pool`` + ``run_pipeline_v2``)
[5-4-Tail] — verkettet die obigen Stufen. → Card-Paket P5-4 komplett.
"""
