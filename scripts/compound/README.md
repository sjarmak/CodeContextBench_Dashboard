# Compound Engineering - Nightly Loop

An automated nightly loop that reviews your Claude Code sessions, extracts learnings, researches improvements, and ships code while you sleep.

## How It Works

Two jobs run every night via macOS launchd:

### Job 1: Compound Review (default 10:30 PM)

1. Exports Claude Code transcripts via `claude-code-transcripts all`
2. Reads recent session HTML from `~/claude-archive/{project}/`
3. Extracts patterns, gotchas, and decisions into `CLAUDE.md`
4. Commits and pushes to main

### Job 2: Auto-Compound (default 11:00 PM)

Runs 5 phases:

| Phase | What happens | Output |
|-------|-------------|--------|
| 1. Research | Reviews codebase, past reports, and CLAUDE.md | `reports/nightly/YYYY-MM-DD-review.md` |
| 2. PRD | Creates a PRD from the top recommendation | `tasks/prd-compound-YYYY-MM-DD.md` |
| 3. Ralph JSON | Converts PRD to Ralph's task format | `prd.json` (project root) |
| 4. Ralph loop | Runs `ralph.sh --tool claude 20` on a feature branch | Code changes, `progress.txt` |
| 5. Validate | Runs tests, pushes branch, creates draft PR | Draft PR on GitHub |

## Quick Start

### Set up a new project

```bash
./setup-compound.sh /path/to/your/project
```

With custom schedule (to stagger multiple projects):

```bash
./setup-compound.sh /path/to/your/project \
  --review-hour 1 --review-min 0 \
  --compound-hour 1 --compound-min 30
```

### Toggle on/off

```bash
# Check status
/path/to/project/scripts/compound/toggle.sh

# Disable the nightly loop
/path/to/project/scripts/compound/toggle.sh off

# Re-enable it
/path/to/project/scripts/compound/toggle.sh on
```

## Prerequisites

- **macOS** (uses launchd for scheduling)
- **Claude Code CLI** (`claude`) installed and in PATH
- **`claude-code-transcripts` CLI** installed (for exporting session history)
- **`gh` CLI** installed (for creating PRs)
- **`jq`** installed (for parsing prd.json)
- **Git remote** (`origin`) configured on the project
- **Ralph** (`scripts/ralph/ralph.sh`) in the project if you want the implementation loop
- **Caffeinate LaunchAgent** running to keep Mac awake (setup instructions below)

## File Structure

After setup, your project will have:

```
your-project/
├── CLAUDE.md                          # Living knowledge base (auto-updated)
├── prd.json                           # Current Ralph task list (auto-generated)
├── progress.txt                       # Ralph iteration log
├── logs/
│   ├── compound-review.log            # Review job output
│   └── auto-compound.log              # Compound job output
├── reports/
│   ├── priorities.md                  # Review focus areas (you edit this)
│   └── nightly/
│       ├── 2026-01-29-review.md       # Nightly research reports
│       └── 2026-01-30-review.md
├── tasks/
│   └── prd-compound-2026-01-29.md     # Generated PRDs
└── scripts/
    ├── daily-compound-review.sh       # Review job script
    └── compound/
        ├── auto-compound.sh           # Compound job script
        ├── setup-compound.sh          # This setup tool
        ├── toggle.sh                  # On/off toggle
        └── README.md                  # This file
```

LaunchAgent plists are created at:
```
~/Library/LaunchAgents/com.compound.{project-name}.review.plist
~/Library/LaunchAgents/com.compound.{project-name}.compound.plist
```

## What You Control

| File | Purpose | Who edits |
|------|---------|-----------|
| `reports/priorities.md` | Focus areas for nightly review | You |
| `CLAUDE.md` | Accumulated learnings | Auto + you |
| Schedule times | When jobs run | Set at setup time |
| `toggle.sh` | Enable/disable | You |

## Keeping Mac Awake

launchd won't wake a sleeping Mac. Set up a caffeinate agent:

```bash
# Create plist
cat > ~/Library/LaunchAgents/com.compound.caffeinate.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.compound.caffeinate</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string>
    <string>-i</string>
    <string>-t</string>
    <string>32400</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>17</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
</dict>
</plist>
EOF

# Load it
launchctl load ~/Library/LaunchAgents/com.compound.caffeinate.plist
```

This keeps your Mac awake from 5 PM to 2 AM (9 hours). Extend the `-t` value if your jobs run later.

## Debugging

```bash
# Check if jobs are scheduled
launchctl list | grep compound

# View logs
tail -f /path/to/project/logs/compound-review.log
tail -f /path/to/project/logs/auto-compound.log

# Run manually
launchctl start com.compound.{project-name}.review
launchctl start com.compound.{project-name}.compound
```

## Multiple Projects

Stagger schedules so projects don't overlap (Ralph can run for hours):

```bash
# Project A: 10:30 PM / 11:00 PM (default)
./setup-compound.sh ~/projects/project-a

# Project B: 1:00 AM / 1:30 AM
./setup-compound.sh ~/projects/project-b \
  --review-hour 1 --review-min 0 \
  --compound-hour 1 --compound-min 30

# Project C: 4:00 AM / 4:30 AM
./setup-compound.sh ~/projects/project-c \
  --review-hour 4 --review-min 0 \
  --compound-hour 4 --compound-min 30
```
