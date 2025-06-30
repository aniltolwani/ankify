# Ankify - ChatGPT to Flashcards

Convert your ChatGPT Socratic dialogue conversations into spaced repetition flashcards.

## Quick Start

1. **Setup Authentication** (one-time)
   ```bash
   python scripts/setup_auth.py
   ```
   Log into ChatGPT when the browser opens.

2. **Run Full Pipeline**
   ```bash
   export OPENAI_API_KEY="your-key-here"
   python main.py --all
   ```

3. **Find Your Flashcards**
   Check the `flashcards/` directory for:
   - `flashcards_*.csv` - Universal format
   - `anki_flashcards_*.txt` - Anki import format
   - `flashcards_*.md` - Human-readable format
   - `flashcards_*.json` - Structured data

## Pipeline Steps

The pipeline consists of 4 steps:

1. **Fetch** - Download conversations from ChatGPT
2. **Extract** - Find Q&A pairs using GPT-4
3. **Post-process** - Filter Socratic questions & fix incomplete ones
4. **Generate** - Create flashcard files

Run individual steps:
```bash
python main.py --fetch         # Download new conversations
python main.py --extract       # Extract Q&A pairs
python main.py --postprocess   # Filter & fix questions
python main.py --generate      # Create flashcard files
```

## Essential Files

```
ankify/
├── main.py                    # Main orchestration script
├── scripts/
│   └── setup_auth.py         # One-time browser login setup
├── src/
│   ├── fetch_conversations.py # Download from ChatGPT
│   ├── extract_qa.py         # Extract Q&A pairs
│   ├── postprocess_qa.py     # Filter & fix questions
│   ├── generate_flashcards.py # Create output files
│   └── generate_fresh_answers.py # (Optional) Generate new answers
├── config.yaml               # Configuration
└── requirements.txt          # Python dependencies
```

## What It Extracts

The system specifically extracts Socratic teaching questions where ChatGPT tests your understanding:
- Questions marked with "Q:", "Quick Check:", "Test Question:"
- Questions at the end of teaching segments
- Excludes FAQ-style questions with immediate answers

## Example Output

**Question:** If you have a DNA strand that is 10 base pairs long, how many nucleotides total does that mean (considering both strands)?

**Answer:** A DNA strand that is 10 base pairs long would have 20 nucleotides in total, considering both strands. Each base pair consists of two nucleotides, one on each strand.

## Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

## Configuration

Edit `config.yaml` to customize:
- Model selection (default: gpt-4o)
- Output paths
- Processing options
