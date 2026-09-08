# YouTube Data API v3 Reference — metadata writes

Everything this skill sends to `videos.update`, plus the OAuth model behind it.

## The two-token model

This suite deliberately keeps read and write credentials in **separate files with
separate scopes**. They are never merged into one token.

| Token file | Scopes | Written by | Can change anything? |
|------------|--------|-----------|----------------------|
| `~/.config/youtube-skills/token.json` | `yt-analytics.readonly`, `youtube.readonly`, optionally `yt-analytics-monetary.readonly` | `youtube-channel-insights/scripts/auth.py` | **No** |
| `~/.config/youtube-skills/token_write.json` | `https://www.googleapis.com/auth/youtube.force-ssl` — and nothing else | `youtube-metadata-updater/scripts/auth_write.py` | Yes — titles and descriptions |

Both live in `$YT_OAUTH_DIR` if set, otherwise `~/.config/youtube-skills/`, at mode `600`,
and share one `client_secret.json` (Desktop-app OAuth client, downloaded once from Google
Cloud Console).

Enforcement is symmetric and mutual:

- `auth.py` hard-fails if a stored token contains any of `youtube`, `youtube.force-ssl`, `youtube.upload`, `youtubepartner`.
- `auth_write.py` hard-fails if a stored token contains **anything other than** `youtube.force-ssl` — an unexpected scope means the token did not come from this tool, and it will not be used.

`auth_write.py` also writes `channel_write.json` (`{"channel_id", "channel_title"}`) after
verifying ownership with `channels.list(part=snippet, mine=True)`. `update_metadata.py`
re-checks it on every run and refuses to continue if the token now controls a different
channel.

### Scope

| Scope | Grants | Why this one |
|-------|--------|--------------|
| `https://www.googleapis.com/auth/youtube.force-ssl` | Manage the account: read + write video metadata, comments, playlists | The narrowest scope Google offers that permits `videos.update`. There is no title-and-description-only scope. |

Because the scope is broader than what the skill does, the *code* is the boundary: only
`videos.update(part="snippet")` is ever called, and `part="status"` is never requested in
any call, so privacy/publish state is neither read nor transmitted.

Consent flow: `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0,
prompt="consent")`. A consent screen left in **Testing** status expires refresh tokens
after 7 days; publish it to **Production** to stop weekly re-authorization.

## videos.update — full-snippet replacement

```
PUT https://www.googleapis.com/youtube/v3/videos?part=snippet
```

```python
youtube.videos().update(
    part="snippet",
    body={"id": video_id, "snippet": merged_snippet},
).execute()
```

**This is a replace, not a patch.** Any writable field of `snippet` that is absent from
the request body is **cleared**. Sending `{"snippet": {"title": "New title"}}` wipes the
video's tags, `defaultLanguage`, and `defaultAudioLanguage`, and fails outright because
`categoryId` is required.

The correct sequence, which `update_metadata.py` performs for every single write:

1. `videos.list(part="snippet", id=VIDEO_ID)` — fetch the **live** snippet.
2. Copy every writable field forward unchanged.
3. Overwrite only `title` and/or `description`.
4. `videos.update(part="snippet", ...)` with the complete merged object.

### Writable snippet fields

| Field | Required on update | Handling here |
|-------|--------------------|---------------|
| `title` | Yes | The field being changed |
| `categoryId` | **Yes** | Copied forward verbatim; a missing value aborts the update |
| `description` | No | The other field being changed |
| `tags[]` | No | Copied forward verbatim — the classic data-loss bug |
| `defaultLanguage` | No | Copied forward verbatim |
| `defaultAudioLanguage` | No | Copied forward verbatim |

### Read-only snippet fields

`publishedAt`, `channelId`, `channelTitle`, `thumbnails`, `liveBroadcastContent`,
`localized`. The API returns them in `videos.list`; they are **not** echoed back in the
update body.

`channelId` is used for the ownership check: a video whose `snippet.channelId` differs
from `channel_write.json` is rejected before any write.

## Validation limits

| Field | Limit | Enforced before the call |
|-------|-------|--------------------------|
| `title` | Non-empty, **100 characters** max | Yes |
| `title` | Must not contain `<` or `>` — YouTube rejects angle brackets | Yes |
| `description` | **5000 bytes** max, measured in **UTF-8 bytes, not characters** | Yes (`len(s.encode("utf-8"))`) |
| `description` | Must not contain `<` or `>` | Yes |
| `tags` | 500 characters total across all tags | Not modified, so not re-validated |

Emoji and non-Latin scripts cost 2–4 bytes each, so a 4,000-character description can
easily exceed the 5,000-**byte** limit. Counting characters is the common mistake.

Also enforced locally, above the API's own rules:

- **50 updates per run**, hard cap.
- **Drift guard** — if a video's live title no longer matches the title recorded when the preview was generated (`expected_current_title`), the entry is skipped with `changed since preview`.
- **Backup before write** — the complete pre-edit snippet is written to `reports/backups/metadata-<date>/<videoId>.json`; a failed backup aborts the run.

## Endpoints used

| Endpoint | Part(s) | Purpose |
|----------|---------|---------|
| `channels.list` | `snippet`, `contentDetails` | Ownership verification, uploads-playlist ID |
| `playlistItems.list` | `contentDetails` | Enumerate the uploads playlist |
| `videos.list` | `snippet`, `statistics` | Current metadata, view counts |
| `videos.update` | `snippet` | **The only write** |

Never called: `videos.insert`, `videos.delete`, `thumbnails.set`, `playlists.*`,
`comments.*`, `videos.rate`, or anything touching `part="status"`.

## Quota costs

Default budget: **10,000 units/day**, reset at midnight Pacific Time, shared across every
skill in this suite that uses the Data API.

| Operation | Units |
|-----------|------:|
| `channels.list` | 1 |
| `playlistItems.list` (up to 50 items) | 1 |
| `videos.list` (up to 50 IDs) | 1 |
| **`videos.update`** | **50** |

Consequences worth stating to the user:

- 20 videos updated = **1,000 units** = 10% of the day's budget.
- The theoretical ceiling is 200 updates/day, well above this skill's 50-per-run cap.
- `list`, `get`, and `preview` are effectively free (1–3 units) and can be re-run as often as needed.
- A `revert` costs the same as an apply: 50 units per video, plus 1 to re-read it.

## Error reference

| HTTP / reason | Meaning | Fix |
|---------------|---------|-----|
| `403 forbidden` | The token cannot edit this video | Wrong Google account, or the video belongs to another channel |
| `403 quotaExceeded` | Daily budget spent | Wait for the Pacific-midnight reset |
| `400 invalidVideoMetadata` | Title/description rejected | Angle brackets, or over the length limits |
| `400 invalidCategoryId` / missing category | `categoryId` absent or not valid in the channel's region | Should be impossible here — the merge copies it forward and aborts if it is missing |
| `404 videoNotFound` | Bad ID, or the video was deleted | Re-run `list` |
| `401` | Token expired and could not refresh | `python3 scripts/auth_write.py --force` |
