# Ankify - ChatGPT to Flashcards

Automatically convert your ChatGPT Socratic dialogues into spaced repetition flashcards.

## Features

- 🤖 Fetches conversations directly from ChatGPT (no manual export needed)
- 🎯 Extracts pedagogical Q&A pairs using GPT-4
- 📚 Creates flashcards in Mochi (or saves locally)
- 🔄 Runs mostly automated (manual login every 2-4 weeks)

## Quick Start

### 1. Install Dependencies

```bash
# Option 1: Use the helper script (recommended)
./run.sh setup

# Option 2: Manual setup
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Initial Setup (One-time)

```bash
# Login to ChatGPT and save browser profile
./run.sh setup
# Or: source venv/bin/activate && python scripts/setup_auth.py
```

This opens a browser window. Log in to ChatGPT, then press Enter to save the profile.

### 3. Configure

Edit `config.yaml`:
- Set your Mochi `deck_id` (or leave as-is to save cards locally)
- Adjust other settings as needed

### 4. Set API Keys

```bash
export OPENAI_API_KEY="sk-..."
export MOCHI_API_KEY="your-mochi-api-key"  # Optional
```

### 5. Run Pipeline

```bash
# Run full pipeline
./run.sh

# Or run individual steps
./run.sh --fetch    # Fetch conversations
./run.sh --extract  # Extract Q&A pairs  
./run.sh --generate # Create flashcards

# If not using the helper script:
source venv/bin/activate
python main.py
```

## Automation

Add to crontab for daily runs:

```bash
# Run at 2 AM daily
0 2 * * * cd /path/to/ankify && python main.py >> ankify.log 2>&1
```

## How It Works

1. **Fetch**: Uses Playwright to access ChatGPT with saved browser profile
2. **Extract**: GPT-4 identifies teaching questions and answers
3. **Generate**: Creates flashcards with question on front, answer on back

## Maintenance

- The browser profile lasts 2-4 weeks before needing manual re-login
- Check logs for "Session expires in X days" warnings
- Re-run `python scripts/setup_auth.py` when needed

## Output

- Conversations saved to `data/*.json`
- Extracted Q&A pairs in `data/extracted_qa.json`
- Local flashcards in `data/flashcards.jsonl` (if Mochi not configured)
