#!/usr/bin/env python3
"""Debug extraction to see what's happening"""

import json
import re
from pathlib import Path

# Load the DNA conversation
conv_file = Path("data/6860ad75-3480-8005-bb0f-5477aeb53260.json")
with open(conv_file) as f:
    conv_data = json.load(f)

print(f"Title: {conv_data.get('title', 'Unknown')}")
print(f"Mapping keys: {len(conv_data.get('mapping', {}))}")

# Extract all assistant messages
assistant_messages = []

def extract_messages(node):
    if node is None or isinstance(node, list):
        return
        
    message = node.get('message', {})
    if message and message.get('content', {}).get('content_type') == 'text':
        role = message.get('author', {}).get('role', '')
        parts = message.get('content', {}).get('parts', [])
        
        if isinstance(parts, list) and parts:
            content = parts[0] if isinstance(parts[0], str) else str(parts[0])
            if content and role == 'assistant':
                assistant_messages.append(content)
    
    # Traverse children
    children = node.get('children', [])
    if isinstance(children, list):
        for child_id in children:
            if child_id in conv_data.get('mapping', {}):
                extract_messages(conv_data['mapping'][child_id])

# Start from root
root_id = conv_data.get('current_node')
if root_id and 'mapping' in conv_data:
    # Find actual root by going up the tree
    mapping = conv_data['mapping']
    while root_id in mapping and mapping[root_id].get('parent'):
        parent_id = mapping[root_id]['parent']
        if parent_id in mapping:
            root_id = parent_id
        else:
            break
    
    extract_messages(mapping.get(root_id))

print(f"\nFound {len(assistant_messages)} assistant messages")

# Search for Q: patterns
all_text = "\n\n".join(assistant_messages)
print(f"\nTotal text length: {len(all_text)} characters")

# Search for specific patterns
patterns = [
    r'Q:\s*([^\n]+)',
    r'\*\*Q:\s*([^\*\n]+)\*\*',
    r'Q\d+:\s*([^\n]+)',
    r'Quick Check.*?Q:\s*([^\n]+)'
]

found_questions = []
for pattern in patterns:
    matches = re.findall(pattern, all_text, re.MULTILINE | re.DOTALL)
    if matches:
        print(f"\nPattern '{pattern}' found {len(matches)} matches:")
        for i, match in enumerate(matches[:5]):  # Show first 5
            print(f"  {i+1}. {match[:100]}...")
            found_questions.append(match)

# Also search for the specific text mentioned
if "What are the three components" in all_text:
    print("\n✓ Found 'What are the three components' in text")
    # Find the context
    idx = all_text.find("What are the three components")
    print(f"Context: ...{all_text[max(0, idx-50):idx+150]}...")
else:
    print("\n✗ Did NOT find 'What are the three components' in text")

# Check if the project.md content is there
if "# Ankify: Automated Socratic" in all_text:
    print("\n✓ Found project.md content in conversation")
    
print(f"\nTotal unique questions found: {len(set(found_questions))}")