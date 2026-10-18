"""Release metadata must still satisfy the locked installation contract."""
import ast
from pathlib import Path
import runpy
import shutil
import subprocess
import tomllib

import pytest


def test_version_update_keeps_package_metadata_and_lock_in_sync(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    # Keep this metadata test independent of registry access and model inputs.
    (tmp_path / "pyproject.toml").write_text('[project]\n' + '\n'.join(
        f'{name} = "{project[name]}"' for name in ("name", "version", "requires-python")) + '\n')
    target = tmp_path / "src/priorityx/__init__.py"
    target.parent.mkdir(parents=True)
    shutil.copyfile(root / "src/priorityx/__init__.py", target)
    update = runpy.run_path(str(root / "scripts/version.py"))["update_version_file"]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UV_OFFLINE", "true")
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    subprocess.run(["uv", "lock", "--offline"], cwd=tmp_path, check=True)
    update("0.7.0")
    assert tomllib.loads((tmp_path / "pyproject.toml").read_text())["project"]["version"] == "0.7.0"
    assignments = ast.parse((tmp_path / "src/priorityx/__init__.py").read_text()).body
    assert next(ast.literal_eval(node.value) for node in assignments
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "__version__"
                        for target in node.targets)) == "0.7.0"
    refreshed = tomllib.loads((tmp_path / "uv.lock").read_text())
    assert next(p["version"] for p in refreshed["package"] if p["name"] == "priorityx") == "0.7.0"
    subprocess.run(["uv", "lock", "--check", "--offline"], cwd=tmp_path, check=True)


@pytest.mark.parametrize("answer", ["y", "n"])
def test_release_tag_uses_explicit_annotation(monkeypatch, answer):
    """Configured signing stays enabled and pushes require the existing prompt."""
    root = Path(__file__).resolve().parents[1]
    module = runpy.run_path(str(root / "scripts/version.py"))
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="")

    monkeypatch.setattr(module["subprocess"], "run", fake_run)
    monkeypatch.setattr("builtins.input", lambda _: answer)
    module["git_commit_and_tag"]("0.7.1")
    assert ["git", "tag", "-m", "Release v0.7.1", "v0.7.1"] in calls
    pushes = [call for call in calls if call[:2] == ["git", "push"]]
    assert pushes == ([["git", "push"], ["git", "push", "origin", "v0.7.1"]] if answer == "y" else [])


@pytest.mark.parametrize("existing", [True, False])
def test_release_existing_tag_or_failure_never_pushes(monkeypatch, existing):
    root = Path(__file__).resolve().parents[1]
    module = runpy.run_path(str(root / "scripts/version.py"))
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:3] == ["git", "tag", "-m"]:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, stdout="v0.7.1" if existing else "")

    monkeypatch.setattr(module["subprocess"], "run", fake_run)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("push prompt must not be reached"))
    if existing:
        module["git_commit_and_tag"]("0.7.1")
        assert calls == [["git", "tag", "-l", "v0.7.1"]]
    else:
        with pytest.raises(subprocess.CalledProcessError):
            module["git_commit_and_tag"]("0.7.1")
    assert all(call[:2] != ["git", "push"] for call in calls)
