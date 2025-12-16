import requests
import re
import os
import json
from datetime import datetime, date
import time
from bs4 import BeautifulSoup
import urllib3
import random

urllib3.disable_warnings()

# Configuration
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
CACHE_DIR = "cache"
NOTE_DIR = "note"
MAIN_URL = "https://www.kllotteryresult.com/"

def robust_get(url: str, headers: dict, timeout: int = 20, max_retries: int = 3):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
             # Random UA
            current_headers = headers.copy()
            current_headers['User-Agent'] = random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ])
            res = requests.get(url, headers=current_headers, timeout=timeout, verify=False)
            if res.status_code == 200:
                return res
            print(f"DEBUG: Status {res.status_code} for {url}")
        except Exception as e:
            last_exc = e
            print(f"DEBUG: Error fetching {url}: {e}")
            time.sleep(2)
    if last_exc:
        raise last_exc
    raise Exception(f"Failed to fetch {url}")

def fetch_page_text(url: str) -> str:
    print(f"Fetching {url}...")
    res = robust_get(url, HEADERS)
    return res.text

def parse_date_from_text(text: str):
    # 16.12.2025 or 16-12-2025
    m = re.search(r"(\d{2})[./-](\d{2})[./-](\d{4})", text)
    if m:
        try:
            return datetime.strptime(f"{m.group(3)}-{m.group(2)}-{m.group(1)}", "%Y-%m-%d").date()
        except: pass
    return None

def scrape_lottery_result(url, html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Metadata
    title_text = ""
    if soup.title:
        title_text = soup.title.string.strip()
    
    # Try getting title from h1 if not suitable in title tag
    h1 = soup.find("h1")
    if h1 and "lottery result" not in h1.text.lower():
        pass 
    
    # Date
    result_date = parse_date_from_text(title_text)
    if not result_date:
        result_date = parse_date_from_text(soup.get_text())
        
    if not result_date:
        print("DEBUG: No date found")
        return None
        
    str_date = str(result_date)
    
    # Parse Name and Draw Number
    # Pattern: "Kerala Lottery Result ... Sthree Sakthi (SS-498)"
    lottery_name = "Unknown Lottery"
    draw_number = "XX"
    code = "XX"
    
    # Extract Draw Code/Number e.g. (SS-498)
    m_draw = re.search(r"\(([A-Z]+)-(\d+)\)", title_text)
    if m_draw:
        code = m_draw.group(1)
        draw_number = f"{code}-{m_draw.group(2)}"
    
    # Extract Name: "Sthree Sakthi (SS-498)"
    # Fallback: Remove known prefixes
    clean_title = title_text
    clean_title = re.sub(r'Kerala Lottery Result Today', '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'\d+[./-]\d+[./-]\d+', '', clean_title) # Remove date
    clean_title = re.sub(r'\([^\)]+\)', '', clean_title) # Remove (SS-498)
    clean_title = clean_title.replace('|', '').replace('-', '').strip()
    
    if clean_title:
        lottery_name = clean_title.upper()
    
    if lottery_name == "UNKNOWN LOTTERY" or len(lottery_name) < 3:
        # Try map from code
        code_map = {
             'SS': 'STHREE SAKTHI', 'DL': 'DHANALEKSHMI', 'AK': 'AKSHAYA', 
             'KR': 'KARUNYA', 'KN': 'KARUNYA PLUS', 'NR': 'NIRMAL', 'FF': 'FIFTY FIFTY',
             'SK': 'SUVARNA KERALAM', 'BT': 'BHAGYATHARA', 'SM': 'SAMRUDHI'
        }
        if code in code_map:
            lottery_name = code_map[code]
    
    # 2. Prizes keys
    prizes = {}
    
    # Definitions
    prize_defs = [
        ("1st_prize", ["1st Prize", "First Prize"], 10000000),
        ("consolation_prize", ["Consolation Prize", "Cons. Prize", "Cons Prize"], 8000),
        ("2nd_prize", ["2nd Prize", "Second Prize"], 1000000),
        ("3rd_prize", ["3rd Prize", "Third Prize"], 100000),
        ("4th_prize", ["4th Prize", "Fourth Prize"], 5000),
        ("5th_prize", ["5th Prize", "Fifth Prize"], 2000),
        ("6th_prize", ["6th Prize", "Sixth Prize"], 1000),
        ("7th_prize", ["7th Prize", "Seventh Prize"], 500),
        ("8th_prize", ["8th Prize", "Eighth Prize"], 100),
        ("9th_prize", ["9th Prize", "Ninth Prize"], 50),
    ]
    
    label_map = {}
    for key, labels, amt in prize_defs:
        for l in labels:
            label_map[l.lower()] = (key, labels[0], amt)

    # State machine
    raw_text = soup.get_text("\n")
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    
    current_key = None
    current_label = None
    current_amount = 0
    current_winners = []
    
    def commit_prize():
        nonlocal current_key, current_winners
        if current_key:
            valid = []
            for w in current_winners:
                w_clean = re.sub(r'[^A-Z0-9]', '', w.upper())
                if len(w_clean) >= 4:
                    valid.append(w)
            
            prizes[current_key] = {
                "amount": current_amount,
                "label": current_label,
                "winners": valid
            }
        current_winners = []

    for line in lines:
        line_lower = line.lower()
        
        # Check header
        found_header = False
        for l_txt, (key, main_label, amt) in label_map.items():
             # Basic fuzzy match: contains text
            if l_txt in line_lower and len(line) < 60:
                commit_prize()
                current_key = key
                current_label = main_label
                current_amount = amt
                found_header = True
                break
        
        if found_header:
            continue
            
        if current_key:
            if "rs" in line_lower and ("/-" in line_lower or len(line) < 25): continue
            if "lottery" in line_lower: continue
            if "page" in line_lower: continue
            
            # Find candidate tickets
            # Regex patterns to preserve Series Code + Number (e.g. AB 123456 or AB-123456)
            # OR just a sequence of digits (e.g. 1234 or 123456)
            # We want to capture [A-Z]{2}[\s\-]?[0-9]{6} OR [0-9]{4,6}
            
            # Simple approach: Find all sequences of alphanumeric chars, then filter
            # But "AB 123456" is two sequences in regex \w+.
            # Better: Match specific ticket patterns first.
            
            # Pattern 1: Series + Digits (e.g. WA 123456, WA-123456, WA123456)
            # Allowing 1-3 letters, optional separator, 6 digits.
            series_matches = list(re.finditer(r'\b([A-Z]{1,3})[\s-]?(\d{6})\b', line, re.IGNORECASE))
            
            # We also need to capture plain numbers (4 digits, 6 digits) that are NOT part of the above.
            # So, we can replace the found series_matches in the line with spaces, then look for remaining numbers?
            # Or just assume if we found series matches, that's what we want from this line.
            
            if series_matches:
                for match in series_matches:
                    # reconstruct standardized "AB 123456"
                    code_part = match.group(1).upper()
                    num_part = match.group(2)
                    current_winners.append(f"{code_part} {num_part}")
            else:
                # Fallback: look for simple numbers (4 to 6 digits)
                # This covers lower prizes which often don't have series
                nums = re.findall(r'\b\d{4,6}\b', line)
                for n in nums:
                    current_winners.append(n)

                   
    commit_prize() # trailing

    # Filename
    # If SS-498 exists, fine.
    # We use code-num-date format
    num_part = m_draw.group(2) if m_draw else 'XX'
    filename = f"{code}-{num_part}-{str_date}.json"

    return {
        "lottery_name": lottery_name,
        "draw_number": draw_number,
        "draw_date": str_date,
        "venue": "", 
        "prizes": prizes,
        "filename": filename,
        "github_url": f"https://raw.githubusercontent.com/santhkhd/kerala_loto/main/note/{filename}",
        "downloadLink": ""
    }

def get_last_n_result_links(n=15):
    text = fetch_page_text(MAIN_URL)
    soup = BeautifulSoup(text, 'html.parser')
    links = set()
    
    for a in soup.find_all('a', href=True):
        h = a['href']
        if 'kerala-lottery-result' in h.lower():
            if h.startswith('/'):
                h = MAIN_URL.rstrip('/') + h
            links.add(h)
    
    return sorted(list(links))

def main():
    os.makedirs(NOTE_DIR, exist_ok=True)
    links = get_last_n_result_links()
    print(f"Found {len(links)} links")
    
    today = date.today()
    
    for url in links:
        try:
            print(f"Processing {url}")
            text = fetch_page_text(url)
            data = scrape_lottery_result(url, text)
            
            if data:
                fpath = os.path.join(NOTE_DIR, data['filename'])
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                print(f"Saved {fpath}")
                
        except Exception as e:
            print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    main()
