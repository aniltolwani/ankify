#!/usr/bin/env python3
"""
Post-process extracted Q&A pairs using LLM to filter for true Socratic teaching questions.
"""

import json
import logging
from pathlib import Path
import os
import requests
import yaml
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

DATA_DIR = Path("./data")

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY environment variable not set")
    exit(1)

# Prompt for filtering Socratic questions
FILTER_PROMPT = """You are analyzing questions extracted from ChatGPT conversations where the assistant was teaching the user through the Socratic method.

A Socratic teaching question is one where:
- The assistant asks the user to test their understanding
- The user needs to think and apply what they learned
- It's checking if the user grasped a concept
- Examples: "What are the three components of a DNA nucleotide?", "Which bases pair together?", "If you have a DNA strand that is 10 base pairs long, how many nucleotides total does that mean?"

NOT Socratic teaching questions:
- Questions the user asked the assistant
- FAQ-style questions with immediate answers
- Meta questions about the process
- Rhetorical questions in explanations

Important: Many good teaching questions don't have explicit markers like "Q:". Focus on whether the question tests understanding.

For this question, respond with JSON:
{
  "is_socratic": true/false,
  "reasoning": "brief explanation",
  "category": "socratic_test" | "faq" | "rhetorical" | "meta" | "other"
}

Question to analyze:"""

def call_openai_api(messages):
    """Call OpenAI API using requests."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": config['models']['extractor'],
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API error: {response.status_code} - {response.text}")

def is_socratic_question(qa: dict) -> tuple[bool, str]:
    """Use LLM to determine if this is a true Socratic teaching question."""
    question = qa.get('question', '')
    
    # Quick pre-filter for obviously bad questions
    if len(question) < 15 or not question.endswith('?'):
        return False, "too_short"
    
    try:
        response = call_openai_api([
            {"role": "system", "content": "Analyze questions to identify true Socratic teaching questions."},
            {"role": "user", "content": FILTER_PROMPT + "\n\n" + question}
        ])
        
        result = json.loads(response['choices'][0]['message']['content'])
        return result.get('is_socratic', False), result.get('category', 'unknown')
        
    except Exception as e:
        logging.error(f"Error in Socratic check: {e}")
        # Conservative fallback - exclude on error
        return False, "error"

def process_qa_pairs():
    """Filter Q&A pairs using LLM."""
    # Load extracted Q&A pairs
    input_file = DATA_DIR / "extracted_qa.json"
    if not input_file.exists():
        logging.error(f"Input file not found: {input_file}")
        return 1
    
    with open(input_file) as f:
        all_qa = json.load(f)
    
    logging.info(f"Processing {len(all_qa)} Q&A pairs using LLM...")
    
    # Track statistics by category
    category_counts = {}
    socratic_qa = []
    
    for i, qa in enumerate(all_qa):
        if i % 5 == 0:
            logging.info(f"  Processing {i+1}/{len(all_qa)}...")
        
        # Check if it's a true Socratic question
        is_socratic, category = is_socratic_question(qa)
        category_counts[category] = category_counts.get(category, 0) + 1
        
        if not is_socratic:
            logging.debug(f"Excluded ({category}): {qa['question'][:60]}...")
            continue
        
        socratic_qa.append(qa)
    
    # Save processed Q&A pairs
    output_file = DATA_DIR / "extracted_qa_final.json"
    with open(output_file, 'w') as f:
        json.dump(socratic_qa, f, indent=2)
    
    # Save detailed statistics
    stats_file = DATA_DIR / "postprocess_stats.json"
    with open(stats_file, 'w') as f:
        json.dump({
            "total_processed": len(all_qa),
            "socratic_kept": len(socratic_qa),
            "category_breakdown": category_counts
        }, f, indent=2)
    
    logging.info(f"\n✅ Post-processing complete!")
    logging.info(f"   Total processed: {len(all_qa)}")
    logging.info(f"   Kept {len(socratic_qa)} Socratic questions")
    logging.info(f"\n   Category breakdown:")
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        logging.info(f"     {category}: {count}")
    logging.info(f"\n   Saved to: {output_file}")
    logging.info(f"   Stats saved to: {stats_file}")
    
    return socratic_qa

def main():
    """Main entry point."""
    try:
        process_qa_pairs()
        return 0
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())