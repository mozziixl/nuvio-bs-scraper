import os
import re
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://brokensilenze.net"
FAVICON = "https://brokensilenze.net"

SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://brokensilenze.net"
}

def clean_and_extract_show_name(title_str: str):
    """Strips season and episode tags to find the root show name for database mapping"""
    match = re.search(r'(.*?)\s+Season\s+(\d+)', title_str, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return title_str.split("Episode")[0].strip()

def find_official_imdb_id(show_name: str) -> str:
    """Queries Stremio/Nuvio's global database to fetch the real IMDb ID to build the premium UI layout"""
    try:
        url = f"https://strem.io{requests.utils.quote(show_name)}.json"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            metas = response.json().get("metas", [])
            if metas and isinstance(metas, list):
                return metas[0].get("id")  # Example: returns 'tt14622242'
    except Exception as e:
        print(f"Database lookup connection delay: {e}")
    return None

def parse_catalog_feed(url: str):
    metas = []
    try:
        response = requests.get(url, headers=SESSION_HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for article in soup.find_all("article"):
                title_tag = article.find("h2") or article.find("h3")
                img_tag = article.find("img")
                link_tag = article.find("a")
                
                post_url = link_tag["href"] if link_tag else ""
                if not post_url or "/category/" in post_url:
                    continue
                    
                raw_title = title_tag.text.strip() if title_tag else ""
                if not raw_title:
                    continue
                
                # Step 1: Clean show name and match it with a global ID
                root_show_name = clean_and_extract_show_name(raw_title)
                imdb_id = find_official_imdb_id(root_show_name)
                
                clean_slug = post_url.rstrip("/").split("/")[-1]
                scraped_img = img_tag.get("src") or img_tag.get("data-src") or FAVICON
                
                # CRITICAL SEAMLESS MATRIX: If an IMDb ID is found, use it. Nuvio draws the full screen.
                # If not found, fall back to custom slug so it doesn't crash.
                final_id = imdb_id if imdb_id else f"bs_{clean_slug}"
                
                metas.append({
                    "id": final_id,
                    "type": "series",
                    "name": root_show_name,
                    "poster": scraped_img,
                    "background": scraped_img,
                    "description": f"Stream sources attached for: {raw_title}"
                })
    except Exception as e:
        print(f"Catalog compiler tracking block: {e}")
    return metas

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.cinematic",
        "version": "8.0.0",
        "name": "BS Cinematic Addon",
        "description": "Binds web streams to global movie databases for premium UI layouts with cast and summaries.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "bs_pro_feed",
                "name": "BS Complete Directory",
                "extra": [{"name": "skip", "isRequired": False}]
            }
        ],
        "resources": ["catalog", "stream"]  # No "meta" resource declared! Nuvio pulls the info automatically.
    }

# 1. CATALOG ENDPOINT: Endless multi-page browsing
@app.get("/catalog/series/{catalog_id}.json")
@app.get("/catalog/series/{catalog_id}")
def get_catalog(catalog_id: str, skip: int = Query(0)):
    items_per_page = 12
    page_number = (skip // items_per_page) + 1
    target_url = BASE_URL if page_number == 1 else f"{BASE_URL}/page/{page_number}/"
    return {"metas": parse_catalog_feed(target_url)}

# 2. STREAM ENDPOINT: Automatically maps Nuvio's internal player clicks to web links
@app.get("/stream/series/{video_id}.json")
@app.get("/stream/series/{video_id}")
def get_stream(video_id: str):
    clean_video_id = video_id.replace(".json", "")
    target_page_url = BASE_URL
    
    try:
        # If Nuvio requests an episode via IMDb format (e.g., tt1234567:1:5 for Season 1, Ep 5)
        if ":" in clean_video_id:
            parts = clean_video_id.split(":")
            imdb_id = parts[0]
            season_num = parts[1]
            episode_num = parts[2]
            
            # Fetch show name from database to find its web address
            db_lookup = requests.get(f"https://strem.io{imdb_id}.json", timeout=5)
            if db_lookup.status_code == 200:
                show_real_title = db_lookup.json().get("meta", {}).get("name", "")
                
                # Format string to look for specific episode links on the site
                search_slug = f"{show_real_title} Season {season_num} Episode {episode_num}".lower().replace(" ", "-")
                target_page_url = f"{BASE_URL}/{search_slug}/"
        else:
            # Fallback path if utilizing custom slugs
            slug = clean_video_id.replace("bs_", "")
            target_page_url = f"{BASE_URL}/{slug}/"
            
        streams = []
        response = requests.get(target_page_url, headers=SESSION_HEADERS, timeout=10)
        if response.status_code == 200:
            html_text = response.text
            soup = BeautifulSoup(html_text, "html.parser")
            
            # Pull direct high-speed video channels (.mp4 / .m3u8 structures)
            found_urls = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4|webm)[^\s"\']*)', html_text)
            for idx, media_url in enumerate(set(found_urls)):
                if any(x in media_url for x in ["favicon", "logo", "wp-content"]):
                    continue
                streams.append({
                    "name": "⚡ AUTO-PLAY",
                    "title": f"Native Playback Channel {idx + 1}",
                    "url": media_url
                })
                
            # Pull player iframes if direct stream links are blocked
            for idx, iframe in enumerate(soup.find_all("iframe")):
                src = iframe.get("src", "")
                if "http" in src:
                    streams.append({
                        "name": "🎬 INTERNAL PLAYER",
                        "title": f"Video Server Mirror {idx + 1}",
                        "url": src
                    })
                    
    except Exception as e:
        print(f"Streaming compilation routing mismatch: {e}")

    if not streams:
        streams.append({
            "name": "🌐 WEB PLAYER",
            "title": "Launch Direct Video Web View Page",
            "externalUrl": target_page_url
        })
        
    return {"streams": streams}
    
