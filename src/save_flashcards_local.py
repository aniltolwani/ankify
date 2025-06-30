#!/usr/bin/env python3
"""
Save flashcards to local directory in multiple formats.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

DATA_DIR = Path("./data")
FLASHCARDS_DIR = Path("./flashcards")

def create_anki_format(qa_pairs):
    """Create Anki-compatible TSV format."""
    anki_file = FLASHCARDS_DIR / f"anki_flashcards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(anki_file, 'w', encoding='utf-8') as f:
        for qa in qa_pairs:
            # Anki format: question[tab]answer
            question = qa['question'].replace('\n', '<br>').replace('\t', '    ')
            answer = qa['answer'].replace('\n', '<br>').replace('\t', '    ')
            f.write(f"{question}\t{answer}\n")
    
    return anki_file

def create_csv_format(qa_pairs):
    """Create CSV format for easy import."""
    csv_file = FLASHCARDS_DIR / f"flashcards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['question', 'answer', 'source', 'title'])
        writer.writeheader()
        
        for qa in qa_pairs:
            writer.writerow({
                'question': qa['question'],
                'answer': qa['answer'],
                'source': qa.get('source_conversation', ''),
                'title': qa.get('title', '')
            })
    
    return csv_file

def create_markdown_format(qa_pairs):
    """Create Markdown format for easy reading."""
    md_file = FLASHCARDS_DIR / f"flashcards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Extracted Flashcards\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total cards: {len(qa_pairs)}\n\n")
        
        # Group by conversation
        by_conversation = {}
        for qa in qa_pairs:
            title = qa.get('title', 'Unknown')
            if title not in by_conversation:
                by_conversation[title] = []
            by_conversation[title].append(qa)
        
        for title, cards in by_conversation.items():
            f.write(f"## {title}\n\n")
            for i, qa in enumerate(cards, 1):
                f.write(f"### Card {i}\n\n")
                f.write(f"**Question:** {qa['question']}\n\n")
                f.write(f"**Answer:** {qa['answer']}\n\n")
                f.write("---\n\n")
    
    return md_file

def create_json_format(qa_pairs):
    """Create JSON format for programmatic access."""
    json_file = FLASHCARDS_DIR / f"flashcards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'total_cards': len(qa_pairs),
                'source': 'ChatGPT Socratic Dialogues'
            },
            'flashcards': qa_pairs
        }, f, indent=2)
    
    return json_file

def main():
    """Main entry point."""
    # Load extracted Q&A pairs - try complete questions first
    qa_file = DATA_DIR / "extracted_qa_complete.json"
    if not qa_file.exists():
        qa_file = DATA_DIR / "extracted_qa_socratic_filtered.json"
        if not qa_file.exists():
            qa_file = DATA_DIR / "extracted_qa_per_message.json"
            if not qa_file.exists():
                qa_file = DATA_DIR / "extracted_qa.json"
                if not qa_file.exists():
                    logging.error("No extracted Q&A pairs found. Run extraction first.")
                    return 1
    
    with open(qa_file) as f:
        qa_pairs = json.load(f)
    
    if not qa_pairs:
        logging.warning("No Q&A pairs to process.")
        return 0
    
    logging.info(f"Saving {len(qa_pairs)} flashcards to multiple formats...")
    
    # Create flashcards directory
    FLASHCARDS_DIR.mkdir(exist_ok=True)
    
    # Save in different formats
    files_created = []
    
    try:
        # Anki format
        anki_file = create_anki_format(qa_pairs)
        files_created.append(('Anki TSV', anki_file))
        logging.info(f"✅ Created Anki format: {anki_file}")
        
        # CSV format
        csv_file = create_csv_format(qa_pairs)
        files_created.append(('CSV', csv_file))
        logging.info(f"✅ Created CSV format: {csv_file}")
        
        # Markdown format
        md_file = create_markdown_format(qa_pairs)
        files_created.append(('Markdown', md_file))
        logging.info(f"✅ Created Markdown format: {md_file}")
        
        # JSON format
        json_file = create_json_format(qa_pairs)
        files_created.append(('JSON', json_file))
        logging.info(f"✅ Created JSON format: {json_file}")
        
    except Exception as e:
        logging.error(f"Error creating flashcards: {e}")
        return 1
    
    # Summary
    logging.info("\n" + "="*60)
    logging.info("FLASHCARD GENERATION COMPLETE!")
    logging.info("="*60)
    logging.info(f"Total flashcards created: {len(qa_pairs)}")
    logging.info("\nFiles created:")
    for format_name, filepath in files_created:
        logging.info(f"  - {format_name}: {filepath}")
    logging.info("\nYou can now import these flashcards into:")
    logging.info("  - Anki: Use the TSV file")
    logging.info("  - Mochi: Use the CSV or manually add cards")
    logging.info("  - Any other app: Use CSV or JSON format")
    
    return 0

if __name__ == "__main__":
    exit(main())