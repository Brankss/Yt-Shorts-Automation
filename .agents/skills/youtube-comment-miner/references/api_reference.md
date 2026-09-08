# YouTube Data API v3 Reference - Comment Miner

## Authentication
All requests require `key={API_KEY}` parameter.

## Endpoints Used

### commentThreads.list (1 unit/call)
```
GET https://www.googleapis.com/youtube/v3/commentThreads
  ?part=snippet
  &videoId={videoId}
  &maxResults={1-100}
  &order=relevance
  &textFormat=plainText
  &pageToken={token}
  &key={API_KEY}
```

Response fields:
- `items[].snippet.topLevelComment.snippet.textDisplay` - Comment text
- `items[].snippet.topLevelComment.snippet.authorDisplayName` - Author
- `items[].snippet.topLevelComment.snippet.likeCount` - Likes
- `items[].snippet.topLevelComment.snippet.publishedAt` - Date
- `items[].snippet.totalReplyCount` - Reply count

### search.list (100 units/call) -- topic mode only
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet&q={topic}&order=viewCount&type=video&maxResults=50
```

### playlistItems.list (1 unit per 50) -- channel mode
Channel mode never uses `search.list?channelId=`. It pages the uploads playlist and
ranks by actual view count -- cheaper, and it sees every upload instead of a slice:
```
channels.list?part=contentDetails  ->  contentDetails.relatedPlaylists.uploads
GET https://www.googleapis.com/youtube/v3/playlistItems
  ?part=contentDetails,snippet&playlistId={uploads}&maxResults=50&key={API_KEY}
```

### videos.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,statistics&id={comma-separated}&key={API_KEY}
```

### channels.list (1 unit/call)
Used for channel resolution.
```
GET https://www.googleapis.com/youtube/v3/channels
  ?part=snippet,contentDetails,statistics&forHandle={handle}&key={API_KEY}
```

## Quota Budget

| Mode | Estimated Units |
|------|----------------|
| Direct videos (5 videos, 100 comments each) | ~6 |
| Channel top 5 (500-video channel) | ~26 |
| Topic top 10 | ~111 |

Note: commentThreads.list is very efficient at 1 unit per call (up to 100 comments each).

## Common Errors

| Code | Meaning |
|------|---------|
| 403 | Comments disabled, quota exceeded, or API not enabled |
| 404 | Video not found |
| 400 | Invalid video ID |
