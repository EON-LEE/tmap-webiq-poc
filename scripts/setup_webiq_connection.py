"""Store or rotate the WebIQ key in a Foundry project connection. Plan only by default.

    python scripts/setup_webiq_connection.py --connection-id <WEBIQ_CONNECTION_ID> --apply

The key comes from WEBIQ_API_KEY or a hidden prompt, is checked against WebIQ before it is
stored, and travels only in the HTTPS request body. Running apps use a new key within 10 minutes.
New environments get this connection from scripts/provision.py.
"""

import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from provision import Azure, ProvisionError, check_webiq_key, put_webiq_connection, webiq_key  # noqa: E402

CONNECTION_ID = re.compile(
    r"/subscriptions/(?P<subscription>[^/]+)/resourceGroups/[^/]+/providers/Microsoft\.CognitiveServices"
    r"/accounts/[^/]+/projects/[^/]+/connections/[^/]+",
    re.IGNORECASE,
)


def main(argv=None, *, azure=None, out=print):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--connection-id", required=True, help="Project connection resource ID (WEBIQ_CONNECTION_ID).")
    parser.add_argument("--apply", action="store_true", help="Check and store the key. Without it nothing is read or changed.")
    args = parser.parse_args(argv)
    match = CONNECTION_ID.fullmatch(args.connection_id)
    if not match:
        parser.error("--connection-id must be a Foundry project connection resource ID.")
    name = args.connection_id.rsplit("/", 1)[-1]
    if not args.apply:
        out(f"Plan only: check the WebIQ key, then store it in connection '{name}'. Add --apply.")
        return
    key = webiq_key(prompt=True)
    if not key:
        parser.error("Set WEBIQ_API_KEY or run in a terminal to type the key.")
    azure = azure or Azure(match["subscription"])
    azure.secret(key)
    try:
        check_webiq_key(azure, key)
        put_webiq_connection(azure, args.connection_id, key)
    except ProvisionError as error:
        parser.exit(1, f"error: {error}\n")
    out(f"WebIQ key stored in connection '{name}'. Running apps use it within 10 minutes.")


if __name__ == "__main__":
    main()
