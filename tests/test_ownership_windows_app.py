"""Synthetic tests for Windows application attribution (J2)."""

from __future__ import annotations

from pathlib import PureWindowsPath

from filesteward.ownership.windows_app import (
    AppLifecycleClass,
    UninstallRegistration,
    attribute_path,
    classify_uninstall_registration,
    collect_app_ownership,
)


def _exists_map(present: set[str]):
    keys = {tuple(part.lower() for part in PureWindowsPath(p).parts) for p in present}

    def path_exists(path: str) -> bool:
        candidate = tuple(part.lower() for part in PureWindowsPath(path).parts)
        return candidate in keys

    return path_exists


def test_broken_required_when_registered_uninstaller_missing():
    """Wispr-shaped: Windows still registers the app; updater/uninstaller gone."""

    install = r"C:\Users\demo\AppData\Local\WisprFlow"
    missing_updater = r"C:\Users\demo\AppData\Local\WisprFlow\Update.exe"
    entry = UninstallRegistration(
        app_id="wispr-flow",
        display_name="Wispr Flow",
        publisher="Wispr",
        install_location=install,
        uninstall_string=f'"{missing_updater}" --uninstall',
        hive="HKCU",
    )
    record = classify_uninstall_registration(
        entry,
        path_exists=_exists_map({install}),
    )
    assert record.lifecycle_class is AppLifecycleClass.BROKEN_REQUIRED
    assert record.user_facing_badge == "Broken app dependency"
    assert record.safety_floor == "PROTECTED"
    assert "APP_INSTALLATION_BROKEN" in record.consequence_classes
    assert "APP_SERVICEABILITY_DEPENDENCY" in record.consequence_classes
    assert record.semantic_actions == (
        "REPAIR_APPLICATION",
        "UNINSTALL_APPLICATION",
    )
    assert any(e.edge_type == "SERVICEABILITY_REQUIRES" for e in record.edges)
    assert "CLEAN_CACHE" not in record.semantic_actions

    attribution = attribute_path(install, [record])
    assert attribution.governing_lifecycle is AppLifecycleClass.BROKEN_REQUIRED
    assert attribution.user_facing_badge == "Broken app dependency"
    assert "Wispr Flow" in attribution.required_by


def test_active_required_when_install_and_serviceability_present():
    install = r"C:\Program Files\DemoApp"
    uninstaller = r"C:\Program Files\DemoApp\uninstall.exe"
    entry = UninstallRegistration(
        app_id="demo-app",
        display_name="Demo App",
        install_location=install,
        uninstall_string=f'"{uninstaller}"',
    )
    record = classify_uninstall_registration(
        entry,
        path_exists=_exists_map({install, uninstaller}),
        runtime_paths=[rf"{install}\bin\demo.exe"],
    )
    assert record.lifecycle_class is AppLifecycleClass.ACTIVE_REQUIRED
    assert record.user_facing_badge == "Required by app"
    assert record.safety_floor == "PROTECTED"
    assert "APP_RUNTIME_DEPENDENCY" in record.consequence_classes
    assert any(e.edge_type == "RUNTIME_REQUIRES" for e in record.edges)


def test_cache_regenerable_only_with_adapter_proof():
    cache = r"C:\Users\demo\AppData\Local\DemoApp\Cache"
    entry = UninstallRegistration(
        app_id="demo-cache",
        display_name="Demo App Cache",
        regenerable_cache_roots=(cache,),
    )
    record = classify_uninstall_registration(
        entry,
        path_exists=_exists_map({cache}),
    )
    assert record.lifecycle_class is AppLifecycleClass.CACHE_REGENERABLE
    assert record.user_facing_badge == "Regenerable cache"
    assert record.semantic_actions == ("CLEAN_CACHE",)
    assert "APP_CACHE_REGENERABLE" in record.consequence_classes


def test_orphan_candidate_fails_closed_after_adapter_exhaustion():
    entry = UninstallRegistration(app_id="empty", display_name="")
    record = classify_uninstall_registration(
        entry,
        path_exists=_exists_map(set()),
    )
    assert record.lifecycle_class is AppLifecycleClass.ORPHAN_CANDIDATE
    assert record.safety_floor == "HUMAN_REVIEW_AFTER_ADAPTER_EXHAUSTION"
    assert "ORPHAN_CANDIDATE" in record.consequence_classes
    assert record.semantic_actions == ()

    attribution = attribute_path(
        r"C:\Users\demo\AppData\Local\MysteryStuff",
        [],
        adapters_exhausted=True,
    )
    assert attribution.governing_lifecycle is AppLifecycleClass.ORPHAN_CANDIDATE
    assert attribution.user_facing_badge == "Unknown ownership"
    assert attribution.safety_floor == "HUMAN_REVIEW_AFTER_ADAPTER_EXHAUSTION"
    assert "disposability" in attribution.reasons[0]


def test_age_or_path_location_never_inferred():
    """Classifier ignores age/location heuristics; only explicit edges count."""

    entry = UninstallRegistration(
        app_id="old-looking",
        display_name="Old Looking App",
        install_location=r"C:\Users\demo\AppData\Local\OldLooking",
        uninstall_string=r'"C:\Users\demo\AppData\Local\OldLooking\Update.exe"',
    )
    # Both install and updater exist => ACTIVE, regardless of "AppData" or age.
    record = classify_uninstall_registration(
        entry,
        path_exists=_exists_map(
            {
                r"C:\Users\demo\AppData\Local\OldLooking",
                r"C:\Users\demo\AppData\Local\OldLooking\Update.exe",
            }
        ),
    )
    assert record.lifecycle_class is AppLifecycleClass.ACTIVE_REQUIRED
    assert record.lifecycle_class is not AppLifecycleClass.ORPHAN_CANDIDATE


def test_most_protective_edge_wins_across_records():
    install = r"C:\Shared\Tool"
    active = classify_uninstall_registration(
        UninstallRegistration(
            app_id="tool-a",
            display_name="Tool A",
            install_location=install,
            uninstall_string=rf'"{install}\uninstall.exe"',
        ),
        path_exists=_exists_map({install, rf"{install}\uninstall.exe"}),
    )
    broken = classify_uninstall_registration(
        UninstallRegistration(
            app_id="tool-b",
            display_name="Tool B",
            install_location=install,
            uninstall_string=rf'"{install}\missing-updater.exe"',
        ),
        path_exists=_exists_map({install}),
    )
    attribution = attribute_path(install, [active, broken])
    assert attribution.governing_lifecycle is AppLifecycleClass.BROKEN_REQUIRED
    assert set(attribution.required_by) == {"Tool A", "Tool B"}


def test_collect_app_ownership_batch():
    records = collect_app_ownership(
        [
            UninstallRegistration(
                app_id="a",
                display_name="A",
                install_location=r"C:\A",
                uninstall_string=r'"C:\A\u.exe"',
            ),
            UninstallRegistration(
                app_id="b",
                display_name="B",
                install_location=r"C:\B",
                uninstall_string=r'"C:\B\missing.exe"',
            ),
        ],
        path_exists=_exists_map({r"C:\A", r"C:\A\u.exe", r"C:\B"}),
    )
    assert len(records) == 2
    assert records[0].lifecycle_class is AppLifecycleClass.ACTIVE_REQUIRED
    assert records[1].lifecycle_class is AppLifecycleClass.BROKEN_REQUIRED


def test_forbidden_product_inventory_probe_absent():
    """Guard: legacy product-inventory probe identifier must not appear."""

    import filesteward.ownership.windows_app as mod
    import inspect

    source = inspect.getsource(mod)
    forbidden = "Win32_" + "Product"
    assert forbidden not in source
