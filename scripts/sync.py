#!/usr/bin/env python3
"""
Auto-sync script for Nate Jones YouTube transcripts.
Uses free tools only: yt-dlp (video discovery), youtube-transcript-api (transcripts), pytubefix (metadata).
Designed to run via launchd on a daily schedule.
"""

import os
import re
import json
import time
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Try imports, install if missing
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "youtube-transcript-api"])
    from youtube_transcript_api import YouTubeTranscriptApi

try:
    from pytubefix import YouTube
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pytubefix"])
    from pytubefix import YouTube

# Configuration
BASE_DIR = Path(__file__).parent.parent
EPISODES_DIR = BASE_DIR / "episodes"
VIDEO_IDS_FILE = BASE_DIR / "video_ids.txt"
PROGRESS_FILE = BASE_DIR / "progress.json"
LOG_FILE = Path.home() / "scripts" / "nate-sync.log"
CHANNEL_URL = "https://www.youtube.com/@NateBJones/videos"

# Rate limiting - conservative to avoid IP bans
MIN_DELAY = 3
MAX_DELAY = 6
BATCH_SIZE = 10  # Take a longer break every N videos
BATCH_BREAK = 60  # Seconds to pause between batches
MAX_CONSECUTIVE_ERRORS = 3  # Stop after this many errors in a row


def log(msg):
    """Log to both stdout and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": [], "last_run": None}


def save_progress(progress):
    progress["last_run"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80].strip('-')


def get_channel_video_ids():
    """Get all video IDs from channel using yt-dlp."""
    log("Fetching video list from YouTube channel...")
    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--print", "id", CHANNEL_URL],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            log(f"yt-dlp error: {result.stderr[:200]}")
            return []
        ids = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        log(f"Found {len(ids)} videos on channel")
        return ids
    except Exception as e:
        log(f"Error fetching channel videos: {e}")
        return []


def get_video_metadata(video_id):
    """Get video metadata using pytubefix."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url)
        return {
            "title": yt.title,
            "video_id": video_id,
            "url": url,
            "duration_seconds": yt.length,
            "duration": f"{yt.length // 60}:{yt.length % 60:02d}",
            "view_count": yt.views,
            "publish_date": yt.publish_date.strftime("%Y-%m-%d") if yt.publish_date else None,
            "description": yt.description or "",
            "author": yt.author,
            "keywords": yt.keywords or [],
        }
    except Exception as e:
        log(f"  Warning: Could not get metadata for {video_id}: {e}")
        return None


def get_transcript_free(video_id):
    """Get transcript using youtube-transcript-api v1.x (free, no API key)."""
    try:
        ytt_api = YouTubeTranscriptApi()
        segments = ytt_api.fetch(video_id)

        full_text = ' '.join([seg.text for seg in segments])
        timestamped = [
            {"text": seg.text, "start": seg.start, "duration": seg.duration}
            for seg in segments
        ]

        return {
            "full_text": full_text,
            "segments": timestamped,
            "segment_count": len(segments)
        }
    except Exception as e:
        raise Exception(f"Transcript error: {e}")


def extract_substack_url(description):
    if not description:
        return None
    match = re.search(r'https://natesnewsletter\.substack\.com/p/[^\s\)]+', description)
    return match.group(0) if match else None


def save_transcript(metadata, transcript):
    """Save transcript with YAML frontmatter."""
    slug = slugify(metadata.get("title", metadata["video_id"]))
    date_prefix = metadata.get("publish_date", "unknown")
    folder_name = f"{date_prefix}-{slug}"

    episode_dir = EPISODES_DIR / folder_name
    episode_dir.mkdir(parents=True, exist_ok=True)

    substack_url = extract_substack_url(metadata.get("description", ""))

    yaml_content = f'''---
title: "{metadata.get('title', 'Unknown').replace('"', '\\"')}"
video_id: "{metadata['video_id']}"
youtube_url: "{metadata.get('url', '')}"
substack_url: {f'"{substack_url}"' if substack_url else 'null'}
publish_date: "{metadata.get('publish_date', 'unknown')}"
duration: "{metadata.get('duration', 'unknown')}"
duration_seconds: {metadata.get('duration_seconds', 0)}
view_count: {metadata.get('view_count', 0)}
author: "{metadata.get('author', 'Nate Jones')}"

yt_tags:
{chr(10).join(f'  - "{tag}"' for tag in metadata.get('keywords', [])) or '  []'}

# AI-generated fields (to be enriched later)
content_type: null
primary_topic: null
audience: []
difficulty: null
entities:
  companies: []
  people: []
  products: []
  models: []
concepts: []
chapters: []
summary: []
---

# {metadata.get('title', 'Unknown')}

{transcript['full_text']}
'''

    output_file = episode_dir / "transcript.md"
    with open(output_file, "w") as f:
        f.write(yaml_content)

    return str(episode_dir)


def git_commit_and_push(new_count):
    """Commit and push changes to GitHub."""
    try:
        os.chdir(BASE_DIR)
        subprocess.run(["git", "add", "-A"], capture_output=True)
        msg = f"Sync {new_count} new transcript{'s' if new_count != 1 else ''} — {datetime.now().strftime('%Y-%m-%d')}"
        subprocess.run(["git", "commit", "-m", msg], capture_output=True)
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"Pushed to GitHub: {msg}")
        else:
            log(f"Push failed (will retry next run): {result.stderr[:200]}")
    except Exception as e:
        log(f"Git error: {e}")


def main():
    log("=== Nate Jones Transcript Sync ===")

    # Get all channel video IDs
    channel_ids = get_channel_video_ids()
    if not channel_ids:
        log("Could not fetch channel videos. Exiting.")
        return

    # Load progress
    progress = load_progress()
    completed = set(progress["completed"])

    # Load existing video_ids.txt
    existing_ids = set()
    if VIDEO_IDS_FILE.exists():
        existing_ids = set(line.strip() for line in VIDEO_IDS_FILE.read_text().strip().split("\n") if line.strip())

    # Find new videos
    new_ids = [vid for vid in channel_ids if vid not in completed and vid not in existing_ids]

    # Also retry any in video_ids.txt that haven't been completed
    retry_ids = [vid for vid in existing_ids if vid not in completed]

    # Retry previously failed videos (e.g. from IP blocks)
    failed_ids = [f["id"] for f in progress.get("failed", []) if f["id"] not in completed]
    # Clear the failed list — they'll be re-added if they fail again
    progress["failed"] = []

    all_to_process = new_ids + [vid for vid in failed_ids if vid not in set(new_ids)] + retry_ids
    log(f"Channel videos: {len(channel_ids)}")
    log(f"Already completed: {len(completed)}")
    log(f"New videos: {len(new_ids)}")
    log(f"Retries: {len(retry_ids)}")
    log(f"Total to process: {len(all_to_process)}")

    if not all_to_process:
        log("Everything up to date!")
        save_progress(progress)
        return

    # Process videos
    success_count = 0
    consecutive_errors = 0
    for i, video_id in enumerate(all_to_process, 1):
        log(f"[{i}/{len(all_to_process)}] Processing {video_id}...")

        try:
            # Get metadata
            metadata = get_video_metadata(video_id)
            if not metadata:
                metadata = {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}

            time.sleep(random.uniform(1, 2))

            # Get transcript (free)
            transcript = get_transcript_free(video_id)

            # Save
            output_path = save_transcript(metadata, transcript)
            log(f"  Saved: {Path(output_path).name} ({transcript['segment_count']} segments)")

            # Update progress
            progress["completed"].append(video_id)
            save_progress(progress)
            success_count += 1
            consecutive_errors = 0  # Reset on success

            # Rate limiting
            if i < len(all_to_process):
                if success_count % BATCH_SIZE == 0:
                    log(f"  Batch break: {BATCH_BREAK}s cooldown...")
                    time.sleep(BATCH_BREAK)
                else:
                    delay = random.uniform(MIN_DELAY, MAX_DELAY)
                    time.sleep(delay)

        except Exception as e:
            error_msg = str(e)
            consecutive_errors += 1

            # Detect IP ban / rate limit
            if "blocking" in error_msg.lower() or "IP" in error_msg:
                log(f"  IP blocked by YouTube. Got {success_count} transcripts before block.")
                log(f"  Remaining videos will be retried on next run.")
                # Don't add to failed list — just skip for now
                break
            elif consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                log(f"  {MAX_CONSECUTIVE_ERRORS} consecutive errors — stopping to avoid ban.")
                break
            else:
                log(f"  ERROR: {error_msg[:200]}")
                progress["failed"].append({
                    "id": video_id,
                    "reason": error_msg[:200],
                    "time": datetime.now().isoformat()
                })
                save_progress(progress)

    # Update video_ids.txt with any new IDs
    all_known_ids = list(existing_ids | set(channel_ids))
    VIDEO_IDS_FILE.write_text("\n".join(all_known_ids) + "\n")

    # Run enrichment
    if success_count > 0:
        log(f"Running enrichment on all episodes...")
        try:
            enrich_script = BASE_DIR / "scripts" / "enrich.py"
            subprocess.run([sys.executable, str(enrich_script)], capture_output=True, timeout=300)
            log("Enrichment complete")
        except Exception as e:
            log(f"Enrichment error: {e}")

        # Rebuild index
        log("Rebuilding index...")
        try:
            index_script = BASE_DIR / "scripts" / "create_index.py"
            if index_script.exists():
                subprocess.run([sys.executable, str(index_script)], capture_output=True, timeout=120)
            build_script = BASE_DIR / "scripts" / "build_index.py"
            if build_script.exists():
                subprocess.run([sys.executable, str(build_script)], capture_output=True, timeout=120)
            log("Index rebuild complete")
        except Exception as e:
            log(f"Index error: {e}")

        # Git commit and push
        git_commit_and_push(success_count)

    # Update README stats
    try:
        total_episodes = len(list(EPISODES_DIR.iterdir()))
        earliest = sorted(EPISODES_DIR.iterdir())[0].name[:10]
        latest = sorted(EPISODES_DIR.iterdir())[-1].name[:10]
        readme = BASE_DIR / "README.md"
        if readme.exists():
            content = readme.read_text()
            content = re.sub(r'\*\*Videos Downloaded\*\*:.*', f'**Videos Downloaded**: {total_episodes}', content)
            content = re.sub(r'\*\*Date Range\*\*:.*', f'**Date Range**: {earliest} - {latest}', content)
            content = re.sub(r'\*\*Last Updated\*\*:.*', f'**Last Updated**: {datetime.now().strftime("%b %d, %Y")}', content)
            readme.write_text(content)
    except Exception:
        pass

    log(f"\n=== Sync Complete ===")
    log(f"Downloaded: {success_count}/{len(all_to_process)}")
    log(f"Total episodes: {len(progress['completed'])}")


if __name__ == "__main__":
    main()
