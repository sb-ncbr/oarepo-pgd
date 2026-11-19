"""The configuration served and the overrides registered for an app's models.

Both are read from the app's own ``OAREPO_MODELS``.
"""

from types import SimpleNamespace

import oarepo_ui.config
from flask import Flask

from oarepo_pgd.components import DepositionProfilesComponent
from oarepo_pgd.ext import OARepoPGD, finalize_app
from oarepo_pgd.registry import NAMESPACE_KEY
from oarepo_pgd.views import create_api_blueprint

OTHER_MODEL = SimpleNamespace(namespace=None, ui_blueprint_name=None)


def registered_model(profile_id, application_id=None, ui_blueprint_name="datasets_ui"):
    """What OARepo keeps in OAREPO_MODELS: a runtime model with its built namespace."""
    configuration = {"semantic_types": [], "profiles": [{"id": profile_id}]}
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

    assert served(first)[1]["profiles"] == [{"id": "interviews"}]
    assert served(second, "?model=datasets")[1]["profiles"] == [{"id": "imaging"}]


def test_overrides_cover_the_deposit_pages_of_profile_models():
    app = create_app({"datasets": registered_model("interviews", application_id="data"), "vocabularies": OTHER_MODEL})

    overrides = app.config["OAREPO_UI_OVERRIDES"]
    assert {override.endpoint for override in overrides} == {"datasets_ui.deposit_create", "datasets_ui.deposit_edit"}
    assert {override.overridable_id for override in overrides} == {
        "Data.Form.WizardForm.container",
        "Data.Form.TabForm.PublishButton",
    }
    assert served(app)[0] == 200
    assert served(app, "?model=vocabularies")[0] == 404


def test_a_model_without_a_ui_gets_no_overrides():
    app = create_app({"datasets": registered_model("interviews", ui_blueprint_name=None)})
    assert app.config["OAREPO_UI_OVERRIDES"] == set()
    assert served(app)[0] == 200


def form_config(app, model_name):
    resource = SimpleNamespace(config=SimpleNamespace(model_name=model_name))
    result = {}
    with app.app_context():
        DepositionProfilesComponent(resource).form_config(form_config=result, identity=None)
    return result


def test_the_form_config_carries_the_models_configuration():
    app = create_app({"datasets": registered_model("interviews"), "vocabularies": OTHER_MODEL})

    assert form_config(app, "datasets") == {"deposition_profiles": served(app)[1]}
    assert form_config(app, "vocabularies") == {}


def test_overrides_can_be_switched_off():
    app = create_app({"datasets": registered_model("interviews")}, OAREPO_PGD_UI_OVERRIDES=False)
    assert app.config["OAREPO_UI_OVERRIDES"] == set()


def test_overrides_do_not_leak_into_other_apps():
    first = create_app({"datasets": registered_model("interviews")})
    second = create_app({"datasets": registered_model("imaging")}, OAREPO_PGD_UI_OVERRIDES=False)

    assert len(first.config["OAREPO_UI_OVERRIDES"]) == 4
    assert second.config["OAREPO_UI_OVERRIDES"] == set()
    # The default set shared by all apps is never changed.
    assert oarepo_ui.config.OAREPO_UI_OVERRIDES == set()
