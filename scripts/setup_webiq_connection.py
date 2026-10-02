"""Create the Foundry project connection that lets the MCP tool carry the key.

The agent service rejects an MCP tool that passes ``x-apikey`` inline, and
directs callers to reference a project connection instead. So the Web IQ key
is stored once as a CustomKeys connection on the project and the tool refers
to it by id -- which is also why no key ever needs to reach the agent
definition or the results files.

Creating this is a metadata operation on the project that already exists; it
provisions no billable resource.
"""

import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from tmap_poc.config import load_dotenv

load_dotenv()

CONNECTION_NAME = "webiq-mcp"
KEY = os.environ["WEBIQ_API_KEY"]
SUB = os.environ["TMAP_POC_AZ_SUBSCRIPTION"]

#: The Bing connection id already encodes account and project, so the new
#: connection is placed beside it rather than asking for more configuration.
existing = os.environ["GWB_CONNECTION_ID"]
m = re.match(
    r"/subscriptions/(?P<sub>[^/]+)/resourceGroups/(?P<rg>[^/]+)"
    r"/providers/Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)"
    r"/projects/(?P<project>[^/]+)/connections/",
    existing,
)
if not m:
    sys.exit(f"could not parse GWB_CONNECTION_ID (shape: {existing[:60]}...)")
sub_id, rg, account, project = (m["sub"], m["rg"], m["account"], m["project"])
print(f"account={account} project={project} rg={rg}")

url = (
    f"https://management.azure.com/subscriptions/{sub_id}"
    f"/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/"
    f"{account}/projects/{project}/connections/{CONNECTION_NAME}"
    f"?api-version=2025-04-01-preview"
)
body = {
    "properties": {
        "category": "CustomKeys",
        "target": "https://api.microsoft.ai/v3/mcp",
        "authType": "CustomKeys",
        "isSharedToAll": False,
        "credentials": {"keys": {"x-apikey": KEY}},
        "metadata": {"purpose": "Web IQ MCP server for the TMAP PoC"},
    }
}

proc = subprocess.run(
    ["az", "rest", "--method", "put", "--url", url,
     "--subscription", SUB, "--body", json.dumps(body)],
    capture_output=True, text=True,
)
out = (proc.stdout + proc.stderr).replace(KEY, "<redacted>")
if proc.returncode != 0:
    sys.exit(f"failed:\n{out[:1500]}")

created = json.loads(proc.stdout)
print(f"connection id: .../connections/{created['name']}")
print(f"target: {created['properties']['target']}")
print(f"authType: {created['properties']['authType']}")
print("\nAdd to .env:")
print(f"WEBIQ_CONNECTION_ID={created['id']}")
