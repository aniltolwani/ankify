# Ankify: Automated Socratic Dialogue to Flashcard System

## Overview

Ankify is an automated system that transforms ChatGPT web conversations into spaced repetition flashcards. It processes your exported ChatGPT data to extract pedagogical questions and their comprehensive answers, then creates cards in Mochi (preferred) or Anki.

## Important: ChatGPT Data Access Methods

### Option 1: Direct Backend API (Recommended for Automation)

Use ChatGPT's unofficial backend API endpoints:

```python
# Endpoints
GET https://chat.openai.com/backend-api/conversations?offset=0&limit=100
GET https://chat.openai.com/backend-api/conversation/{conversation_id}

# Required headers
Authorization: Bearer <session_token>
User-Agent: Mozilla/5.0...
```

The `session_token` is from the `__Secure-next-auth.session-token` cookie (valid ~24h).

### Option 2: Browser Extensions (Manual)

- [chatgpt-exporter](https://github.com/pionxzh/chatgpt-exporter) - Feature-rich with multiple formats
- [chatgpt-export](https://github.com/ryanschiang/chatgpt-export) - Simple and lightweight

### Option 3: Official Data Export (Backup)

1. Settings → Data Controls → Export Data
2. Wait for email with download link
3. Download ZIP containing `conversations.json`

## Key Improvements Over Original Blueprint

### 1. Enhanced Socratic Pattern Recognition
- **Multi-pattern detection**: Identifies questions marked as "Test Question", "Quick Check", "Q:", and contextual questions
- **Pedagogical flow preservation**: Tracks the teaching narrative across multiple exchanges
- **Answer synthesis**: Combines user attempts with assistant corrections for comprehensive answers

### 2. Mochi-First Architecture
- **Direct API integration**: Leverages Mochi's markdown support and deck hierarchies
- **Rich content support**: Preserves code blocks, math notation, and formatting
- **Tag automation**: Intelligently tags based on conversation topics

### 3. Intelligent Processing Pipeline
- **Context-aware chunking**: Respects question-answer boundaries when splitting conversations
- **Deduplication**: Fuzzy matching to avoid duplicate cards across sessions
- **Quality scoring**: Prioritizes high-value pedagogical questions

## System Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ ChatGPT Backend │────▶│  API Fetcher     │────▶│  Conversation   │
│      API        │     │  (w/ Auth)      │     │     Cache       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Mochi/Anki     │◀────│  Card Generator  │◀────│  Q&A Extractor  │
│     API         │     │                  │     │   (GPT-4o)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
                                                  ┌─────────────────┐
                                                  │ Answer Enhancer │
                                                  │   (o3-mini)     │
                                                  └─────────────────┘
```

## Workflow

### 1. Fully Automated Daily Process

```bash
# Automated token refresh (runs every 20 hours)
python scripts/refresh_token.py

# Automated conversation sync and processing (via cron)
0 */6 * * * python main.py --sync --process
```

### 2. Token Management Strategy

We use Playwright's persistent browser context for near-automated token management:

**Initial Setup (One-time):**
```python
# scripts/setup_auth.py
from playwright.sync_api import sync_playwright

# First run with headless=False for manual login
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        "./chatgpt_profile",
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = ctx.pages[0]
    page.goto("https://chat.openai.com")
    input("Login manually, then press Enter...")
    ctx.close()
```

**Daily Automated Fetch:**
```python
# scripts/fetch_conversations.py
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests, json, time, logging

PROFILE = Path("./chatgpt_profile")
CONV_URL = "https://chat.openai.com/backend-api/conversations?offset=0&limit=100"

def load_cookies():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, headless=True, 
            args=['--disable-blink-features=AutomationControlled']
        )
        page = ctx.new_page()
        page.goto("https://chat.openai.com", wait_until="networkidle")
        page.wait_for_timeout(2000)  # Allow token refresh
        
        cookies = {c['name']: c for c in ctx.cookies()
                   if c['name'] in ['__Secure-next-auth.session-token',
                                    '__Secure-next-auth.csrf-token',
                                    '_puid']}
        
        # Check token expiry
        exp_ts = cookies['__Secure-next-auth.session-token'].get('expires', 0)
        if time.time() > exp_ts - 172_800:  # < 2 days left
            logging.warning("Session token expiring soon - re-login needed")
            # Send notification here
        
        ctx.close()
        return cookies

def fetch_conversations(cookies):
    token = cookies['__Secure-next-auth.session-token']['value']
    ck = "; ".join(f"{c['name']}={c['value']}" for c in cookies.values())
    headers = {
        "Authorization": f"Bearer {token}",
        "Cookie": ck,
        "User-Agent": "Mozilla/5.0"
    }
    
    r = requests.get(CONV_URL, headers=headers, allow_redirects=False)
    if r.status_code == 302:
        raise RuntimeError("Session expired - run setup_auth.py again")
    
    return r.json()["items"]
```

**How it Works:**
- Browser profile persists cookies for 2-4 weeks
- ChatGPT auto-refreshes JWT tokens on each visit
- Proactive expiry warnings 2 days before
- Clean failure detection via 302 redirects

**Maintenance:**
- Runs unattended for weeks
- Manual re-login only when cookies fully expire
- Email/Slack alerts when intervention needed

### 3. Conversation Tracking

SQLite database tracks:
- Processed conversation IDs and message timestamps
- Avoids reprocessing same content
- Incremental updates only

## Core Components

### 1. Conversation Parser (`parse_conversations.py`)
```python
# Parses conversations.json from ChatGPT export
# Extracts messages with role and content
# Filters conversations by title pattern (e.g., containing "Socratic")
# Tracks processed conversations in SQLite
```

### 2. Q&A Extractor (`extract_qa.py`)
```python
# Uses GPT-4o with specialized Socratic dialogue prompt
# Identifies question patterns and teaching moments
# Preserves context and pedagogical flow
# Returns structured JSON with question metadata
```

### 3. Answer Enhancer (`enhance_answers.py`)
```python
# Uses o3-mini for deep reasoning when needed
# Only enhances incomplete or missing answers
# Synthesizes user attempts + assistant corrections
# Creates comprehensive, accurate answers
```

### 4. Card Generator (`generate_cards.py`)
```python
# Formats cards for Mochi API with markdown
# Uses content field with "---" separator for Q&A
# Implements intelligent deck assignment
# Adds metadata tags via manual-tags field
# Handles code blocks and LaTeX formatting
# Creates deck if it doesn't exist
```

### 5. Orchestrator (`main.py`)
```python
# Manages the full pipeline
# Implements error handling and retries
# Tracks processing state
# Sends notifications on completion
```

## Extraction Strategy

### Pattern Recognition
The extractor identifies these question types:

1. **Explicit Test Questions**
   - Marked with "Test Question #X:", "Quick Check:", "Q:"
   - Clear answer expectations

2. **Implicit Teaching Questions**
   - "How might you...?"
   - "What would happen if...?"
   - "Can you explain...?"

3. **Verification Questions**
   - Follow-ups to user responses
   - Clarification requests

### Answer Synthesis Algorithm
```
1. Identify question in assistant message
2. Find user's response (if any)
3. Locate assistant's feedback/correction
4. Synthesize complete answer:
   - If user correct: user answer + any elaboration
   - If user incorrect: correction + explanation
   - If no user response: assistant's complete answer
```

## Configuration

### `config.yaml`
```yaml
chatgpt:
  export_path: "data/conversations.json"
  conversation_filter: "Socratic"  # Only process conversations with this in title
  
openai:
  api_key: ${OPENAI_API_KEY}
  
mochi:
  api_key: ${MOCHI_API_KEY}
  default_deck: "AI Learning::Socratic Dialogues"
  
processing:
  chunk_size: 40  # messages per chunk
  dedup_threshold: 0.85
  enhance_incomplete: true  # Use o3-mini for missing answers
  
models:
  extractor: "gpt-4o-mini"
  enhancer: "o3-mini"  # For answer enhancement
  
database:
  path: "data/ankify.db"
  
notifications:
  webhook_url: ${SLACK_WEBHOOK}  # Optional
```

## API Integration Details

### Mochi API Usage
```python
# Authentication
headers = {
    "Authorization": f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
}

# Create card (Option 1: Using markdown with separator)
payload = {
    "content": f"{question}\n---\n{enhanced_answer}",  # Markdown with separator
    "deck-id": deck_id,
    "review-reverse?": False,
    "manual-tags": ["socratic", "auto-generated", topic]
}

# Create card (Option 2: Using template with fields)
payload = {
    "content": "# << Front >>\n---\n<< Back >>",  # Template reference
    "deck-id": deck_id,
    "template-id": template_id,  # Need to get this from templates endpoint
    "fields": {
        "Front": {
            "id": "Front",
            "value": question
        },
        "Back": {
            "id": "Back", 
            "value": enhanced_answer
        }
    },
    "review-reverse?": False,
    "manual-tags": ["socratic", "auto-generated", topic]
}
```

### Alternative: Anki Integration
```python
# For users preferring Anki
payload = {
    "action": "addNote",
    "version": 6,
    "params": {
        "note": {
            "deckName": "Socratic::Learning",
            "modelName": "Basic",
            "fields": {
                "Front": question,
                "Back": answer
            },
            "tags": tags
        }
    }
}
```

## Deployment Options

### 1. GitHub Actions (Recommended)
```yaml
name: daily-flashcard-sync
on:
  schedule:
    - cron: "0 7 * * *"  # 7 AM daily
  workflow_dispatch:

jobs:
  generate-cards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python main.py --days 1
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          MOCHI_API_KEY: ${{ secrets.MOCHI_API_KEY }}
```

### 2. Local Cron
```bash
# Add to crontab
0 7 * * * cd /path/to/ankify && python main.py --days 1
```

### 3. AWS Lambda
- Use EventBridge for scheduling
- Store secrets in AWS Secrets Manager
- Output logs to CloudWatch

## File Structure
```
ankify/
├── README.md
├── project.md              # This file
├── requirements.txt        # Dependencies
├── config.yaml            # Configuration
├── src/
│   ├── __init__.py
│   ├── fetch_conversations.py
│   ├── extract_qa.py
│   ├── enhance_answers.py
│   ├── generate_cards.py
│   ├── deduplication.py
│   └── utils/
│       ├── __init__.py
│       ├── chunking.py
│       └── prompts.py
├── main.py                # Entry point
├── eval.py                # Evaluation script
├── manual_extract.py      # Manual extraction tool
├── tests/
│   ├── test_extraction.py
│   ├── test_enhancement.py
│   └── fixtures/
│       └── sample_conversations.json
├── evals/
│   ├── sample_threads/     # JSONL exports from OpenAI
│   │   ├── biology_thread.jsonl
│   │   ├── concurrency_thread.jsonl
│   │   └── README.md
│   ├── expected_outputs/   # Hand-verified Q&As
│   │   ├── biology_expected.json
│   │   └── concurrency_expected.json
│   └── eval_results/      # Comparison outputs
└── .github/
    └── workflows/
        └── daily-sync.yml
```

## Enhanced Prompts

### Extraction Prompt
```python
SOCRATIC_EXTRACTOR = """
You are an expert at identifying pedagogical questions in Socratic dialogues.

Extract ALL questions that serve a teaching purpose, including:
1. Explicit test questions (marked with "Test Question", "Q:", etc.)
2. Comprehension checks ("What would happen if...?")
3. Conceptual probes ("How do you think about...?")
4. Application questions ("How might you...?")

For each question, capture:
- The complete question text
- Any user response (even partial or incorrect)
- The assistant's feedback/correction/answer
- Teaching context (what concept is being tested)

Output JSON:
[{
  "question": "full question text",
  "user_answer": "user's response or null",
  "correct_answer": "assistant's answer/correction",
  "concept": "topic being taught",
  "difficulty": "beginner|intermediate|advanced"
}]
"""
```

### Answer Enhancement Prompt
```python
ANSWER_ENHANCER = """
Create a comprehensive flashcard answer by:
1. Synthesizing the user's attempt (if any) with the assistant's correction
2. Providing the most accurate and complete answer
3. Including key insights from the teaching exchange
4. Keeping the answer concise but complete
5. Preserving code/examples where relevant

Context:
- Question: {question}
- User attempt: {user_answer}
- Assistant's response: {assistant_answer}

Generate an ideal flashcard answer that captures the learning objective.
"""
```

## Quality Assurance

### Deduplication Strategy
- Fuzzy matching on question text (threshold: 0.85)
- Semantic embedding comparison for edge cases
- Track question hashes to avoid re-processing

### Card Quality Metrics
- **Completeness**: Both Q and A present
- **Clarity**: Question is self-contained
- **Pedagogical value**: Tests understanding, not memorization
- **Answer accuracy**: Verified against source material

## Cost Optimization

### Estimated Costs (per 100-message conversation)
- OpenAI API fetch: ~$0.001
- GPT-4o extraction: ~$0.02
- Claude enhancement: ~$0.05
- Total: ~$0.07 per conversation

### Optimization Strategies
1. Cache processed conversations
2. Batch API calls
3. Use smaller models for simple extractions
4. Skip enhancement for clear Q&A pairs

## Future Enhancements

1. **Multi-source support**: Slack, Discord, ChatGPT exports
2. **Adaptive scheduling**: More cards from recent topics
3. **Performance tracking**: Monitor card success rates
4. **AI feedback loop**: Improve extraction based on review data
5. **Voice notes**: Generate audio for cards
6. **Collaborative decks**: Share generated cards with study groups

## Example Conversations & Extraction Results

### Example 1: DNA/Biology Socratic Dialogue

**Raw Conversation:**
```
User: Okay, so the way to think about this is that DNA is wrapped in this helix structure...
Assistant: [Provides structured explanation with 3 components]
...
### ✅ Quick Check #1:
Q: What are the three components of a DNA nucleotide?
Q: Which bases pair together?
```

**Extracted Cards:**
1. **Q:** "What are the three components of a DNA nucleotide?"
   **A:** "1. A sugar (deoxyribose), 2. A phosphate group (links to the next nucleotide), 3. A nitrogenous base (A, T, C, or G)"

2. **Q:** "Which bases pair together?"
   **A:** "A always pairs with T, C always pairs with G"

3. **Q:** "If the sequence on one strand is 5'- A C G -3', what would the complementary strand be?"
   **A:** "3'- T G C -5' (complementary bases in reverse orientation)"

### Example 2: Concurrency/Threading Dialogue

**Raw Conversation:**
```
User: in the case where both are true...
Assistant: You're *very* close—and you've hit on the classic concurrency pitfall!
...
### Test Question 4:
How might you modify the threads' behavior so that each prints at most once per value of n?
```

**Extracted Cards:**
1. **Q:** "How might you modify the threads' behavior so that each prints at most once per value of n—and only when that condition is uniquely true?"
   **A:** "Add a 'fizz_printed' (and 'buzz_printed') boolean for each thread, reset these right after n is updated in the main loop. Each thread checks both their condition AND whether they've already printed for this value of n."

2. **Q:** "What potential race condition could still exist if you don't reset all print flags while holding the mutex in the main thread when updating n?"
   **A:** "If you don't do it while holding the mutex, someone could still read the value before the update happens and again there could be multiple prints"

## Extraction Validation

The extraction approach WILL work because:

1. **Clear Question Markers**: Your conversations use explicit markers like "✅ Quick Check #1:", "### Test Question 4:", making extraction straightforward
2. **Structured Q&A Flow**: Questions are followed by user responses and assistant feedback
3. **Self-Contained Questions**: Each question can stand alone on a flashcard
4. **Complete Answers Available**: Either from user+correction or assistant's explanation

## Evaluation & Testing

### Manual Extraction Flow

Use `manual_extract.py` to test extraction on specific conversations:

```bash
# Extract from a single thread
python manual_extract.py --thread-id thread_abc123 --output extracted.json

# Extract from exported JSONL file
python manual_extract.py --file evals/sample_threads/biology_thread.jsonl --output extracted.json

# Extract with specific date range
python manual_extract.py --thread-id thread_abc123 --start-date 2025-01-29 --end-date 2025-01-30
```

### Evaluation Script

The `eval.py` script compares extraction results against hand-verified outputs:

```bash
# Run evaluation on sample threads
python eval.py

# Run on specific thread
python eval.py --thread evals/sample_threads/biology_thread.jsonl

# Generate detailed diff report
python eval.py --detailed
```

### Sample Thread Format (JSONL)

Each line in the JSONL file represents one message:
```json
{"id": "msg_123", "role": "assistant", "content": "Let's test your understanding.\n\n### ✅ Quick Check #1:\n**Q: What are the three components of a DNA nucleotide?**", "created_at": 1234567890}
{"id": "msg_124", "role": "user", "content": "A sugar, phosphate group, and nitrogenous base", "created_at": 1234567891}
{"id": "msg_125", "role": "assistant", "content": "Correct! Specifically, the sugar is deoxyribose...", "created_at": 1234567892}
```

### Expected Output Format

```json
{
  "thread_id": "thread_abc123",
  "extraction_date": "2025-01-30",
  "cards": [
    {
      "question": "What are the three components of a DNA nucleotide?",
      "answer": "1. A sugar (deoxyribose), 2. A phosphate group (links to the next nucleotide), 3. A nitrogenous base (A, T, C, or G)",
      "user_answer": "A sugar, phosphate group, and nitrogenous base",
      "source_message_ids": ["msg_123", "msg_124", "msg_125"],
      "concept": "DNA structure",
      "confidence_score": 0.95
    }
  ],
  "stats": {
    "total_messages": 125,
    "questions_found": 8,
    "cards_created": 8,
    "extraction_time_seconds": 2.4
  }
}
```

### Evaluation Metrics

The evaluation script calculates:
- **Precision**: % of extracted Q&As that match expected
- **Recall**: % of expected Q&As that were found
- **F1 Score**: Harmonic mean of precision and recall
- **Fuzzy Match Score**: For partial matches (>85% similarity)

### Creating Test Data

1. **Export a thread from OpenAI**:
   ```python
   # Use fetch_conversations.py with --export flag
   python src/fetch_conversations.py --thread-id thread_abc123 --export biology_thread.jsonl
   ```

2. **Manually create expected outputs**:
   - Review the exported JSONL
   - Create corresponding expected.json with Q&A pairs
   - Include edge cases (unanswered questions, multi-part questions)

3. **Add to test suite**:
   ```bash
   cp biology_thread.jsonl evals/sample_threads/
   cp biology_expected.json evals/expected_outputs/
   ```

## Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/ankify.git
cd ankify

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your API keys

# Test extraction on sample data
python eval.py

# Manual extraction test
python manual_extract.py --file evals/sample_threads/biology_thread.jsonl

# Test locally
python main.py --days 1 --dry-run

# Deploy to GitHub Actions
# Add secrets: OPENAI_API_KEY, MOCHI_API_KEY
# Enable Actions and workflow
```

## Dependencies

```txt
openai>=1.35.0
anthropic>=0.25.0
pyyaml>=6.0
requests>=2.31.0
python-dateutil>=2.8.2
tenacity>=8.2.3  # For retries
rich>=13.7.0     # For CLI output
pydantic>=2.5.0  # For validation
```

## License

MIT License - Feel free to adapt for your learning needs!