#!/usr/bin/env bash
# Build script for Render.com deployment
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Initialize database and seed default users on every deploy
python init_db.py
