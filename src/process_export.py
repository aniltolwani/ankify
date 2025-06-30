#!/usr/bin/env python3
"""
Process conversations.json from ChatGPT export.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

DATA_DIR = Path("./data")

def process_export_file(export_file: Path):
    """Process the conversations.json file from ChatGPT export."""
    
    if not export_file.exists():
        logging.error(f"Export file not found: {export_file}")
        logging.info("Please download and extract your ChatGPT export to ./data/conversations.json")
        return []
    
    logging.info(f"Processing {export_file}")
    
    with open(export_file) as f:
        data = json.load(f)
    
    conversations = []
    
    # The export format is an array of conversation objects
    for conv in data:
        conv_id = conv.get('id', '')
        title = conv.get('title', 'Untitled')
        
        # Skip if no ID
        if not conv_id:
            continue
        
        # Extract messages
        messages = []
        
        # The conversation structure varies, but usually has a 'mapping' field
        mapping = conv.get('mapping', {})
        
        # Build message list by traversing the tree
        for node_id, node in mapping.items():
            message = node.get('message', {})
            if message and message.get('content', {}).get('content_type') == 'text':
                role = message.get('author', {}).get('role', '')
                content_parts = message.get('content', {}).get('parts', [])
                
                if role in ['user', 'assistant'] and content_parts:
                    content = ' '.join(str(part) for part in content_parts)
                    messages.append({
                        'role': role,
                        'content': content
                    })
        
        # Save individual conversation
        conv_file = DATA_DIR / f"{conv_id}.json"
        conv_data = {
            'id': conv_id,
            'title': title,
            'messages': messages,
            'message_count': len(messages)
        }
        
        with open(conv_file, 'w') as f:
            json.dump(conv_data, f, indent=2)
        
        conversations.append(conv_data)
        logging.info(f"  Processed: {title} ({len(messages)} messages)")
    
    return conversations

def main():
    """Main entry point."""
    export_file = DATA_DIR / "conversations.json"
    
    try:
        conversations = process_export_file(export_file)
        
        if conversations:
            logging.info(f"\n✅ Processed {len(conversations)} conversations")
            
            # Save summary
            summary = {
                "processed_at": datetime.now().isoformat(),
                "conversation_count": len(conversations),
                "conversations": [
                    {"id": c['id'], "title": c['title'], "messages": c['message_count']} 
                    for c in conversations
                ]
            }
            
            with open(DATA_DIR / ".process_summary.json", 'w') as f:
                json.dump(summary, f, indent=2)
        else:
            logging.warning("No conversations found in export")
            
        return 0
        
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())