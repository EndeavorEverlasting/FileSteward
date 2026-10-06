"""Exact delete-set visibility, approval, permanent delete, and reclaim verify.

Dependency floor: MAIN — imports only repository-owned ``filesteward.*``
modules already on ``origin/main`` (classify, inventory.windows, manifest,
models, policy.paths) plus the deletion package itself. No UI/visualization
stack imports.
"""

from filesteward.deletion.approval import (
    DELETE_APPROVAL_FILENAME,
    DELETE_APPROVAL_SCHEMA,
    DELETE_ACTION,
    DeleteApprovalRecord,
    build_delete_approval,
    load_delete_approval,
    request_permanent_delete_set,
    validate_delete_approval,
    write_delete_approval,
)
from filesteward.deletion.execute import (
    ExecutionResult,
    execute_permanent_delete,
    scan_root_allowed_for_execute,
)
from filesteward.deletion.manifest import (
    DELETE_MANIFEST_FILENAME,
    DELETE_MANIFEST_SCHEMA,
    DeleteManifestResult,
    build_delete_manifest,
    emit_delete_manifest,
    sha256_file,
)
from filesteward.deletion.preflight import (
    PREFLIGHT_SCHEMA_VERSION,
    PreflightResult,
    run_preflight,
    write_preflight_receipt,
)
from filesteward.deletion.receipt import (
    DELETE_RECEIPT_FILENAME,
    load_delete_receipt,
    write_delete_receipt,
)
from filesteward.deletion.reclaim import (
    ReclaimState,
    ReclaimVerification,
    verify_reclaim,
)
from filesteward.deletion.surface import (
    DELETE_SET_HTML_FILENAME,
    DELETE_SET_TXT_FILENAME,
    render_delete_set_html,
    render_delete_set_text,
    write_delete_set_surface,
)

__all__ = [
    "DELETE_ACTION",
    "DELETE_APPROVAL_FILENAME",
    "DELETE_APPROVAL_SCHEMA",
    "DELETE_MANIFEST_FILENAME",
    "DELETE_MANIFEST_SCHEMA",
    "DELETE_RECEIPT_FILENAME",
    "DELETE_SET_HTML_FILENAME",
    "DELETE_SET_TXT_FILENAME",
    "DELETE_ACTION",
    "DeleteApprovalRecord",
    "DeleteManifestResult",
    "ExecutionResult",
    "PREFLIGHT_SCHEMA_VERSION",
    "PreflightResult",
    "ReclaimState",
    "ReclaimVerification",
    "build_delete_approval",
    "build_delete_manifest",
    "emit_delete_manifest",
    "execute_permanent_delete",
    "load_delete_approval",
    "load_delete_receipt",
    "render_delete_set_html",
    "render_delete_set_text",
    "request_permanent_delete_set",
    "run_preflight",
    "scan_root_allowed_for_execute",
    "sha256_file",
    "validate_delete_approval",
    "verify_reclaim",
    "write_delete_approval",
    "write_delete_receipt",
    "write_delete_set_surface",
    "write_preflight_receipt",
]
