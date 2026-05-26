#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browser and its dependencies (required for the web scraper)
playwright install --with-deps chromium
