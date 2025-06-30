#!/usr/bin/env python3
"""
Extract only Socratic questions (no answers) with proper context.
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

# Simpler prompt - just extract questions with context
QUESTION_EXTRACTION_PROMPT = """
Extract pedagogical questions where the assistant tests the user's understanding.

For questions that need context (e.g., "How many nucleotides total does that mean?"), 
include the necessary context from earlier in the message.

Examples of good extraction:
- "What are the three components of a DNA nucleotide?"
- "If you have a DNA strand that is 10 base pairs long, how many nucleotides total does that mean (considering both strands)?"

Look for questions marked with:
- Q:, Q1:, Q2:, etc.
- Quick Check, Test Question, Check #
- Questions at the end of teaching segments

Return a JSON array of question strings only:
["question 1 with context", "question 2", ...]

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

def has_socratic_questions(content: str) -> bool:
    """Quick check if message likely contains Socratic questions."""
    if not content or len(content) < 50:
        return False
    
    patterns = [
        r'Q\d*:\s*[^\n]+\?',
        r'Quick Check',
        r'Test Question',
        r'Check #\d+',
        r'✅.*Check'
    ]
    
    return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)

def extract_questions_from_message(content: str) -> List[str]:
    """Extract just the questions from a single message."""
    if not has_socratic_questions(content):
        return []
    
    try:
        response = call_openai_api([
            {"role": "system", "content": "Extract pedagogical questions with necessary context. Return JSON array of strings."},
            {"role": "user", "content": QUESTION_EXTRACTION_PROMPT + "\n" + content[:10000]}
        ])
        
        result = json.loads(response['choices'][0]['message']['content'])
        
        # Handle various response formats
        if isinstance(result, list):
            return [q for q in result if isinstance(q, str) and q.strip()]
        elif isinstance(result, dict):
            if 'questions' in result and isinstance(result['questions'], list):
                return result['questions']
            # Try to find any list in the dict
            for value in result.values():
                if isinstance(value, list):
                    return [q for q in value if isinstance(q, str)]
        
        return []
            
    except Exception as e:
        logging.debug(f"Error extracting from message: {e}")
        return []

def generate_answer_for_question(question: str) -> str:
    """Generate a correct answer for a question using GPT-4."""
    try:
        response = call_openai_api([
            {"role": "system", "content": "You are an expert tutor. Provide accurate, comprehensive answers to educational questions."},
            {"role": "user", "content": f"Please provide a clear, accurate answer to this question:\n\n{question}"}
        ])
        
        return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Error generating answer: {e}")
        return "Error generating answer"

def process_conversation_messages(conv_data: Any) -> List[Dict]:
    """Process each message and extract questions."""
    if isinstance(conv_data, list) or not conv_data:
        return []
    
    all_questions = []
    
    def process_node(node):
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
                    # Extract questions from this message
                    questions = extract_questions_from_message(content)
                    all_questions.extend(questions)
        
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
    
    return all_questions

def process_all_conversations():
    """Process all conversations and generate Q&A pairs."""
    conv_files = list(DATA_DIR.glob("*.json"))
    conv_files = [f for f in conv_files if not f.name.startswith(('.', 'extracted_'))]
    
    logging.info(f"Processing {len(conv_files)} conversations...")
    
    all_qa_pairs = []
    
    for i, conv_file in enumerate(conv_files):
        logging.info(f"  [{i+1}/{len(conv_files)}] Processing {conv_file.name}")
        
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)
            
            # Extract questions
            questions = process_conversation_messages(conv_data)
            
            if questions:
                logging.info(f"    Found {len(questions)} questions, generating answers...")
                
                # Generate answers for each question
                for j, question in enumerate(questions):
                    # Filter out FAQ-style questions
                    if any(faq in question for faq in ['How to obtain', 'Deck strategy', 'MVP first']):
                        continue
                        
                    logging.debug(f"      Generating answer {j+1}/{len(questions)}")
                    answer = generate_answer_for_question(question)
                    
                    qa_pair = {
                        'question': question,
                        'answer': answer,
                        'source_conversation': conv_file.stem,
                        'title': conv_data.get('title', 'Untitled') if isinstance(conv_data, dict) else 'Untitled'
                    }
                    all_qa_pairs.append(qa_pair)
            
        except Exception as e:
            logging.error(f"    Error processing {conv_file.name}: {e}")
    
    # Save extracted Q&A pairs
    output_file = DATA_DIR / "extracted_qa_final.json"
    with open(output_file, 'w') as f:
        json.dump(all_qa_pairs, f, indent=2)
    
    logging.info(f"\n✅ Extraction complete! Generated {len(all_qa_pairs)} Q&A pairs")
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