# Google Colab Auto-Updater Script
# ==============================================================================
# Instructions:
# 1. Go to https://colab.research.google.com/
# 2. Click "New Notebook"
# 3. Create a GitHub Personal Access Token (PAT) if you haven't:
#    - Go to https://github.com/settings/tokens
#    - Generate new token (Classic) -> Select 'repo' scope -> Generate
# 4. Copy the code below into the first cell of the notebook.
# 5. Fill in your REPO_URL and GITHUB_TOKEN in the configuration section.
# 6. Click the "Play" button (Run) whenever you want to update (e.g. daily at 3:30 PM).

# ================= Copy from here down =================

import os
import sys

# --- CONFIGURATION (FILL THIS CAREFULLY) ---
# Your GitHub Repository URL (must be HTTPS)
# Example: "https://github.com/santosh/kerala-lottery.git"
REPO_URL = "https://github.com/santhkhd/lotteryresults.git"

# Your Secret GitHub Token
# Fetched from Colab Secrets (Key: GITHUB_TOKEN)
try:
    from google.colab import userdata
    GITHUB_TOKEN = userdata.get('GITHUB_TOKEN')
except ImportError:
    GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Fallback for local testing

if not GITHUB_TOKEN:
    print("WARNING: GITHUB_TOKEN not found in Secrets!")

# -------------------------------------------

def run_command(cmd):
    print(f"Running: {cmd}")
    ret = os.system(cmd)
    if ret != 0:
        print(f"Error executing command: {cmd}")
        # Don't exit, try to continue cleaning up or reporting
    return ret

def main():
    print("Starting Lottery Auto-Update on Colab...")

    # 1. Formatting URL with Token for Authentication
    # Converts https://github.com/user/repo.git -> https://TOKEN@github.com/user/repo.git
    if "github.com" in REPO_URL and GITHUB_TOKEN not in REPO_URL:
        authed_url = REPO_URL.replace("https://", f"https://{GITHUB_TOKEN}@", 1)
    else:
        authed_url = REPO_URL

    repo_name = REPO_URL.split("/")[-1].replace(".git", "")

    # 2. Remove previous runs to start fresh
    if os.path.exists(repo_name):
        print("Cleaning up previous run...")
        run_command(f"rm -rf {repo_name}")

    # 3. Clone the Repository
    print("Cloning repository...")
    if run_command(f"git clone {authed_url}") != 0:
        print("Failed to clone. Check your Token and URL.")
        return

    # 4. Enter Directory
    os.chdir(repo_name)

    # 5. Install Python Dependencies
    print("Installing dependencies...")
    run_command("pip install requests beautifulsoup4 pytz schedule")

    # 6. Run the scraping script
    print("Fetching lottery results...")
    # Using 'updateloto.py' as improved in the previous steps
    run_command("python updateloto.py")

    # 7. Run Node.js generators (Colab usually has Node installed by default)
    print("Generating manifests...")
    run_command("node generate-manifest.js")
    run_command("node generate-history.js")

    # 8. Configure Git Identity (Virtual Bot)
    run_command('git config user.email "colab-bot@example.com"')
    run_command('git config user.name "Colab Updater"')

    # 9. Commit and Push
    print("Pushing changes to GitHub...")
    run_command("git add .")
    
    # Check if there are changes
    status = os.popen("git status --porcelain").read()
    if not status:
        print("No new results found. Nothing to push.")
    else:
        run_command('git commit -m "chore: daily result update from Colab"')
        if run_command("git push") == 0:
            print("✅ SUCCESS: Results updated and pushed to GitHub!")
        else:
            print("❌ FAILED: Could not push to GitHub.")

if __name__ == "__main__":
    main()
