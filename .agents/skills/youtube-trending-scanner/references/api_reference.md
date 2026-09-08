# YouTube Data API v3 Reference - Trending Scanner

## Authentication
All requests require `key={API_KEY}` parameter.

## Endpoints Used

### search.list (100 units/call)
Key parameter: `publishedAfter` for time-windowed search
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet
  &q={niche}
  &type=video
  &order={relevance|viewCount|date}
  &publishedAfter={ISO8601_date}
  &maxResults=50
  &key={API_KEY}
```

### videos.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,statistics,contentDetails
  &id={comma-separated}
  &key={API_KEY}
```

### channels.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/channels
  ?part=snippet,statistics
  &id={comma-separated}
  &key={API_KEY}
```

## Quota Budget
| Operation | Calls | Units |
|-----------|-------|-------|
| search.list (relevance, recent) | 1 | 100 |
| search.list (viewCount, recent) | 1 | 100 |
| search.list (date, recent) | 1 | 100 |
| search.list (baseline, 90 days) | 1 | 100 |
| videos.list | 2-4 | 2-4 |
| channels.list | 1-2 | 1-2 |
| **Total** | | **~405** |

Daily limit: 10,000 units
