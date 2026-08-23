# YouTube Playlist Transcripts

Extracts the transcripts (subtitles) of all videos in a YouTube playlist and saves them as text files.

## Features

- Reads all videos from a playlist (also works with `watch?v=...&list=...` URLs)
- Prefers manually created transcripts, falls back to auto-generated ones
- Translates into the desired language if no matching transcript exists
- Saves one `.txt` file per video with title, video ID, URL, and transcript text
- Optional: a single combined file containing all transcripts
- Prints a summary at the end (successful/failed videos)

## Requirements

- Python 3.8+
- Packages:

```bash
pip install yt-dlp youtube-transcript-api
```

## Usage

```bash
python playlist_transcripts.py "https://www.youtube.com/playlist?list=XXXXXXXX"
```

### Options

| Option        | Description                                                         | Default          |
|---------------|----------------------------------------------------------------------|------------------|
| `--lang`      | Preferred languages, comma-separated, in priority order              | `de,en`          |
| `--outdir`    | Target folder for the transcripts                                    | `transcripts`    |
| `--combined`  | Also generate a single file containing all transcripts               | disabled         |

### Examples

Default run (German preferred, then English):

```bash
python playlist_transcripts.py "https://www.youtube.com/playlist?list=XXXXXXXX"
```

English transcripts only, custom output folder:

```bash
python playlist_transcripts.py "https://www.youtube.com/playlist?list=XXXXXXXX" --lang en --outdir out
```

With an additional combined file:

```bash
python playlist_transcripts.py "https://www.youtube.com/playlist?list=XXXXXXXX" --combined
```

## Output

The target folder (default `transcripts/`) will contain one file per video:

```
001_VideoTitle_VIDEOID.txt
002_AnotherVideo_VIDEOID.txt
...
```

Each file contains:

```
Titel: ...
Video-ID: ...
URL: https://www.youtube.com/watch?v=...
------------------------------------------------------------

<transcript text>
```

With `--combined`, an additional `_alle_transkripte.txt` file is created containing all transcripts.

## Transcript lookup order

For each video, the script tries to fetch a transcript in this order:

1. Manually created transcript in one of the preferred languages (`--lang`)
2. Auto-generated transcript in one of the preferred languages
3. Any available transcript — if translatable, it's translated into the first preferred language

If all of these fail (e.g. transcripts disabled, video unavailable), the video is listed as failed in the summary, and the rest of the playlist is still processed.

## Notes

- Playlist URLs that also contain a `list=` ID (e.g. opened from within a single video) are automatically normalized to a pure playlist URL.
- Nested playlist structures (e.g. some channel tabs) are resolved one level deep.
- Filenames are sanitized from the video title (special characters removed, truncated to 150 characters).
- Unavailable or private videos are skipped and noted in the log.

## Known limitations

- Very large playlists may be slow depending on YouTube rate limiting.
- Live streams or premieres without subtitles will not yield a transcript.
- Regional restrictions may prevent access to individual videos.
