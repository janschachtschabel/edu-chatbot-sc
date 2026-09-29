"""ST-6: ein Feld, das der Code festsetzt, sagt es dem Studio (``x-fixed``).

``privacy-config.logging.safety`` liest der Lader nie — er gibt ``True`` fest
zurück (Audit-Pfad). Bis ST-6 zeigte das Studio trotzdem einen Schalter, der
sich auf „aus" stellen und speichern ließ: gespeichert, angezeigt, wirkungslos.
"""

from boerdi.domain.config_models.base_governance import PrivacyConfigArea
from boerdi.services.config_loader.safety import load_privacy_config


def test_das_sicherheitsprotokoll_ist_als_fest_markiert() -> None:
    block = PrivacyConfigArea.model_json_schema()["$defs"]["PrivacyLoggingBlock"]
    assert block["properties"]["safety"].get("x-fixed") is True
    # die anderen drei Schalter wirken — sie bleiben bedienbar
    for key in ("messages", "memory", "quality"):
        assert "x-fixed" not in block["properties"][key], key


def test_der_lader_setzt_es_fest_gleich_was_gespeichert_ist(monkeypatch) -> None:
    from boerdi.services.config_loader import safety as modul

    monkeypatch.setattr(modul, "area", lambda _k: {"logging": {"safety": False}})
    assert load_privacy_config()["safety"] is True
