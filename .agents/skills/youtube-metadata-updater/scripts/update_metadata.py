#!/usr/bin/env python3
"""
YouTube Metadata Updater - titles and descriptions only.

The only write-capable script in this suite. It can change two fields on videos
the authenticated account owns: snippet.title and snippet.description.
It never touches status/privacy, thumbnails, playlists, comments, or deletes -
part="status" is never even requested, so a bug cannot unpublish a video.

Usage:
    python3 scripts/update_metadata.py list    --limit 50
    python3 scripts/update_metadata.py get     --videos ID,ID
    python3 scripts/update_metadata.py preview --plan reports/data/plan.json
    python3 scripts/update_metadata.py apply   --plan reports/data/plan.json            # dry run
    python3 scripts/update_metadata.py apply   --plan reports/data/plan.json --confirm  # WRITES
    python3 scripts/update_metadata.py revert  --videos ID,ID --confirm

Plan file format - a JSON array (or the preview file this script writes, which
is also a valid plan):

    [
      {
        "videoId": "dQw4w9WgXcQ",
        "new_title": "...",              # optional if new_description is given
        "new_description": "...",        # optional if new_title is given
        "reason": "why, citing data"     # optional, carried into the report
      }
    ]

------------------------------------------------------------------------------
THE DESTRUCTIVE BUG THIS SCRIPT IS BUILT TO AVOID
------------------------------------------------------------------------------
videos.update REPLACES the entire snippet part. It is not a patch. Sending
{"snippet": {"title": "New"}} silently WIPES tags, categoryId (which is
required, so the call 400s), defaultLanguage and defaultAudioLanguage.
The classic failure mode is a video quietly losing all of its tags.

So: every write here goes through merge_snippet(), which starts from the video's
freshly fetched current snippet and changes only title/description.

Test-style assertions the code must always satisfy (enforced in merge_snippet):
    assert merged["categoryId"] == current["categoryId"]
    assert merged.get("tags") == current.get("tags")
    assert merged.get("defaultLanguage") == current.get("defaultLanguage")
    assert merged.get("defaultAudioLanguage") == current.get("defaultAudioLanguage")
    assert merged["title"] == new_title or current["title"]
    assert merged["description"] == new_description or current["description"]
"""

import argparse
import copy
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INSTALL_HINT = (
    "ERROR: Google API libraries not installed.\n"
    "Run: pip3 install google-api-python-client google-auth-oauthlib"
)

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(INSTALL_HINT)
    sys.exit(1)

try:
    from auth_write import AuthError, get_credentials, load_channel, save_channel
except ImportError:
    print("ERROR: could not import auth_write.py. Run this script from the skill's scripts/ dir.")
    sys.exit(1)


# --- Constants --------------------------------------------------------------

TITLE_MAX_CHARS = 100          # YouTube hard limit
DESC_MAX_BYTES = 5000          # YouTube hard limit, measured in UTF-8 BYTES
MOBILE_TITLE_CUT = 45          # roughly what survives in mobile search results
MAX_UPDATES_PER_RUN = 50       # hard cap, refuses to run larger batches
UPDATE_COST_UNITS = 50         # videos.update quota cost, per video
LIST_COST_UNITS = 1            # videos.list / playlistItems.list / channels.list

# Only these snippet fields are writable. Everything else the API returns
# (publishedAt, channelId, thumbnails, channelTitle, localized,
# liveBroadcastContent) is read-only and is deliberately not echoed back.
WRITABLE_SNIPPET_FIELDS = (
    "title",
    "description",
    "tags",
    "categoryId",
    "defaultLanguage",
    "defaultAudioLanguage",
)

# Fields that must survive an update untouched.
PRESERVED_FIELDS = ("tags", "categoryId", "defaultLanguage", "defaultAudioLanguage")

REPORTS_DIR_DEFAULT = "reports"


# --- Small helpers ----------------------------------------------------------

def eprint(*args):
    print(*args, file=sys.stderr)


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def stamp():
    return datetime.now().strftime("%H%M%S")


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def ensure_dir(path):
    if path and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def save_json(path, payload):
    """Write JSON, exiting with a clear message if the write fails."""
    ensure_dir(os.path.dirname(path))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        eprint("ERROR: Could not write " + path + ": " + str(e))
        sys.exit(1)
    return path


def emit(payload, out_path=None):
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out_path:
        save_json(out_path, payload)
        print("Wrote " + out_path)
    else:
        print(text)


def byte_len(text):
    return len((text or "").encode("utf-8"))


def split_ids(raw):
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def first_n(text, n):
    return (text or "")[:n]


# --- Client / channel -------------------------------------------------------

def get_client():
    try:
        creds = get_credentials()
    except AuthError as exc:
        eprint("ERROR: " + str(exc))
        sys.exit(1)
    except RuntimeError as exc:  # scope refusal from auth_write
        eprint("ERROR: " + str(exc))
        sys.exit(1)
    return build("youtube", "v3", credentials=creds)


def get_channel(youtube):
    """
    Resolve the authenticated channel: id, title, uploads playlist.

    part="snippet,contentDetails" - never "status". 1 quota unit.
    Refreshes channel_write.json so ownership checks stay accurate.
    """
    try:
        resp = youtube.channels().list(part="snippet,contentDetails", mine=True).execute()
    except HttpError as e:
        eprint("ERROR: channels.list failed: " + str(e))
        sys.exit(1)
    items = resp.get("items", [])
    if not items:
        eprint("ERROR: this account has no YouTube channel. Re-run auth_write.py.")
        sys.exit(1)
    item = items[0]
    info = {
        "id": item.get("id", ""),
        "title": item.get("snippet", {}).get("title", ""),
        "uploads": item.get("contentDetails", {})
                       .get("relatedPlaylists", {})
                       .get("uploads", ""),
    }

    saved = load_channel()
    if saved and saved.get("channel_id") and saved["channel_id"] != info["id"]:
        eprint(
            "ERROR: the write token now controls channel " + info["id"] + " ("
            + info["title"] + ") but channel_write.json records "
            + saved["channel_id"] + ". Refusing to continue.\n"
            "If you intentionally switched channels: python3 scripts/auth_write.py --force"
        )
        sys.exit(1)
    save_channel(info["id"], info["title"])
    return info


def fetch_snippets(youtube, video_ids):
    """
    id -> snippet dict, in batches of 50. part="snippet" only (never "status").
    Missing/inaccessible IDs simply do not appear in the result.
    """
    out = {}
    for batch in chunks(video_ids, 50):
        try:
            resp = youtube.videos().list(part="snippet", id=",".join(batch)).execute()
        except HttpError as e:
            eprint("ERROR: videos.list failed: " + str(e))
            sys.exit(1)
        for item in resp.get("items", []):
            out[item["id"]] = item.get("snippet", {})
    return out


def fetch_snippets_and_stats(youtube, video_ids):
    """id -> {"snippet":..., "statistics":...} for the list subcommand."""
    out = {}
    for batch in chunks(video_ids, 50):
        try:
            resp = youtube.videos().list(
                part="snippet,statistics", id=",".join(batch)
            ).execute()
        except HttpError as e:
            eprint("ERROR: videos.list failed: " + str(e))
            sys.exit(1)
        for item in resp.get("items", []):
            out[item["id"]] = {
                "snippet": item.get("snippet", {}),
                "statistics": item.get("statistics", {}),
            }
    return out


def fetch_uploads(youtube, uploads_playlist, limit):
    """Video IDs from the uploads playlist, newest first. 1 unit per 50."""
    ids = []
    page = None
    calls = 0
    while len(ids) < limit:
        try:
            resp = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist,
                maxResults=min(50, limit - len(ids)),
                pageToken=page,
            ).execute()
        except HttpError as e:
            eprint("ERROR: playlistItems.list failed: " + str(e))
            sys.exit(1)
        calls += 1
        for item in resp.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                ids.append(vid)
        page = resp.get("nextPageToken")
        if not page:
            break
    return ids, calls


# --- The merge (the whole point of this script) -----------------------------

def merge_snippet(current, new_title=None, new_description=None):
    """
    Build the FULL snippet to send to videos.update.

    Starts from the freshly fetched current snippet, copies every writable field
    forward, and changes only title and/or description. categoryId is required
    by the API; tags are the field people lose when they get this wrong.
    """
    merged = {}
    for field in WRITABLE_SNIPPET_FIELDS:
        if field in current:
            merged[field] = copy.deepcopy(current[field])

    if new_title is not None:
        merged["title"] = new_title
    if new_description is not None:
        merged["description"] = new_description

    # Guarantees, asserted rather than assumed.
    if not merged.get("categoryId"):
        raise ValueError(
            "current snippet has no categoryId - refusing to update, the API "
            "would reject the call and a partial write is worse than none"
        )
    for field in PRESERVED_FIELDS:
        if current.get(field) != merged.get(field):
            raise ValueError("merge_snippet would have altered preserved field: " + field)
    if "description" not in merged:
        merged["description"] = ""
    if not merged.get("title"):
        raise ValueError("merged snippet has an empty title - refusing to update")
    return merged


# --- Validation -------------------------------------------------------------

def validate_entry(entry, current, channel_id):
    """Return a list of human-readable errors. Empty list == safe to apply."""
    errors = []
    vid = entry.get("videoId")

    if not vid:
        return ["entry has no videoId"]
    if current is None:
        return ["video " + vid + " not found, or not visible to this account"]
    if channel_id and current.get("channelId") and current["channelId"] != channel_id:
        errors.append(
            "video belongs to channel " + current["channelId"]
            + ", not the authenticated channel " + channel_id
        )

    new_title = entry.get("new_title")
    new_desc = entry.get("new_description")

    if new_title is None and new_desc is None:
        errors.append("entry changes nothing: needs new_title and/or new_description")

    if new_title is not None:
        if not isinstance(new_title, str):
            errors.append("new_title must be a string")
        elif not new_title.strip():
            errors.append("new_title is empty")
        else:
            if len(new_title) > TITLE_MAX_CHARS:
                errors.append(
                    "new_title is " + str(len(new_title)) + " chars, limit is "
                    + str(TITLE_MAX_CHARS)
                )
            if "<" in new_title or ">" in new_title:
                errors.append("new_title contains < or > - YouTube rejects angle brackets")

    if new_desc is not None:
        if not isinstance(new_desc, str):
            errors.append("new_description must be a string")
        else:
            nbytes = byte_len(new_desc)
            if nbytes > DESC_MAX_BYTES:
                errors.append(
                    "new_description is " + str(nbytes) + " UTF-8 bytes, limit is "
                    + str(DESC_MAX_BYTES)
                )
            if "<" in new_desc or ">" in new_desc:
                errors.append("new_description contains < or > - YouTube rejects angle brackets")

    return errors


def is_noop(entry, current):
    """True when nothing would actually change."""
    if current is None:
        return False
    title_same = entry.get("new_title") is None or entry.get("new_title") == current.get("title")
    desc_same = (
        entry.get("new_description") is None
        or entry.get("new_description") == current.get("description")
    )
    return title_same and desc_same


# --- Plan loading -----------------------------------------------------------

def load_plan(path):
    """
    Accept either a bare JSON array of entries, or an object with an "entries"
    key - which means the file this script writes from `preview` can be fed
    straight back into `apply`.
    """
    if not os.path.isfile(path):
        eprint("ERROR: plan file not found: " + path)
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, IOError, OSError) as e:
        eprint("ERROR: could not read plan " + path + ": " + str(e))
        sys.exit(1)

    if isinstance(data, dict):
        data = data.get("entries")
    if not isinstance(data, list):
        eprint("ERROR: plan must be a JSON array of {videoId, new_title?, new_description?, reason?}")
        sys.exit(1)

    entries = []
    for raw in data:
        if not isinstance(raw, dict):
            eprint("ERROR: every plan entry must be an object")
            sys.exit(1)
        entries.append({
            "videoId": raw.get("videoId") or raw.get("video_id"),
            "new_title": raw.get("new_title"),
            "new_description": raw.get("new_description"),
            "reason": raw.get("reason"),
            # Written by `preview`; lets `apply` detect drift since the user
            # looked at the diff.
            "expected_current_title": raw.get("expected_current_title") or raw.get("current_title"),
        })
    return entries


# --- Preview ----------------------------------------------------------------

def build_preview(youtube, entries, channel, plan_path=None):
    ids = [e["videoId"] for e in entries if e.get("videoId")]
    current_by_id = fetch_snippets(youtube, ids) if ids else {}

    out_entries = []
    n_ok = n_err = n_noop = 0

    for entry in entries:
        vid = entry.get("videoId")
        current = current_by_id.get(vid)
        errors = validate_entry(entry, current, channel["id"])

        cur_title = (current or {}).get("title")
        cur_desc = (current or {}).get("description")
        new_title = entry.get("new_title")
        new_desc = entry.get("new_description")

        if errors:
            status = "error"
            n_err += 1
        elif is_noop(entry, current):
            status = "no-op"
            n_noop += 1
        else:
            status = "ok"
            n_ok += 1

        row = {
            "videoId": vid,
            "status": status,
            "errors": errors,
            "reason": entry.get("reason"),
            "current_title": cur_title,
            "new_title": new_title,
            "title_change": bool(new_title is not None and new_title != cur_title),
            # What survives the mobile-search truncation - the keyword has to be
            # inside this window or search users never see it.
            "truncation_check": {
                "cut_at_chars": MOBILE_TITLE_CUT,
                "current_first_45": first_n(cur_title, MOBILE_TITLE_CUT),
                "new_first_45": first_n(new_title, MOBILE_TITLE_CUT) if new_title is not None else None,
                "new_title_truncated": bool(new_title is not None and len(new_title) > MOBILE_TITLE_CUT),
            },
            "description_change": bool(new_desc is not None and new_desc != cur_desc),
            "current_description_first_150": first_n(cur_desc, 150),
            "new_description_first_150": first_n(new_desc, 150) if new_desc is not None else None,
            "new_description": new_desc,
            "lengths": {
                "current_title_chars": len(cur_title) if cur_title is not None else None,
                "new_title_chars": len(new_title) if new_title is not None else None,
                "current_description_bytes": byte_len(cur_desc) if cur_desc is not None else None,
                "new_description_bytes": byte_len(new_desc) if new_desc is not None else None,
            },
            "preserved": {
                "tags_count": len((current or {}).get("tags", []) or []),
                "categoryId": (current or {}).get("categoryId"),
                "defaultLanguage": (current or {}).get("defaultLanguage"),
                "defaultAudioLanguage": (current or {}).get("defaultAudioLanguage"),
            },
            # Round-trips into apply for drift detection.
            "expected_current_title": cur_title,
        }
        out_entries.append(row)

    return {
        "generated_at": now_iso(),
        "plan_file": plan_path,
        "channel": {"id": channel["id"], "title": channel["title"]},
        "counts": {
            "total": len(out_entries),
            "applicable": n_ok,
            "errors": n_err,
            "no_ops": n_noop,
        },
        "limits": {
            "title_max_chars": TITLE_MAX_CHARS,
            "description_max_bytes": DESC_MAX_BYTES,
            "max_updates_per_run": MAX_UPDATES_PER_RUN,
        },
        "quota": {
            "videos_update_units_each": UPDATE_COST_UNITS,
            "estimated_units_if_applied": n_ok * UPDATE_COST_UNITS,
            "daily_budget_units": 10000,
        },
        "entries": out_entries,
    }


def print_preview_table(preview):
    """Compact human summary. The full diff lives in the JSON."""
    print("Channel: " + preview["channel"]["title"] + " (" + preview["channel"]["id"] + ")")
    c = preview["counts"]
    print(
        "Entries: " + str(c["total"]) + "  applicable: " + str(c["applicable"])
        + "  errors: " + str(c["errors"]) + "  no-ops: " + str(c["no_ops"])
    )
    print("Estimated quota if applied: " + str(preview["quota"]["estimated_units_if_applied"]) + " units")
    print()
    for row in preview["entries"]:
        print(row["videoId"] + "  [" + row["status"] + "]")
        print("  now : " + (row["current_title"] or "-"))
        if row["new_title"] is not None:
            print("  new : " + row["new_title"] + "  (" + str(row["lengths"]["new_title_chars"]) + " chars)")
            print("  45ch: " + row["truncation_check"]["new_first_45"]
                  + ("..." if row["truncation_check"]["new_title_truncated"] else ""))
        if row["description_change"]:
            print("  desc: rewritten (" + str(row["lengths"]["new_description_bytes"]) + " bytes)")
        if row["reason"]:
            print("  why : " + row["reason"])
        for err in row["errors"]:
            print("  ERR : " + err)
        print()


# --- Backups ----------------------------------------------------------------

def backup_dir(reports_dir, day=None):
    return os.path.join(reports_dir, "backups", "metadata-" + (day or today_str()))


def write_backup(reports_dir, video_id, snippet, kind="pre-edit"):
    """
    Write the complete pre-edit snippet. Never overwrites an existing backup:
    a second edit on the same day lands beside the first, so the original is
    always recoverable.

    kind="pre-revert" backups are written before a revert and are excluded from
    revert's own candidate search, so reverting twice cannot ping-pong a video
    back to the edited title.
    """
    d = backup_dir(reports_dir)
    ensure_dir(d)
    if kind == "pre-revert":
        path = os.path.join(d, video_id + "-pre-revert-" + stamp() + ".json")
    else:
        path = os.path.join(d, video_id + ".json")
        if os.path.exists(path):
            path = os.path.join(d, video_id + "-" + stamp() + ".json")
    payload = {
        "videoId": video_id,
        "backed_up_at": now_iso(),
        "kind": kind,
        "snippet": snippet,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        raise IOError("could not write backup " + path + ": " + str(e))
    return path


def find_backup(reports_dir, video_id, day=None):
    """
    Most recent pre-edit backup for a video, or the one from --date.
    Returns (path, payload) or (None, None).
    """
    root = os.path.join(reports_dir, "backups")
    if not os.path.isdir(root):
        return None, None

    if day:
        dirs = [os.path.join(root, "metadata-" + day)]
    else:
        dirs = sorted(
            (os.path.join(root, n) for n in os.listdir(root) if n.startswith("metadata-")),
            reverse=True,
        )

    for d in dirs:
        if not os.path.isdir(d):
            continue
        candidates = [
            os.path.join(d, n) for n in os.listdir(d)
            if n.endswith(".json")
            and (n == video_id + ".json" or n.startswith(video_id + "-"))
            and "-pre-revert-" not in n
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        path = candidates[0]
        try:
            with open(path, "r", encoding="utf-8") as f:
                return path, json.load(f)
        except (ValueError, IOError, OSError):
            continue
    return None, None


# --- Writes -----------------------------------------------------------------

def do_update(youtube, video_id, merged_snippet):
    """The single write call in this suite. 50 quota units."""
    return youtube.videos().update(
        part="snippet",
        body={"id": video_id, "snippet": merged_snippet},
    ).execute()


# --- Subcommands ------------------------------------------------------------

def cmd_list(args):
    youtube = get_client()
    channel = get_channel(youtube)
    ids, pl_calls = fetch_uploads(youtube, channel["uploads"], args.limit)
    data = fetch_snippets_and_stats(youtube, ids)

    videos = []
    for vid in ids:
        rec = data.get(vid)
        if not rec:
            continue
        snip = rec["snippet"]
        stats = rec["statistics"]
        videos.append({
            "videoId": vid,
            "published_at": snip.get("publishedAt", ""),
            "views": int(stats.get("viewCount", 0) or 0),
            "title": snip.get("title", ""),
            "title_chars": len(snip.get("title", "")),
            "description_bytes": byte_len(snip.get("description", "")),
            "tags_count": len(snip.get("tags", []) or []),
            "categoryId": snip.get("categoryId"),
        })

    units = LIST_COST_UNITS * (1 + pl_calls + (len(ids) + 49) // 50)
    payload = {
        "generated_at": now_iso(),
        "channel": {"id": channel["id"], "title": channel["title"]},
        "count": len(videos),
        "quota_units_used": units,
        "videos": videos,
    }
    out = os.path.join(args.reports_dir, "data", "metadata-videos-" + today_str() + ".json")
    save_json(out, payload)

    print(channel["title"] + " - " + str(len(videos)) + " uploads (newest first)")
    print()
    print("VIDEO ID      PUBLISHED    VIEWS       TITLE")
    for v in videos:
        print(
            v["videoId"].ljust(13)
            + v["published_at"][:10].ljust(13)
            + str(v["views"]).rjust(9) + "   "
            + v["title"]
        )
    print()
    print("Wrote " + out + "  (" + str(units) + " quota units)")
    return 0


def cmd_get(args):
    youtube = get_client()
    channel = get_channel(youtube)
    ids = split_ids(args.videos)
    if not ids:
        eprint("ERROR: --videos requires at least one video ID")
        return 1
    snippets = fetch_snippets(youtube, ids)

    videos = []
    for vid in ids:
        snip = snippets.get(vid)
        if snip is None:
            videos.append({"videoId": vid, "error": "not found or not accessible"})
            continue
        videos.append({
            "videoId": vid,
            "owned_by_this_channel": snip.get("channelId") == channel["id"],
            "published_at": snip.get("publishedAt"),
            "title": snip.get("title"),
            "title_chars": len(snip.get("title", "")),
            "title_first_45": first_n(snip.get("title"), MOBILE_TITLE_CUT),
            "description": snip.get("description"),
            "description_bytes": byte_len(snip.get("description", "")),
            "description_first_150": first_n(snip.get("description"), 150),
            "tags": snip.get("tags", []),
            "categoryId": snip.get("categoryId"),
            "defaultLanguage": snip.get("defaultLanguage"),
            "defaultAudioLanguage": snip.get("defaultAudioLanguage"),
        })

    emit({
        "generated_at": now_iso(),
        "channel": {"id": channel["id"], "title": channel["title"]},
        "videos": videos,
    }, args.out)
    return 0


def cmd_preview(args):
    youtube = get_client()
    channel = get_channel(youtube)
    entries = load_plan(args.plan)
    preview = build_preview(youtube, entries, channel, plan_path=args.plan)

    out = args.out or os.path.join(
        args.reports_dir, "data", "metadata-preview-" + today_str() + ".json"
    )
    save_json(out, preview)
    print_preview_table(preview)
    print("Preview written to " + out)
    print("Nothing has been changed. This file is itself a valid --plan for `apply`.")
    return 0


def cmd_apply(args):
    youtube = get_client()
    channel = get_channel(youtube)
    entries = load_plan(args.plan)
    preview = build_preview(youtube, entries, channel, plan_path=args.plan)

    if not args.confirm:
        preview_out = args.out or os.path.join(
            args.reports_dir, "data", "metadata-preview-" + today_str() + ".json"
        )
        save_json(preview_out, preview)
        print_preview_table(preview)
        print("Preview written to " + preview_out)
        print()
        print("WARNING: --confirm was not passed. NOTHING WAS WRITTEN.")
        print("Show this diff to the user, get explicit approval, then re-run with --confirm.")
        return 0

    expected_by_id = {}
    for e in entries:
        if e.get("videoId") and e.get("expected_current_title") is not None:
            expected_by_id[e["videoId"]] = e["expected_current_title"]

    applicable = [row for row in preview["entries"] if row["status"] == "ok"]
    if not applicable:
        print("No applicable entries (all were errors or no-ops). Nothing written.")
        save_json(
            os.path.join(args.reports_dir, "data", "metadata-apply-" + today_str() + ".json"),
            {"generated_at": now_iso(), "results": [], "preview": preview},
        )
        return 1

    if len(applicable) > MAX_UPDATES_PER_RUN:
        eprint(
            "ERROR: " + str(len(applicable)) + " updates requested, hard cap is "
            + str(MAX_UPDATES_PER_RUN) + " per run. Split the plan."
        )
        return 1

    by_id = {e["videoId"]: e for e in entries if e.get("videoId")}
    results = []
    units = 0
    aborted = None

    for row in applicable:
        vid = row["videoId"]
        entry = by_id.get(vid, {})

        # (1) Re-fetch the live snippet immediately before writing.
        fresh = fetch_snippets(youtube, [vid]).get(vid)
        units += LIST_COST_UNITS
        if fresh is None:
            results.append({"videoId": vid, "status": "failed",
                            "error": "video disappeared between preview and apply"})
            continue

        # Drift guard: if the title moved since the user saw the diff, skip it.
        expected = expected_by_id.get(vid, row.get("expected_current_title"))
        if expected is not None and fresh.get("title") != expected:
            results.append({
                "videoId": vid,
                "status": "skipped",
                "error": "changed since preview",
                "expected_title": expected,
                "actual_title": fresh.get("title"),
            })
            continue

        # (2) Backup BEFORE the write. A failure here aborts the whole run.
        try:
            backup_path = write_backup(args.reports_dir, vid, fresh, kind="pre-edit")
        except IOError as e:
            aborted = "backup failed for " + vid + ": " + str(e)
            results.append({"videoId": vid, "status": "aborted", "error": str(e)})
            break

        # (3) Merge and write.
        try:
            merged = merge_snippet(fresh, entry.get("new_title"), entry.get("new_description"))
        except ValueError as e:
            results.append({"videoId": vid, "status": "failed", "error": str(e),
                            "backup": backup_path})
            continue

        try:
            do_update(youtube, vid, merged)
            units += UPDATE_COST_UNITS
        except HttpError as e:
            results.append({"videoId": vid, "status": "failed", "error": str(e),
                            "backup": backup_path})
            continue

        results.append({
            "videoId": vid,
            "status": "updated",
            "backup": backup_path,
            "old_title": fresh.get("title"),
            "new_title": merged["title"],
            "title_changed": merged["title"] != fresh.get("title"),
            "description_changed": merged.get("description") != fresh.get("description"),
            "tags_preserved": len(merged.get("tags", []) or []),
            "categoryId": merged.get("categoryId"),
            "reason": entry.get("reason"),
        })

    n_ok = sum(1 for r in results if r["status"] == "updated")
    run = {
        "generated_at": now_iso(),
        "channel": {"id": channel["id"], "title": channel["title"]},
        "plan_file": args.plan,
        "aborted": aborted,
        "counts": {
            "attempted": len(applicable),
            "updated": n_ok,
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "failed": sum(1 for r in results if r["status"] in ("failed", "aborted")),
        },
        "quota": {
            "videos_update_units_each": UPDATE_COST_UNITS,
            "units_used": units,
            "daily_budget_units": 10000,
        },
        "backup_dir": backup_dir(args.reports_dir),
        "revert_command": (
            "python3 scripts/update_metadata.py revert --videos "
            + ",".join(r["videoId"] for r in results if r["status"] == "updated")
            + " --date " + today_str() + " --confirm"
        ) if n_ok else None,
        "results": results,
    }

    out = os.path.join(args.reports_dir, "data", "metadata-apply-" + today_str() + ".json")
    if os.path.exists(out):
        out = os.path.join(
            args.reports_dir, "data", "metadata-apply-" + today_str() + "-" + stamp() + ".json"
        )
    save_json(out, run)

    for r in results:
        line = r["videoId"] + "  " + r["status"]
        if r.get("new_title"):
            line += "  -> " + r["new_title"]
        if r.get("error"):
            line += "  (" + r["error"] + ")"
        print(line)
    print()
    print("Updated " + str(n_ok) + "/" + str(len(applicable)) + " videos, "
          + str(units) + " quota units used (videos.update costs "
          + str(UPDATE_COST_UNITS) + " units each).")
    print("Backups : " + backup_dir(args.reports_dir))
    print("Run log : " + out)
    if run["revert_command"]:
        print("Revert  : " + run["revert_command"])
    if aborted:
        eprint("ABORTED: " + aborted)
        return 1
    return 0 if n_ok else 1


def cmd_revert(args):
    youtube = get_client()
    channel = get_channel(youtube)
    ids = split_ids(args.videos)
    if not ids:
        eprint("ERROR: --videos requires at least one video ID")
        return 1

    plan_rows = []
    for vid in ids:
        path, backup = find_backup(args.reports_dir, vid, args.date)
        if backup is None:
            plan_rows.append({"videoId": vid, "status": "no-backup",
                              "error": "no backup found"
                                       + (" for " + args.date if args.date else "")})
            continue
        snap = backup.get("snippet", {})
        plan_rows.append({
            "videoId": vid,
            "status": "ready",
            "backup_file": path,
            "backed_up_at": backup.get("backed_up_at"),
            "restore_title": snap.get("title"),
            "restore_description_bytes": byte_len(snap.get("description", "")),
            "restore_description": snap.get("description"),
        })

    if not args.confirm:
        for row in plan_rows:
            print(row["videoId"] + "  [" + row["status"] + "]")
            if row.get("restore_title"):
                print("  would restore title: " + row["restore_title"])
                print("  from: " + row["backup_file"])
            if row.get("error"):
                print("  ERR : " + row["error"])
        print()
        print("WARNING: --confirm was not passed. NOTHING WAS WRITTEN.")
        return 0

    ready = [r for r in plan_rows if r["status"] == "ready"]
    if len(ready) > MAX_UPDATES_PER_RUN:
        eprint("ERROR: " + str(len(ready)) + " reverts requested, hard cap is "
               + str(MAX_UPDATES_PER_RUN) + " per run.")
        return 1

    results = [r for r in plan_rows if r["status"] != "ready"]
    units = 0
    aborted = None

    for row in ready:
        vid = row["videoId"]
        fresh = fetch_snippets(youtube, [vid]).get(vid)
        units += LIST_COST_UNITS
        if fresh is None:
            results.append({"videoId": vid, "status": "failed",
                            "error": "video not found or not accessible"})
            continue
        if fresh.get("channelId") and fresh["channelId"] != channel["id"]:
            results.append({"videoId": vid, "status": "failed",
                            "error": "video does not belong to the authenticated channel"})
            continue

        # Same discipline as apply: back up the CURRENT state before overwriting it.
        try:
            pre = write_backup(args.reports_dir, vid, fresh, kind="pre-revert")
        except IOError as e:
            aborted = "backup failed for " + vid + ": " + str(e)
            results.append({"videoId": vid, "status": "aborted", "error": str(e)})
            break

        try:
            merged = merge_snippet(fresh, row.get("restore_title"), row.get("restore_description"))
            do_update(youtube, vid, merged)
            units += UPDATE_COST_UNITS
        except (ValueError, HttpError) as e:
            results.append({"videoId": vid, "status": "failed", "error": str(e),
                            "backup": pre})
            continue

        results.append({
            "videoId": vid,
            "status": "reverted",
            "restored_from": row["backup_file"],
            "pre_revert_backup": pre,
            "title_now": merged["title"],
        })

    n_ok = sum(1 for r in results if r["status"] == "reverted")
    run = {
        "generated_at": now_iso(),
        "channel": {"id": channel["id"], "title": channel["title"]},
        "aborted": aborted,
        "counts": {"attempted": len(ready), "reverted": n_ok},
        "quota": {"units_used": units, "videos_update_units_each": UPDATE_COST_UNITS},
        "results": results,
    }
    out = os.path.join(
        args.reports_dir, "data", "metadata-revert-" + today_str() + "-" + stamp() + ".json"
    )
    save_json(out, run)

    for r in results:
        line = r["videoId"] + "  " + r["status"]
        if r.get("title_now"):
            line += "  -> " + r["title_now"]
        if r.get("error"):
            line += "  (" + r["error"] + ")"
        print(line)
    print()
    print("Reverted " + str(n_ok) + "/" + str(len(ready)) + " videos, " + str(units) + " quota units.")
    print("Run log : " + out)
    if aborted:
        eprint("ABORTED: " + aborted)
        return 1
    return 0 if n_ok else 1


# --- CLI --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Update YouTube video titles and descriptions on your own channel. "
            "Titles and descriptions only - never privacy, thumbnails, playlists, or deletes."
        )
    )
    parser.add_argument("--reports-dir", default=REPORTS_DIR_DEFAULT,
                        help="Root output directory (default: reports)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List the channel's uploads (id, date, views, title)")
    p_list.add_argument("--limit", type=int, default=50,
                        help="How many recent uploads to list (default: 50)")

    p_get = sub.add_parser("get", help="Full current snippet for specific videos")
    p_get.add_argument("--videos", required=True, help="Comma-separated video IDs")
    p_get.add_argument("--out", help="Write JSON here instead of stdout")

    p_prev = sub.add_parser("preview", help="Show the old -> new diff for a plan. Writes nothing.")
    p_prev.add_argument("--plan", required=True, help="Path to the plan JSON")
    p_prev.add_argument("--out", help="Where to write the preview JSON")

    p_apply = sub.add_parser("apply", help="Apply a plan. Requires --confirm to write anything.")
    p_apply.add_argument("--plan", required=True, help="Path to the plan JSON")
    p_apply.add_argument("--confirm", action="store_true",
                         help="Actually write. Without it this behaves exactly like preview.")
    p_apply.add_argument("--out", help="Where to write the preview JSON when not confirming")

    p_rev = sub.add_parser("revert", help="Restore title+description from the most recent backup")
    p_rev.add_argument("--videos", required=True, help="Comma-separated video IDs")
    p_rev.add_argument("--date", help="Use backups from this YYYY-MM-DD instead of the newest")
    p_rev.add_argument("--confirm", action="store_true",
                       help="Actually write. Without it this only reports what would change.")

    args = parser.parse_args()

    if args.command == "list":
        return cmd_list(args)
    if args.command == "get":
        return cmd_get(args)
    if args.command == "preview":
        return cmd_preview(args)
    if args.command == "apply":
        return cmd_apply(args)
    if args.command == "revert":
        return cmd_revert(args)
    eprint("Unknown command: " + str(args.command))
    return 1


if __name__ == "__main__":
    sys.exit(main())
