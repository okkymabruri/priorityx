"""Release metadata must still satisfy the locked installation contract."""
import ast
from pathlib import Path
import runpy
import shutil
import subprocess
import tomllib


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
