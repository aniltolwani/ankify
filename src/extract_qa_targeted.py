#!/usr/bin/env python3
"""
Targeted extraction for specific Q: style questions in Socratic dialogues.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
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

# More specific extraction prompt for Q: style questions
EXTRACTION_PROMPT = """
You are extracting pedagogical questions from a Socratic dialogue where the ASSISTANT tests the USER's understanding.

Find ALL instances where the assistant asks questions in these formats:
- "Q: [question]"
- "Q1: [question]", "Q2: [question]", etc.
- "**Q: [question]**"
- Questions under headers like "Quick Check", "Test Question", "Check #"

For each question:
1. Extract the EXACT question text (everything after "Q:" or similar marker)
2. Look for the answer in:
   - The assistant's later explanation
   - A synthesis of the conversation context
   - Generate a correct answer based on the teaching material

IMPORTANT: Look through the ENTIRE conversation, including within long messages.

Return JSON with these exact questions:
[{"question": "exact question text", "answer": "comprehensive answer"}]

CONVERSATION:
"""

def extract_questions_regex(text: str) -> List[str]:
    """Extract questions using regex patterns."""
    questions = []
    
    # Patterns to match various question formats
    patterns = [
        r'\*\*Q\d*:\s*([^\*\n]+)\*\*',  # **Q: question** or **Q1: question**
        r'Q\d*:\s*([^\n]+)',              # Q: question or Q1: question
        r'(?:Test Question|Quick Check)[^\n]*:\s*([^\n]+)',  # Test Question: or Quick Check:
        r'###.*(?:Check|Question)[^\n]*\n[^\n]*Q\d*:\s*([^\n]+)',  # Headers followed by Q:
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        questions.extend([q.strip() for q in matches if q.strip()])
    
    return list(set(questions))  # Remove duplicates

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
    
    response = requests.post(url, headers=headers, json=data, timeout=60)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API error: {response.status_code} - {response.text}")

def extract_qa_from_conversation(conv_data: Any) -> List[Dict]:
    """Extract Q&A pairs from a single conversation with targeted approach."""
    # Handle empty or list conversations
    if isinstance(conv_data, list) or not conv_data:
        return []
        
    # Build conversation text from message tree
    messages = []
    all_text = []  # Collect all text for regex search
    
    def extract_messages(node):
        if node is None or isinstance(node, list):
            return
            
        message = node.get('message', {})
        if message and message.get('content', {}).get('content_type') == 'text':
            role = message.get('author', {}).get('role', '')
            parts = message.get('content', {}).get('parts', [])
            
            if isinstance(parts, list) and parts:
                content = parts[0] if isinstance(parts[0], str) else str(parts[0])
                if content and role in ['user', 'assistant']:
                    messages.append(f"{role.upper()}: {content}")
                    if role == 'assistant':
                        all_text.append(content)
        
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
    
    if not messages:
        return []
    
    # First try regex extraction on all assistant messages
    all_assistant_text = "\n\n".join(all_text)
    regex_questions = extract_questions_regex(all_assistant_text)
    
    logging.debug(f"Found {len(regex_questions)} questions via regex")
    
    # Join messages into conversation text
    conversation_text = "\n\n".join(messages)
    
    # Use GPT-4 to extract Q&A pairs with enhanced context
    try:
        # Include regex-found questions as hints
        enhanced_prompt = EXTRACTION_PROMPT
        if regex_questions:
            enhanced_prompt += f"\n\nHINT: Found these questions in the text:\n" + "\n".join(f"- {q}" for q in regex_questions)
        
        response = call_openai_api([
            {"role": "system", "content": "Extract Q: style pedagogical questions from conversations. Focus on exact question text after Q: markers."},
            {"role": "user", "content": enhanced_prompt + "\n\n" + conversation_text[:25000]}  # Increased limit
        ])
        
        result = json.loads(response['choices'][0]['message']['content'])
        
        # Handle various response formats
        if isinstance(result, dict):
            if 'questions' in result:
                return result['questions']
            elif 'qa_pairs' in result:
                return result['qa_pairs']
            elif isinstance(result.get('cards'), list):
                return result['cards']
            else:
                # Try to find any list in the result
                for key, value in result.items():
                    if isinstance(value, list):
                        return value
        elif isinstance(result, list):
            return result
            
        return []
            
    except Exception as e:
        logging.error(f"Error extracting Q&A: {e}")
        # Fallback: create cards from regex questions
        if regex_questions:
            return [{"question": q, "answer": "[To be extracted from context]"} for q in regex_questions]
        return []

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
            
            # Extract Q&A pairs
            qa_pairs = extract_qa_from_conversation(conv_data)
            
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
    output_file = DATA_DIR / "extracted_qa_targeted.json"
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