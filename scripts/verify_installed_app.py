"""Installed-wheel/CLI/spawn/offline-browser check using maintained test frames.

Run after replacing the editable project install with the built wheel. No model
fitting, private data, browser-driver package or Node runtime is involved.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import sysconfig
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class BrowserReceipt(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre" and dict(attrs).get("id") == "priorityx-ci-result":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "pre":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def browser_executable(explicit):
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise RuntimeError(f"Browser does not exist: {path}")
        return str(path)
    for name in ("google-chrome", "chromium", "chromium-browser", "msedge"):
        if value := shutil.which(name):
            return value
    candidates = [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if base := os.environ.get(variable):
            candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                           Path(base) / "Google/Chrome/Application/chrome.exe"]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Chrome/Edge is required for the offline file journey; no browser found.")


def offline_browser(browser, html, output, phase):
    # A fresh browser profile and blocked DNS exercise file: without a service.
    # The prelude counts attempted application requests and denies connections.
    prelude = """<meta data-ci-policy http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
      img-src data: blob:; font-src data:; connect-src 'none'; base-uri 'none'">
    <script>document.currentScript.remove();
      window.priorityxNetworkAttempts=[];
      window.fetch=(...args)=>{priorityxNetworkAttempts.push(String(args[0]));return Promise.reject(Error('Offline check: network denied'))};
      XMLHttpRequest.prototype.open=function(...args){priorityxNetworkAttempts.push(String(args[1]));throw Error('Offline check: network denied')};
    </script>"""
    journey = Path(__file__).with_name("verify_offline_workspace.js").read_text(encoding="utf-8")
    script = "<script>window.priorityxCheckOptions=" + json.dumps({"phase": phase}) + ";" + journey + "</script>"
    target = output / f"{phase}-check.html"
    target.write_text(html.replace("</head>", prelude + "</head>", 1).replace("</body>", script + "</body>", 1), encoding="utf-8")
    profile = output / f"browser-{phase}"
    command = [browser, "--headless=new", "--no-first-run", "--no-default-browser-check",
               "--disable-background-networking", "--disable-component-update", "--disable-sync",
               "--disable-default-apps", "--host-resolver-rules=MAP * ~NOTFOUND",
               "--user-data-dir=" + str(profile), "--window-size=1440,1000",
               "--virtual-time-budget=12000", "--dump-dom", target.as_uri()]
    run = subprocess.run(command, capture_output=True, timeout=60, encoding="utf-8", errors="replace")
    (output / f"browser-{phase}.stderr.log").write_text(run.stderr, encoding="utf-8")
    parser = BrowserReceipt()
    parser.feed(run.stdout)
    if run.returncode or not parser.parts:
        (output / f"browser-{phase}-failure.html").write_text(run.stdout, encoding="utf-8")
        raise RuntimeError(f"Browser {phase} failed ({run.returncode}); see captured DOM/stderr.")
    result = json.loads("".join(parser.parts))
    exported = result.pop("exported", None)
    (output / f"browser-{phase}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if result["status"] != "pass":
        raise RuntimeError(f"Browser {phase}: {result.get('error')}")
    # Profiles are disposable. Keep the actual exported workspace and receipts.
    shutil.rmtree(profile)
    return result, exported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser", help="Chrome or Edge executable; defaults to installed browser")
    parser.add_argument("--console-script", type=Path, help="Installed entry point for a custom --target install")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    import priorityx
    from priorityx.app import build_html
    from priorityx.results import ResultBundle
    from priorityx.views import prepare_bundle, resolve_settings

    package = Path(priorityx.__file__).resolve()
    if package.is_relative_to(ROOT / "src"):
        raise RuntimeError("Expected an installed wheel; editable source checkout was imported.")
    sys.path.insert(0, str(ROOT / "tests"))
    from test_views import bundle

    source = ResultBundle(bundle().datasets + bundle("monthly").datasets)
    source_before = source.to_dict()
    prepared = prepare_bundle(source)
    path_root = output / "saved results café"
    path_root.mkdir()
    source.save(path_root / "bundle.json")
    executable = (args.console_script.resolve() if args.console_script else
                  Path(sysconfig.get_path("scripts")) / ("priorityx.exe" if os.name == "nt" else "priorityx"))
    if not executable.is_file():
        raise RuntimeError(f"Installed console entry point missing: {executable}")
    stderr = (output / "app.stderr.log").open("w", encoding="utf-8")
    started = time.perf_counter()
    process = subprocess.Popen([str(executable), "app", "--bundle", str(path_root / "bundle.json"),
                                "--port", "0", "--no-browser"], cwd=path_root,
                               stdout=subprocess.PIPE, stderr=stderr, text=True, encoding="utf-8")
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    checks = []
    try:
        try:
            line = lines.get(timeout=30).strip()
        except queue.Empty as exc:
            if sys.platform == "darwin" and shutil.which("sample"):
                subprocess.run(["sample", str(process.pid), "1", "-file", str(output / "startup-sample.log")],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
            raise RuntimeError(f"Console startup exceeded 30 seconds (exit={process.poll()}); see app stderr/startup sample.") from exc
        if not line.startswith("PriorityX workspace: http://127.0.0.1:"):
            raise RuntimeError(f"Unexpected startup response: {line!r}")
        url = line.split(": ", 1)[1]
        with urllib.request.urlopen(url + "/api/bootstrap", timeout=20) as response:
            assert json.load(response)["bundle"] == source_before
        startup = time.perf_counter() - started
        with urllib.request.urlopen(url, timeout=20) as response:
            assert response.status == 200 and b'id="workspace-data"' in response.read()
        for cadence in ("quarterly", "monthly"):
            settings = resolve_settings(None, prepared).to_dict()
            settings["cadence"] = cadence
            for family in ("matrix", "timeline", "paths"):
                for image_format in ("png", "svg"):
                    request = urllib.request.Request(url + "/api/static", data=json.dumps({
                        "bundle": source_before, "settings": settings, "family": family,
                        "format": image_format}).encode(), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(request, timeout=40) as response:
                        image = response.read()
                        report = json.loads(response.headers["X-PriorityX-Layout"])
                    assert report["bundle_id"] == prepared["bundle_id"] and report["unresolved"] == 0
                    assert image.startswith(b"\x89PNG") if image_format == "png" else b"<svg" in image
                    filename = f"{cadence}-{family}.{image_format}"
                    (output / filename).write_bytes(image)
                    checks.append({"cadence": cadence, "family": family, "format": image_format,
                                   "sha256": hashlib.sha256(image).hexdigest(), "report": report})
        with urllib.request.urlopen(url + "/api/bootstrap", timeout=20) as response:
            assert json.load(response)["bundle"] == source_before
        assert source.to_dict() == source_before
        html = build_html(source)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        stderr.close()
    # Reopen only after the Python service has stopped.
    browser = browser_executable(args.browser)
    first, exported = offline_browser(browser, html, output, "first")
    assert exported and 'data-service="false"' in exported
    (output / "exported-workspace.html").write_text(exported, encoding="utf-8")
    reopened, _ = offline_browser(browser, exported, output, "reopen")
    receipt = {"status": "pass", "platform": sys.platform, "python": sys.version,
               "package": str(package), "console": str(executable), "startup_seconds": startup,
               "saved_data_unchanged": True, "exports": checks, "browser": [first, reopened],
               "qualification": "Installed package, CLI, spawned exports and headless Chromium file journey; physical input, fonts and Safari remain separate."}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "platform": sys.platform, "exports": len(checks),
                      "offline_checks": len(first["checks"]) + len(reopened["checks"])}))


if __name__ == "__main__":
    main()
