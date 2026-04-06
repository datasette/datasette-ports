import asyncio
import json as json_module
import re
import subprocess

import click
import httpx
from datasette import hookimpl


def parse_lsof(output):
    """Parse lsof output to extract (host, port) pairs for Python TCP listeners."""
    results = []
    for line in output.strip().splitlines():
        match = re.search(r"TCP\s+(\S+):(\d+)\s+\(LISTEN\)", line)
        if match:
            host = match.group(1)
            port = int(match.group(2))
            if host == "*":
                host = "0.0.0.0"
            results.append((host, port))
    return results


def get_lsof_output():
    """Run lsof to find all Python processes listening on TCP ports."""
    try:
        result = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
            capture_output=True,
            text=True,
        )
        return "\n".join(
            line for line in result.stdout.splitlines() if "python" in line.lower()
        )
    except FileNotFoundError:
        return ""


async def probe_port(host, port):
    """Probe a port to see if it's a Datasette instance.

    Returns dict with databases, version, plugins keys, or None if not Datasette.
    """
    url_host = host if host != "0.0.0.0" else "127.0.0.1"
    base = f"http://{url_host}:{port}"
    try:
        async with httpx.AsyncClient() as client:
            responses = await asyncio.gather(
                client.get(f"{base}/-/databases.json", timeout=2.0),
                client.get(f"{base}/-/versions.json", timeout=2.0),
                client.get(f"{base}/-/plugins.json", timeout=2.0),
            )
            databases_resp, versions_resp, plugins_resp = responses

            if databases_resp.status_code != 200:
                return None

            databases_data = databases_resp.json()
            if not isinstance(databases_data, list):
                return None

            databases = [db["name"] for db in databases_data if "name" in db]

            # Extract version
            version = None
            if versions_resp.status_code == 200:
                versions_data = versions_resp.json()
                version = versions_data.get("datasette", {}).get("version")

            # Extract plugin names
            plugins = []
            if plugins_resp.status_code == 200:
                plugins_data = plugins_resp.json()
                if isinstance(plugins_data, list):
                    plugins = [p["name"] for p in plugins_data if "name" in p]

            return {
                "databases": databases,
                "version": version,
                "plugins": plugins,
            }
    except (httpx.ConnectError, httpx.TimeoutException, Exception):
        pass
    return None


def _find_instances(output_json):
    """Find all currently running Datasette instances and list their ports."""
    lsof_output = get_lsof_output()
    candidates = parse_lsof(lsof_output)

    if not candidates:
        if output_json:
            click.echo("[]")
        else:
            click.echo("No running Datasette instances found")
        return

    async def gather_results():
        tasks = [probe_port(host, port) for host, port in candidates]
        return await asyncio.gather(*tasks)

    results = asyncio.run(gather_results())

    instances = []
    for (host, port), info in zip(candidates, results):
        if info is not None:
            instances.append(
                {
                    "url": f"http://{host}:{port}/",
                    "host": host,
                    "port": port,
                    "version": info["version"],
                    "databases": info["databases"],
                    "plugins": info["plugins"],
                }
            )

    if output_json:
        click.echo(json_module.dumps(instances, indent=2))
    elif instances:
        for instance in instances:
            version_str = f" - v{instance['version']}" if instance["version"] else ""
            click.echo(f"{instance['url']}{version_str}")
            click.echo(f"  Databases: {', '.join(instance['databases'])}")
            if instance["plugins"]:
                click.echo(f"  Plugins: {', '.join(instance['plugins'])}")
    else:
        click.echo("No running Datasette instances found")


@click.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def cli(output_json):
    """Find all currently running Datasette instances and list their ports."""
    _find_instances(output_json)


@hookimpl
def register_commands(cli):
    @cli.command()
    @click.option("--json", "output_json", is_flag=True, help="Output as JSON")
    def ports(output_json):
        """Find all currently running Datasette instances and list their ports."""
        _find_instances(output_json)
