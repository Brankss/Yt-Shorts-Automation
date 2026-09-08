# YouTube Data API v3 Reference

## Authentication

All requests require `key={API_KEY}` parameter.

Get API key: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
1. Create project → Enable YouTube Data API v3 → Create credentials → API Key

## Channels Endpoint

```
GET https://www.googleapis.com/youtube/v3/channels
```

### Parameters
| Param | Required | Description |
|-------|----------|-------------|
| part | Yes | snippet,statistics,contentDetails,brandingSettings |
| id | One of | Channel ID (UC...) |
| forUsername | One of | Legacy username |
| key | Yes | API key |

### Response Fields
```json
{
  "items": [{
    "id": "UC...",
    "snippet": {
      "title": "Channel Name",
      "description": "...",
      "customUrl": "@handle",
      "publishedAt": "2020-01-01T00:00:00Z",
      "country": "US",
      "thumbnails": { "default": {}, "medium": {}, "high": {} }
    },
    "statistics": {
      "viewCount": "1000000",
      "subscriberCount": "50000",
      "hiddenSubscriberCount": false,
      "videoCount": "200"
    },
    "contentDetails": {
      "relatedPlaylists": {
        "uploads": "UU..."
      }
    },
    "brandingSettings": {
      "channel": {
        "keywords": "keyword1 keyword2"
      }
    }
  }]
}
```

## Listing a Channel's Videos (do NOT use search.list)

`search.list?channelId=...` costs **100 units per 50 videos** and only returns a
truncated slice of a channel. Use the uploads playlist instead — **1 unit per 50 videos**:

```
1. channels.list?part=contentDetails&id={channelId}         -> 1 unit
   => contentDetails.relatedPlaylists.uploads  (UU... playlist ID)
2. playlistItems.list?playlistId={uploads}&maxResults=50     -> 1 unit per page
   => contentDetails.videoId, contentDetails.videoPublishedAt
3. videos.list?id={50 comma-separated IDs}                   -> 1 unit per batch
```

This skill never calls `search.list`.

## Channel ID Resolution

| Input | Resolution | Cost |
|-------|-----------|------|
| `UC...` | `channels.list?id=UC...` | 1 |
| `youtube.com/channel/UC...` | extract ID, then `id=` | 1 |
| `@handle` / `youtube.com/@handle` | `channels.list?forHandle=handle` | 1 |
| `youtube.com/c/name` | `forHandle=name`, then `forUsername=name` | 1-2 |
| `youtube.com/user/name` (legacy) | `channels.list?forUsername=name` | 1 |

## Videos Endpoint

```
GET https://www.googleapis.com/youtube/v3/videos
```

### Parameters
| Param | Required | Description |
|-------|----------|-------------|
| part | Yes | snippet,statistics,contentDetails |
| id | Yes | Comma-separated video IDs (max 50) |
| key | Yes | API key |

### Response Fields
```json
{
  "items": [{
    "id": "videoId",
    "snippet": {
      "publishedAt": "...",
      "channelId": "...",
      "title": "...",
      "description": "...",
      "tags": ["tag1", "tag2"],
      "categoryId": "22"
    },
    "statistics": {
      "viewCount": "10000",
      "likeCount": "500",
      "commentCount": "50"
    },
    "contentDetails": {
      "duration": "PT10M30S",
      "definition": "hd"
    }
  }]
}
```

## PlaylistItems Endpoint

```
GET https://www.googleapis.com/youtube/v3/playlistItems
```

### Parameters
| Param | Required | Description |
|-------|----------|-------------|
| part | Yes | snippet,contentDetails |
| playlistId | Yes | Playlist ID (uploads: UU...) |
| maxResults | No | 1-50 |
| pageToken | No | For pagination |
| key | Yes | API key |

## Quota Costs

| Operation | Cost |
|-----------|------|
| search.list | 100 (not used by this skill) |
| channels.list | 1 |
| videos.list | 1 |
| playlistItems.list | 1 |

**This skill's total**: ~9 units for 200 videos (1 resolve + 4 playlistItems + 4 videos).

**Daily quota**: 10,000 units (default), resetting at midnight Pacific Time.

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad request (invalid params) |
| 403 | Forbidden (quota exceeded, API not enabled) |
| 404 | Not found |
| 429 | Too many requests |

## Duration Format (ISO 8601)

Format: `PT{hours}H{minutes}M{seconds}S`

Examples:
- `PT1H30M` = 1 hour 30 minutes
- `PT10M30S` = 10 minutes 30 seconds
- `PT45S` = 45 seconds

Parse with regex: `/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/`
