#!/usr/bin/env python3
"""
Generate flashcards in Mochi from extracted Q&A pairs.
"""

import json
import logging
import requests
import base64
from pathlib import Path
import os
import yaml
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

MOCHI_API_KEY = os.getenv("MOCHI_API_KEY")
MOCHI_BASE_URL = "https://app.mochi.cards/api"
DATA_DIR = Path(config['paths']['data_dir'])

def create_mochi_card(question: str, answer: str, deck_id: str, tags: List[str] = None) -> bool:
    """Create a single card in Mochi."""
    if not MOCHI_API_KEY:
        logging.error("MOCHI_API_KEY not set")
        return False
    
    # Prepare auth header
    auth_str = base64.b64encode(f"{MOCHI_API_KEY}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json"
    }
    
    # Prepare card data
    payload = {
        "content": f"{question}\n---\n{answer}",
        "deck-id": deck_id,
        "review-reverse?": False
    }
    
    # Add tags if provided
    if tags:
        payload["manual-tags"] = tags
    
    # Create card
    try:
        response = requests.post(
            f"{MOCHI_BASE_URL}/cards",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create card: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response: {e.response.text}")
        return False

def process_qa_pairs():
    """Process extracted Q&A pairs and create Mochi cards."""
    # Load extracted Q&A pairs
    qa_file = DATA_DIR / "extracted_qa.json"
    if not qa_file.exists():
        logging.error(f"No extracted Q&A pairs found at {qa_file}")
        logging.info("Run extract_qa.py first")
        return 1
    
    with open(qa_file) as f:
        qa_pairs = json.load(f)
    
    logging.info(f"Processing {len(qa_pairs)} Q&A pairs...")
    
    # Check if we have Mochi credentials
    if not MOCHI_API_KEY:
        logging.warning("MOCHI_API_KEY not set - will save cards locally only")
        output_file = DATA_DIR / "flashcards.jsonl"
        with open(output_file, 'w') as f:
            for qa in qa_pairs:
                if qa.get('question') and qa.get('answer'):
                    card = {
                        "front": qa['question'],
                        "back": qa['answer'],
                        "tags": ["chatgpt", "socratic"],
                        "source": qa.get('title', 'Unknown')
                    }
                    f.write(json.dumps(card) + "\n")
        logging.info(f"✅ Saved {len(qa_pairs)} cards to {output_file}")
        return 0
    
    # Create cards in Mochi
    deck_id = config['mochi']['deck_id']
    if deck_id == "YOUR_DECK_ID":
        logging.error("Please set your Mochi deck_id in config.yaml")
        return 1
    
    created = 0
    failed = 0
    
    for i, qa in enumerate(qa_pairs):
        question = qa.get('question', '').strip()
        answer = qa.get('answer', '').strip()
        
        if not question or not answer:
            logging.warning(f"  [{i+1}] Skipping - missing question or answer")
            continue
        
        # Create tags
        tags = ["chatgpt", "socratic", "auto-generated"]
        if qa.get('title'):
            # Add first word of title as tag (often the topic)
            topic = qa['title'].split()[0].lower()
            if topic not in ['untitled', 'new', 'chat']:
                tags.append(topic)
        
        logging.info(f"  [{i+1}/{len(qa_pairs)}] Creating card: {question[:50]}...")
        
        if create_mochi_card(question, answer, deck_id, tags):
            created += 1
        else:
            failed += 1
        
        # Rate limiting
        if i < len(qa_pairs) - 1:
            import time
            time.sleep(0.5)
    
    logging.info(f"\n✅ Card generation complete!")
    logging.info(f"   Created: {created}")
    logging.info(f"   Failed: {failed}")
    
    return 0

def main():
    """Main entry point."""
    try:
        return process_qa_pairs()
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())