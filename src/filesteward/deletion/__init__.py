"""Exact delete-set visibility (P04 D1).

Builds an UNAPPROVED local/private delete-manifest from RECLAIM_PROVEN
cleanup-plan rows and an operator-readable decision surface. This package
never mutates scanned targets, never claims permanent deletion, and never
self-approves.
"""

from filesteward.deletion.manifest import (
    DELETE_MANIFEST_FILENAME,
    DELETE_MANIFEST_SCHEMA,
    DeleteManifestResult,
    build_delete_manifest,
    emit_delete_manifest,
    sha256_file,
)
from filesteward.deletion.surface import (
    DELETE_SET_HTML_FILENAME,
    DELETE_SET_TXT_FILENAME,
    render_delete_set_html,
    render_delete_set_text,
    write_delete_set_surface,
)

__all__ = [
    "DELETE_MANIFEST_FILENAME",
    "DELETE_MANIFEST_SCHEMA",
    "DELETE_SET_HTML_FILENAME",
    "DELETE_SET_TXT_FILENAME",
    "DeleteManifestResult",
    "build_delete_manifest",
    "emit_delete_manifest",
    "render_delete_set_html",
    "render_delete_set_text",
    "sha256_file",
    "write_delete_set_surface",
]
