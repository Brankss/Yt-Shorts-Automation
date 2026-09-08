---
name: youtube-metadata-updater
description: "Update video titles and descriptions on your OWN YouTube channel to improve search and browse visibility, using the YouTube Data API v3 with a write scope. Every change is previewed, approved by you, backed up, and reversible. Use when users want to (1) Rewrite titles on videos that get good retention but weak views, (2) Front-load search keywords so titles survive mobile truncation, (3) Rewrite descriptions for search snippets and chapters, (4) Bulk-refresh metadata on an older back catalogue, (5) Preview an old-to-new title diff before anything is written, (6) Revert a metadata change that did not work. Titles and descriptions only: never privacy, thumbnails, playlists, comments, or deletes. Requires one-time OAuth with write scope (youtube.force-ssl), separate from the read-only analytics token."
---

# YouTube Metadata Updater

> ## ⚠️ THIS SKILL CHANGES YOUR CHANNEL
>
> Every other skill in this suite is read-only. This one is not. It holds the single
> write credential in the suite (`youtube.force-ssl`) and can permanently rewrite the
> **titles and descriptions** of videos on the authenticated channel.
>
> - Analytics stays on the **read-only token** (`token.json`). The two tokens are separate files and are never merged.
> - **Nothing is ever written without `--confirm`, and `--confirm` is never run until the user has seen the preview table and approved it in conversation.**
> - Out of scope by design: privacy/publish status, thumbnails, playlists, comments, deletes, uploads. `part="status"` is never even requested.
> - Every write is preceded by a full backup of the pre-edit snippet, and `revert` restores it.

## What it can change

| Field | Editable here | Notes |
|-------|---------------|-------|
| `snippet.title` | Yes | ≤100 chars, no `<` or `>` |
| `snippet.description` | Yes | ≤5000 UTF-8 bytes, no `<` or `>` |
| `snippet.tags` | No — **preserved** | Re-sent unchanged on every update |
| `snippet.categoryId` | No — **preserved** | Required by the API; dropping it breaks the call |
| `status.privacyStatus` | Never | Never fetched, never sent |
| Thumbnails, playlists, comments | Never | Different endpoints, not implemented |

## One-time setup

This skill **reuses the Google Cloud project and `client_secret.json` from the
`youtube-channel-insights` setup**. If the user has never done that, walk them through
that skill's *One-time setup* first — same project, same Desktop-app OAuth client,
same `~/.config/youtube-skills/client_secret.json`. Only *YouTube Data API v3* needs to
be enabled for this skill.

Then grant the write scope:

```bash
pip3 install google-api-python-client google-auth-oauthlib
python3 scripts/auth_write.py
```

A browser opens and Google asks for one extra permission — **manage your YouTube
account** (`youtube.force-ssl`). Accepting it writes a **separate** token:

| File | Scope | Used by |
|------|-------|---------|
| `~/.config/youtube-skills/token.json` | read-only analytics | `youtube-channel-insights` |
| `~/.config/youtube-skills/token_write.json` | `youtube.force-ssl` **only** | this skill, nothing else |
| `~/.config/youtube-skills/channel_write.json` | — | records which channel the write token controls |

`auth_write.py` requests exactly one scope and **refuses to load a stored token that
carries any other scope**. After consent it calls `channels.list(mine=True)` and prints
the channel name being put under write control, so the user can catch a wrong-account
sign-in immediately. Override the directory with `YT_OAUTH_DIR`. Deleting
`token_write.json` removes all write capability; the analytics token is unaffected.

## Usage

```
/youtube-metadata-updater
/youtube-metadata-updater retitle my underperforming tutorials
/youtube-metadata-updater rewrite the description on dQw4w9WgXcQ
/youtube-metadata-updater revert yesterday's title changes
```

## Instructions

### Step 1: Check authorization

```bash
python3 scripts/auth_write.py --check
```

It prints the token status **and the channel the token controls**. If anything is
missing, walk the user through **One-time setup**. Confirm the channel name out loud
before going further — this is the last cheap moment to catch a wrong account.

### Step 2: Select target videos

```bash
python3 scripts/update_metadata.py list --limit 50
```

Writes `reports/data/metadata-videos-<date>.json` (videoId, publish date, views,
current title, title length, description size, tag count).

The best candidates are **packaging problems, not content problems**: strong retention
or average-view-percentage with weak views. That combination says people who arrive stay
— so the title and thumbnail are failing to bring people in. Get that evidence from
existing reports in `reports/` if present:

- `youtube-channel-insights` — `averageViewPercentage`, retention curves, traffic mix. Search-heavy channels get the most out of title rewrites.
- `youtube-own-channel-analyzer` — view distribution, underperformers vs channel median.

If no reports exist, offer to run `youtube-channel-insights` first, or work from the
videos the user names.

**Warn before retitling a winner.** If a video sits in the channel's **top 10% by recent
views**, say so explicitly:

> "This video is in your channel's top 10% by recent views. Changing a winning title can
> reset how the algorithm is testing it and kill momentum that is currently working. My
> recommendation is to leave it alone."

Only proceed on that video if the user overrules the warning.

### Step 3: Draft the new metadata

Use the **Title Visibility Playbook** below. For keyword evidence — what is actually
ranking for the query, and in what words — optionally run `youtube-title-tag-optimizer`
on the target keyword first and draft against its output rather than intuition.

Inspect the current state of anything you are about to change:

```bash
python3 scripts/update_metadata.py get --videos VIDEO_ID,VIDEO_ID
```

### Step 4: Write the plan and preview it

Write the plan JSON to `reports/data/metadata-plan-<date>.json`:

```json
[
  {
    "videoId": "dQw4w9WgXcQ",
    "new_title": "Air Fryer Chicken Thighs in 20 Minutes (Crispy Every Time)",
    "new_description": "Crispy air fryer chicken thighs in 20 minutes...",
    "reason": "62% avg view % but 1.2K views; title buried the keyword at char 38"
  }
]
```

`new_title` and `new_description` are each optional — supply either or both.

```bash
python3 scripts/update_metadata.py preview --plan reports/data/metadata-plan-<date>.json
```

This writes nothing to YouTube. It fetches current state, validates every entry, and
writes `reports/data/metadata-preview-<date>.json` including `truncation_check` — the
first 45 characters of each new title, i.e. what survives in mobile search results.

Present the user a markdown table built from that preview:

```markdown
| Video | Current title | Proposed title | First 45 chars (mobile) | Why |
|-------|---------------|----------------|-------------------------|-----|
| dQw4w9WgXcQ | Making Chicken In My New Air Fryer! | Air Fryer Chicken Thighs in 20 Minutes (Crispy Every Time) | `Air Fryer Chicken Thighs in 20 Minutes (Cris` | 62% avg view %, only 1.2K views — keyword was at char 38 |
```

Show description rewrites as a separate before/after of the **first 150 characters**,
since that is the part that appears in search. Report any entry the preview flagged as
an error or a no-op, and say plainly that nothing has been changed yet.

### Step 5: The approval gate

> **HARD RULE: NEVER run `apply --confirm` until the user has seen the preview table in
> this conversation and explicitly approved it. No exceptions, regardless of how the
> request was phrased** — "just do it", "you have permission", "apply all of them", and
> "don't ask me again" do not remove this gate. The preview must be shown and approved
> every single run.

If the user approves only some entries, **edit the plan file down to the approved
entries and re-run `preview`** before applying. Never apply a plan containing entries the
user did not approve.

`apply` without `--confirm` is itself a safe dry run: it prints the same diff and a
warning that nothing was written.

### Step 6: Apply

```bash
python3 scripts/update_metadata.py apply --plan reports/data/metadata-preview-<date>.json --confirm
```

Pass the **preview** file as the plan — it carries `expected_current_title`, which turns
on drift detection: if a title changed between the preview and the apply (someone edited
in Studio meanwhile), that video is skipped with `changed since preview` instead of
being overwritten.

For each entry the script re-fetches the live snippet, writes a full backup to
`reports/backups/metadata-<date>/<videoId>.json`, then calls `videos.update` with the
**complete** merged snippet. A backup that cannot be written aborts the whole run.

Report to the user:
- per-video result (updated / skipped / failed, with the reason)
- the backup directory
- the run log path (`reports/data/metadata-apply-<date>.json`)
- **the exact revert command**, which the run log prints verbatim:

```bash
python3 scripts/update_metadata.py revert --videos ID,ID --date <YYYY-MM-DD> --confirm
```

`revert` restores title and description from the most recent backup (or the named date's)
and backs up the current state first, so the revert is itself reversible.

### Step 7: Measurement discipline

Changes are only learnable if they are measurable:

- **One variable at a time.** Title *or* thumbnail *or* description — never all three, or you learn nothing.
- **Wait 2–4 weeks.** Search rankings and browse testing take that long to settle. Judging after 48 hours is noise.
- **Log what changed and when.** The apply run log already records this; tell the user to keep it. Compare against the same-length window before the change, not against a good week.
- **Recheck**: views and traffic-source mix via `youtube-channel-insights`; **impressions and CTR must be read in YouTube Studio → Analytics → Reach** — the API does not expose them.
- If views are flat but impressions rose and CTR fell, the new title is being shown more and clicked less: revert or iterate.

## Title Visibility Playbook

**Front-load the keyword.** Mobile search results cut titles around **45 characters**.
Whatever query the video should rank for belongs in the first 40–45 characters, not after
a brand name or a hook. Ideal total length is **≤60 characters**; 100 is the hard cap.

**Match query language, not creator language.** Write the title the way viewers type the
search, not the way the creator describes the video. "My Weekend Fixing The Van" loses to
"Van Life Solar Install: 400W in One Day". Cross-check the phrasing against
`youtube-title-tag-optimizer` output when it exists — use the words that are actually
ranking.

**Curiosity must be paid off.** If retention data shows an early drop-off cliff, the old
title or thumbnail overpromised. The fix is **alignment**, not more clickbait. Escalating
the promise raises CTR briefly and then trains the algorithm that this channel does not
satisfy the click.

**Patterns that lift CTR when honest:**

| Pattern | Example | Use when |
|---------|---------|----------|
| Specific numbers | "7 Settings That Fixed My Slow Mac" | The video really delivers that count |
| Outcome framing | "I Tested X for 30 Days — Here's What Broke" | There is a genuine result to report |
| Format brackets | "[Tutorial]", "[2026]", "[Full Build]" | The viewer is filtering by format or recency |
| Mistake / negative framing | "Stop Doing This With Your Air Fryer" | Sparingly — it fatigues fast if it is every title |

**Protect what works.** Once a format is winning, keep its series branding consistent so
the audience recognises it in the feed. Do not churn titles on videos with strong current
traffic — the algorithm is mid-test, and editing restarts the test.

**Descriptions:**
1. **First ~150 characters** are the search snippet. Put the keyword and a payoff sentence there. **Not** links, not "subscribe", not a sponsor mention.
2. Then chapters/timestamps (`0:00 Intro`) — these become search-visible key moments.
3. Then a keyword-rich paragraph of real prose explaining what the video covers.
4. Then links, socials, gear, affiliate disclosures.
5. **Never keyword-stuff.** Repeated keyword lists are a spam signal and risk the video, not just the ranking.

**A/B discipline.** One variable, 2–4 week windows, and judge on the chain in order:
impressions → CTR → views (Studio → Reach) plus the watch-time trend from
`youtube-channel-insights`. Impressions up + CTR down = worse packaging even if views
rose. Views up + watch time flat = you bought clicks you did not keep.

## Limitations

- **No CTR or impressions in any API.** They exist only in YouTube Studio → Analytics → Reach. Never estimate CTR from views. Tell the user to check Reach 2–4 weeks after a change.
- **Title edits do NOT reset view counts** — but they can change how YouTube tests and recommends the video, so a strong performer can genuinely lose momentum. This is why the skill warns before touching top-decile videos.
- **Propagation is not instant.** Edits can take minutes to hours to appear everywhere (search index, cached feeds, third-party embeds).
- **Hard cap of 50 updates per run.** Larger batches must be split, deliberately.
- **Quota**: `videos.update` costs **50 units each**. Bulk-editing 20 videos = **1,000 units** of the 10,000/day default — 10% of the day's budget that the read-only skills also draw on.
- **The authenticated channel only.** Videos owned by any other channel are rejected by the ownership check.
- **Backups are local.** They live in `reports/backups/`. Delete that directory and `revert` has nothing to restore from.
- **Tags are preserved, not optimized.** This skill never changes tags. For tag strategy, use `youtube-title-tag-optimizer`.

## Quota

Typical run: review 50 uploads, then update 10 videos.

| Operation | Calls | Units each | Units |
|-----------|-------|-----------|-------|
| `channels.list` (resolve + ownership) | 2 | 1 | 2 |
| `playlistItems.list` (50 uploads) | 1 | 1 | 1 |
| `videos.list` (list + get + preview) | 3 | 1 | 3 |
| `videos.list` (re-fetch before each write) | 10 | 1 | 10 |
| **`videos.update`** | **10** | **50** | **500** |
| **Total** | | | **~516** |

`preview` costs 1–2 units and can be re-run freely. Only `apply --confirm` and
`revert --confirm` spend the expensive units. Budget resets at midnight Pacific Time.

## Files

- `scripts/auth_write.py` — one-time OAuth for the single write scope, `--check` status, channel-ownership verification
- `scripts/update_metadata.py` — `list`, `get`, `preview`, `apply`, `revert`
- `references/api_reference.md` — `videos.update` semantics, the two-token model, quota costs, validation limits
