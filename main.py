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

# Real browser signatures to prevent Cloudflare blocks
SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# Dynamic Cinemeta/TMDB Lookup Engine
def find_imdb_id(title: str) -> str:
    """Searches open streaming catalogs to find the official IMDb ID for a title"""
    try:
        # Clean title variations (e.g. removing 'Season 1' or dates) for accurate search matching
        search_query = re.sub(r'\s*(?:Season|S)\s*\d+|\s*\(\d{4}\)', '', title, flags=re.IGNORECASE).strip()
        url = f"https://strem.io{requests.utils.quote(search_query)}.json"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            metas = data.get("metas", [])
            if metas:
                return metas[0].get("id")  # Returns something like "tt14622242"
    except Exception as e:
        print(f"IMDb metadata matching lookup error: {e}")
    return None

def parse_complete_catalog(url: str):
    metas = []
    try:
        response = requests.get(url, headers=SESSION_HEADERS, timeout=10)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article")
        
        for idx, article in enumerate(articles):
            title_tag = article.find("h2") or article.find("h3")
            img_tag = article.find("img")
            link_tag = article.find("a")
            
            post_url = link_tag["href"] if link_tag else ""
            if not post_url or "/category/" in post_url:
                continue
                
            raw_title = title_tag.text.strip() if title_tag else ""
            if not raw_title:
                continue
                
            clean_slug = post_url.rstrip("/").split("/")[-1]
            img_url = img_tag.get("src") or img_tag.get("data-src") or FAVICON
            
            # Lookup real database ID
            imdb_id = find_imdb_id(raw_title)
            
            # CRITICAL FIX: If found, use the IMDb ID. Nuvio fills out the layout itself.
            # If not found, use a clean slug so it displays a proper name instead of 'Show_14'
            final_id = imdb_id if imdb_id else f"bs_{clean_slug}"
            
            metas.append({
                "id": final_id,
                "type": "series",
                "name": raw_title,
                "poster": img_url,
                "description": f"Stream links matched from web backend source files."
            })
    except Exception as e:
        print(f"Catalog processing grid warning: {e}")
    return metas

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.imdbmatched",
        "version": "3.0.0",
        "name": "BS Pro Media Addon",
        "description": "Natively binds website content to official cinematic databases for complete metadata layouts.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "bs_pro_feed",
                "name": "BS Main Library",
                "extra": [{"name": "skip", "isRequired": False}]
            }
        ],
        "resources": ["catalog", "stream"]  # Removed "meta" so Nuvio falls back to global databases
    }

# 1. Catalog Endpoint: Pulls items and matches database codes
@app.get("/catalog/series/{catalog_id}.json")
@app.get("/catalog/series/{catalog_id}")
def get_catalog(catalog_id: str, skip: int = Query(0)):
    items_per_page = 12
    page_number = (skip // items_per_page) + 1
    
    target_url = BASE_URL if page_number == 1 else f"{BASE_URL}/page/{page_number}/"
    return {"metas": parse_complete_catalog(target_url)}

# 2. Stream Endpoint: Tracks selected media stream requests
@app.get("/stream/series/{video_id}.json")
@app.get("/stream/series/{video_id}")
def get_stream(video_id: str):
    # Cleans trailing routing artifacts from the request string
    clean_video_id = video_id.replace(".json", "")
    
    # Fallback default source landing page if video matching parameters drop
    target_page_url = BASE_URL
    
    streams = []
    try:
        # If Nuvio requests using a native IMDb identifier format (e.g. tt1234567:1:1)
        if ":" in clean_video_id:
            parts = clean_video_id.split(":")
            imdb_id = parts[0]
            # Fetch the actual show title from Cinemeta using its IMDb ID to reconnect with the web source path
            meta_lookup = requests.get(f"https://strem.io{imdb_id}.json", timeout=5)
            if meta_lookup.status_code == 200:
                show_name = meta_lookup.json().get("meta", {}).get("name", "")
                slug = show_name.lower().replace(" ", "-")
                target_page_url = f"{BASE_URL}/{slug}/"
        else:
            # Handles internal backup fallback slug tags
            slug = clean_video_id.replace("bs_", "")
            target_page_url = f"{BASE_URL}/{slug}/"

        response = requests.get(target_page_url, headers=SESSION_HEADERS, timeout=10)
        if response.status_code == 200:
            html_text = response.text
            soup = BeautifulSoup(html_text, "html.parser")
            
            # Deep Scan: Uncovers hidden underlying video media addresses
            found_urls = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4|webm)[^\s"\']*)', html_text)
            for idx, media_url in enumerate(set(found_urls)):
                if any(x in media_url for x in ["favicon", "logo", "wp-content"]):
                    continue
                streams.append({
                    "name": "⚡ AUTO-PLAY",
                    "title": f"Native Video Playback Stream {idx + 1}",
                    "url": media_url
                })
                
            # Mirror frame fallback scraping layer
            for idx, iframe in enumerate(soup.find_all("iframe")):
                src = iframe.get("src", "")
                if "http" in src:
                    streams.append({
                        "name": "🎬 LINK PLAYER",
                        "title": f"External Video Source Mirror {idx + 1}",
                        "url": src
                    })
    except Exception as e:
        print(f"Stream resolution matching failure: {e}")

    if not streams:
        streams.append({
            "name": "🌐 WEB FALLBACK",
            "title": "Open Original Video Source Web Link",
            "url": target_page_url
        })
        
    return {"streams": streams}
    
