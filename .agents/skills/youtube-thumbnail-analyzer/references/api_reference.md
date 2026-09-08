# YouTube Data API v3 Reference - Thumbnail Analyzer

## Authentication
All requests require `key={API_KEY}` parameter.

## Endpoints Used

### search.list (100 units/call) -- topic mode only
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet
  &q={topic}
  &type=video
  &order=viewCount
  &maxResults=50
  &key={API_KEY}
```

### playlistItems.list (1 unit per 50) -- channel mode
Channel mode never uses `search.list?channelId=`. It pages the uploads playlist and
ranks by actual view count, which is both cheaper and covers the whole channel:
```
channels.list?part=contentDetails  ->  contentDetails.relatedPlaylists.uploads
GET https://www.googleapis.com/youtube/v3/playlistItems
  ?part=contentDetails,snippet&playlistId={uploads}&maxResults=50&key={API_KEY}
```

### videos.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,statistics,contentDetails
  &id={comma-separated}
  &key={API_KEY}
```

### channels.list (1 unit/call, batch up to 50)
For channel resolution and subscriber counts.
```
GET https://www.googleapis.com/youtube/v3/channels
  ?part=snippet,statistics,contentDetails
  &forHandle={handle}  OR  &id={ids}
  &key={API_KEY}
```

## Thumbnail Download URLs (no API quota)
```
https://img.youtube.com/vi/{videoId}/maxresdefault.jpg  (1280x720)
https://img.youtube.com/vi/{videoId}/sddefault.jpg      (640x480)
https://img.youtube.com/vi/{videoId}/hqdefault.jpg      (480x360)
https://img.youtube.com/vi/{videoId}/mqdefault.jpg      (320x180)
```
Fallback order: maxres -> sd -> hq -> mq

## Quota Budget

**Topic mode (20 thumbnails)**
| Operation | Calls | Units |
|-----------|-------|-------|
| search.list | 1 | 100 |
| videos.list | 1 | 1 |
| channels.list | 1 | 1 |
| **Total** | | **~102** |

**Channel mode (500-video channel)**
| Operation | Calls | Units |
|-----------|-------|-------|
| channels.list (resolve) | 1 | 1 |
| playlistItems.list | ~10 | ~10 |
| videos.list | ~10 | ~10 |
| channels.list (subs) | 1 | 1 |
| **Total** | | **~22** |

Note: Thumbnail image downloads are free (no API quota).
Daily limit: 10,000 units, resetting at midnight Pacific Time.
