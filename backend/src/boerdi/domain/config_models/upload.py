"""01-base/upload-config — Schalter und Grenzen des Hochladens (Paket U3-2a, Plan §16.6).

Gelesen von ``config_loader.upload``: der Dienst ``upload_angebot`` gibt die Schalter in den Block
von ``ui_upload`` (das Modul zeigt nur, was an ist), der Endpunkt ``POST /api/ui/dokumente`` prüft
sie und die Grenzen noch einmal — das Widget ist kein Torwächter.

Die Obergrenzen sind fest, weil die Rumpf-Grenze (``api/body_limit``) vor jeder Konfiguration
greift: ``OBERGRENZE_MB`` ist dort die Grenze des Pfads.
"""

from typing import ClassVar

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel


class UploadSettings(AreaModel):
    """Was die Person hochladen darf und wie lange es bleibt."""

    OBERGRENZE_MB: ClassVar[int] = 25

    #: Ein Dokument im Chat umwandeln und verwerten (ohne Ablage im Repositorium).
    dokument_im_chat: bool = True
    #: Dasselbe auch ohne WLO-Anmeldung (Kosten und Missbrauch: Vorgabe aus).
    dokument_ohne_anmeldung: bool = False
    #: Inhalte im persönlichen Bereich von WLO anlegen (U3-3; nur mit bestätigter Anmeldung;
    #: je Datei höchstens ``max_mb``).
    ablage_in_wlo: bool = False
    max_mb: int = Field(default=10, ge=1, le=OBERGRENZE_MB)
    max_seiten: int = Field(default=300, ge=1, le=1000)
    #: Frist nach der letzten Nutzung; danach löscht der Aufbewahrungslauf das Dokument.
    aufbewahrung_h: int = Field(default=24, ge=1, le=72)


class UploadConfigArea(AreaModel):
    upload: UploadSettings = UploadSettings()
