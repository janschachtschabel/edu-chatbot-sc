"""The evaluation engine (ALT ``eval_*`` services, ported in P7-E and C3).

Seven modules, mirroring ALT's own split so the port stays diffable:

* ``text_utils`` — marker/ID helpers shared by judge and metrics
* ``prompts`` — the three LLM templates (scenario, simulator, judge)
* ``scenario_gen`` — LLM scenario generation per persona×intent combo
* ``judge`` — per-turn LLM scoring + the expectation blocks it is given
* ``metrics`` — pure aggregation of judged turns into a run summary
* ``runner`` — conversation simulation + the generative run orchestrator
* ``golden`` — the soft layer over a golden run (C3, ALT ``eval_golden``)

``eval_service`` stays the HTTP-facing layer and owns persistence. The
deterministic *golden* half — firing the flows and the hard Soll-Ist checks —
stays in the framework-free ``evals/run_golden.py``; ``golden`` here is only the
part that needs config and an LLM.
"""
