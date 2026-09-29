"""Paket F: Links ins Repositorium — einen Knoten ansehen, einen Skill bearbeiten.

Der md-editor des Repositoriums lässt sich auch außerhalb von edu-sharing öffnen
(Nutzer 2026-09-29); er liest ``nodeId`` und ``field`` aus der Adresse
(``md-editor-merged/src/host.js``).
"""

from __future__ import annotations

from boerdi.domain.repo_links import editor_url, render_url


def test_ansehen_ist_der_permalink_der_render_seite() -> None:
    assert render_url("abc-1", "https://repo.example/") == (
        "https://repo.example/edu-sharing/components/render/abc-1")


def test_bearbeiten_oeffnet_die_datei_im_md_editor() -> None:
    """``field=file``: der Anleitungstext eines Skills steht in seiner Datei.
    ``name`` fehlt bewusst — der Editor nimmt die angemeldete Person, das Studio
    behauptet keine Identität."""
    assert editor_url("abc-1", "https://repo.example/") == (
        "https://repo.example/edu-sharing/services/md-editor/?nodeId=abc-1&field=file")


def test_bearbeiten_kodiert_die_kennung() -> None:
    """Die Kennung kommt aus einer MCP-Antwort; sie darf keinen Parameter anhängen."""
    assert "?nodeId=a%26field%3Dx&field=file" in editor_url("a&field=x", "https://repo.example")


def test_ansehen_kodiert_die_kennung() -> None:
    """Review 2026-09-29: dieselbe Regel für den Pfad — ein ``/``, ``?`` oder
    ``#`` in der Kennung darf weder Pfad noch Abfrage noch Sprungmarke ändern."""
    assert render_url("a/../b?x=1#y", "https://repo.example") == (
        "https://repo.example/edu-sharing/components/render/a%2F..%2Fb%3Fx%3D1%23y")
