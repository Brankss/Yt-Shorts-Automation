#!/usr/bin/env python3
"""
YouTube Metadata Updater - OAuth helper (WRITE scope).

Performs the one-time browser consent flow for the ONE write scope this skill
needs and stores a refreshable token on disk. update_metadata.py imports
get_credentials() from here to load + silently refresh the stored token.

Scope requested (exactly one, nothing else is ever asked for or accepted):
    https://www.googleapis.com/auth/youtube.force-ssl

This token is DELIBERATELY SEPARATE from the read-only analytics token used by
youtube-channel-insights (token.json). The two are never merged: analytics keeps
running on credentials that physically cannot change anything, and this file is
the only credential in the suite that can edit the channel.

Credential files live in ~/.config/youtube-skills/ (override with $YT_OAUTH_DIR):
    client_secret.json  - REUSED from the youtube-channel-insights setup
    token_write.json    - written by this script, chmod 600
    channel_write.json  - id + title of the channel this token controls

Usage:
    python3 scripts/auth_write.py            # grant write access (opens browser)
    python3 scripts/auth_write.py --check     # report token status, no browser
    python3 scripts/auth_write.py --force     # discard token_write.json, re-consent
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
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print(INSTALL_HINT)
    sys.exit(1)


# --- Scopes -----------------------------------------------------------------

SCOPE_FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"

# The complete, closed set. Anything outside it is a bug or a hijacked token.
WRITE_SCOPES = [SCOPE_FORCE_SSL]
ALLOWED_SCOPES = {SCOPE_FORCE_SSL}


# --- Paths ------------------------------------------------------------------

def oauth_dir() -> Path:
    """Directory holding client_secret.json, token_write.json, channel_write.json."""
    override = os.environ.get("YT_OAUTH_DIR")
    return Path(override).expanduser() if override else Path.home() / ".config" / "youtube-skills"


def client_secret_path() -> Path:
    return oauth_dir() / "client_secret.json"


def token_path() -> Path:
    return oauth_dir() / "token_write.json"


def channel_file() -> Path:
    return oauth_dir() / "channel_write.json"


def _assert_scopes_exact(scopes) -> None:
    """Refuse anything that is not exactly the single force-ssl scope.

    Mirrors the paranoia in youtube-channel-insights/scripts/auth.py, inverted:
    that script refuses write scopes, this one refuses everything *except* the
    one write scope it declares. A token carrying youtube.upload or
    youtubepartner did not come from this tool and will not be used by it.
    """
    granted = set(scopes or [])
    if not granted:
        raise RuntimeError("Stored token records no scopes. Re-run: python3 scripts/auth_write.py --force")
    extra = granted - ALLOWED_SCOPES
    if extra:
        raise RuntimeError(
            "Refusing to use a token with unexpected scopes: "
            + ", ".join(sorted(extra))
            + "\nThis skill grants exactly one scope: "
            + SCOPE_FORCE_SSL
            + "\nDelete "
            + str(token_path())
            + " and re-run: python3 scripts/auth_write.py --force"
        )
    if SCOPE_FORCE_SSL not in granted:
        raise RuntimeError(
            "Stored token is missing " + SCOPE_FORCE_SSL + " and cannot write.\n"
            "Run: python3 scripts/auth_write.py --force"
        )


def _chmod_600(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _ensure_dir() -> Path:
    d = oauth_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, stat.S_IRWXU)
    except OSError:
        pass
    return d


def _save_token(creds) -> None:
    _ensure_dir()
    tp = token_path()
    tp.write_text(creds.to_json(), encoding="utf-8")
    _chmod_600(tp)


def _load_token():
    """Load token_write.json into Credentials, or None if absent/unreadable."""
    tp = token_path()
    if not tp.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(tp))
    except (ValueError, json.JSONDecodeError, OSError):
        return None


def save_channel(channel_id: str, channel_title: str) -> None:
    """Record which channel this write token controls, for later sanity checks."""
    _ensure_dir()
    cf = channel_file()
    cf.write_text(
        json.dumps({"channel_id": channel_id, "channel_title": channel_title}, indent=2),
        encoding="utf-8",
    )
    _chmod_600(cf)


def load_channel():
    """Return {"channel_id":..., "channel_title":...} or None if never verified."""
    cf = channel_file()
    if not cf.exists():
        return None
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not data.get("channel_id"):
        return None
    return data


# --- Public API used by update_metadata.py ----------------------------------

class AuthError(RuntimeError):
    """Raised when no usable write credential can be produced without a browser."""


def get_credentials():
    """
    Load the stored write credential, refreshing silently if expired.

    Never opens a browser - if consent is needed, raises AuthError telling the
    user to run auth_write.py.
    """
    creds = _load_token()
    if creds is None:
        raise AuthError(
            "No stored write token at " + str(token_path()) + ".\n"
            "Run: python3 scripts/auth_write.py"
        )

    _assert_scopes_exact(creds.scopes)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _save_token(creds)
            except Exception as exc:  # refresh token revoked / expired
                raise AuthError(
                    "Stored write token could not be refreshed (" + str(exc) + ").\n"
                    "Re-authorize with: python3 scripts/auth_write.py --force\n"
                    "Tip: if your OAuth consent screen is still in 'Testing' mode, "
                    "refresh tokens expire after 7 days. Publish the app to "
                    "'Production' in Google Cloud Console to stop this recurring."
                ) from exc
        else:
            raise AuthError(
                "Stored write token is invalid and has no refresh token.\n"
                "Run: python3 scripts/auth_write.py --force"
            )

    return creds


# --- Ownership verification -------------------------------------------------

def verify_channel(creds):
    """
    channels.list(part=snippet, mine=True) - confirm the token controls a channel.

    Returns {"channel_id":..., "channel_title":...}. Costs 1 quota unit.
    Note the part list: snippet only. This script never requests part=status.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print(INSTALL_HINT)
        sys.exit(1)

    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise AuthError(
            "This Google account has no YouTube channel, or you signed in with the "
            "wrong account. Re-run: python3 scripts/auth_write.py --force"
        )
    item = items[0]
    return {
        "channel_id": item.get("id", ""),
        "channel_title": item.get("snippet", {}).get("title", ""),
    }


# --- Interactive flow -------------------------------------------------------

def run_flow():
    """Run the installed-app consent flow on a random localhost port."""
    _assert_requested_scopes()
    cs = client_secret_path()
    if not cs.exists():
        print("ERROR: OAuth client secret not found at " + str(cs))
        print()
        print("This skill REUSES the client_secret.json from the youtube-channel-insights")
        print("setup. If you have never done that setup, do it now:")
        print("  1. https://console.cloud.google.com/apis/library - enable 'YouTube Data API v3'")
        print("  2. APIs & Services > OAuth consent screen > External, add yourself")
        print("     as a test user, then PUBLISH the app to Production")
        print("  3. APIs & Services > Credentials > Create OAuth client ID >")
        print("     Application type: 'Desktop app' > Download JSON")
        print("  4. Save that file as " + str(cs))
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(cs), WRITE_SCOPES)
    print("Opening your browser for Google sign-in...")
    print("Sign in with the account that OWNS the YouTube channel you want to edit.")
    print()
    print("You are about to grant WRITE access (youtube.force-ssl). This skill uses it")
    print("for exactly one thing: updating video titles and descriptions, and only after")
    print("you approve a preview. Nothing else in this suite gets this token.")
    return flow.run_local_server(port=0, prompt="consent")


def _assert_requested_scopes() -> None:
    if set(WRITE_SCOPES) != ALLOWED_SCOPES:
        raise RuntimeError("Scope list tampered with; refusing to start a consent flow.")


def print_status() -> int:
    creds = _load_token()
    chan = load_channel()
    print("Credential directory : " + str(oauth_dir()))
    print("client_secret.json   : " + ("found" if client_secret_path().exists() else "MISSING"))
    if creds is None:
        print("token_write.json     : MISSING - run: python3 scripts/auth_write.py")
        return 1
    print("token_write.json     : found")
    print("Scopes               : " + ", ".join(creds.scopes or []))
    try:
        _assert_scopes_exact(creds.scopes)
    except RuntimeError as exc:
        print("Status               : REFUSED - " + str(exc))
        return 1
    if chan:
        print("Channel controlled   : " + chan.get("channel_title", "?") + " (" + chan.get("channel_id", "?") + ")")
    else:
        print("Channel controlled   : unknown - run: python3 scripts/auth_write.py")
    if creds.valid:
        print("Status               : valid (WRITE access to titles + descriptions)")
        return 0
    if creds.expired and creds.refresh_token:
        print("Status               : expired, will refresh automatically on next use")
        return 0
    print("Status               : INVALID - run: python3 scripts/auth_write.py --force")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-time OAuth setup for YouTube metadata WRITES "
            "(youtube.force-ssl, separate token from the read-only analytics one)."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore any existing write token and re-run the consent flow",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report stored-token status and exit (never opens a browser)",
    )
    args = parser.parse_args()

    if args.check:
        return print_status()

    if not args.force and _load_token() is not None:
        try:
            creds = get_credentials()
            _save_token(creds)
            info = verify_channel(creds)
            save_channel(info["channel_id"], info["channel_title"])
            print("Already authorized. Write token is valid.")
            print("Token file      : " + str(token_path()))
            print("Scopes          : " + ", ".join(creds.scopes or []))
            print("Channel controlled: " + info["channel_title"] + " (" + info["channel_id"] + ")")
            return 0
        except (AuthError, RuntimeError) as exc:
            print("Existing write token unusable: " + str(exc))
            print("Re-running consent flow...\n")

    creds = run_flow()
    _assert_scopes_exact(creds.scopes)
    _save_token(creds)

    info = verify_channel(creds)
    save_channel(info["channel_id"], info["channel_title"])

    print()
    print("Authorization complete.")
    print("Token saved to " + str(token_path()) + " (permissions 600)")
    print("Scopes granted: " + ", ".join(creds.scopes or []))
    print()
    print("This token can CHANGE this channel:")
    print("  " + info["channel_title"] + "  (" + info["channel_id"] + ")")
    print("Channel recorded in " + str(channel_file()) + " for ownership checks.")
    print()
    print("Your read-only analytics token (token.json) is untouched and stays read-only.")
    print()
    print("Next: python3 scripts/update_metadata.py list --limit 50")
    return 0


if __name__ == "__main__":
    sys.exit(main())
