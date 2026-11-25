"""Flask extension: put the profile controls into the deposit forms.

For every model of the app that uses profile-guided deposition this overrides
the tabbed form of the model's deposit pages, so its files section gets the
profile controls. A host that already overrides the form keeps its own
component; it can then compose the plugin's components itself (see the README).

``OAREPO_PGD_UI_OVERRIDES = False`` switches the automatic overrides off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from oarepo_ui.overrides import UIComponent, UIComponentOverride

from .registry import profile_models

if TYPE_CHECKING:
    from flask import Flask

    from .registry import ModelProfiles


def ui_overrides(models: dict[str, ModelProfiles]) -> list[UIComponentOverride]:
    """Overrides for the deposit pages of the given models; a model without a UI gets none."""
    overrides = []
    for entry in models.values():
        if not entry.ui_blueprint:
            continue
        form = UIComponent("ProfileTabForm", "@js/oarepo_pgd/overrides")
        for page in ("deposit_create", "deposit_edit"):
            endpoint = f"{entry.ui_blueprint}.{page}"
            overrides.append(UIComponentOverride(endpoint, f"{entry.form_prefix}.WizardForm.container", form))
    return overrides


class OARepoPGD:
    """oarepo-pgd extension."""

    def __init__(self, app: Flask | None = None) -> None:
        if app:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        # oarepo-ui's default override set is one module-level object shared by
        # every app in the process. Give this app its own copy before anything
        # is added to it, so one app's overrides never show up in another.
        app.config["OAREPO_UI_OVERRIDES"] = set(app.config.get("OAREPO_UI_OVERRIDES", ()))
        app.extensions["oarepo-pgd"] = self


def finalize_app(app: Flask) -> None:
    """Register the overrides once the app's models are known.

    Models enter ``OAREPO_MODELS`` while extensions initialise, so this runs at
    finalization. The set is changed in place, because oarepo-ui may already
    hold a reference to it.
    """
    if not app.config.get("OAREPO_PGD_UI_OVERRIDES", True):
        return
    # Overrides are equal by endpoint and component id, and a set keeps the element
    # it already holds, so an override the host configured for the same component wins.
    app.config["OAREPO_UI_OVERRIDES"].update(ui_overrides(profile_models(app)))
