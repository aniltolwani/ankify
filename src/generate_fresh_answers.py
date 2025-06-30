#!/usr/bin/env python3
"""Generate fresh, accurate answers for questions using GPT-4o"""

import json
import logging
from pathlib import Path
import os
import requests
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY environment variable not set")
    exit(1)

DATA_DIR = Path(config['paths']['data_dir'])

def call_openai_api(messages):
    """Call OpenAI API using requests."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": "gpt-4o",  # Use GPT-4o for best answers
        "messages": messages,
        "temperature": 0.3,  # Lower temperature for more accurate answers
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API error: {response.status_code} - {response.text}")

def generate_answer(question: str) -> str:
    """Generate a comprehensive answer for an educational question."""
    try:
        response = call_openai_api([
            {"role": "system", "content": """You are an expert tutor providing accurate answers for spaced repetition flashcards. 
            Keep answers concise but complete. Include key facts and explanations.
            For science questions, be precise with terminology."""},
            {"role": "user", "content": f"Question: {question}\n\nProvide a clear, accurate answer suitable for a flashcard:"}
        ])
        
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        logging.error(f"Error generating answer for '{question[:50]}...': {e}")
        return "[Error generating answer]"

def main():
    """Generate fresh answers for all questions."""
    # Load questions
    input_file = DATA_DIR / "extracted_qa_complete.json"
    if not input_file.exists():
        logging.error(f"Input file not found: {input_file}")
        return 1
    
    with open(input_file) as f:
        qa_pairs = json.load(f)
    
    logging.info(f"Generating fresh answers for {len(qa_pairs)} questions...")
    
    # Generate new answers
    for i, qa in enumerate(qa_pairs):
        logging.info(f"  [{i+1}/{len(qa_pairs)}] {qa['question'][:60]}...")
        new_answer = generate_answer(qa['question'])
        qa['fresh_answer'] = new_answer
        
        # Keep original answer for comparison if desired
        qa['original_answer'] = qa.get('answer', '')
        qa['answer'] = new_answer  # Use fresh answer as main answer
    
    # Save with fresh answers
    output_file = DATA_DIR / "extracted_qa_fresh.json"
    with open(output_file, 'w') as f:
        json.dump(qa_pairs, f, indent=2)
    
    logging.info(f"\n✅ Generated fresh answers for all questions!")
    logging.info(f"   Saved to: {output_file}")
    
    # Show a few examples
    print("\nExample Q&A pairs:")
    for qa in qa_pairs[:3]:
        print(f"\nQ: {qa['question']}")
        print(f"A: {qa['answer'][:200]}...")

if __name__ == "__main__":
    exit(main())