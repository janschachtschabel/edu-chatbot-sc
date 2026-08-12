"""C5: Ressourcen-Abtastung im Lasttest (psutil) + die Spitzenwerte im Summary.

Port von ALT ``loadtest_service._sample_resources`` (Z. 226-245) und der
Peak-Berechnung (Z. 355-361). NEU hatte beides weggelassen — ``pyproject.toml``
lag außerhalb des damaligen Slice —, wodurch ``resource_samples`` immer ``[]``
blieb und das Summary die zwei Spitzenwerte gar nicht erst führte. Das Studio
benannte den Zustand seit B5 ehrlich; hier wird er behoben.

DB-frei und deterministisch: die Abtastschleife sampelt in ihrer ERSTEN
Iteration ohne Wartezeit (ALT-Form: erst messen, dann ``wait_for(0.5)``), also
liefert ein sofortiges ``stop`` bereits einen Messpunkt — ohne den Test an eine
halbe Sekunde Wanduhr zu hängen.
"""

from __future__ import annotations

import asyncio

from boerdi.services.loadtest import _sample_resources, _summary

# Ein Lauf, dessen Stufen alle gesund sind — hier interessiert nur, was das
# Summary AUS DEN SAMPLES macht, nicht die stable_concurrency-Logik.
STAGES = [{"concurrency": 2, "errors": 0, "p95_s": 1.0, "requests": 4}]


async def test_sampler_records_alt_four_keys_and_stops_on_event():
    samples: list[dict] = []
    stop = asyncio.Event()

    task = asyncio.create_task(_sample_resources(samples, stop))
    await asyncio.sleep(0)      # der Schleife die erste Iteration lassen
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    assert samples, "die erste Iteration muss ohne Wartezeit messen (ALT-Form)"
    assert set(samples[0]) == {"t", "proc_cpu", "sys_cpu", "rss_mb"}
    assert samples[0]["rss_mb"] > 0      # ein laufender Prozess belegt Speicher
    assert samples[0]["t"] >= 0


def test_summary_reports_peaks_from_samples():
    samples = [
        {"t": 0.0, "proc_cpu": 12.5, "sys_cpu": 30.0, "rss_mb": 120.0},
        {"t": 0.5, "proc_cpu": 47.0, "sys_cpu": 55.0, "rss_mb": 210.5},
        {"t": 1.0, "proc_cpu": 8.0, "sys_cpu": 22.0, "rss_mb": 180.0},
    ]

    out = _summary(STAGES, threshold=2.0, samples=samples)

    assert out["peak_rss_mb"] == 210.5
    assert out["peak_proc_cpu_pct"] == 47.0


def test_summary_without_samples_reports_zero_peaks_like_alt():
    """ALT: ``max(..., default=0.0)``. Eine 0.0 ist hier ehrlich — der Lauf hat
    nichts gemessen —, und der Schlüssel FEHLT nicht, damit das Studio nicht
    wieder zwischen „kein Wert" und „nicht erhoben" raten muss."""
    out = _summary(STAGES, threshold=2.0, samples=[])

    assert out["peak_rss_mb"] == 0.0
    assert out["peak_proc_cpu_pct"] == 0.0
