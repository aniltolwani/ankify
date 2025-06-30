#!/bin/bash
# Helper script to run Ankify with virtual environment

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
    python -m playwright install chromium
else
    source venv/bin/activate
fi

# Run the command
if [ "$1" == "setup" ]; then
    python scripts/setup_auth.py
else
    python main.py "$@"
fi