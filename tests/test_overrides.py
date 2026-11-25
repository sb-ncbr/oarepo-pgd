"""The configuration served and the overrides registered for an app's models.

Both are read from the app's own ``OAREPO_MODELS``.
"""

from types import SimpleNamespace

import oarepo_ui.config
import pytest
from flask import Flask
from oarepo_ui.overrides import UIComponent, UIComponentOverride

from oarepo_pgd.components import DepositionProfilesComponent
from oarepo_pgd.config import ConfigurationError
from oarepo_pgd.ext import OARepoPGD, finalize_app
from oarepo_pgd.profiles import Configuration, Profile
from oarepo_pgd.registry import NAMESPACE_KEY
from oarepo_pgd.views import create_api_blueprint

OTHER_MODEL = SimpleNamespace(namespace=None, ui_blueprint_name=None)


def registered_model(profile_id, application_id=None, ui_blueprint_name="datasets_ui"):
    """What OARepo keeps in OAREPO_MODELS: a runtime model with its built namespace."""
    profile = Profile(profile_id, revision="1", dataset_category=profile_id, semantic_types=(), requirements=())
    configuration = Configuration(profiles=(profile,))
    stored = {"configuration": configuration}
    # As oarepo-model builds it: keys whose value is None are left out.
    if application_id:
        stored["application_id"] = application_id
    return SimpleNamespace(
        namespace=SimpleNamespace(**{NAMESPACE_KEY: stored}),
        ui_blueprint_name=ui_blueprint_name,
    )


def create_app(models, **config):
    app = Flask(__name__)
    app.config.update(OAREPO_MODELS=models, **config)
    # As oarepo-ui's extension does: every app starts from the same default set.
    app.config.setdefault("OAREPO_UI_OVERRIDES", oarepo_ui.config.OAREPO_UI_OVERRIDES)
    OARepoPGD(app)
    app.register_blueprint(create_api_blueprint(app))
    finalize_app(app)
    return app


def served(app, query=""):
    response = app.test_client().get(f"/deposition-profiles{query}")
    return response.status_code, response.get_json()


def test_each_app_serves_its_own_configuration():
    first = create_app({"datasets": registered_model("interviews")})
    second = create_app({"datasets": registered_model("imaging")})

    assert [profile["id"] for profile in served(first)[1]["profiles"]] == ["interviews"]
    assert [profile["id"] for profile in served(second, "?model=datasets")[1]["profiles"]] == ["imaging"]


def test_overrides_cover_the_deposit_pages_of_profile_models():
    app = create_app({"datasets": registered_model("interviews", application_id="data"), "vocabularies": OTHER_MODEL})

    overrides = app.config["OAREPO_UI_OVERRIDES"]
    assert {override.endpoint for override in overrides} == {"datasets_ui.deposit_create", "datasets_ui.deposit_edit"}
    assert {override.overridable_id for override in overrides} == {"Data.Form.WizardForm.container"}
    assert served(app)[0] == 200
    assert served(app, "?model=vocabularies")[0] == 404


def test_a_model_without_a_ui_gets_no_overrides():
    app = create_app({"datasets": registered_model("interviews", ui_blueprint_name=None)})
    assert app.config["OAREPO_UI_OVERRIDES"] == set()
    assert served(app)[0] == 200


def form_config(app, model_name, prefix=None):
    """Run the component as oarepo-ui does: the form config already holds the page's prefix."""
    config = SimpleNamespace(model_name=model_name)
    result = {"overridableIdPrefix": prefix or f"{model_name.capitalize()}.Form"}
    with app.app_context():
        DepositionProfilesComponent(SimpleNamespace(config=config)).form_config(form_config=result, identity=None)
    result.pop("overridableIdPrefix")
    return result


def test_the_form_config_carries_the_models_configuration():
    app = create_app({"datasets": registered_model("interviews"), "vocabularies": OTHER_MODEL})

    assert form_config(app, "datasets") == {"deposition_profiles": served(app)[1]}
    assert form_config(app, "vocabularies", prefix="Default.Form") == {}


def stop_message(app, model_name, prefix):
    with pytest.raises(ConfigurationError) as error:
        form_config(app, model_name, prefix=prefix)
    return str(error.value)


def test_a_deposit_form_with_other_ids_than_the_override_stops_with_the_fix():
    # oarepo-ui's default application_id; the preset assumed the model name.
    message = stop_message(create_app({"samples": registered_model("interviews")}), "samples", "Default.Form")
    assert "the deposit form uses the ids Default.Form.*, but oarepo-pgd added its profile controls under " \
        "Samples.Form.*" in message
    assert "Pass application_id='Default' to pgd_preset" in message


def test_the_prefix_the_page_sends_to_the_form_decides():
    # The page may send another prefix than its application_id gives; only that one reaches React.
    app = create_app({"samples": registered_model("interviews", application_id="Default")})
    assert "deposition_profiles" in form_config(app, "samples", prefix="Default.Form")
    assert "Pass application_id='Other'" in stop_message(app, "samples", "Other.Form")


def test_a_prefix_no_application_id_gives_points_to_a_custom_form():
    message = stop_message(create_app({"samples": registered_model("interviews")}), "samples", "MyLab.Deposit")
    assert "Set OAREPO_PGD_UI_OVERRIDES = False" in message


def test_a_host_with_its_own_form_needs_no_matching_ids():
    app = create_app({"samples": registered_model("interviews")}, OAREPO_PGD_UI_OVERRIDES=False)
    assert "deposition_profiles" in form_config(app, "samples", prefix="Default.Form")


def test_an_override_the_host_configured_for_the_same_component_wins():
    own = UIComponent("MyForm", "@js/datasets/forms/MyForm")
    host = UIComponentOverride("datasets_ui.deposit_create", "Datasets.Form.WizardForm.container", own)
    app = create_app({"datasets": registered_model("interviews")}, OAREPO_UI_OVERRIDES={host})

    kept = {override.endpoint: override.component for override in app.config["OAREPO_UI_OVERRIDES"]}
    assert kept["datasets_ui.deposit_create"] is own
    assert kept["datasets_ui.deposit_edit"].import_name == "ProfileTabForm"


def test_overrides_can_be_switched_off():
    app = create_app({"datasets": registered_model("interviews")}, OAREPO_PGD_UI_OVERRIDES=False)
    assert app.config["OAREPO_UI_OVERRIDES"] == set()


def test_overrides_do_not_leak_into_other_apps():
    first = create_app({"datasets": registered_model("interviews")})
    second = create_app({"datasets": registered_model("imaging")}, OAREPO_PGD_UI_OVERRIDES=False)

    assert len(first.config["OAREPO_UI_OVERRIDES"]) == 2
    assert second.config["OAREPO_UI_OVERRIDES"] == set()
    # The default set shared by all apps is never changed.
    assert oarepo_ui.config.OAREPO_UI_OVERRIDES == set()
