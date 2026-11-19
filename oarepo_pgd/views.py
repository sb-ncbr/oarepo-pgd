"""Publish the deposition configuration for other software.

The deposit form does not use this; it gets the configuration with its form config.
"""

from __future__ import annotations

from flask import Blueprint, Flask, Response, abort, current_app, jsonify, request

from .registry import profile_models


def create_api_blueprint(app: Flask) -> Blueprint:
    """Serve semantic types and profiles at ``/api/deposition-profiles``.

    ``?model=<name>`` selects the model. It can be omitted while exactly one
    model uses profile-guided deposition.
    """
    blueprint = Blueprint("oarepo_pgd", __name__)

    @blueprint.get("/deposition-profiles")
    def deposition_profiles() -> Response:
        models = profile_models(current_app)
        model = request.args.get("model")
        if model is None and len(models) == 1:
            model = next(iter(models))
        if model not in models:
            abort(404)
        return jsonify(models[model].configuration)

    return blueprint
