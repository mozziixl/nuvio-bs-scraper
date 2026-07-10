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
    "Accept-Language": "en-US,en;q=0.5"
}

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
            scraped_img = img_tag.get("src") or img_tag.get("data-src") or FAVICON
            
            metas.append({
                "id": f"bs_{clean_slug}",
                "type": "movie",
                "name": raw_title,
                "poster": scraped_img,
                "background": scraped_img,
                "description": f"Direct link to player source for {raw_title}."
            })
    except Exception as e:
        print(f"Catalog collection error: {e}")
    return metas

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.fixedmovie",
        "version": "6.5.0",
        "name": "BS Seamless Movie Addon",
        "description": "Natively parses episode cover art and handles iframe streaming players.",
        "types": ["movie"],
        "catalogs": [
            {
                "type": "movie",
                "id": "bs_master_movies",
                "name": "BS Complete Directory List",
                "extra": [{"name": "skip", "isRequired": False}]
            }
        ],
        "resources": ["catalog", "meta", "stream"]
    }

# 1. CATALOG ENDPOINT: Multi-page scrolling
@app.get("/catalog/movie/{catalog_id}.json")
@app.get("/catalog/movie/{catalog_id}")
def get_catalog(catalog_id: str, skip: int = Query(0)):
    items_per_page = 12
    page_number = (skip // items_per_page) + 1
    target_url = BASE_URL if page_number == 1 else f"{BASE_URL}/page/{page_number}/"
    return {"metas": parse_complete_catalog(target_url)}

# 2. META ENDPOINT: FIXED - Pulls the real background image dynamically from the post page
@app.get("/meta/movie/{meta_id}.json")
@app.get("/meta/movie/{meta_id}")
def get_meta(meta_id: str):
    clean_id = meta_id.replace(".json", "").replace("bs_", "")
    display_title = clean_id.replace("-", " ").title()
    
    # Scrapes the show's actual page to grab the high-quality banner image
    target_page_url = f"{BASE_URL}/{clean_id}/"
    extracted_art = FAVICON
    try:
        res = requests.get(target_page_url, headers=SESSION_HEADERS, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            img_tag = soup.find("img")
            if img_tag:
                extracted_art = img_tag.get("src") or img_tag.get("data-src") or FAVICON
    except Exception:
        pass
    
    return {
        "meta": {
            "id": f"bs_{clean_id}",
            "type": "movie",
            "name": display_title,
            "poster": extracted_art,
            "background": extracted_art,
            "description": f"Video stream tracking active for webpage entry: {display_title}"
        }
    }

# 3. STREAM ENDPOINT: FIXED - Handles iframe structures safely
@app.get("/stream/movie/{video_id}.json")
@app.get("/stream/movie/{video_id}")
def get_stream(video_id: str):
    clean_id = video_id.replace(".json", "").replace("bs_", "")
    target_page_url = f"{BASE_URL}/{clean_id}/"
    
    streams = []
    try:
        response = requests.get(target_page_url, headers=SESSION_HEADERS, timeout=10)
        if response.status_code == 200:
            html_text = response.text
            soup = BeautifulSoup(html_text, "html.parser")
            
            # Extract direct raw video paths if visible (.mp4 or .m3u8)
            found_urls = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4|webm)[^\s"\']*)', html_text)
            for idx, media_url in enumerate(set(found_urls)):
                if any(x in media_url for x in ["favicon", "logo", "wp-content"]):
                    continue
                streams.append({
                    "name": "⚡ AUTO-PLAY",
                    "title": f"Direct Stream Channel Source {idx + 1}",
                    "url": media_url
                })
                
            # Extract iframe embeds and format them safely
            for idx, iframe in enumerate(soup.find_all("iframe")):
                src = iframe.get("src", "")
                if "http" in src:
                    streams.append({
                        "name": "🎬 LINK PLAYER",
                        "title": f"Video Server Mirror Server {idx + 1}",
                        "url": src
                    })
    except Exception as e:
        print(f"Streaming link node extractor error: {e}")

    # Fallback Option: Allows Nuvio to trigger its built-in external player engine
    streams.append({
        "name": "🌐 WEB PLAYER",
        "title": "Launch Direct Video Web View Page",
        "externalUrl": target_page_url
    })
        
    return {"streams": streams}
    
