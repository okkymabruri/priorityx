# Installation

PriorityX requires **Python 3.12 or later**. Automated checks cover Python
3.12, 3.13 and 3.14 on macOS, Linux and Windows. AutoViz runs in your browser;
Node.js and a separate chart-library installation are not required.

## macOS and Linux

Create an environment and install the package:

```sh
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install priorityx
```

Use a Python 3.12+ executable if your `python3` points to an older version.

## Windows PowerShell

Create an environment with Python 3.12 and use it directly:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install priorityx
.\.venv\Scripts\python.exe -m priorityx app
```

Replace `-3.12` with your installed supported version if needed. Activation is
optional; these commands do not require a PowerShell execution-policy change.

## Launch AutoViz

In your activated environment:

```sh
python -m priorityx app
```

The workspace opens in your browser. Keep the terminal running and press Ctrl+C
to stop it. Load a bundle immediately with
`python -m priorityx app --bundle results.json`.

Start with the [saved IT incidents example](autoviz-example.md), or follow the
[workspace guide](app.md) to import your results. For Python analysis, continue
with the [quickstart](quickstart.md).

## Upgrade

Use the same environment in which PriorityX is installed:

```sh
python -m pip install --upgrade priorityx
```

For an unactivated Windows environment, replace `python` with
`.\.venv\Scripts\python.exe`.

## Develop from source

With [uv](https://docs.astral.sh/uv/) installed:

```sh
git clone https://github.com/okkymabruri/priorityx.git
cd priorityx
uv sync --locked
uv run --no-sync python -m priorityx app --bundle examples/autoviz/incidents-quarterly.json
```

The repository pins Python 3.12 as its default and supplies a dependency lockfile.
