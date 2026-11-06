"""Lader für ``01-base/upload-config`` (Paket U3-2a).

Tolerant wie ``pricing``: ``seed_io.import_tree`` schreibt ungeprüfte Dicts, ein Bestand am
Validator vorbei darf weder den Zug noch das Hochladen mit einem 500 beenden. Dann gilt die
Vorgabe — mit Warnung im Log, damit der Tippfehler nicht unsichtbar bleibt.
"""

from __future__ import annotations

import logging

from boerdi.domain.config_models.upload import UploadConfigArea, UploadSettings
from boerdi.services.config_loader._store import area

logger = logging.getLogger(__name__)

BEREICH = "01-base/upload-config"


def load_upload_config() -> UploadSettings:
    try:
        return UploadConfigArea.model_validate(area(BEREICH)).upload
    except Exception:
        logger.warning("upload: %s ist unlesbar — es gilt die Vorgabe", BEREICH, exc_info=True)
        return UploadSettings()
