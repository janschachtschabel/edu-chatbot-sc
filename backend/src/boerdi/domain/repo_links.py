"""Links ins Repositorium (edu-sharing): einen Knoten ansehen, einen Skill bearbeiten.

Rein: die Basis-Adresse kommt vom Aufrufer (``get_repo_base_url``), damit die
Domäne keine Einstellung liest. Der Master-Skill im Studio und das
Skill-Verzeichnis bauen ihre Links hier, statt sie je selbst zusammenzusetzen.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode


def render_url(node_id: str, repo_base: str) -> str:
    """Der Permalink der Render-Seite — zum Ansehen eines Knotens.

    Die Kennung ist kodiert wie beim Editor: ein ``/``, ``?`` oder ``#`` darf
    weder Pfad noch Abfrage noch Sprungmarke ändern (Review 2026-09-29).
    """
    return f"{repo_base.rstrip('/')}/edu-sharing/components/render/{quote(node_id, safe='')}"


def editor_url(node_id: str, repo_base: str) -> str:
    """Der md-editor des Repositoriums für den Markdown-Text eines Skills.

    Er lässt sich auch außerhalb von edu-sharing öffnen (Nutzer 2026-09-29) und
    liest ``nodeId`` und ``field`` aus der Adresse. ``field=file``: der
    Anleitungstext eines Skills steht in seiner Datei. ``name`` fehlt bewusst —
    der Editor nimmt die angemeldete Person; aus dem Studio heraus behaupten wir
    keine Identität. Gespeichert wird mit der edu-sharing-Anmeldung im Browser.
    """
    abfrage = urlencode({"nodeId": node_id, "field": "file"})
    return f"{repo_base.rstrip('/')}/edu-sharing/services/md-editor/?{abfrage}"
