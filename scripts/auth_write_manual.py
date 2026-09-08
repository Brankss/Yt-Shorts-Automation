#!/usr/bin/env python3
"""Two-step (manual) OAuth for the youtube-metadata-updater WRITE scope.

The skill ships auth_write.py, which authorizes via run_local_server(): it opens
a browser and catches the redirect on a localhost port. That only works when the
browser and the script run on the same machine. When they do not -- an agent
container, a remote shell, a phone doing the sign-in -- there is nothing
listening on that port and the flow cannot complete.

This helper is the same consent flow split in two, mirroring the --manual /
--manual-code pair that youtube-channel-insights/scripts/auth.py already
provides for its read-only token:

    step 1:  python3 scripts/auth_write_manual.py --start
             prints the consent URL and stashes the PKCE verifier + state

    step 2:  python3 scripts/auth_write_manual.py --code "<pasted redirect URL>"
             exchanges the code and writes token_write.json

The redirect points at a localhost port nothing listens on, so the browser lands
on a "can't connect" page whose address bar still holds ?code=...; that address
is what gets pasted into step 2.

Everything else -- the single force-ssl scope, the scope guardrails, the file
paths and permissions, the channel ownership record -- is reused verbatim from
the skill's own auth_write.py, so the token this produces is indistinguishable
from one made by the built-in flow and update_metadata.py consumes it directly.
"""

import argparse
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_AUTH = REPO_ROOT / ".agents/skills/youtube-metadata-updater/scripts/auth_write.py"


def load_skill_auth():
    """Import the skill's auth_write.py so this helper reuses its exact rules."""
    if not SKILL_AUTH.exists():
        sys.exit(
            "ERROR: cannot find the metadata-updater skill at\n  " + str(SKILL_AUTH) +
            "\nInstall it first: npx skills add nikhilbhansali/youtube-data-skills"
        )
    spec = importlib.util.spec_from_file_location("skill_auth_write", SKILL_AUTH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    from google_auth_oauthlib.flow import Flow
except ImportError:
    sys.exit(
        "ERROR: Google OAuth libraries not installed.\n"
        "Run: pip3 install google-api-python-client google-auth-oauthlib"
    )

skill = load_skill_auth()

REDIRECT_URI = "http://localhost:8765/"


def pending_path() -> Path:
    return skill.oauth_dir() / "pending_write_auth.json"


def start() -> int:
    cs = skill.client_secret_path()
    if not cs.exists():
        print("ERROR: OAuth client secret not found at " + str(cs))
        print("Save the Desktop-app JSON from Google Cloud Console there first.")
        return 1

    flow = Flow.from_client_secrets_file(str(cs), skill.WRITE_SCOPES, redirect_uri=REDIRECT_URI)
    url, state = flow.authorization_url(access_type="offline", prompt="consent")

    pp = pending_path()
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps({"state": state, "code_verifier": flow.code_verifier}))
    os.chmod(pp, stat.S_IRUSR | stat.S_IWUSR)

    print("STEP 1 of 2 - open this URL in a browser (any device) and sign in with")
    print("the account that OWNS the channel you want to edit.")
    print()
    print("This grants WRITE access (youtube.force-ssl). The skill uses it for one")
    print("thing only: updating video titles and descriptions, after you approve a")
    print("preview of every change.")
    print()
    print(url)
    print()
    print("The browser lands on a 'can't connect to localhost' page - that is expected.")
    print("Copy the FULL address from the address bar and finish with:")
    print('    python3 scripts/auth_write_manual.py --code "<paste address here>"')
    return 0


def finish(response: str) -> int:
    pp = pending_path()
    if not pp.exists():
        print("ERROR: no pending flow. Start with: python3 scripts/auth_write_manual.py --start")
        return 1
    pending = json.loads(pp.read_text())

    response = response.strip()
    if response.startswith("http"):
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(response).query)
        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        if not code:
            print("ERROR: pasted URL has no ?code= parameter.")
            return 1
        if state and state != pending["state"]:
            print("ERROR: state mismatch - that redirect belongs to a different --start run.")
            print("Start over: python3 scripts/auth_write_manual.py --start")
            return 1
    else:
        code = response

    flow = Flow.from_client_secrets_file(
        str(skill.client_secret_path()), skill.WRITE_SCOPES,
        redirect_uri=REDIRECT_URI, code_verifier=pending["code_verifier"],
    )
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        print("ERROR: code exchange failed (" + str(exc) + ").")
        print("Codes are single-use and expire in ~10 minutes.")
        print("Start over: python3 scripts/auth_write_manual.py --start")
        return 1

    creds = flow.credentials
    # The skill's own guardrail: exactly one write scope, nothing more.
    skill._assert_scopes_exact(creds.scopes or skill.WRITE_SCOPES)
    skill._save_token(creds)
    pp.unlink(missing_ok=True)

    info = skill.verify_channel(creds)
    skill.save_channel(info["channel_id"], info["channel_title"])

    print("Authorization complete.")
    print("Token saved to " + str(skill.token_path()) + " (permissions 600)")
    print("Scopes granted: " + ", ".join(creds.scopes or []))
    print()
    print("This token can CHANGE this channel:")
    print("  " + info["channel_title"] + "  (" + info["channel_id"] + ")")
    print()
    print("Next: python3 scripts/update_metadata.py list --limit 50")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Two-step OAuth for the metadata-updater write scope, for when "
                    "the browser cannot reach the script's localhost port."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Step 1: print the consent URL")
    group.add_argument("--code", metavar="URL_OR_CODE", help="Step 2: the redirect URL or bare code")
    args = parser.parse_args()

    return start() if args.start else finish(args.code)


if __name__ == "__main__":
    sys.exit(main())
