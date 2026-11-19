"""Fester Beispielsatz für die Zuordnung Datei → Punkt (Paket N3, Plan 2026-11-19).

16 Materialien im Format des Teils ``metadaten`` (``wlo.metadaten@1``): je 3–4 zu vier klaren
Themen der Erdkunde (Vulkane, Plattentektonik, Erdbeben, Klima) und zwei fachfremde, die keinem
Punkt gehören. Dazu vier Punkte, wie sie ein Entwurf ``aus_inhalten`` trägt (Titel, Beschreibung,
Unterpunkte), und die erwartete Zuordnung (``None`` = nicht zugeordnet).

Gebraucht vom CI-Test (``test_n3_zuordnung.py``, mit festen Vektoren) und vom Messlauf mit echtem
Einbettungsmodell (``scripts/zuordnung_messen.py``).
"""

from __future__ import annotations

from typing import Any, Final

_M: Final = [
    # (Titel, Beschreibung, Schlagworte, erwarteter Punkt)
    ("Aufbau eines Schichtvulkans", "Schnittbild mit Magmakammer, Schlot, Krater und "
     "Ascheschichten; Arbeitsblatt zum Beschriften.", ["Vulkan", "Magma", "Krater"], "k1"),
    ("Der Ausbruch des Vesuv 79 n. Chr.", "Quellentext und Fragen zum Untergang von Pompeji "
     "unter Asche und pyroklastischen Strömen.", ["Vesuv", "Pompeji", "Ausbruch"], "k1"),
    ("Hawaii: Schildvulkane und Lavaströme", "Video über dünnflüssige Lava, Hotspots und die "
     "Entstehung der Inselkette.", ["Schildvulkan", "Lava", "Hotspot"], "k1"),
    ("Leben mit dem Vulkan am Ätna", "Fallbeispiel: fruchtbare Böden, Gefahren und "
     "Vulkanüberwachung auf Sizilien.", ["Ätna", "Vulkanismus", "Gefahren"], "k1"),
    ("Kontinentaldrift nach Alfred Wegener", "Puzzle der Kontinente, Fossilienfunde und "
     "Belege für die Drift der Kontinente.", ["Wegener", "Kontinentaldrift", "Pangäa"], "k2"),
    ("Plattengrenzen im Überblick", "Divergente, konvergente und transforme Grenzen der "
     "Lithosphärenplatten mit Karte.", ["Plattengrenze", "Lithosphäre", "Subduktion"], "k2"),
    ("Mittelozeanischer Rücken und Seafloor-Spreading", "Wie am Meeresboden neue Kruste "
     "entsteht und die Platten auseinanderweichen.", ["Ozeanboden", "Spreizung", "Kruste"], "k2"),
    ("Gebirgsbildung: Wie der Himalaya entstand", "Kollision der Indischen und der "
     "Eurasischen Platte, Faltengebirge.", ["Himalaya", "Kollision", "Faltengebirge"], "k2"),
    ("Erdbebenwellen und Seismograph", "Wie P- und S-Wellen entstehen und wie ein Seismograph "
     "sie aufzeichnet.", ["Seismograph", "Erdbebenwellen", "Epizentrum"], "k3"),
    ("Richterskala und Magnitude", "Stärke von Erdbeben messen und vergleichen; Übungen zur "
     "logarithmischen Skala.", ["Magnitude", "Richterskala", "Beben"], "k3"),
    ("Tsunami nach dem Seebeben 2004", "Ursachen und Folgen des Tsunamis im Indischen Ozean, "
     "Frühwarnsysteme.", ["Tsunami", "Seebeben", "Frühwarnung"], "k3"),
    ("Erdbebensicher bauen in Japan", "Bauweisen und Verhalten im Ernstfall: so schützen sich "
     "Menschen vor Beben.", ["Erdbebenschutz", "Japan", "Gebäude"], "k3"),
    ("Klimazonen der Erde", "Tropen, Subtropen, gemäßigte und polare Zone mit Klimadiagrammen.",
     ["Klimazone", "Klimadiagramm", "Temperatur"], "k4"),
    ("Der Treibhauseffekt einfach erklärt", "Wie CO2 und andere Gase die Erde erwärmen; "
     "Folgen des Klimawandels.", ["Treibhauseffekt", "Klimawandel", "CO2"], "k4"),
    # fachfremd — gehört keinem Punkt
    ("Bruchrechnung: Brüche erweitern und kürzen", "Übungsblatt mit Lösungen zum Erweitern und "
     "Kürzen von Brüchen.", ["Bruch", "Kürzen", "Mathematik"], None),
    ("Present Perfect üben", "Englische Grammatik: Bildung und Gebrauch des Present Perfect "
     "mit Lückentext.", ["Grammatik", "Englisch", "Tenses"], None),
]

#: Die vier Punkte eines Entwurfs ``aus_inhalten`` (obere Ebene, mit Unterpunkten).
PUNKTE: Final[list[dict[str, Any]]] = [
    {"id": "k1", "titel": "Vulkane", "beschreibung": "Aufbau, Arten und Ausbrüche von "
     "Vulkanen und das Leben in ihrer Nähe.",
     "kinder": [{"id": "k1-1", "titel": "Aufbau eines Vulkans"},
                {"id": "k1-2", "titel": "Vulkanausbrüche und ihre Folgen"}]},
    {"id": "k2", "titel": "Plattentektonik", "beschreibung": "Der Aufbau der Erde in "
     "Platten, ihre Bewegung und was an den Grenzen geschieht.",
     "kinder": [{"id": "k2-1", "titel": "Kontinentaldrift"},
                {"id": "k2-2", "titel": "Plattengrenzen"}]},
    {"id": "k3", "titel": "Erdbeben", "beschreibung": "Entstehung, Messung und Folgen von "
     "Erdbeben sowie Schutz davor.",
     "kinder": [{"id": "k3-1", "titel": "Messung von Erdbeben"},
                {"id": "k3-2", "titel": "Tsunamis"}]},
    {"id": "k4", "titel": "Klima", "beschreibung": "Klimazonen der Erde und der Wandel des "
     "Klimas.",
     "kinder": [{"id": "k4-1", "titel": "Klimazonen"},
                {"id": "k4-2", "titel": "Klimawandel"}]},
]

#: Kennung ``aN`` (wie ``metadaten.als_dokument``) → erwarteter Punkt (``None``: keiner).
ERWARTET: Final[dict[str, str | None]] = {f"a{n}": m[3] for n, m in enumerate(_M, 1)}


def teil(*, mit_node_ids: bool = False, block_id: str = "blockbsp01") -> dict[str, Any]:
    """Der Teil ``metadaten`` des Beispiels — ``mit_node_ids``: wie nach ``metadaten_lesen``
    (WLO), sonst wie lokal (``quelle: chatbot``, mit ``upload_id``)."""
    inhalte = []
    for n, (titel, beschreibung, schlagworte, _punkt) in enumerate(_M):
        e: dict[str, Any] = {"i": n, "rolle": "inhalt", "titel": titel,
                             "beschreibung": beschreibung, "schlagworte": schlagworte}
        if mit_node_ids:
            e["node_id"] = f"00000000-0000-4000-8000-{n:012d}"
        else:
            e.update(lesbar=True, upload_id=f"up{n:04d}")
        inhalte.append(e)
    wert: dict[str, Any] = {"format": "wlo.metadaten@1", "inhalte": inhalte, "fehlend": [],
                            "block_id": block_id}
    if not mit_node_ids:
        wert["quelle"] = "chatbot"
    return wert
