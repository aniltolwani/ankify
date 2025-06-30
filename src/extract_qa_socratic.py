#!/usr/bin/env python3
"""
Extract true Socratic dialogue questions - where the assistant tests the user's understanding.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import requests
import yaml

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s: %(message)s")

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY environment variable not set")
    exit(1)

DATA_DIR = Path(config['paths']['data_dir'])

# Refined prompt for true Socratic questions
SOCRATIC_EXTRACTION_PROMPT = """
Extract ONLY true Socratic teaching questions where the assistant is testing the user's understanding.

Characteristics of Socratic questions to INCLUDE:
1. Questions that appear at or near the END of the assistant's message
2. Questions that expect the USER to provide an answer (not rhetorical)
3. Often numbered (Q1:, Q2:) or marked (Test Question, Quick Check)
4. The answer is NOT provided in the same message
5. Examples:
   - "Q: What are the three components of a DNA nucleotide?"
   - "Quick Check: Which bases pair together?"
   - "Test Question 4: How might you modify the threads' behavior...?"

Questions to EXCLUDE:
1. FAQ-style headers where the answer immediately follows
2. Questions in the middle of explanatory text
3. Rhetorical questions
4. Questions like "How to obtain thread IDs?" followed by an answer
5. Section headers posed as questions

For each Socratic question found:
1. Extract the exact question text
2. Generate a comprehensive answer based on the context

Return JSON array. Empty array if no true Socratic questions found:
[{"question": "exact text", "answer": "comprehensive answer"}]

MESSAGE TEXT:
"""

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

def is_likely_socratic(content: str) -> bool:
    """Quick heuristic to check if message likely contains Socratic questions."""
    if not content or len(content) < 50:
        return False
    
    # Check for question indicators
    question_patterns = [
        r'Q\d*:\s*[^\n]+\?',  # Q: or Q1: followed by question
        r'Quick Check[^\n]*:\s*[^\n]+\?',
        r'Test Question[^\n]*:\s*[^\n]+\?',
        r'Check #\d+[^\n]*:\s*[^\n]+\?',
        r'✅[^\n]*Check[^\n]*:\s*[^\n]+\?',
        r'\*\*Q\d*:\*\*\s*[^\n]+\?'  # **Q:** format
    ]
    
    for pattern in question_patterns:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            # Check if question appears near end of message
            lines = content.strip().split('\n')
            # Use at least last 10 lines or quarter of message
            last_section_size = max(10, len(lines) // 4)
            last_section = '\n'.join(lines[-last_section_size:])
            if re.search(pattern, last_section, re.IGNORECASE | re.MULTILINE):
                return True
    
    return False

def extract_questions_from_message(content: str) -> List[Dict]:
    """Extract Socratic questions from a single message."""
    if not is_likely_socratic(content):
        return []
    
    try:
        response = call_openai_api([
            {"role": "system", "content": "Extract only true Socratic teaching questions where the assistant tests the user. Exclude FAQ-style questions with immediate answers."},
            {"role": "user", "content": SOCRATIC_EXTRACTION_PROMPT + "\n" + content[:10000]}
        ])
        
        result = json.loads(response['choices'][0]['message']['content'])
        
        if isinstance(result, list):
            # Additional filtering to remove FAQ-style questions
            filtered = []
            for qa in result:
                question = qa.get('question', '')
                # Skip if question looks like a header
                if not any(header in question for header in ['How to', 'What is the', 'Why use']):
                    filtered.append(qa)
            return filtered
        elif isinstance(result, dict) and 'questions' in result:
            return result['questions']
        else:
            return []
            
    except Exception as e:
        logging.debug(f"Error extracting from message: {e}")
        return []

def process_conversation_messages(conv_data: Any) -> List[Dict]:
    """Process each message in conversation individually."""
    if isinstance(conv_data, list) or not conv_data:
        return []
    
    all_qa_pairs = []
    processed_messages = 0
    
    def process_node(node):
        nonlocal processed_messages
        
        if node is None or isinstance(node, list):
            return
            
        message = node.get('message', {})
        if message and message.get('content', {}).get('content_type') == 'text':
            role = message.get('author', {}).get('role', '')
            parts = message.get('content', {}).get('parts', [])
            
            # Only process assistant messages
            if role == 'assistant' and isinstance(parts, list) and parts:
                content = parts[0] if isinstance(parts[0], str) else str(parts[0])
                
                if content:
                    processed_messages += 1
                    # Extract questions from this specific message
                    qa_pairs = extract_questions_from_message(content)
                    if qa_pairs:
                        logging.debug(f"Found {len(qa_pairs)} Socratic Q&A pairs in message")
                        all_qa_pairs.extend(qa_pairs)
        
        # Traverse children
        children = node.get('children', [])
        if isinstance(children, list):
            for child_id in children:
                if child_id in conv_data.get('mapping', {}):
                    process_node(conv_data['mapping'][child_id])
    
    # Start from root
    root_id = conv_data.get('current_node')
    if root_id and 'mapping' in conv_data:
        # Find actual root
        mapping = conv_data['mapping']
        while root_id in mapping and mapping[root_id].get('parent'):
            parent_id = mapping[root_id]['parent']
            if parent_id in mapping:
                root_id = parent_id
            else:
                break
        
        process_node(mapping.get(root_id))
    
    logging.debug(f"Processed {processed_messages} assistant messages")
    return all_qa_pairs

def process_all_conversations():
    """Process all downloaded conversations."""
    conv_files = list(DATA_DIR.glob("*.json"))
    conv_files = [f for f in conv_files if f.name not in [".state.json", "conversations_list.json", "extracted_qa.json", "extracted_qa_per_message.json", "extracted_qa_targeted.json"]]
    
    logging.info(f"Processing {len(conv_files)} conversations...")
    
    all_qa_pairs = []
    
    for i, conv_file in enumerate(conv_files):
        logging.info(f"  [{i+1}/{len(conv_files)}] Processing {conv_file.name}")
        
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)
            
            # Process messages individually
            qa_pairs = process_conversation_messages(conv_data)
            
            if qa_pairs:
                # Add metadata
                for qa in qa_pairs:
                    qa['source_conversation'] = conv_file.stem
                    qa['title'] = conv_data.get('title', 'Untitled') if isinstance(conv_data, dict) else 'Untitled'
                
                all_qa_pairs.extend(qa_pairs)
                logging.info(f"    Found {len(qa_pairs)} Socratic Q&A pairs")
            
        except Exception as e:
            logging.error(f"    Error processing {conv_file.name}: {e}")
    
    # Save extracted Q&A pairs
    output_file = DATA_DIR / "extracted_qa_socratic.json"
    with open(output_file, 'w') as f:
        json.dump(all_qa_pairs, f, indent=2)
    
    logging.info(f"\n✅ Extraction complete! Found {len(all_qa_pairs)} Socratic Q&A pairs")
    logging.info(f"   Saved to: {output_file}")
    
    return all_qa_pairs

def main():
    """Main entry point."""
    try:
        qa_pairs = process_all_conversations()
        return 0
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())