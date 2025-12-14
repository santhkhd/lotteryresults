import schedule
import time
import subprocess
import pytz
from datetime import datetime, time as dt_time
import threading
import os
import logging
import sys
import requests
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)

# Set Indian timezone
IST = pytz.timezone('Asia/Kolkata')

def run_lottery_scraper():
    """Run the lottery scraper with better error handling"""
    try:
        logging.info(f"Running lottery scraper at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST")
        # Run the scraper script
        result = subprocess.run([sys.executable, 'lottery_scraper.py'], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        if result.returncode == 0:
            logging.info("Lottery scraper completed successfully")
            if result.stdout:
                logging.info(f"Output: {result.stdout}")
            
            # Run the manifest generation script
            manifest_result = subprocess.run(['node', 'generate-manifest.js'], capture_output=True, text=True, timeout=120)
            if manifest_result.returncode == 0:
                logging.info("Manifest generation completed successfully")
            else:
                logging.warning(f"Manifest generation had issues: {manifest_result.stderr}")

            # Run the history generation script (optional but kept for compatibility)
            hist_result = subprocess.run(['node', 'generate-history.js'], capture_output=True, text=True, timeout=120)  # 2 minute timeout
            if hist_result.returncode == 0:
                logging.info("History generation completed successfully")
            else:
                logging.warning(f"History generation had issues: {hist_result.stderr}")
                    
            # Check if there are actual changes worth committing
            # We rely on git status in commit_and_push_changes, so we proceed if scripts ran fine.
            if True:
                # If GitHub token is set, commit and push changes
                # Also try pushing if git is configured with SSH/credential helper (implied if token is missing but user wants automation)
                github_token = os.environ.get('GITHUB_TOKEN')
                if github_token or True: # Try pushing regardless, let git handle auth errors if any
                    try:
                        commit_and_push_changes()
                    except Exception as e:
                        logging.error(f"Error during git operations: {e}")
        else:
            logging.error(f"Error running lottery scraper: {result.stderr}")
    except subprocess.TimeoutExpired:
        logging.error("Lottery scraper timed out after 5 minutes")
    except Exception as e:
        logging.error(f"Exception occurred while running scraper: {e}")

def has_actual_results():
    """Deprecated: Check performed via git status."""
    return True

def commit_and_push_changes():
    """Commit and push changes to GitHub"""
    try:
        logging.info("Checking for git changes...")
        
        # Check if there are any changes
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if not result.stdout.strip():
            logging.info("No changes to commit")
            return
            
        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Commit changes
        commit_message = f"Update lottery results - {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        
        # Push changes
        subprocess.run(['git', 'push'], check=True)
        
        logging.info("Changes successfully pushed to GitHub")
    except subprocess.CalledProcessError as e:
        logging.error(f"Git operation failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during git operations: {e}")

def scheduled_task():
    """Task that runs at specific times during the day"""
    current_time = datetime.now(IST).strftime('%H:%M:%S')
    logging.info(f"Scheduler check at {current_time} IST")
    run_lottery_scraper()

def run_scheduler():
    """Run the scheduler with specific times"""
    # Clear any existing schedules
    schedule.clear()
    
    # Schedule the task to run at specific times
    schedule.every().day.at("15:15").do(scheduled_task)  # 3:15 PM
    schedule.every().day.at("15:30").do(scheduled_task)  # 3:30 PM
    schedule.every().day.at("15:45").do(scheduled_task)  # 3:45 PM
    schedule.every().day.at("16:15").do(scheduled_task)  # 4:15 PM
    schedule.every().day.at("16:30").do(scheduled_task)  # 4:30 PM
    
    logging.info("Scheduler started - will run at specific times daily:")
    logging.info("Times: 3:15 PM, 3:30 PM, 3:45 PM, 4:15 PM, 4:30 PM IST")
    logging.info("Press Ctrl+C to stop the scheduler")
    
    # Run one initial check
    scheduled_task()
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        logging.info("Starting Kerala lottery result scheduler...")
        logging.info(f"Current time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST")
        
        # Check if GitHub token is set
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            logging.info("GitHub token detected. Automatic pushing enabled.")
        else:
            logging.warning("GITHUB_TOKEN not set. Auto-push to GitHub will not work.")
        
        # Start the scheduler
        run_scheduler()
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")