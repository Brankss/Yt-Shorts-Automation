# YouTube Data API v3 Reference - Content Strategist

## Authentication
All requests require `key={API_KEY}` parameter.

## Endpoints Used

### channels.list (1 unit/call)
```
GET https://www.googleapis.com/youtube/v3/channels
  ?part=snippet,statistics,contentDetails
  &forHandle={handle}
  &key={API_KEY}
```

### playlistItems.list (1 unit/call, paginated)
```
GET https://www.googleapis.com/youtube/v3/playlistItems
  ?part=contentDetails,snippet
  &playlistId={uploads_playlist}
  &maxResults=50
  &pageToken={token}
  &key={API_KEY}
```

### videos.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,statistics,contentDetails
  &id={comma-separated}
  &key={API_KEY}
```

### playlists.list (1 unit/call)
```
GET https://www.googleapis.com/youtube/v3/playlists
  ?part=snippet,contentDetails
  &channelId={channel_id}
  &maxResults=50
  &key={API_KEY}
```

### search.list (100 units/call)
Used for niche benchmarking.
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet&q={niche}&type=video&order=viewCount&maxResults=50
```

## Quota Budget
| Operation | Calls | Units |
|-----------|-------|-------|
| channels.list | 1 | 1 |
| playlistItems.list | 4 | 4 |
| videos.list | 4-5 | 4-5 |
| playlists.list | 1 | 1 |
| search.list (niche) | 1 | 100 |
| **Total** | | **~111** |

Daily limit: 10,000 units
