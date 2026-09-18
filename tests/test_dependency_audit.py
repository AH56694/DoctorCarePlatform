import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "dependency_audit", Path(__file__).resolve().parents[1] / "scripts/audit-dependencies.py",
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_official_cpu_build_is_checked_against_its_public_release():
    requirements, mappings = audit.public_requirements("torch==2.14.0+cpu\nfastapi==0.141.1\n")
    assert requirements == ["torch==2.14.0", "fastapi==0.141.1"]
    assert mappings[0]["build"] == "2.14.0+cpu"


@pytest.mark.parametrize("requirement", ["torch==2.14.0+private", "internal==1.0+cpu", "torch>=2", "-r another.txt"])
def test_unreviewed_builds_and_unpinned_inputs_cannot_silently_pass(requirement):
    with pytest.raises(ValueError):
        audit.public_requirements(requirement)
