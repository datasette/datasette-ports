from datasette.app import Datasette
from datasette.cli import cli
from click.testing import CliRunner
from unittest.mock import patch
import json
import pytest


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-ports" in installed_plugins


LSOF_OUTPUT = """\
python3.1 1001 user   67u  IPv4 0xabc      0t0  TCP 127.0.0.1:8001 (LISTEN)
python3.1 1002 user    7u  IPv4 0xdef      0t0  TCP 127.0.0.1:8333 (LISTEN)
python3.1 1003 user    5u  IPv4 0x123      0t0  TCP 127.0.0.1:8000 (LISTEN)
python3.1 1004 user   12u  IPv4 0x456      0t0  TCP *:8014 (LISTEN)
"""


@pytest.fixture
def mock_lsof():
    with patch("datasette_ports.get_lsof_output") as m:
        m.return_value = LSOF_OUTPUT
        yield m


@pytest.fixture
def mock_probe():
    with patch("datasette_ports.probe_port") as m:
        yield m


@pytest.fixture(autouse=True)
def mock_cwd():
    with patch("datasette_ports.get_process_cwd") as m:
        m.return_value = None
        yield m


def _fake_probe(responses):
    async def fake(host, port):
        return responses.get((host, port))

    return fake


def test_ports_command(mock_lsof, mock_probe):
    mock_probe.side_effect = _fake_probe(
        {
            ("127.0.0.1", 8001): {
                "databases": [{"name": "creatures", "path": "/tmp/creatures.db"}],
                "version": "1.0a26",
                "plugins": ["datasette-llm"],
            },
            ("127.0.0.1", 8333): {
                "databases": [
                    {"name": "data", "path": "data.db"},
                    {"name": "logs", "path": None},
                ],
                "version": "0.65.2",
                "plugins": [],
            },
            ("0.0.0.0", 8014): {
                "databases": [
                    {"name": "content", "path": "content.db"},
                    {"name": "_internal", "path": None},
                ],
                "version": "1.0a26",
                "plugins": ["datasette-llm", "datasette-extract"],
            },
        }
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["ports"])
    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:8001/ - v1.0a26" in result.output
    assert "  Databases:" in result.output
    assert "    creatures: /tmp/creatures.db" in result.output
    assert "  Plugins:" in result.output
    assert "    datasette-llm" in result.output
    assert "http://127.0.0.1:8333/ - v0.65.2" in result.output
    assert "    data: data.db" in result.output
    assert "    logs" in result.output
    assert "http://0.0.0.0:8014/ - v1.0a26" in result.output
    assert "    content: content.db" in result.output
    assert "    _internal" in result.output
    assert "    datasette-extract" in result.output
    # Port 8000 returned None (not datasette), should not appear
    assert "8000" not in result.output


def test_ports_no_plugins_line_when_empty(mock_lsof, mock_probe):
    mock_probe.side_effect = _fake_probe(
        {
            ("127.0.0.1", 8001): {
                "databases": [{"name": "db1", "path": None}],
                "version": "0.65.2",
                "plugins": [],
            },
        }
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["ports"])
    assert result.exit_code == 0, result.output
    assert "Plugins" not in result.output


def test_ports_json_output(mock_lsof, mock_probe):
    mock_probe.side_effect = _fake_probe(
        {
            ("127.0.0.1", 8001): {
                "databases": [{"name": "creatures", "path": "/tmp/creatures.db"}],
                "version": "1.0a26",
                "plugins": ["datasette-llm"],
            },
        }
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["ports", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["url"] == "http://127.0.0.1:8001/"
    assert data[0]["port"] == 8001
    assert data[0]["version"] == "1.0a26"
    assert data[0]["databases"] == [{"name": "creatures", "path": "/tmp/creatures.db"}]
    assert data[0]["plugins"] == ["datasette-llm"]


def test_ports_json_empty(mock_lsof, mock_probe):
    mock_lsof.return_value = ""
    mock_probe.side_effect = _fake_probe({})

    runner = CliRunner()
    result = runner.invoke(cli, ["ports", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


def test_ports_no_instances(mock_lsof, mock_probe):
    mock_lsof.return_value = ""
    mock_probe.side_effect = _fake_probe({})

    runner = CliRunner()
    result = runner.invoke(cli, ["ports"])
    assert result.exit_code == 0
    assert "No running Datasette instances found" in result.output


def test_ports_all_non_datasette(mock_lsof, mock_probe):
    mock_probe.side_effect = _fake_probe({})

    runner = CliRunner()
    result = runner.invoke(cli, ["ports"])
    assert result.exit_code == 0
    assert "No running Datasette instances found" in result.output


def test_parse_lsof():
    from datasette_ports import parse_lsof

    results = parse_lsof(LSOF_OUTPUT)
    assert ("127.0.0.1", 8001, 1001) in results
    assert ("127.0.0.1", 8333, 1002) in results
    assert ("127.0.0.1", 8000, 1003) in results
    assert ("0.0.0.0", 8014, 1004) in results
    assert len(results) == 4


def test_parse_lsof_wildcard():
    from datasette_ports import parse_lsof

    results = parse_lsof(
        "python3.1 1234 user 12u  IPv4 0x456  0t0  TCP *:9000 (LISTEN)\n"
    )
    assert results == [("0.0.0.0", 9000, 1234)]


def test_cwd_resolves_relative_paths(mock_lsof, mock_probe, mock_cwd):
    mock_cwd.return_value = "/home/user/project"
    mock_probe.side_effect = _fake_probe(
        {
            ("127.0.0.1", 8001): {
                "databases": [
                    {"name": "data", "path": "data.db"},
                    {"name": "abs", "path": "/tmp/abs.db"},
                    {"name": "mem", "path": None},
                ],
                "version": "1.0a26",
                "plugins": [],
            },
        }
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["ports"])
    assert result.exit_code == 0, result.output
    assert "Directory: /home/user/project" in result.output
    assert "data: /home/user/project/data.db" in result.output
    assert "abs: /tmp/abs.db" in result.output
    assert "    mem" in result.output


def test_no_cwd_leaves_paths_as_is(mock_lsof, mock_probe, mock_cwd):
    mock_cwd.return_value = None
    mock_probe.side_effect = _fake_probe(
        {
            ("127.0.0.1", 8001): {
                "databases": [{"name": "data", "path": "data.db"}],
                "version": "1.0a26",
                "plugins": [],
            },
        }
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["ports"])
    assert result.exit_code == 0, result.output
    assert "Directory" not in result.output
    assert "data: data.db" in result.output


def test_parse_lsof_empty():
    from datasette_ports import parse_lsof

    assert parse_lsof("") == []
