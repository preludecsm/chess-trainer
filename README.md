# LocalRAG — Personal File Intelligence System

Fully local document Q&A over your macOS home folder.
**No API calls. No cloud. Runs entirely on your Mac mini M2.**

---

## Stack

| Layer | Tool |
|---|---|
| Inference | Gemma 4 8B via Ollama |
| Embeddings | nomic-embed-text via Ollama |
| Vector DB | ChromaDB (file-based, persistent) |
| Web UI | Chainlit (localhost:8000) |
| OCR | ocrmypdf (auto, via Homebrew) |

---

## Supported File Types

| Category | Extensions | Notes |
|---|---|---|
| PDF | `.pdf` | Auto-OCR for scanned pages |
| Word | `.docx` | |
| Apple Pages | `.pages` | Text extracted from XML bundle |
| Text / Markdown | `.txt`, `.md` | |
| Rich Text | `.rtf` | |
| Spreadsheets | `.xlsx`, `.xls`, `.csv` | One chunk per sheet |
| JSON | `.json` | FHIR R4 bundles auto-detected |
| XML | `.xml` | C-CDA/CCD health files auto-detected |
| Apple Mail native | `.emlx` | Index directly from Mail library |
| Standard email | `.eml` | |
| Mbox archives | `.mbox` | Apple Mail exports, Gmail Takeout |
| Outlook email | `.msg` | |
| iMessages | `chat.db` | Read-only SQLite, requires FDA |

Zip files are excluded. Unzip archives you want indexed;
the contents will be picked up automatically.

---

## ⚠️  iCloud Drive — Critical Setup Decision

### The Problem

macOS "Optimize Mac Storage" evicts infrequently-used files from local
disk, replacing them with stub placeholders. Python cannot read stubs —
only files physically present on disk can be indexed.

### Option A — Turn Off Optimize Mac Storage (Recommended)

1. **System Settings → Apple ID → iCloud → iCloud Drive**
2. Uncheck **"Optimize Mac Storage"**
3. Wait for all files to download (cloud icons in Finder disappear
   when a file is local)

**Tradeoff:** You need enough disk space for your full iCloud library.

### Option B — Force Download Before Indexing

```bash
# Force-download everything in iCloud Drive
brctl download ~/Library/Mobile\ Documents/com~apple~CloudDocs -r
```

macOS may re-evict files later, making the index stale.

### Check What Is Not Downloaded

```bash
# List iCloud stub files (not yet local)
find ~ -name "*.icloud" 2>/dev/null | head -40
```

---

## iMessages Setup

### Grant Full Disk Access to Terminal

macOS blocks access to `~/Library/Messages/chat.db` by default.

1. **System Settings → Privacy & Security → Full Disk Access**
2. Click **+** and add **Terminal** (or iTerm2)
3. Toggle it **on** and restart Terminal

### Verify Access

```bash
ls ~/Library/Messages/chat.db
# Should print the path — if you get "Operation not permitted", FDA is not set
```

### iCloud Messages

If "Messages in iCloud" is enabled (Settings → Messages → Messages in
iCloud), your full message history syncs to `chat.db` automatically.
No extra steps needed.

---

## Apple Mail — Exporting for Indexing

### Option A — Export Mailboxes (Simplest)

1. Open **Mail.app**
2. Select a mailbox in the sidebar (e.g. Inbox)
3. **Mailbox → Export Mailbox…** → save to `~/MailExports/`
4. Repeat for each mailbox (Sent, Archive, etc.)

Each export creates a `.mbox` file. Add `~/MailExports/` to
`EXTRA_INDEX_PATHS` in `config/settings.py`.

### Option B — Index .emlx Files Directly

Apple Mail's native files live at:
```
~/Library/Mail/V10/   (check: ls ~/Library/Mail/)
```

Add this path to `EXTRA_INDEX_PATHS`. Requires Full Disk Access for
Terminal (same grant as iMessages above).

---

## Gmail — Exporting for Indexing

1. Go to **https://takeout.google.com**
2. Deselect all → check **Mail** only
3. Optionally click "All Mail data included" to select specific labels
4. **Next step** → Send download link via email → File type: `.zip`
5. Download and unzip when ready
6. Copy the `.mbox` files from the `Mail/` folder inside to
   `~/MailExports/Gmail/`

The indexer handles `.mbox` natively. Re-export quarterly, or use
`mbsync` / `offlineimap` for a continuously updated local mirror.

---

## Health Records

Hospital portals (Epic MyChart, Kaiser, etc.) export clinical summaries
in standard formats. LocalRAG auto-detects and parses both:

- **FHIR R4 JSON** — emits one chunk per resource
  (Immunization, Condition, Medication, Encounter, Procedure, etc.)
- **C-CDA / CCD XML** — emits one chunk per clinical section

### Download Your Health Summary

1. Log in to your hospital's patient portal (e.g. MyChart)
2. Look for **"Download My Record"** or **"Health Summary"**
3. Choose **FHIR** or **CCD/CDA** format if given the option
4. Save anywhere under your home folder — the indexer auto-detects the format

### Example Query After Indexing

```
@file ~/Documents/Health/health_summary.json  List all my vaccinations with dates
```

---

## OCR for Scanned PDFs

`ocrmypdf` runs automatically during indexing whenever a PDF is
detected as image-only (scanned). OCR'd copies are cached in
`~/.localrag/ocr_cache/` so each file is only processed once.

### Install ocrmypdf

```bash
brew install ocrmypdf
```

Verify:
```bash
ocrmypdf --version
```

If `ocrmypdf` is not installed, scanned pages are silently skipped
and a warning is logged to `~/.localrag/indexer.log`.

---

## Prerequisites

```bash
# Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Ollama
brew install --cask ollama

# OCR
brew install ocrmypdf

# Python 3.11+
brew install python@3.11
```

### Pull Ollama models

```bash
ollama pull gemma4
ollama pull nomic-embed-text
```

### Ollama memory optimizations (add to ~/.zshrc)

```bash
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=30m
```

---

## Installation

```bash
cd localrag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## First Run — Index Your Files

```bash
source venv/bin/activate

# Full index of home folder (first run — allow 30–60 min)
python -m ingest.indexer

# Index a specific path only
python -m ingest.indexer --path ~/Documents

# Index iMessages only
python -m ingest.indexer --messages-only

# Force re-index everything (clears hash cache)
python -m ingest.indexer --force
```

Progress is shown in the terminal. Logs go to `~/.localrag/indexer.log`.

---

## Start the Web UI

```bash
source venv/bin/activate
chainlit run ui/app.py --port 8000
```

Open **http://localhost:8000** in your browser.

---

## Querying

### Scope Prefixes

| Prefix | Effect |
|---|---|
| *(none)* | Search entire index |
| `@file ~/path/to/file.ext  question` | Restrict to one exact file |
| `@folder ~/path/to/dir  question` | Restrict to files under that folder |

### Example Queries

```
@file ~/Documents/Health/health_summary.json
  Build a list of my active vaccinations with dates and upcoming schedule

@file ~/Documents/Health/health_summary.json
  What species of bacteria was implicated in my 2021-22 hospitalization?

@folder ~/Documents/Finance/Taxes
  What were my blended state and federal effective tax rates from 2018–2025?

@folder ~/Documents/Finance/Accounts
  Construct a history of house maintenance events

What medications am I currently prescribed?

Find any emails mentioning the Johnson contract from last year
```

### Commands

| Command | Effect |
|---|---|
| `/sources [query]` | Show matching files without generating an answer |
| `/stats` | Show total chunks in index |
| `/help` | Show help and examples |

---

## Auto-Watch for New Files

```bash
# Run in a separate terminal
python -m ingest.watcher
```

Or install as a background launchd service:

```bash
# Edit YOUR_USERNAME in the plist first
cp scripts/com.localrag.watcher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.localrag.watcher.plist

# Check it's running
launchctl list | grep localrag

# View watcher log
tail -f ~/.localrag/watcher.log
```

---

## Configuration (`config/settings.py`)

| Setting | Default | Purpose |
|---|---|---|
| `INDEX_ROOT` | `~/` | Root directory to index |
| `EXTRA_INDEX_PATHS` | `[]` | Additional paths (e.g. mail exports) |
| `IMESSAGE_DB_PATH` | `~/Library/Messages/chat.db` | iMessage DB |
| `IMESSAGE_LIMIT` | `50000` | Max messages per conversation |
| `SUPPORTED_EXTENSIONS` | see file | File types to index |
| `EXCLUDED_EXTENSIONS` | see file | File types to never index |
| `SKIP_DIRS` | see file | Directory names to skip |
| `CHUNK_SIZE` | `800` | Characters per chunk |
| `TOP_K_RESULTS` | `6` | Chunks retrieved for normal queries |
| `TOP_K_AGGREGATION` | `15` | Chunks retrieved for list/table queries |
| `LLM_NUM_CTX` | `4096` | LLM context window |
| `AGGREGATION_KEYWORDS` | see file | Words that trigger aggregation mode |

---

## Performance Notes (M2 16GB)

- Gemma 4 8B loads ~9.6 GB — set `OLLAMA_MAX_LOADED_MODELS=1`
- First full index of thousands of files: 30–60 min (longer with OCR)
- Subsequent runs skip unchanged files via MD5 hash cache
- OCR'd PDFs are cached; only new or changed PDFs are re-OCR'd
- If memory pressure appears in Activity Monitor, reduce `TOP_K_AGGREGATION`
- Health files (FHIR/CDA) index faster than mbox — they produce fewer,
  smaller chunks than large email archives

---

## Project Structure

```
localrag/
├── config/
│   └── settings.py          ← all configuration
├── ingest/
│   ├── parsers.py            ← dispatcher + all file parsers
│   ├── health_parsers.py     ← FHIR JSON + C-CDA XML parsers
│   ├── pdf_utils.py          ← PDF extraction + OCR fallback
│   ├── indexer.py            ← file walker, chunker, ChromaDB writer
│   └── watcher.py            ← filesystem watcher for auto-reindex
├── rag/
│   └── engine.py             ← retrieval, scope filters, LLM, citations
├── ui/
│   └── app.py                ← Chainlit web UI
├── scripts/
│   └── com.localrag.watcher.plist   ← launchd agent
├── requirements.txt
└── README.md
```
