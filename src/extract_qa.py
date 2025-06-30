#!/usr/bin/env python3
"""
Extract Q&A pairs by processing each message individually.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
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

# Prompt for extracting teaching questions with full context
MESSAGE_EXTRACTION_PROMPT = """
Extract any pedagogical questions where the assistant is testing the user's understanding.

Look for questions in formats like:
- Q: [question]
- Q1: [question], Q2: [question]
- **Q: [question]**
- Test Question: [question]
- Quick Check: [question]
- Or any question at the end of an explanation that tests understanding

IMPORTANT: Include any necessary context that makes the question complete and self-contained.
For example, if the message says "If you have a DNA strand that is 10 base pairs long... Q: How many nucleotides total does that mean?"
Extract as: "If you have a DNA strand that is 10 base pairs long, how many nucleotides total does that mean?"

For each question found:
1. Extract the COMPLETE question including any setup/context needed to understand it
2. Generate a comprehensive answer based on the message content

Return JSON array:
[{"question": "complete self-contained question", "answer": "comprehensive answer"}]

If no pedagogical questions found, return empty array [].

MESSAGE:
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

def extract_questions_from_message(content: str) -> List[Dict]:
    """Extract questions from a single message using GPT-4."""
    if not content or len(content) < 50:  # Skip very short messages
        return []
    
    try:
        # For efficiency, first check if message likely contains questions
        question_indicators = ['Q:', 'Q1:', 'Q2:', 'Test Question', 'Quick Check', '?**']
        if not any(indicator in content for indicator in question_indicators):
            return []
        
        response = call_openai_api([
            {"role": "system", "content": "Extract pedagogical questions from individual messages. Return JSON array."},
            {"role": "user", "content": MESSAGE_EXTRACTION_PROMPT + "\n" + content[:8000]}  # Limit per message
        ])
        
        result = json.loads(response['choices'][0]['message']['content'])
        
        if isinstance(result, list):
            return result
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
                        logging.debug(f"Found {len(qa_pairs)} Q&A pairs in message")
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
    conv_files = [f for f in conv_files if f.name not in [".state.json", "conversations_list.json", "extracted_qa.json"]]
    
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
                logging.info(f"    Found {len(qa_pairs)} Q&A pairs")
            
        except Exception as e:
            logging.error(f"    Error processing {conv_file.name}: {e}")
    
    # Save extracted Q&A pairs
    output_file = DATA_DIR / "extracted_qa.json"
    with open(output_file, 'w') as f:
        json.dump(all_qa_pairs, f, indent=2)
    
    logging.info(f"\n✅ Extraction complete! Found {len(all_qa_pairs)} total Q&A pairs")
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