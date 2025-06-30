#!/usr/bin/env python3
"""
Main entry point for Ankify - automated ChatGPT to flashcard pipeline.
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
    parser = argparse.ArgumentParser(description="Ankify - ChatGPT to Flashcards")
    parser.add_argument("--fetch", action="store_true", help="Fetch conversations from ChatGPT")
    parser.add_argument("--export", action="store_true", help="Request ChatGPT data export via browser")
    parser.add_argument("--process", action="store_true", help="Process downloaded conversations.json")
    parser.add_argument("--extract", action="store_true", help="Extract Q&A pairs from conversations")
    parser.add_argument("--generate", action="store_true", help="Generate flashcards from Q&A pairs")
    parser.add_argument("--all", action="store_true", help="Run full pipeline (fetch, extract, generate)")
    
    args = parser.parse_args()
    
    # Default to --all if no options specified
    if not any([args.fetch, args.export, args.process, args.extract, args.generate, args.all]):
        args.all = True
    
    # Check if profile exists
    if (args.fetch or args.all) and not Path("./chatgpt_profile").exists():
        logging.error("❌ Browser profile not found!")
        logging.error("   Run: python scripts/setup_auth.py")
        return 1
    
    exit_code = 0
    
    # Fetch conversations
    if args.fetch or args.all:
        exit_code = run_command(
            "python src/fetch_conversations.py",
            "Fetching conversations from ChatGPT"
        )
        if exit_code != 0:
            logging.error("❌ Fetch failed!")
            return exit_code
    
    # Extract Q&A pairs
    if args.extract or args.all:
        exit_code = run_command(
            "python src/extract_qa.py",
            "Extracting Q&A pairs with GPT-4"
        )
        if exit_code != 0:
            logging.error("❌ Extraction failed!")
            return exit_code
    
    # Generate flashcards
    if args.generate or args.all:
        exit_code = run_command(
            "python src/generate_cards.py",
            "Generating flashcards in Mochi"
        )
        if exit_code != 0:
            logging.error("❌ Card generation failed!")
            return exit_code
    
    if args.all or (args.fetch and args.extract and args.generate):
        logging.info("\n✅ Full pipeline complete!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())