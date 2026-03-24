# Nate Jones Transcripts

Transcript archive of [Nate Jones](https://www.youtube.com/@NateBJones) YouTube videos.

## Stats

- **Videos Downloaded**: 497
- **Date Range**: .DS_Store - unknown-_v
- **Last Updated**: Mar 23, 2026

## Structure

```
nate-jones-transcripts/
├── README.md
├── index.json                    # Master index of all videos
├── index/                        # Topic-based index (111 topics)
│   ├── README.md                 # All topics with episode counts
│   ├── ai-agents.md              # Episodes about AI agents
│   ├── anthropic.md              # Episodes mentioning Anthropic
│   ├── claude.md                 # Episodes about Claude
│   ├── openai.md                 # Episodes about OpenAI
│   └── ...                       # 100+ more topic files
├── episodes/
│   └── YYYY-MM-DD-video-title/
│       └── transcript.md         # YAML frontmatter + full transcript
└── scripts/
    ├── download.py               # Download script (uses Supadata API)
    ├── enrich.py                 # AI enrichment (entities, topics, etc.)
    ├── create_index.py           # Generates index.json
    └── build_index.py            # Builds topic index files
```

## Transcript Format

Each `transcript.md` contains:

```yaml
---
title: "Video Title"
video_id: "abc123"
youtube_url: "https://www.youtube.com/watch?v=abc123"
substack_url: "https://natesnewsletter.substack.com/p/..."
publish_date: "2026-01-14"
duration: "32:18"
view_count: 107305
yt_tags:
  - "AI agents"
  - "Claude"

# AI-enriched metadata
content_type: "Tutorial"        # News Roundup, Deep Dive, Tutorial, Framework, Opinion, Case Study
primary_topic: "AI Tools"       # AI Agents, AI Strategy, AI Tools, Career, Prompting, AI News
difficulty: "Advanced"          # Beginner, Intermediate, Advanced
audience:
  - "Engineers"
  - "Executives"
entities:
  companies:
    - "OpenAI"
    - "Anthropic"
  people:
    - "Sam Altman"
  products:
    - "Claude"
    - "ChatGPT"
  models:
    - "GPT-4"
    - "Claude 3.5"
concepts:
  - "Key insight extracted from transcript"
summary:
  - "First key point"
  - "Second key point"
---

# Video Title

[Full transcript text here]
```

## Topic Index

Browse episodes by topic via the [`index/`](index/) folder:

**Top Topics:**
- [AI Tools](index/ai-tools.md) (311 episodes)
- [AI Strategy](index/ai-strategy.md) (284 episodes)
- [AI News](index/ai-news.md) (267 episodes)
- [Anthropic](index/anthropic.md) (204 episodes)
- [Claude](index/claude.md) (199 episodes)
- [OpenAI](index/openai.md) (176 episodes)
- [AI Agents](index/ai-agents.md) (171 episodes)

[See all 111 topics →](index/README.md)

## Usage

### Search transcripts
```bash
grep -r "Claude Code" episodes/
```

### Use index.json
```python
import json
with open('index.json') as f:
    data = json.load(f)
for video in data['videos']:
    print(f"{video['publish_date']}: {video['title']}")
```

### Filter by enriched metadata
```python
# Find all tutorials for engineers
tutorials = [v for v in data['videos']
             if v.get('content_type') == 'Tutorial'
             and 'Engineers' in v.get('audience', [])]

# Find videos mentioning Anthropic
anthropic_vids = [v for v in data['videos']
                  if 'Anthropic' in v.get('entities', {}).get('companies', [])]
```

### Download more videos
```bash
# Set your Supadata API key
export SUPADATA_API_KEY="your_key_here"

# Download next batch
python download.py 100
```

## Credits

- Content by [Nate Jones](https://www.youtube.com/@NateBJones)
- Transcripts via [Supadata API](https://supadata.ai)
