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
| id | One of | Channel ID (UC...) - can be comma-separated for multiple |
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

## Search Endpoint (Channel Discovery)

```
GET https://www.googleapis.com/youtube/v3/search
```

### Parameters
| Param | Required | Description |
|-------|----------|-------------|
| part | Yes | snippet |
| q | Yes | Search query (keywords, channel names) |
| type | Yes | channel (for competitor discovery) |
| order | No | relevance (default), viewCount |
| maxResults | No | 1-50 (default 5) |
| pageToken | No | For pagination |
| key | Yes | API key |

### Response
```json
{
  "nextPageToken": "...",
  "items": [{
    "id": {
      "kind": "youtube#channel",
      "channelId": "UC..."
    },
    "snippet": {
      "channelId": "UC...",
      "title": "Channel Name",
      "description": "...",
      "thumbnails": {}
    }
  }]
}
```

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

## Quota Costs

| Operation | Cost |
|-----------|------|
| search.list | 100 |
| channels.list | 1 |
| videos.list | 1 |
| playlistItems.list | 1 |

**Daily quota**: 10,000 units (default)

**Optimization for competitor analysis**:
- Batch channel IDs (comma-separated, up to 50) to reduce calls
- Limit initial discovery searches to essential keywords (`--max-queries`, 100 units each)
- Profile recent content only for top-ranked competitors (`--top`)
- Profile competitor uploads via `playlistItems.list` (1 unit/50), never `search.list?channelId=`

**Typical totals**: ~328 units in discovery mode (3 searches + 12 profiles);
~40 units in direct mode (`--competitors`, no discovery searches).

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad request (invalid params) |
| 403 | Forbidden (quota exceeded, API not enabled) |
| 404 | Not found |
| 429 | Too many requests |

## Channel ID Formats

All resolution goes through `channels.list` (1 unit). Never use `search.list` (100 units)
to resolve a channel reference.

| Format | Example | Resolution | Cost |
|--------|---------|------------|------|
| Direct ID | UC... | `channels.list?id=UC...` | 1 |
| @handle | @channelname | `channels.list?forHandle=channelname` | 1 |
| /channel/ URL | youtube.com/channel/UC... | extract ID, then `id=` | 1 |
| /@handle URL | youtube.com/@name | `forHandle=name` | 1 |
| /c/ URL | youtube.com/c/name | `forHandle=name`, then `forUsername=name` | 1-2 |
| /user/ URL | youtube.com/user/name | `channels.list?forUsername=name` | 1 |

## Duration Format (ISO 8601)

Format: `PT{hours}H{minutes}M{seconds}S`

Examples:
- `PT1H30M` = 1 hour 30 minutes
- `PT10M30S` = 10 minutes 30 seconds

Parse: `/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/`
