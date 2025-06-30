#!/usr/bin/env python3
"""
Extract Q&A pairs from ChatGPT conversations using GPT-4.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
import os
from openai import OpenAI
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY environment variable not set")
    exit(1)

# Initialize OpenAI client with minimal configuration
client = OpenAI(
    api_key=api_key,
)
DATA_DIR = Path(config['paths']['data_dir'])

EXTRACTION_PROMPT = """
You are an expert at identifying pedagogical questions in Socratic dialogues.

Extract ALL questions that serve a teaching purpose from this conversation, including:
1. Explicit test questions (marked with "Test Question", "Q:", "Quick Check", etc.)
2. Comprehension checks ("What would happen if...?")
3. Conceptual probes ("How do you think about...?")

For each question found, return:
- The complete question text
- The best available answer (user's if correct, assistant's if user was wrong/incomplete)
- Empty answer if no answer was provided

Return as JSON array:
[{"question": "...", "answer": "..."}]

CONVERSATION:
"""

def extract_qa_from_conversation(conv_data: Dict) -> List[Dict]:
    """Extract Q&A pairs from a single conversation."""
    # Build conversation text from message tree
    messages = []
    
    # ChatGPT conversations have a complex tree structure
    # We'll flatten it for simplicity
    def extract_messages(node):
        if node is None:
            return
        
        message = node.get('message', {})
        if message and message.get('content', {}).get('content_type') == 'text':
            role = message.get('author', {}).get('role', '')
            content = message.get('content', {}).get('parts', [''])[0]
            
            if content and role in ['user', 'assistant']:
                messages.append(f"{role.upper()}: {content}")
        
        # Traverse children
        for child_id in node.get('children', []):
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
    
    if not messages:
        return []
    
    # Join messages into conversation text
    conversation_text = "\n\n".join(messages)
    
    # Use GPT-4 to extract Q&A pairs
    try:
        response = client.chat.completions.create(
            model=config['models']['extractor'],
            messages=[
                {"role": "system", "content": "You extract Q&A pairs from conversations. Return only valid JSON."},
                {"role": "user", "content": EXTRACTION_PROMPT + conversation_text[:15000]}  # Limit context
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        # Handle both {"questions": [...]} and direct array formats
        if isinstance(result, dict) and 'questions' in result:
            return result['questions']
        elif isinstance(result, list):
            return result
        else:
            # Try to extract array from various formats
            for key in ['qa_pairs', 'cards', 'items', 'data']:
                if key in result and isinstance(result[key], list):
                    return result[key]
            return []
            
    except Exception as e:
        logging.error(f"Error extracting Q&A: {e}")
        return []

def process_all_conversations():
    """Process all downloaded conversations."""
    conv_files = list(DATA_DIR.glob("*.json"))
    conv_files = [f for f in conv_files if f.name != ".state.json"]
    
    logging.info(f"Processing {len(conv_files)} conversations...")
    
    all_qa_pairs = []
    
    for i, conv_file in enumerate(conv_files):
        logging.info(f"  [{i+1}/{len(conv_files)}] Processing {conv_file.name}")
        
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)
            
            # Extract Q&A pairs
            qa_pairs = extract_qa_from_conversation(conv_data)
            
            if qa_pairs:
                # Add metadata
                for qa in qa_pairs:
                    qa['source_conversation'] = conv_file.stem
                    qa['title'] = conv_data.get('title', 'Untitled')
                
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