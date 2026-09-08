#!/usr/bin/env python3
"""
YouTube Channel Insights - OAuth helper.

Performs the one-time browser consent flow for the YouTube Analytics API v2
and stores a refreshable token on disk. Also exposes get_credentials() which
fetch_insights.py imports to load + silently refresh the stored token.

Scopes requested (ALL READ-ONLY - this tool never asks for write access):
    https://www.googleapis.com/auth/yt-analytics.readonly
    https://www.googleapis.com/auth/youtube.readonly
    https://www.googleapis.com/auth/yt-analytics-monetary.readonly   (--with-revenue only)

Credential files live in ~/.config/youtube-skills/ (override with $YT_OAUTH_DIR):
    client_secret.json  - you download this from Google Cloud Console
    token.json          - written by this script, chmod 600

Usage:
    python3 scripts/auth.py                  # analytics + channel read access
    python3 scripts/auth.py --with-revenue   # also request monetary metrics
    python3 scripts/auth.py --check          # report token status, no browser
    python3 scripts/auth.py --force          # discard token.json and re-consent
    python3 scripts/auth.py --manual         # step 1: print consent URL (no browser / no local server)
    python3 scripts/auth.py --manual-code "<pasted redirect URL or code>"   # step 2: finish
"""

import argparse
import json
import os
import stat
import sys
from pathlib import Path

INSTALL_HINT = (
    "ERROR: Google OAuth libraries not installed.\n"
    "Run: pip3 install google-api-python-client google-auth-oauthlib"
)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow, InstalledAppFlow
except ImportError:
    print(INSTALL_HINT)
    sys.exit(1)


# --- Scopes -----------------------------------------------------------------

SCOPE_ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
SCOPE_YOUTUBE_RO = "https://www.googleapis.com/auth/youtube.readonly"
SCOPE_MONETARY = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"

BASE_SCOPES = [SCOPE_ANALYTICS, SCOPE_YOUTUBE_RO]
REVENUE_SCOPES = BASE_SCOPES + [SCOPE_MONETARY]

# Write scopes are deliberately never requested. Guard against accidents.
FORBIDDEN_SCOPES = {
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtubepartner",
}


# --- Paths ------------------------------------------------------------------

def oauth_dir() -> Path:
    """Directory holding client_secret.json and token.json."""
    override = os.environ.get("YT_OAUTH_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".config" / "youtube-skills"
    return base


def client_secret_path() -> Path:
    return oauth_dir() / "client_secret.json"


def token_path() -> Path:
    return oauth_dir() / "token.json"


def _assert_read_only(scopes) -> None:
    bad = FORBIDDEN_SCOPES.intersection(set(scopes or []))
    if bad:
        raise RuntimeError(
            "Refusing to use write scopes: " + ", ".join(sorted(bad))
        )


def _chmod_600(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _save_token(creds) -> None:
    d = oauth_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, stat.S_IRWXU)
    except OSError:
        pass
    tp = token_path()
    tp.write_text(creds.to_json(), encoding="utf-8")
    _chmod_600(tp)


def _load_token():
    """Load token.json into Credentials, or None if absent/unreadable."""
    tp = token_path()
    if not tp.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(tp))
    except (ValueError, json.JSONDecodeError, OSError):
        return None


def has_revenue_scope(creds) -> bool:
    """True if the stored credential includes the monetary analytics scope."""
    return bool(creds and SCOPE_MONETARY in (creds.scopes or []))


# --- Public API used by fetch_insights.py -----------------------------------

class AuthError(RuntimeError):
    """Raised when no usable credential can be produced without a browser."""


def get_credentials(with_revenue: bool = False):
    """
    Load stored credentials, refreshing silently if expired.

    Never opens a browser - if consent is needed, raises AuthError telling the
    user to run auth.py. `with_revenue=True` additionally requires the monetary
    scope to be present.
    """
    creds = _load_token()
    if creds is None:
        raise AuthError(
            f"No stored token at {token_path()}.\n"
            "Run: python3 scripts/auth.py"
            + ("  --with-revenue" if with_revenue else "")
        )

    _assert_read_only(creds.scopes)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _save_token(creds)
            except Exception as exc:  # refresh token revoked / expired
                raise AuthError(
                    f"Stored token could not be refreshed ({exc}).\n"
                    "Re-authorize with: python3 scripts/auth.py --force\n"
                    "Tip: if your OAuth consent screen is still in 'Testing' mode, "
                    "refresh tokens expire after 7 days. Publish the app to "
                    "'Production' in Google Cloud Console to stop this recurring."
                ) from exc
        else:
            raise AuthError(
                "Stored token is invalid and has no refresh token.\n"
                "Run: python3 scripts/auth.py --force"
            )

    if with_revenue and not has_revenue_scope(creds):
        raise AuthError(
            "Revenue metrics need the monetary scope, which was not granted.\n"
            "Run: python3 scripts/auth.py --with-revenue"
        )

    return creds


# --- Interactive flow -------------------------------------------------------

def run_flow(scopes) -> "Credentials":
    """Run the installed-app consent flow on a random localhost port."""
    _assert_read_only(scopes)
    cs = client_secret_path()
    if not cs.exists():
        print(f"ERROR: OAuth client secret not found at {cs}")
        print()
        print("Fix it in 4 steps:")
        print("  1. https://console.cloud.google.com/apis/library - enable")
        print("     'YouTube Data API v3' AND 'YouTube Analytics API'")
        print("  2. APIs & Services > OAuth consent screen > External, add yourself")
        print("     as a test user, then PUBLISH the app to Production")
        print("  3. APIs & Services > Credentials > Create OAuth client ID >")
        print("     Application type: 'Desktop app' > Download JSON")
        print(f"  4. Save that file as {cs}")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(cs), scopes)
    print("Opening your browser for Google sign-in...")
    print("Sign in with the account that OWNS the YouTube channel you want to analyze.")
    creds = flow.run_local_server(port=0, prompt="consent")
    return creds


# --- Manual (two-step) flow --------------------------------------------------
#
# For cases where run_local_server() cannot receive the redirect: the person
# authorizing is on a different device, the browser is on another machine, or
# the local listener died before the redirect arrived. Step 1 prints the URL and
# stashes the PKCE verifier + state (chmod 600, next to the token). Step 2 takes
# the redirect URL (or bare code) and exchanges it in a fresh process.
#
# The redirect URI points at a localhost port nothing listens on, so the browser
# lands on a "can't connect" page whose address bar still holds ?code=...; that
# address is what the user pastes back.

MANUAL_REDIRECT_URI = "http://localhost:8765/"


def pending_path() -> Path:
    return oauth_dir() / "pending_auth.json"


def _write_private(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def manual_start(scopes) -> int:
    _assert_read_only(scopes)
    cs = client_secret_path()
    if not cs.exists():
        print(f"ERROR: OAuth client secret not found at {cs}")
        return 1
    flow = Flow.from_client_secrets_file(str(cs), scopes, redirect_uri=MANUAL_REDIRECT_URI)
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _write_private(pending_path(), {
        "state": state,
        "code_verifier": flow.code_verifier,
        "scopes": list(scopes),
    })
    print("STEP 1 of 2 - open this URL in a browser (any device), sign in with the")
    print("account that owns/manages the channel, pick the CHANNEL on the")
    print("'Choose an account' screen, and click Allow:")
    print()
    print(url)
    print()
    print("The browser will then land on a 'can't connect to localhost' page - that is")
    print("expected. Copy the FULL address from the address bar (it contains ?code=...)")
    print("and finish with:")
    print('    python3 scripts/auth.py --manual-code "<paste address here>"')
    return 0


def manual_finish(response: str) -> "Credentials":
    pp = pending_path()
    if not pp.exists():
        raise AuthError("No pending manual flow. Run: python3 scripts/auth.py --manual")
    pending = json.loads(pp.read_text())
    scopes = pending["scopes"]
    _assert_read_only(scopes)

    response = response.strip()
    if response.startswith("http"):
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(response).query)
        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        if not code:
            raise AuthError("Pasted URL has no ?code= parameter.")
        if state and state != pending["state"]:
            raise AuthError("State mismatch - this redirect belongs to a different --manual run. "
                            "Start over with: python3 scripts/auth.py --manual")
    else:
        code = response

    flow = Flow.from_client_secrets_file(
        str(client_secret_path()), scopes,
        redirect_uri=MANUAL_REDIRECT_URI, code_verifier=pending["code_verifier"],
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    _assert_read_only(creds.scopes or scopes)
    pp.unlink(missing_ok=True)
    return creds


def print_status() -> int:
    creds = _load_token()
    print(f"Credential directory : {oauth_dir()}")
    print(f"client_secret.json   : {'found' if client_secret_path().exists() else 'MISSING'}")
    if creds is None:
        print("token.json           : MISSING - run: python3 scripts/auth.py")
        return 1
    print("token.json           : found")
    print(f"Scopes               : {', '.join(creds.scopes or [])}")
    print(f"Revenue metrics      : {'enabled' if has_revenue_scope(creds) else 'not granted (use --with-revenue)'}")
    if creds.valid:
        print("Status               : valid")
        return 0
    if creds.expired and creds.refresh_token:
        print("Status               : expired, will refresh automatically on next use")
        return 0
    print("Status               : INVALID - run: python3 scripts/auth.py --force")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-time OAuth setup for YouTube Analytics (read-only)."
    )
    parser.add_argument(
        "--with-revenue",
        action="store_true",
        help="Also request yt-analytics-monetary.readonly for revenue/RPM metrics",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore any existing token and re-run the consent flow",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report stored-token status and exit (never opens a browser)",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Two-step flow, step 1: print the consent URL instead of opening a browser "
             "(use when the authorizing person is on another device)",
    )
    parser.add_argument(
        "--manual-code",
        metavar="URL_OR_CODE",
        help="Two-step flow, step 2: the redirect URL (or bare code) from the browser",
    )
    args = parser.parse_args()

    if args.check:
        return print_status()

    scopes = REVENUE_SCOPES if args.with_revenue else BASE_SCOPES

    if args.manual:
        return manual_start(scopes)

    if args.manual_code:
        try:
            creds = manual_finish(args.manual_code)
        except AuthError as exc:
            print(f"ERROR: {exc}")
            return 1
        except Exception as exc:
            print(f"ERROR: code exchange failed ({exc}). Codes are single-use and expire "
                  "in ~10 minutes - restart with: python3 scripts/auth.py --manual")
            return 1
        _save_token(creds)
        print("Authorization complete.")
        print(f"Token saved to {token_path()} (permissions 600)")
        print(f"Scopes granted: {', '.join(creds.scopes or [])}")
        return 0

    if not args.force:
        existing = _load_token()
        if existing is not None:
            needs_upgrade = args.with_revenue and not has_revenue_scope(existing)
            if not needs_upgrade:
                try:
                    creds = get_credentials(with_revenue=args.with_revenue)
                    _save_token(creds)
                    print("Already authorized. Token is valid.")
                    print(f"Token file: {token_path()}")
                    print(f"Scopes: {', '.join(creds.scopes or [])}")
                    return 0
                except AuthError as exc:
                    print(f"Existing token unusable: {exc}")
                    print("Re-running consent flow...\n")
            else:
                print("Existing token lacks the monetary scope. Re-consenting...\n")

    creds = run_flow(scopes)
    _save_token(creds)

    print()
    print("Authorization complete.")
    print(f"Token saved to {token_path()} (permissions 600)")
    print(f"Scopes granted: {', '.join(creds.scopes or [])}")
    if not has_revenue_scope(creds):
        print("Revenue metrics are NOT enabled. Re-run with --with-revenue to add them.")
    print()
    print("Next: python3 scripts/fetch_insights.py all --days 90")
    return 0


if __name__ == "__main__":
    sys.exit(main())
