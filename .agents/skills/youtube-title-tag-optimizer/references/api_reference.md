# YouTube Data API v3 Reference - Title & Tag Optimizer

## Authentication
All requests require `key={API_KEY}` parameter.

## Endpoints Used

### search.list (100 units/call)
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet
  &q={keyword}
  &type=video
  &order={relevance|viewCount}
  &maxResults=50
  &key={API_KEY}
```

### videos.list (1 unit/call, batch up to 50)
```
GET https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,statistics,contentDetails
  &id={comma-separated IDs}
  &key={API_KEY}
```

Key fields for optimization:
- `snippet.tags[]` - Video tags (critical for tag extraction)
- `snippet.title` - For pattern analysis
- `snippet.description` - First line for SEO template
- `statistics.viewCount` - For performance correlation

## Quota Budget
| Operation | Calls | Units |
|-----------|-------|-------|
| search.list (relevance) | 1 | 100 |
| search.list (viewCount) | 1 | 100 |
| videos.list | 1-2 | 1-2 |
| **Total** | | **~202** |

## Notes
- Tags field may be empty for some videos (not all creators use tags)
- Description is truncated in search results; full version only in videos.list
- Title max length is ~100 chars but optimal is 40-70
