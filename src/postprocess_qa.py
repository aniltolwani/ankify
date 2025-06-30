#!/usr/bin/env python3
"""
Post-process extracted Q&A pairs:
1. Filter out FAQ-style questions
2. Fix incomplete questions by adding context
3. Prepare final Q&A set
"""

import json
import logging
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

DATA_DIR = Path("./data")

# FAQ patterns to exclude
FAQ_PATTERNS = [
    'How to obtain',
    'Deck strategy',
    'Duplicate handling',
    'Edge cases',
    'MVP first',
    "Claude 'answer enhancer'",
    'What cellular fate',  # This seems like a normal question, not Socratic
    'Checking your understanding',  # Meta-questions about approach
    'Can you explain why',  # These are usually followed by immediate answers
    'idempotency'
]

# Known incomplete questions that need context
CONTEXT_FIXES = {
    "How many nucleotides total does that mean (considering both strands)?": 
        "If you have a DNA strand that is 10 base pairs long, how many nucleotides total does that mean (considering both strands)?",
    
    "How many sugar molecules would be in those nucleotides?":
        "If you have 20 nucleotides total (from a 10 base pair DNA strand), how many sugar molecules would be in those nucleotides?",
        
    "What would the complementary strand be?":
        "If the sequence on one strand is 5'- A C G -3', what would the complementary strand be?"
}

def is_socratic_question(qa: dict) -> bool:
    """Check if this is a true Socratic teaching question."""
    question = qa.get('question', '')
    
    # Exclude FAQ-style questions
    for pattern in FAQ_PATTERNS:
        if pattern.lower() in question.lower():
            return False
    
    # Exclude questions that are too short or look like headers
    if len(question) < 20 or question.endswith('?') is False:
        return False
    
    return True

def fix_incomplete_question(question: str) -> str:
    """Add necessary context to incomplete questions."""
    # Check if this question needs context
    for incomplete, complete in CONTEXT_FIXES.items():
        if question.strip() == incomplete:
            return complete
    
    # Return original if no fix needed
    return question

def process_qa_pairs():
    """Filter and fix Q&A pairs."""
    # Load extracted Q&A pairs
    input_file = DATA_DIR / "extracted_qa.json"
    if not input_file.exists():
        logging.error(f"Input file not found: {input_file}")
        return 1
    
    with open(input_file) as f:
        all_qa = json.load(f)
    
    logging.info(f"Processing {len(all_qa)} Q&A pairs...")
    
    # Filter and fix
    socratic_qa = []
    excluded_count = 0
    fixed_count = 0
    
    for qa in all_qa:
        # Check if it's a true Socratic question
        if not is_socratic_question(qa):
            excluded_count += 1
            continue
        
        # Fix incomplete questions
        original_q = qa['question']
        fixed_q = fix_incomplete_question(original_q)
        if fixed_q != original_q:
            qa['question'] = fixed_q
            fixed_count += 1
            logging.debug(f"Fixed: {original_q[:50]}...")
        
        socratic_qa.append(qa)
    
    # Save processed Q&A pairs
    output_file = DATA_DIR / "extracted_qa_final.json"
    with open(output_file, 'w') as f:
        json.dump(socratic_qa, f, indent=2)
    
    logging.info(f"\n✅ Post-processing complete!")
    logging.info(f"   Kept {len(socratic_qa)} Socratic questions")
    logging.info(f"   Excluded {excluded_count} FAQ-style questions")
    logging.info(f"   Fixed {fixed_count} incomplete questions")
    logging.info(f"   Saved to: {output_file}")
    
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