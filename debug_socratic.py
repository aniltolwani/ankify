#!/usr/bin/env python3
"""Debug Socratic extraction"""

import json
import re
from pathlib import Path

# Load the DNA conversation
conv_file = Path("data/6860ad75-3480-8005-bb0f-5477aeb53260.json")
with open(conv_file) as f:
    conv_data = json.load(f)

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
    mapping = conv_data['mapping']
    while root_id in mapping and mapping[root_id].get('parent'):
        parent_id = mapping[root_id]['parent']
        if parent_id in mapping:
            root_id = parent_id
        else:
            break
    
    extract_messages(mapping.get(root_id))

print(f"Found {len(assistant_messages)} assistant messages")

# Look for messages with questions at the end
for i, msg in enumerate(assistant_messages):
    # Check for question patterns
    patterns = [
        r'Q\d*:\s*[^\n]+\?',
        r'Quick Check[^\n]*:\s*[^\n]+\?',
        r'Test Question[^\n]*:\s*[^\n]+\?',
        r'Check #\d+[^\n]*:\s*[^\n]+\?',
        r'✅[^\n]*:\s*[^\n]+\?'
    ]
    
    has_pattern = False
    for pattern in patterns:
        if re.search(pattern, msg, re.IGNORECASE):
            has_pattern = True
            break
    
    if has_pattern:
        # Check if question appears near end
        lines = msg.strip().split('\n')
        last_quarter_lines = max(1, len(lines) // 4)
        last_quarter = '\n'.join(lines[-last_quarter_lines:])
        
        print(f"\n=== Message {i+1} ===")
        print(f"Total lines: {len(lines)}")
        print(f"Last quarter ({last_quarter_lines} lines):")
        print("---")
        print(last_quarter[:500] + "..." if len(last_quarter) > 500 else last_quarter)
        print("---")
        
        # Check if pattern is in last quarter
        for pattern in patterns:
            if re.search(pattern, last_quarter, re.IGNORECASE):
                print(f"✓ Pattern '{pattern}' found in last quarter")
                break