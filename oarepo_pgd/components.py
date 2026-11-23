"""Give the deposit form its model's deposition configuration.

Add the component to the ``components`` list of the model's UI resource config
class, in ``ui/<model>/__init__.py``, after the entries already there::

    from oarepo_pgd.components import DepositionProfilesComponent


    class DatasetsUIResourceConfig(RDMRecordsUIResourceConfig):
        components = [*RDMRecordsUIResourceConfig.components, DepositionProfilesComponent]

The form then finds the configuration in its form config, as ``deposition_profiles``,
with its texts in the page's language.
"""

from __future__ import annotations

from typing import Any

from flask import current_app
from oarepo_ui.resources.components import UIResourceComponent

from .registry import profile_models
from .texts import localized_configuration

FORM_CONFIG_KEY = "deposition_profiles"


class DepositionProfilesComponent(UIResourceComponent):
    """Put the model's semantic types and profiles into the form config."""

    def form_config(self, *, form_config: dict[str, Any], **kwargs: Any) -> None:
        """Add the configuration when the resource's model uses profile-guided deposition."""
        entry = profile_models(current_app).get(self.config.model_name)
        if entry:
            form_config[FORM_CONFIG_KEY] = localized_configuration(entry.configuration)
