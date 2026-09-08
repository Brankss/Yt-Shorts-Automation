# YouTube Data API v3 Reference - Topic Researcher

## Authentication

All requests require `key={API_KEY}` parameter.
Get API key: [Google Cloud Console](https://console.cloud.google.com/apis/credentials) - Enable YouTube Data API v3 - Create API Key

## Endpoints Used

### search.list (100 units/call)
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet
  &q={query}
  &type=video
  &order={relevance|viewCount|date}
  &maxResults={1-50}
  &pageToken={token}
  &key={API_KEY}
```

Response: `items[].id.videoId`, `items[].snippet.{title,channelId,publishedAt}`

### videos.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,statistics,contentDetails
  &id={comma-separated IDs, max 50}
  &key={API_KEY}
```

Response: `items[].{snippet.tags, statistics.{viewCount,likeCount,commentCount}, contentDetails.duration}`

### channels.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/channels
  ?part=snippet,statistics
  &id={comma-separated IDs, max 50}
  &key={API_KEY}
```

Response: `items[].{snippet.title, statistics.{subscriberCount,viewCount,videoCount}}`

## Quota Budget

| Operation | Calls | Units |
|-----------|-------|-------|
| search.list (relevance) | 1-2 | 100-200 |
| search.list (viewCount) | 1-2 | 100-200 |
| search.list (date) | 1 | 100 |
| videos.list | 1-3 | 1-3 |
| channels.list | 1-2 | 1-2 |
| **Estimated Total** | | **~305** |

Daily limit: 10,000 units

## Duration Format (ISO 8601)

`PT{H}H{M}M{S}S` - Parse with: `/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/`

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Invalid parameters |
| 403 | Quota exceeded or API not enabled |
| 404 | Not found |
| 429 | Rate limited |
