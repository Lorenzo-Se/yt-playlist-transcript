#!/usr/bin/env python3
"""
Extrahiert die Transkripte aller Videos einer YouTube-Playlist.

Voraussetzungen:
    pip install yt-dlp youtube-transcript-api

Nutzung:
    python playlist_transcripts.py "https://www.youtube.com/playlist?list=XXXXXXXX"

Optionen:
    --lang de,en        Bevorzugte Sprachen in Prioritätsreihenfolge (Standard: de,en)
    --outdir transcripts  Zielordner (Standard: ./transcripts)
    --combined          Zusätzlich eine einzige Datei mit allen Transkripten erzeugen
"""

import argparse
import json
import os
import re
import sys

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


def normalize_playlist_url(url: str) -> str:
    """
    Extrahiert die Playlist-ID aus einer beliebigen YouTube-URL (auch watch?v=...&list=...)
    und baut daraus eine eindeutige, reine Playlist-URL. Das verhindert, dass yt-dlp
    die URL fälschlicherweise als Einzelvideo behandelt.
    """
    match = re.search(r"[?&]list=([a-zA-Z0-9_-]+)", url)
    if match:
        playlist_id = match.group(1)
        return f"https://www.youtube.com/playlist?list={playlist_id}"
    return url  # war wohl schon eine reine Playlist-URL oder enthält keine ID


def get_playlist_videos(playlist_url: str):
    """Liefert Liste von (video_id, title) für alle Videos der Playlist."""
    clean_url = normalize_playlist_url(playlist_url)

    ydl_opts = {
        "extract_flat": "in_playlist",  # nur Metadaten, keine Downloads, vollständige Playlist-Auflösung
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
        "noplaylist": False,
    }
    videos = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(clean_url, download=False)
        if info is None:
            raise RuntimeError("Playlist konnte nicht geladen werden (info ist None).")

        entries = list(info.get("entries") or [])

        # Manche Playlists liefern verschachtelte "Tabs" (z.B. bei Channels) -
        # falls entries selbst wieder Playlists mit eigenen entries sind, eine Ebene tiefer gehen.
        flat_entries = []
        for entry in entries:
            if entry is None:
                continue
            if entry.get("_type") == "playlist" and entry.get("entries"):
                flat_entries.extend(e for e in entry["entries"] if e)
            else:
                flat_entries.append(entry)

        for entry in flat_entries:
            video_id = entry.get("id")
            title = entry.get("title", video_id)
            if video_id:
                videos.append((video_id, title))

    return videos, info.get("title", "playlist")


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\-. ]", "_", name)
    return name.strip()[:150]


_ytt_api = YouTubeTranscriptApi()  # seit v1.x instanzbasiert statt Klassenmethoden


def fetch_transcript(video_id: str, languages):
    """Holt Transkript, versucht bevorzugte Sprachen, sonst automatische Untertitel."""
    try:
        transcript_list = _ytt_api.list(video_id)
    except (TranscriptsDisabled, VideoUnavailable) as e:
        return None, f"Kein Transkript verfügbar: {e}"
    except Exception as e:
        return None, f"Fehler beim Abrufen der Transkriptliste: {e}"

    # 1. Versuch: manuell erstellte Transkripte in bevorzugter Sprache
    try:
        transcript = transcript_list.find_manually_created_transcript(languages)
        data = transcript.fetch()
        return data, None
    except NoTranscriptFound:
        pass

    # 2. Versuch: automatisch generierte Transkripte in bevorzugter Sprache
    try:
        transcript = transcript_list.find_generated_transcript(languages)
        data = transcript.fetch()
        return data, None
    except NoTranscriptFound:
        pass

    # 3. Versuch: irgendein verfügbares Transkript, ggf. übersetzt
    try:
        first = next(iter(transcript_list))
        if first.is_translatable:
            translated = first.translate(languages[0])
            data = translated.fetch()
            return data, None
        data = first.fetch()
        return data, None
    except Exception as e:
        return None, f"Kein passendes Transkript gefunden: {e}"


def transcript_to_text(transcript_data) -> str:
    lines = []
    for entry in transcript_data:
        # entry ist entweder dict oder FetchedTranscriptSnippet-Objekt, je nach Version
        text = entry["text"] if isinstance(entry, dict) else entry.text
        lines.append(text.replace("\n", " "))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="YouTube-Playlist-Transkripte extrahieren")
    parser.add_argument("playlist_url", help="URL der YouTube-Playlist")
    parser.add_argument("--lang", default="de,en", help="Bevorzugte Sprachen, kommagetrennt (Standard: de,en)")
    parser.add_argument("--outdir", default="transcripts", help="Zielordner für die Transkripte")
    parser.add_argument("--combined", action="store_true", help="Zusätzlich eine Sammel-Datei erzeugen")
    args = parser.parse_args()

    languages = [l.strip() for l in args.lang.split(",") if l.strip()]
    os.makedirs(args.outdir, exist_ok=True)

    print(f"Lade Playlist-Infos von: {args.playlist_url}")
    videos, playlist_title = get_playlist_videos(args.playlist_url)
    print(f"Playlist: {playlist_title}  |  {len(videos)} Video(s) gefunden.\n")

    combined_parts = []
    summary = []

    for i, (video_id, title) in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {title} ({video_id}) ...", end=" ")
        data, error = fetch_transcript(video_id, languages)

        if error:
            print("FEHLGESCHLAGEN")
            summary.append((title, video_id, f"FEHLER: {error}"))
            continue

        text = transcript_to_text(data)
        safe_title = sanitize_filename(title)
        filename = os.path.join(args.outdir, f"{i:03d}_{safe_title}_{video_id}.txt")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Titel: {title}\n")
            f.write(f"Video-ID: {video_id}\n")
            f.write(f"URL: https://www.youtube.com/watch?v={video_id}\n")
            f.write("-" * 60 + "\n\n")
            f.write(text)

        print("OK")
        summary.append((title, video_id, "OK"))

        if args.combined:
            combined_parts.append(
                f"### {title} ({video_id})\nhttps://www.youtube.com/watch?v={video_id}\n\n{text}\n\n{'='*80}\n"
            )

    if args.combined and combined_parts:
        combined_path = os.path.join(args.outdir, "_alle_transkripte.txt")
        with open(combined_path, "w", encoding="utf-8") as f:
            f.write("\n".join(combined_parts))
        print(f"\nSammel-Datei geschrieben: {combined_path}")

    # Kurze Zusammenfassung ausgeben
    print("\n--- Zusammenfassung ---")
    ok_count = sum(1 for _, _, status in summary if status == "OK")
    print(f"{ok_count}/{len(summary)} Transkripte erfolgreich extrahiert.")
    failed = [(t, v, s) for t, v, s in summary if s != "OK"]
    if failed:
        print("\nOhne Transkript:")
        for title, video_id, status in failed:
            print(f"  - {title} ({video_id}): {status}")


if __name__ == "__main__":
    main()
