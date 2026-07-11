#!/bin/bash

# --- Configuration ---
# Update this path to where your project is located in the Proxmox container
PROJECT_DIR="/opt/macbook-scraper" 
BRANCH="master" # Change to 'main' if your default branch is main
# ---------------------

cd "$PROJECT_DIR" || { echo "Directory not found"; exit 1; }

# Fetch the latest changes from the remote
git fetch origin

# Get the commit hashes for local and remote
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$BRANCH)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): New update detected. Pulling changes..."
    
    # We pull the latest changes. 
    # Git pull only affects tracked files. Untracked folders like ./data will be completely safe and untouched.
    git pull origin "$BRANCH"

    echo "$(date): Rebuilding docker containers..."
    # Rebuild and restart the containers to apply the new code
    docker compose down
    docker compose up -d --build
    
    echo "$(date): Update applied successfully."
else
    echo "$(date): No new updates."
fi
