#!/usr/bin/env python3
"""Filter extracted Q&A to only true Socratic questions"""

import json
from pathlib import Path

# Load the per-message extraction
input_file = Path("data/extracted_qa_per_message.json")
with open(input_file) as f:
    all_qa = json.load(f)

print(f"Total Q&A pairs: {len(all_qa)}")

# Filter out FAQ-style questions
socratic_qa = []
excluded_qa = []

for qa in all_qa:
    question = qa['question']
    
    # Exclude FAQ-style headers
    faq_patterns = [
        'How to obtain',
        'Deck strategy',
        'Duplicate handling',
        'Edge cases',
        'MVP first',
        "Claude 'answer enhancer'",
        'What cellular fate',  # This seems like a normal question, not Socratic
        'Checking your understanding',  # Meta-questions about approach
        'Can you explain'  # These are usually followed by immediate answers
    ]
    
    is_faq = any(pattern in question for pattern in faq_patterns)
    
    if is_faq:
        excluded_qa.append(qa)
    else:
        socratic_qa.append(qa)

print(f"\nFiltered to {len(socratic_qa)} true Socratic questions")
print(f"Excluded {len(excluded_qa)} FAQ-style questions")

# Show examples of excluded questions
print("\nExcluded questions:")
for qa in excluded_qa[:10]:
    print(f"- {qa['question'][:80]}...")

# Save filtered results
output_file = Path("data/extracted_qa_socratic_filtered.json")
with open(output_file, 'w') as f:
    json.dump(socratic_qa, f, indent=2)

print(f"\nSaved filtered questions to: {output_file}")

# Show a few examples of kept questions
print("\nKept Socratic questions:")
for qa in socratic_qa[:5]:
    print(f"- {qa['question']}")