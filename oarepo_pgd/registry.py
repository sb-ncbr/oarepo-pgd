"""Models of one Flask app that enabled profile-guided deposition.

``pgd_preset`` stores each model's configuration on the built model namespace
(as ``DepositionProfiles``). An app reaches its models through
``app.config["OAREPO_MODELS"]``, the registry OARepo itself keeps per app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

    from .profiles import Configuration

NAMESPACE_KEY = "DepositionProfiles"


@dataclass(frozen=True)
class ModelProfiles:
    """One model's deposition configuration and the names of its UI."""

    configuration: Configuration
    ui_blueprint: str | None
    application_id: str


def profile_models(app: Flask) -> dict[str, ModelProfiles]:
    """The app's registered models that use profile-guided deposition, by model name."""
    result = {}
    for name, model in app.config.get("OAREPO_MODELS", {}).items():
        # Models not built by oarepo-model have no namespace.
        data = getattr(model.namespace, NAMESPACE_KEY, None)
        if not data:
            continue
        result[name] = ModelProfiles(
            configuration=data["configuration"],
            ui_blueprint=model.ui_blueprint_name,
            # oarepo-model drops None values from the stored dictionary.
            application_id=data.get("application_id") or name,
        )
    return result
