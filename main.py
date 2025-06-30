#!/usr/bin/env python3
"""
Ankify - Convert ChatGPT Socratic dialogues to spaced repetition flashcards
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

def run_command(cmd: str, description: str) -> int:
    """Run a command and return exit code."""
    logging.info(f"\n{'='*60}")
    logging.info(f"🔄 {description}")
    logging.info(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(
        description="Ankify - Convert ChatGPT Socratic dialogues to flashcards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  python main.py --all
  
  # Run individual steps
  python main.py --fetch              # Fetch conversations from ChatGPT
  python main.py --extract            # Extract Q&A pairs
  python main.py --postprocess        # Filter and fix questions
  python main.py --generate           # Generate flashcard files
  
  # Run specific combinations
  python main.py --extract --postprocess --generate
"""
    )
    
    parser.add_argument("--fetch", action="store_true", 
                       help="Fetch conversations from ChatGPT")
    parser.add_argument("--extract", action="store_true",
                       help="Extract Q&A pairs from conversations")
    parser.add_argument("--postprocess", action="store_true",
                       help="Filter and fix extracted questions")
    parser.add_argument("--generate", action="store_true",
                       help="Generate flashcard files (Anki, CSV, etc.)")
    parser.add_argument("--all", action="store_true",
                       help="Run full pipeline")
    
    args = parser.parse_args()
    
    # Show help if no args
    if not any(vars(args).values()):
        parser.print_help()
        return 1
    
    # Check prerequisites
    if (args.fetch or args.all) and not Path("./chatgpt_profile").exists():
        logging.error("❌ Browser profile not found!")
        logging.error("   Run: python scripts/setup_auth.py")
        return 1
    
    exit_code = 0
    
    # Step 1: Fetch conversations
    if args.fetch or args.all:
        exit_code = run_command(
            "python src/fetch_conversations.py",
            "Step 1/4: Fetching conversations from ChatGPT"
        )
        if exit_code != 0:
            logging.error("❌ Fetch failed!")
            return exit_code
    
    # Step 2: Extract Q&A pairs
    if args.extract or args.all:
        exit_code = run_command(
            "python src/extract_qa.py",
            "Step 2/4: Extracting Q&A pairs"
        )
        if exit_code != 0:
            logging.error("❌ Extraction failed!")
            return exit_code
    
    # Step 3: Post-process Q&A pairs
    if args.postprocess or args.all:
        exit_code = run_command(
            "python src/postprocess_qa.py",
            "Step 3/4: Post-processing (filter & fix)"
        )
        if exit_code != 0:
            logging.error("❌ Post-processing failed!")
            return exit_code
    
    # Step 4: Generate flashcards
    if args.generate or args.all:
        exit_code = run_command(
            "python src/generate_flashcards.py",
            "Step 4/4: Generating flashcard files"
        )
        if exit_code != 0:
            logging.error("❌ Flashcard generation failed!")
            return exit_code
    
    logging.info("\n✅ All requested steps completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())