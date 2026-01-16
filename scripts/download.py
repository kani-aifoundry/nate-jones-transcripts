#!/usr/bin/env python3
"""
Smart YouTube transcript downloader using Supadata API.
"""

import os
import json
import time
import random
import re
import sys
import requests
from datetime import datetime
from pathlib import Path
from pytubefix import YouTube

# Configuration
BASE_DIR = Path(__file__).parent.parent
EPISODES_DIR = BASE_DIR / "episodes"
VIDEO_IDS_FILE = BASE_DIR / "video_ids.txt"
PROGRESS_FILE = BASE_DIR / "progress.json"

# Supadata API
SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")
SUPADATA_ENDPOINT = "https://api.supadata.ai/v1/transcript"

# Rate limiting - can be lighter since we're using paid API
MIN_DELAY = 1  # Minimum seconds between requests
MAX_DELAY = 2  # Maximum seconds between requests
BATCH_SIZE = 50  # Videos before taking a short break
BATCH_BREAK_MIN = 30  # 30 seconds break
BATCH_BREAK_MAX = 60  # 1 minute break

def load_progress():
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": [], "last_run": None}

def save_progress(progress):
    """Save progress to file."""
    progress["last_run"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80].strip('-')

def get_video_metadata(video_id):
    """Get video metadata from YouTube."""
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
        print(f"  Warning: Could not get metadata: {e}")
        return None

def get_transcript(video_id):
    """Get transcript using Supadata API."""
    if not SUPADATA_API_KEY:
        raise Exception("SUPADATA_API_KEY environment variable not set")

    try:
        url = f"{SUPADATA_ENDPOINT}?url=https://youtu.be/{video_id}"
        headers = {"x-api-key": SUPADATA_API_KEY}

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 429:
            raise Exception("RATE_LIMITED: Too many requests")
        elif response.status_code == 401:
            raise Exception("Invalid API key")
        elif response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")

        data = response.json()

        # Extract content from Supadata response
        content = data.get("content", [])

        # Combine all segments into full text
        full_text = ' '.join([seg.get("text", "") for seg in content])

        # Also keep timestamped version (convert ms to seconds)
        timestamped = [
            {
                "text": seg.get("text", ""),
                "start": seg.get("offset", 0) / 1000,
                "duration": seg.get("duration", 0) / 1000
            }
            for seg in content
        ]

        return {
            "full_text": full_text,
            "segments": timestamped,
            "segment_count": len(content)
        }
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {e}")

def extract_substack_url(description):
    """Extract Substack URL from video description."""
    if not description:
        return None
    match = re.search(r'https://natesnewsletter\.substack\.com/p/[^\s\)]+', description)
    return match.group(0) if match else None

def save_transcript(metadata, transcript):
    """Save transcript in rich format with YAML frontmatter."""
    slug = slugify(metadata.get("title", metadata["video_id"]))
    date_prefix = metadata.get("publish_date", "unknown")
    folder_name = f"{date_prefix}-{slug}"

    episode_dir = EPISODES_DIR / folder_name
    episode_dir.mkdir(parents=True, exist_ok=True)

    # Extract Substack URL
    substack_url = extract_substack_url(metadata.get("description", ""))

    # Build YAML frontmatter
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

def download_video(video_id, index, total):
    """Download a single video's transcript and metadata."""
    print(f"\n[{index}/{total}] Processing {video_id}...")

    # Get metadata first (less likely to trigger rate limit)
    print("  Getting metadata...")
    metadata = get_video_metadata(video_id)
    if not metadata:
        metadata = {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}

    # Small delay before transcript request
    time.sleep(random.uniform(1, 2))

    # Get transcript
    print("  Getting transcript...")
    transcript = get_transcript(video_id)

    # Save
    print(f"  Got {transcript['segment_count']} segments ({len(transcript['full_text'])} chars)")
    output_path = save_transcript(metadata, transcript)
    print(f"  Saved to: {output_path}")

    return metadata.get("title", video_id)

def main():
    # Parse arguments
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    print(f"=== Nate Jones Transcript Downloader ===")
    print(f"Rate limiting: {MIN_DELAY}-{MAX_DELAY}s between videos")
    print(f"Batch breaks: {BATCH_BREAK_MIN//60}-{BATCH_BREAK_MAX//60} min every {BATCH_SIZE} videos")
    print(f"Limit: {limit} videos")
    print()

    # Load video IDs
    with open(VIDEO_IDS_FILE) as f:
        all_video_ids = [line.strip() for line in f if line.strip()]

    # Load progress
    progress = load_progress()
    completed = set(progress["completed"])

    # Filter to remaining videos
    remaining = [vid for vid in all_video_ids if vid not in completed]
    to_process = remaining[:limit]

    print(f"Total videos: {len(all_video_ids)}")
    print(f"Already completed: {len(completed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Processing this run: {len(to_process)}")
    print()

    if not to_process:
        print("Nothing to process!")
        return

    # Process videos
    success_count = 0
    for i, video_id in enumerate(to_process, 1):
        try:
            title = download_video(video_id, i, len(to_process))

            # Mark as completed
            progress["completed"].append(video_id)
            save_progress(progress)
            success_count += 1

            # Rate limiting
            if i < len(to_process):  # Don't delay after last video
                if i % BATCH_SIZE == 0:
                    # Longer break after batch
                    break_time = random.uniform(BATCH_BREAK_MIN, BATCH_BREAK_MAX)
                    print(f"\n=== Batch break: {break_time/60:.1f} minutes ===")
                    time.sleep(break_time)
                else:
                    # Normal delay
                    delay = random.uniform(MIN_DELAY, MAX_DELAY)
                    print(f"  Waiting {delay:.1f}s...")
                    time.sleep(delay)

        except Exception as e:
            error_msg = str(e)
            print(f"  ERROR: {error_msg}")

            # Check if rate limited
            if "RATE_LIMITED" in error_msg:
                print("\n!!! RATE LIMITED - STOPPING IMMEDIATELY !!!")
                print("Wait 24-48 hours before trying again.")
                progress["failed"].append({"id": video_id, "reason": error_msg, "time": datetime.now().isoformat()})
                save_progress(progress)
                break
            else:
                # Other error - log and continue
                progress["failed"].append({"id": video_id, "reason": error_msg, "time": datetime.now().isoformat()})
                save_progress(progress)

    print(f"\n=== Complete ===")
    print(f"Successfully downloaded: {success_count}")
    print(f"Total completed: {len(progress['completed'])}")
    print(f"Failed: {len(progress['failed'])}")

if __name__ == "__main__":
    main()
