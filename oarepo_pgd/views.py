"""Blueprints: the deposition configuration and draft checks for other software, and the plugin's templates.

The deposit form does not use the API; it gets the configuration with its form
config and checks the draft itself, with the same rules.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Flask, Response, current_app, g, jsonify, request, url_for
from flask_principal import PermissionDenied
from invenio_pidstore.errors import PIDDeletedError, PIDDoesNotExistError, PIDRedirectedError, ResolverError
from sqlalchemy.orm.exc import NoResultFound

from .registry import profile_models
from .rules import Check, check
from .schema import completed_file_keys


def error(status: int, message: str) -> tuple[Response, int]:
    """A JSON error in the form the repository's REST API uses."""
    return jsonify({"status": status, "message": message}), status


def selected_model(models: dict[str, Any]) -> str | None:
    """The model named by ``?model=``, or the only model when it is omitted; ``None`` when there is none."""
    model = request.args.get("model")
    if model is None and len(models) == 1:
        model = next(iter(models))
    return model if model in models else None


def create_api_blueprint(app: Flask) -> Blueprint:
    """Serve the configuration at ``/api/deposition-profiles`` and draft checks at ``/api/deposition-profiles/check``.

    ``?model=<name>`` selects the model. It can be omitted while exactly one
    model uses profile-guided deposition.
    """
    blueprint = Blueprint("oarepo_pgd", __name__)

    @blueprint.get("/deposition-profiles")
    def deposition_profiles() -> Response | tuple[Response, int]:
        models = profile_models(current_app)
        model = selected_model(models)
        if model is None:
            return error(404, "No model with deposition profiles of that name.")
        return jsonify(models[model].configuration.to_dict())

    @blueprint.get("/deposition-profiles/check")
    def check_draft() -> Response | tuple[Response, int]:
        """Check a saved draft as publication would, with the counts and requirement states.

        ``?draft=<id>`` names the draft. The result names the files and says
        what they are, so the caller needs every permission under which the
        draft's API shows the same: reading the draft, listing its files, and
        reading the file annotations, which the record schema checks as
        ``read_files``. The check covers the draft as last saved and its
        completed uploads, like the record-schema check on publication;
        messages are in the request's language. A draft without files gets no
        check, as on publication. A redirected id answers with a redirect to
        the check of its destination.
        """
        models = profile_models(current_app)
        model = selected_model(models)
        if model is None:
            return error(404, "No model with deposition profiles of that name.")
        draft_id = request.args.get("draft")
        if not draft_id:
            return error(400, "Name the draft with ?draft=<id>.")
        oarepo_model = current_app.config["OAREPO_MODELS"][model]
        service = oarepo_model.service
        try:
            draft = service.read_draft(g.identity, draft_id)._record  # noqa: SLF001
            files_enabled = bool(draft.files.enabled)
            if files_enabled:
                # The same permission as the draft's own file listing.
                oarepo_model.draft_file_service.list_files(g.identity, draft_id)
                # The permission under which the record schema shows the annotations.
                if not service.check_permission(g.identity, "read_files", record=draft):
                    return error(403, "Permission denied.")
        except PermissionDenied:
            return error(403, "Permission denied.")
        except PIDRedirectedError as redirected:
            if redirected.destination_pid.pid_type != redirected.pid.pid_type:
                return error(404, "The persistent identifier does not exist.")
            location = url_for(".check_draft", model=model, draft=redirected.destination_pid.pid_value)
            response = jsonify({"status": 301, "message": "Moved Permanently.", "location": location})
            response.status_code = 301
            response.headers["Location"] = location
            return response
        except PIDDeletedError:
            return error(410, "The record has been deleted.")
        except (PIDDoesNotExistError, ResolverError, NoResultFound):
            return error(404, "The persistent identifier does not exist.")

        file_keys = completed_file_keys(draft) if files_enabled else []
        result = (
            check(draft.get("metadata") or {}, file_keys, models[model].configuration) if files_enabled else Check()
        )
        return jsonify({
            "model": model,
            "draft": draft_id,
            "files_enabled": files_enabled,
            "file_keys": sorted(file_keys),
            **result.to_dict(),
        })

    return blueprint


def create_ui_blueprint(app: Flask) -> Blueprint:
    """Make the plugin's templates available to the UI app, such as the record page's file meanings."""
    return Blueprint("oarepo_pgd_ui", __name__, template_folder="templates")
