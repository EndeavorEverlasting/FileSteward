"""Donor regression cases and FileSteward signature/review authority."""
import base64
import hashlib
import json
import os
import sqlite3

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from filesteward.antivirus import matcher, profile, signatures
from filesteward.cli import main

CONTROL = b"disposable synthetic exact match"


def write_bundle(path, key, sequence, digests=None):
    payload = json.dumps({
        "schema_version": signatures.PAYLOAD,
        "sequence": sequence,
        "sha256": digests if digests is not None else [hashlib.sha256(CONTROL).hexdigest()],
    }).encode()
    path.write_text(json.dumps({
        "schema_version": signatures.ENVELOPE,
        "payload": base64.b64encode(payload).decode(),
        "signature": base64.b64encode(key.sign(payload)).decode(),
    }))
    return path


@pytest.fixture
def detector(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(profile, "runtime_root", lambda: tmp_path / "var")
    key = Ed25519PrivateKey.generate()
    root = tmp_path / "approved"
    root.mkdir()
    bundle = write_bundle(tmp_path / "bundle.json", key, 1)
    args = ["antivirus", "configure", "--root", str(root),
            "--public-key", key.public_key().public_bytes_raw().hex(), "--bundle", str(bundle)]
    assert main(args) == 0
    profile_id = json.loads(capsys.readouterr().out)["profile"]
    return root, key, bundle, profile_id


def invoke(action, profile_id, *argv):
    return main(["antivirus", action, "--profile", profile_id, *argv])


def test_exact_match_is_private_idempotent_review_only(detector, capsys):
    root, _, _, ref = detector
    control = root / "negative.txt"
    control.write_bytes(CONTROL + b".")
    assert invoke("check", ref) == invoke("run", ref) == 0
    assert capsys.readouterr() == ("", "")
    assert profile.review(ref) == []
    candidate = root / "positive.txt"
    candidate.write_bytes(CONTROL)
    for _ in range(2):
        assert invoke("run", ref) == 0
        assert capsys.readouterr() == ("", "")
    [finding] = profile.review(ref)
    assert finding["path"] == str(candidate)
    assert finding["disposition"] == "HUMAN_REVIEW"
    assert finding["authorization_state"] == "UNAPPROVED"
    assert finding["evidence"] == "EXACT_SHA256_MATCH"
    assert finding["bundle_sequence"] == 1
    assert candidate.read_bytes() == CONTROL
    assert control.read_bytes() == CONTROL + b"."


def test_verified_update_rejects_replay_and_wrong_signer(detector, capsys):
    root, key, bundle, ref = detector
    (root / "positive.txt").write_bytes(CONTROL)
    write_bundle(bundle, key, 2, ["f" * 64])
    assert invoke("signature-update", ref, "--bundle", str(bundle)) == 0
    assert json.loads(capsys.readouterr().out) == {"sequence": 2}
    assert invoke("signature-update", ref, "--bundle", str(bundle)) == 12
    write_bundle(bundle, key, 1)
    assert invoke("signature-update", ref, "--bundle", str(bundle)) == 12
    write_bundle(bundle, Ed25519PrivateKey.generate(), 3)
    assert invoke("signature-update", ref, "--bundle", str(bundle)) == 12
    capsys.readouterr()
    assert invoke("run", ref) == 0
    assert profile.review(ref) == []


def test_tampered_installed_policy_fails_before_scope_read(detector, monkeypatch, capsys):
    _, _, _, ref = detector
    database = profile.state_root() / ref / "detector.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("UPDATE policy SET sequence = sequence + 1")
    monkeypatch.setattr(profile, "scope_identity", lambda _: pytest.fail("Scope reached despite invalid policy"))
    assert invoke("run", ref) == 12
    assert capsys.readouterr() == ("", "")


def test_incomplete_keeps_prior_match_and_never_reads_hard_link(detector, capsys, tmp_path):
    root, _, _, ref = detector
    (root / "positive.txt").write_bytes(CONTROL)
    outside = tmp_path / "hardlink-target.txt"
    outside.write_bytes(CONTROL)
    os.link(outside, root / "hardlink.txt")
    assert invoke("run", ref) == 10
    assert capsys.readouterr() == ("", "")
    assert [item["path"] for item in profile.review(ref)] == [str(root / "positive.txt")]


def test_scope_identity_change_invalidates_opt_in(detector, capsys):
    root, _, _, ref = detector
    root.rename(root.with_name("previous"))
    root.mkdir()
    (root / "new-scope.txt").write_bytes(CONTROL)
    assert invoke("run", ref) == 12
    assert capsys.readouterr() == ("", "")
    assert profile.review(ref) == []


@pytest.mark.parametrize("replacement_file", [False, True], ids=["missing", "file"])
def test_missing_approved_scope_rejects_policy_and_retains_review(
    detector, monkeypatch, capsys, replacement_file
):
    root, _, _, ref = detector
    (root / "match.txt").write_bytes(CONTROL)
    assert invoke("run", ref) == 0
    historical = profile.review(ref)
    assert len(historical) == 1

    root.rename(root.with_name("moved"))
    if replacement_file:
        root.write_bytes(CONTROL)
    monkeypatch.setattr(profile, "scan_directory", lambda *_: pytest.fail("Invalid scope reached scanner"))

    assert invoke("check", ref) == 12
    assert invoke("run", ref) == 12
    assert capsys.readouterr() == ("", "")
    assert profile.review(ref) == historical


def test_scope_read_failure_reports_unavailable_state(detector, monkeypatch, capsys):
    _, _, _, ref = detector

    def inaccessible(_):
        raise PermissionError("Synthetic temporary access failure")

    monkeypatch.setattr(profile, "scope_identity", inaccessible)
    assert invoke("check", ref) == 1
    assert invoke("run", ref) == 1
    assert capsys.readouterr() == ("", "")


def test_nested_and_linked_files_remain_out_of_scope(detector, tmp_path):
    root, _, _, ref = detector
    nested = root / "directory"
    nested.mkdir()
    (nested / "positive.txt").write_bytes(CONTROL)
    external = tmp_path / "external.txt"
    external.write_bytes(CONTROL)
    try:
        (root / "symlink.txt").symlink_to(external)
    except OSError:
        pytest.skip("Creating symlinks requires permission")
    assert invoke("run", ref) == 0
    assert profile.review(ref) == []


def test_byte_budget_coverage_is_incomplete(detector, monkeypatch):
    root, _, _, ref = detector
    (root / "unscanned.txt").write_bytes(CONTROL)
    monkeypatch.setattr(matcher, "MAX_SCAN_BYTES", 1)
    assert invoke("run", ref) == 10
    assert profile.review(ref) == []


@pytest.mark.parametrize("digests", [[], ["x" * 64], ["a" * 64] * 2])
def test_signed_bundle_still_requires_valid_rule_shape(tmp_path, digests):
    key = Ed25519PrivateKey.generate()
    bundle = write_bundle(tmp_path / "bundle.json", key, 1, digests)
    with pytest.raises(ValueError):
        signatures.verify_bundle(bundle.read_bytes(), key.public_key().public_bytes_raw())


@pytest.mark.skipif(os.name == "nt", reason="POSIX alternate path anchor")
def test_double_slash_scope_is_rejected(detector):
    root, _, _, _ = detector
    with pytest.raises(ValueError):
        matcher.scope_identity(type(root)("/" + str(root)))


@pytest.mark.skipif(os.name == "nt", reason="Linux mount IDs")
def test_same_device_foreign_mount_is_incomplete(detector, monkeypatch):
    root, _, _, ref = detector
    source = root / "mounted.txt"
    source.write_bytes(CONTROL)
    actual_mount_id = matcher.linux_mount_id

    def file_on_different_mount(fd):
        if os.fstat(fd).st_ino == source.stat().st_ino:
            return "foreign-mount"
        return actual_mount_id(fd)

    monkeypatch.setattr(matcher, "linux_mount_id", file_on_different_mount)
    assert invoke("run", ref) == 10
    assert profile.review(ref) == []


def test_scope_replaced_after_hash_cannot_name_a_new_file(detector, monkeypatch):
    root, _, _, ref = detector
    source = root / "match.txt"
    source.write_bytes(CONTROL)
    original = matcher.digest_file

    def replace_after_digest(*args):
        digest = original(*args)
        root.rename(root.with_name("previous"))
        root.mkdir()
        source.write_bytes(b"unrelated")
        return digest

    monkeypatch.setattr(matcher, "digest_file", replace_after_digest)
    assert invoke("run", ref) == 10
    assert profile.review(ref) == []


@pytest.mark.parametrize("app_id", ["filesteward", "another-app"])
def test_configure_initializes_admitted_installed_runtime(tmp_path, monkeypatch, capsys, app_id):
    from filesteward import runtime_profile
    from filesteward.policy import paths

    def no_checkout():
        raise RuntimeError("an installed wheel has no development checkout")

    known = tmp_path / "LocalAppData"
    application = known / "FileSteward"
    application.mkdir(parents=True)
    marker = application / runtime_profile.APPLICATION_MARKER
    marker.write_text(json.dumps({
        "schema_version": "filesteward.application-root/v1",
        "app_id": app_id,
        "runtime_profile": runtime_profile.PROFILE_ID,
    }))
    monkeypatch.setattr(paths, "repository_root", no_checkout)
    monkeypatch.setattr(runtime_profile, "windows_local_app_data", lambda: known)
    monkeypatch.setattr(runtime_profile, "_wheel_identity", lambda _: None)
    root = tmp_path / "approved"
    root.mkdir()
    key = Ed25519PrivateKey.generate()
    bundle = write_bundle(tmp_path / "signed.json", key, 1)
    args = ["antivirus", "configure", "--root", str(root),
            "--public-key", key.public_key().public_bytes_raw().hex(), "--bundle", str(bundle)]

    assert not (application / "runtime").exists()
    assert invoke("check", "f" * 64) == 1
    assert capsys.readouterr() == ("", "")
    assert not (application / "runtime").exists()
    if app_id != "filesteward":
        assert main(args) == 1
        assert not (application / "runtime").exists()
        return
    assert main(args) == 0
    profile_id = json.loads(capsys.readouterr().out)["profile"]
    assert invoke("run", profile_id) == 0
    assert profile.review(profile_id) == []
    runtime = application / "runtime" / "var"
    assert (runtime / "antivirus" / profile_id / "detector.sqlite").is_file()
    receipt = json.loads((runtime / "runtime-readiness.json").read_text())
    assert receipt["startup_authority"] == "PRIVATE_RUNTIME_ONLY"
    assert not (receipt["scan_started"] or receipt["deletion_started"] or receipt["schedule_registered"])


def test_published_detector_contract_is_public_and_profile_independent(detector, monkeypatch, capsys):
    from filesteward.models import AuthorizationState, authorization_allows_mutation

    root, _, _, ref = detector
    sample = root / "match.txt"
    sample.write_bytes(CONTROL)

    assert invoke("run", ref) == 0
    (finding,) = profile.review(ref)
    monkeypatch.setattr(profile, "profile_state", lambda *_: pytest.fail("contract accessed private state"))

    assert main(["antivirus", "contract"]) == 0
    output = capsys.readouterr().out
    assert str(root) not in output and ref not in output and finding["sha256"] not in output
    metadata = json.loads(output)
    assert metadata["schema_version"] == "filesteward.antivirus-detection/v1"
    for key in ("evidence", "disposition", "authorization_state"):
        assert finding[key] == metadata["review_item"][key]
    assert not authorization_allows_mutation(AuthorizationState(finding["authorization_state"]))
    transport = metadata["scheduler"]
    assert transport["transport"] == "EXIT_STATUS_ONLY"
    assert transport["completion_is_match_independent"] is True
    assert transport["forwards_file_evidence"] is False
    assert transport["grants_action_authority"] is False
