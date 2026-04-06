# datasette-ports

[![PyPI](https://img.shields.io/pypi/v/datasette-ports.svg)](https://pypi.org/project/datasette-ports/)
[![Changelog](https://img.shields.io/github/v/release/datasette/datasette-ports?include_prereleases&label=changelog)](https://github.com/datasette/datasette-ports/releases)
[![Tests](https://github.com/datasette/datasette-ports/actions/workflows/test.yml/badge.svg)](https://github.com/datasette/datasette-ports/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/datasette/datasette-ports/blob/main/LICENSE)

Find all currently running Datasette instances on your machine and list their ports, databases, versions and plugins.

## Installation

Install this plugin in the same environment as Datasette.
```bash
datasette install datasette-ports
```

Or run it directly using `uvx`:
```bash
uvx datasette-ports
```

## Usage

If installed as a Datasette plugin:

```bash
datasette ports
```

Or as a standalone command:

```bash
datasette-ports
```
This uses `lsof` to find all Python processes listening on TCP ports, then probes each one to check if it is a Datasette instance. For each instance found it displays the URL, Datasette version, attached databases and installed plugins.

Example output:
```
http://127.0.0.1:8007/ - v1.0a26
  Databases: simonwillisonblog
  Plugins: datasette-llm, datasette-secrets
http://127.0.0.1:8001/ - v1.0a26
  Databases: creatures
  Plugins: datasette-extract, datasette-llm, datasette-secrets
http://127.0.0.1:8900/ - v0.65.2
  Databases: logs
http://0.0.0.0:8014/ - v1.0a26
  Databases: content, trees, _internal
  Plugins: datasette-llm, datasette-visible-internal-db
```

### JSON output

Use `--json` to get machine-readable output:

```bash
datasette ports --json
# or
datasette-ports --json
```
```json
[
  {
    "url": "http://127.0.0.1:8007/",
    "host": "127.0.0.1",
    "port": 8007,
    "version": "1.0a26",
    "databases": [
      "simonwillisonblog"
    ],
    "plugins": [
      "datasette-llm",
      "datasette-secrets"
    ]
  },
  {
    "url": "http://127.0.0.1:8900/",
    "host": "127.0.0.1",
    "port": 8900,
    "version": "0.65.2",
    "databases": [
      "logs"
    ],
    "plugins": []
  }
]
```

## Development

To set up this plugin locally, first checkout the code. You can confirm it is available like this:
```bash
cd datasette-ports
# Confirm the plugin is visible
uv run datasette plugins
```
To run the tests:
```bash
uv run pytest
```
