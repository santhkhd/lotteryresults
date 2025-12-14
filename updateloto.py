import os
import json
import re
import sys
import requests
from bs4 import BeautifulSoup, Tag
from datetime import datetime, time as dt_time, date, timedelta
from typing import Optional, List, Tuple, Dict, Any
import pytz
import time
import random
import hashlib
import pickle
from urllib.parse import quote

# Define the Indian timezone
IST = pytz.timezone('Asia/Kolkata')

# Enhanced headers to look more like a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0',
    'Referer': 'https://www.kllotteryresult.com/'
}

# Optional proxy-based scraping fallback (e.g., ScraperAPI or compatible)
# Provide an API key via env var SCRAPERAPI_KEY in CI to bypass origin blocking.
SCRAPER_API_KEY = os.environ.get('SCRAPERAPI_KEY', '').strip()
SCRAPER_API_ENDPOINT = os.environ.get('SCRAPERAPI_ENDPOINT', 'http://api.scraperapi.com')

def get_cached_result(url: str, cache_duration_hours: int = 6) -> Optional[str]:
    """Get cached result if available and not expired."""
    # Create cache directory if it doesn't exist
    os.makedirs("cache", exist_ok=True)
    
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_file = f"cache/{cache_key}.pkl"
    
    if os.path.exists(cache_file):
        # Check if cache is still valid
        file_time = os.path.getmtime(cache_file)
        if (time.time() - file_time) < (cache_duration_hours * 3600):
            try:
                with open(cache_file, 'rb') as f:
                    print(f"DEBUG: Using cached result for {url}")
                    return pickle.load(f)
            except Exception as e:
                print(f"DEBUG: Failed to load cache: {e}")
                # Remove corrupted cache file
                os.remove(cache_file)
    return None

def save_to_cache(url: str, content: str):
    """Save content to cache."""
    os.makedirs("cache", exist_ok=True)
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_file = f"cache/{cache_key}.pkl"
    
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(content, f)
        print(f"DEBUG: Saved result to cache for {url}")
    except Exception as e:
        print(f"DEBUG: Failed to save to cache: {e}")

def build_proxy_url(target_url: str) -> str:
    if not SCRAPER_API_KEY:
        return target_url
    # ScraperAPI format: http(s)://api.scraperapi.com?api_key=KEY&url=ENCODED
    from urllib.parse import urlencode
    query = urlencode({'api_key': SCRAPER_API_KEY, 'url': target_url})
    return f"{SCRAPER_API_ENDPOINT}?{query}"

def robust_get(url: str, headers: dict, timeout: int = 20, max_retries: int = 3) -> requests.Response:
    """Try direct fetch first; on 403/429/5xx or network error, retry and fall back to proxy if configured."""
    # First check cache
    cached_content = get_cached_result(url)
    if cached_content:
        # Create a mock response object
        class MockResponse:
            def __init__(self, content):
                self.text = content
                self.status_code = 200
            def raise_for_status(self):
                pass
        return MockResponse(cached_content)
    
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            # Add randomization to headers to avoid detection
            request_headers = headers.copy()
            request_headers['User-Agent'] = random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ])
            
            res = requests.get(url, headers=request_headers, timeout=timeout)
            print(f"DEBUG: Request to {url} returned status {res.status_code}")
            
            if res.status_code in (403, 429) or res.status_code >= 500:
                raise requests.exceptions.RequestException(f"HTTP {res.status_code}")
            
            # Save successful response to cache
            save_to_cache(url, res.text)
            return res
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            print(f"DEBUG: Attempt {attempt} failed with {exc}")
            # Try proxy fallback if available
            if SCRAPER_API_KEY:
                try:
                    proxy_url = build_proxy_url(url)
                    print(f"DEBUG: Trying proxy URL: {proxy_url}")
                    res = requests.get(proxy_url, headers=headers, timeout=timeout)
                    if res.status_code in (403, 429) or res.status_code >= 500:
                        raise requests.exceptions.RequestException(f"Proxy HTTP {res.status_code}")
                    
                    # Save successful response to cache
                    save_to_cache(url, res.text)
                    return res
                except requests.exceptions.RequestException as exc2:
                    last_exc = exc2
                    print(f"DEBUG: Proxy attempt failed with {exc2}")
            # Backoff between attempts
            if attempt < max_retries:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff up to 10 seconds
                print(f"DEBUG: Waiting {wait_time} seconds before retry")
                time.sleep(wait_time)
    # Exhausted retries
    if last_exc:
        raise last_exc
    raise RuntimeError("Failed to fetch URL and no exception captured")

def fetch_text_via_jina(url: str) -> str:
    """Fetch page text via r.jina.ai to bypass Cloudflare challenges without API keys."""
    # Check cache first
    cached_content = get_cached_result(url)
    if cached_content:
        return cached_content
    
    proxied = "https://r.jina.ai/http://" + url.replace("https://", "").replace("http://", "")
    res = requests.get(proxied, headers=HEADERS, timeout=30)
    res.raise_for_status()
    
    # Save to cache
    save_to_cache(url, res.text)
    return res.text

def fetch_page_text(url: str) -> str:
    """Fetch page HTML using direct request first, then fallback to Jina proxy."""
    # Check cache first
    cached_content = get_cached_result(url)
    if cached_content:
        print(f"DEBUG: Using cached content for {url}")
        return cached_content
    
    try:
        print(f"DEBUG: Trying direct fetch for {url}")
        res = robust_get(url, HEADERS, timeout=25)
        res.raise_for_status()
        content = res.text
        print(f"DEBUG: Direct fetch successful, status: {res.status_code}")
        print(f"DEBUG: Content length: {len(content)}")
        print(f"DEBUG: Content preview: {content[:200]}")
        
        # Check if content looks like HTML
        if "<html" not in content.lower() and "<!doctype" not in content.lower():
            print("DEBUG: Content doesn't look like HTML, might be blocked")
        
        # Save to cache
        save_to_cache(url, content)
        return content
    except Exception as e:
        print(f"DEBUG: Direct fetch failed: {e}")
        print("DEBUG: Trying Jina proxy fallback")
        try:
            result = fetch_text_via_jina(url)
            print(f"DEBUG: Jina proxy result length: {len(result)}")
            print(f"DEBUG: Jina content preview: {result[:200]}")
            return result
        except Exception as jina_e:
            print(f"DEBUG: Jina proxy also failed: {jina_e}")
            raise

def parse_date_from_text(text: str) -> Optional[date]:
    """Extract a date from text supporting multiple formats."""
    try:
        # Common numeric formats: 16-09-2025, 16/09/2025, 16.09.2025
        m = re.search(r"(\d{2})[./-](\d{2})[./-](\d{4})", text)
        if m:
            try:
                return datetime.strptime(f"{m.group(3)}-{m.group(2)}-{m.group(1)}", "%Y-%m-%d").date()
            except ValueError:
                pass
        # Textual month formats: 16 September 2025, 16 Sep 2025, Sep 16, 2025
        patterns = [
            "%d %B %Y", "%d %b %Y", "%b %d, %Y", "%B %d, %Y",
            "%d-%b-%Y", "%d-%B-%Y"
        ]
        # Try sliding windows around words that look like dates
        candidates = []
        # Gather tokens that include month names
        month_regex = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)"
        for m2 in re.finditer(rf"\b\d{{1,2}}\s+{month_regex}\s+\d{{4}}\b", text, flags=re.I):
            candidates.append(m2.group(0))
        for m3 in re.finditer(rf"\b{month_regex}\s+\d{{1,2}},\s*\d{{4}}\b", text, flags=re.I):
            candidates.append(m3.group(0))
        for cand in candidates:
            for fmt in patterns:
                try:
                    return datetime.strptime(cand, fmt).date()
                except ValueError:
                    continue
    except Exception as e:
        print(f"Error in parse_date_from_text: {e}")
    return None

def get_last_n_result_links(n=15):
    MAIN_URL = "https://www.kllotteryresult.com/"
    today = datetime.now().date()
    
    # Check if we have cached homepage links
    homepage_cache_file = "cache/homepage_links.pkl"
    if os.path.exists(homepage_cache_file):
        file_time = os.path.getmtime(homepage_cache_file)
        # Use cached links if less than 1 hour old
        if (time.time() - file_time) < 3600:
            try:
                with open(homepage_cache_file, 'rb') as f:
                    cached_links = pickle.load(f)
                    print("DEBUG: Using cached homepage links")
                    return cached_links[:n]
            except Exception as e:
                print(f"DEBUG: Failed to load cached homepage links: {e}")
    
    try:
        page_text = fetch_page_text(MAIN_URL)
        # Add delay to avoid rate limiting
        time.sleep(1)
    except Exception as e:
        print(f"Error fetching homepage: {e}")
        return []

    # Extract links using both HTML parsing and regex as fallback
    candidates_set = set()
    try:
        soup = BeautifulSoup(page_text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "kerala-lottery-result" in href.lower():
                if href.startswith("http"):
                    candidates_set.add(href)
                else:
                    candidates_set.add(f"https://www.kllotteryresult.com{href}")
    except Exception as e:
        print(f"Error parsing homepage HTML: {e}")
        pass
    # Regex fallback
    if not candidates_set:
        abs_links = re.findall(r'https?://www\.kllotteryresult\.com/[a-z0-9-]*kerala-lottery-result[a-z0-9-]*/?', page_text, flags=re.I)
        rel_links = re.findall(r'/[a-z0-9-]*kerala-lottery-result[a-z0-9-]*/?', page_text, flags=re.I)
        for p in abs_links:
            candidates_set.add(p)
        for p in rel_links:
            candidates_set.add(f"https://www.kllotteryresult.com{p}")
    candidates = sorted(candidates_set)

    # Logging: counts (abs/rel) — we normalized to absolute URLs, so report abs only
    abs_count = len([c for c in candidates if c.startswith("http")])
    print(f"Homepage links: abs={abs_count} candidates={len(candidates)}")
    if candidates:
        for preview_url in candidates[:5]:
            print(f"Candidate: {preview_url}")

    results = []
    seen = set()
    dated_candidates: List[Tuple[date, str]] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        # fetch the result page text (direct first, then fallback) and validate date <= today
        try:
            page_text2 = fetch_page_text(url)
            # Add delay between requests to avoid rate limiting
            time.sleep(1)
        except Exception as e:
            print(f"Skip {url}: fetch error {e}")
            continue
        # find date using robust parser
        result_date = parse_date_from_text(page_text2) or None
        if not result_date:
            print(f"Skip {url}: no date found")
            continue
        # Include results from the last 30 days to ensure we don't miss any
        # This will help capture the missing results
        days_diff = (today - result_date).days
        if result_date <= today and days_diff <= 30:
            dated_candidates.append((result_date, url))
        elif result_date <= today:
            # Still include older results but with lower priority
            # Add a large number to sort them after recent results
            dated_candidates.append((result_date, url))
        else:
            print(f"Skip {url}: future date {result_date}")
    # Sort by date descending and return top n URLs
    # For recent results (within 30 days), sort normally
    # For older results, we still include them but they'll be at the end
    dated_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Cache the results
    try:
        with open(homepage_cache_file, 'wb') as f:
            pickle.dump([url for _, url in dated_candidates], f)
    except Exception as e:
        print(f"DEBUG: Failed to cache homepage links: {e}")
    
    for d, u in dated_candidates[:n]:
        results.append(u)
    return results

# ... rest of the code remains the same ...
