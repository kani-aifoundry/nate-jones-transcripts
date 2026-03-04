#!/usr/bin/env python3
"""
Parse batch transcript files and save each as individual episode files
in the nate-jones-transcripts repo format.
"""

import json
import os
import re
import sys

BATCH_FILES = [
    "/Users/kani/Downloads/batch_1_transcripts.md",
    "/Users/kani/Downloads/batch_2_transcripts.md",
    "/Users/kani/Downloads/batch_3_transcripts.md",
    "/Users/kani/Downloads/batch_4_transcripts.md",
]

EPISODES_DIR = "/Users/kani/nate-jones-transcripts/episodes"
PROGRESS_FILE = "/Users/kani/nate-jones-transcripts/progress.json"


def slugify(title, max_len=80):
    """Convert title to URL-friendly slug."""
    slug = title.lower()
    # Remove anything in parentheses for cleaner slugs (optional, keep if short)
    # Replace special chars with hyphens
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > max_len:
        # Cut at last hyphen before max_len
        slug = slug[:max_len]
        last_hyphen = slug.rfind("-")
        if last_hyphen > 40:
            slug = slug[:last_hyphen]
    return slug


def parse_batch_file(filepath):
    """Parse a batch file and return list of transcript dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    transcripts = []

    # Split on the pattern: end-of-transcript "---" followed by start-of-next-frontmatter "---"
    # The pattern between transcripts is: \n---\n\n---\n
    # We split by finding all frontmatter blocks
    # Strategy: find all occurrences of "---\ntitle:" which marks the start of each transcript
    parts = re.split(r"\n---\n\n---\n", content)

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        # Ensure part starts with ---
        if not part.startswith("---"):
            part = "---\n" + part

        # Parse frontmatter
        fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", part, re.DOTALL)
        if not fm_match:
            print(f"  WARNING: Could not parse frontmatter in {filepath}, part {i+1}")
            continue

        fm_text = fm_match.group(1)
        body = fm_match.group(2).strip()

        # Extract fields from frontmatter
        title_m = re.search(r'^title:\s*"(.+?)"', fm_text, re.MULTILINE)
        vid_m = re.search(r'^video_id:\s*"(.+?)"', fm_text, re.MULTILINE)
        url_m = re.search(r'^youtube_url:\s*"(.+?)"', fm_text, re.MULTILINE)
        date_m = re.search(r'^publish_date:\s*"(.+?)"', fm_text, re.MULTILINE)

        if not all([title_m, vid_m, url_m, date_m]):
            print(f"  WARNING: Missing frontmatter fields in {filepath}, part {i+1}")
            print(f"    title={title_m}, vid={vid_m}, url={url_m}, date={date_m}")
            continue

        title = title_m.group(1)
        video_id = vid_m.group(1)
        youtube_url = url_m.group(1)
        publish_date = date_m.group(1)

        # Extract transcript text (skip the markdown heading)
        # Body typically starts with "# Title\n\nTranscript text..."
        heading_match = re.match(r"^#\s+.+?\n\n(.*)", body, re.DOTALL)
        if heading_match:
            transcript_text = heading_match.group(1).strip()
        else:
            transcript_text = body

        # Check for placeholder/empty transcripts
        if not transcript_text or len(transcript_text) < 50:
            print(f"  WARNING: Very short transcript for '{title}' ({video_id}), length={len(transcript_text)}")

        transcripts.append({
            "title": title,
            "video_id": video_id,
            "youtube_url": youtube_url,
            "publish_date": publish_date,
            "transcript_text": transcript_text,
        })

    return transcripts


def build_transcript_md(t):
    """Build the transcript.md content in the repo format."""
    return f'''---
title: "{t['title']}"
video_id: "{t['video_id']}"
youtube_url: "{t['youtube_url']}"
publish_date: "{t['publish_date']}"
duration: "unknown"
duration_seconds: 0
view_count: 0
author: "Nate Jones"

yt_tags:
  []

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

# {t['title']}

{t['transcript_text']}
'''


def main():
    all_transcripts = []
    for bf in BATCH_FILES:
        if not os.path.exists(bf):
            print(f"ERROR: Batch file not found: {bf}")
            sys.exit(1)
        print(f"Parsing {os.path.basename(bf)}...")
        transcripts = parse_batch_file(bf)
        print(f"  Found {len(transcripts)} transcripts")
        all_transcripts.extend(transcripts)

    print(f"\nTotal transcripts parsed: {len(all_transcripts)}")

    # Load existing progress
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
    else:
        progress = {"completed": []}

    existing_ids = set(progress["completed"])

    saved = 0
    skipped_existing = 0
    skipped_other = 0
    new_video_ids = []

    for t in all_transcripts:
        slug = slugify(t["title"])
        folder_name = f"{t['publish_date']}-{slug}"
        folder_path = os.path.join(EPISODES_DIR, folder_name)

        # Check if video_id already exists in progress
        if t["video_id"] in existing_ids:
            print(f"  SKIP (already in progress): {t['video_id']} - {t['title'][:60]}")
            skipped_existing += 1
            continue

        # Check if folder already exists
        if os.path.exists(folder_path):
            print(f"  SKIP (folder exists): {folder_name}")
            skipped_existing += 1
            # Still add to progress if not there
            if t["video_id"] not in existing_ids:
                new_video_ids.append(t["video_id"])
                existing_ids.add(t["video_id"])
            continue

        # Create folder and write transcript
        os.makedirs(folder_path, exist_ok=True)
        transcript_path = os.path.join(folder_path, "transcript.md")
        content = build_transcript_md(t)
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(content)

        new_video_ids.append(t["video_id"])
        existing_ids.add(t["video_id"])
        saved += 1
        print(f"  SAVED: {folder_name}")

    # Update progress.json
    if new_video_ids:
        progress["completed"].extend(new_video_ids)
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f, indent=2)
        print(f"\nUpdated progress.json with {len(new_video_ids)} new video IDs")

    print(f"\n--- SUMMARY ---")
    print(f"Total parsed:       {len(all_transcripts)}")
    print(f"Saved (new):        {saved}")
    print(f"Skipped (existing): {skipped_existing}")
    print(f"Skipped (other):    {skipped_other}")
    print(f"New IDs added:      {len(new_video_ids)}")


if __name__ == "__main__":
    main()
