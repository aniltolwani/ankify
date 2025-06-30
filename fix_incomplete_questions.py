#!/usr/bin/env python3
"""Fix incomplete questions by adding necessary context"""

import json
from pathlib import Path
import re

# Load the filtered questions
input_file = Path("data/extracted_qa_socratic_filtered.json")
with open(input_file) as f:
    qa_pairs = json.load(f)

print(f"Checking {len(qa_pairs)} questions for completeness...\n")

# Questions that need context fixes
questions_needing_context = [
    "How many nucleotides total does that mean (considering both strands)?",
    "How many sugar molecules would be in those nucleotides?"
]

# Manual fixes for known incomplete questions
context_fixes = {
    "How many nucleotides total does that mean (considering both strands)?": 
        "If you have a DNA strand that is 10 base pairs long, how many nucleotides total does that mean (considering both strands)?",
    
    "How many sugar molecules would be in those nucleotides?":
        "If you have 20 nucleotides total (from a 10 base pair DNA strand), how many sugar molecules would be in those nucleotides?"
}

# Apply fixes
fixed_count = 0
for qa in qa_pairs:
    original_q = qa['question']
    if original_q in context_fixes:
        qa['question'] = context_fixes[original_q]
        print(f"Fixed: {original_q[:50]}...")
        print(f"   To: {qa['question'][:80]}...\n")
        fixed_count += 1

print(f"Fixed {fixed_count} incomplete questions")

# Save fixed version
output_file = Path("data/extracted_qa_complete.json")
with open(output_file, 'w') as f:
    json.dump(qa_pairs, f, indent=2)

print(f"\nSaved complete questions to: {output_file}")

# Show a few examples
print("\nExample complete questions:")
for qa in qa_pairs[:5]:
    print(f"- {qa['question']}")