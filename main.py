import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, HTTPException
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
FAVICON = f"{BASE_URL}/favicon.ico"

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.fullscraper",
        "version": "1.3.0",
        "name": "BS Complete Player",
        "description": "Exposes full infinite pagination and video streams for Nuvio.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "bs_complete_catalog",
                "name": "BS Complete Catalogue",
                "extra": [{"name": "skip", "isRequired": False}]
            }
        ],
        "resources": ["catalog", "meta", "stream"]
    }

# Memory-optimized pagination fetching engine
def parse_target_page(url: str):
    metas = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # Timeout prevents Render worker processes from stalling and running out of RAM memory
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article")
        
        for idx, article in enumerate(articles):
            title_tag = article.find("h2")
            img_tag = article.find("img")
            link_tag = article.find("a")
            
            post_url = link_tag["href"] if link_tag else ""
            if not post_url:
                continue
                
            # Use the actual web-slug to match streams directly later
            clean_slug = post_url.rstrip("/").split("/")[-1]
            title = title_tag.text.strip() if title_tag else "Unknown Show"
            img_url = img_tag["src"] if img_tag else FAVICON
            
            metas.append({
                "id": f"bs_{clean_slug}",
                "type": "series",
                "name": title,
                "poster": img_url,
                "description": f"Stream directly extracted from source post."
            })
    except Exception as e:
        print(f"Scraper page allocation error: {e}")
        
    return metas

# 1. Memory-Safe Infinite Catalogue Pagination 
@app.get("/catalog/series/{catalog_id}.json")
@app.get("/catalog/series/{catalog_id}")
def get_catalog(catalog_id: str, skip: int = Query(0, description="Pagination index offset")):
    clean_catalog = catalog_id.replace(".json", "")
    if clean_catalog != "bs_complete_catalog":
        return {"metas": []}
        
    # Keeps individual server response weights tiny to fit Render's free tier profile
    items_per_page = 12 
    calculated_page = (skip // items_per_page) + 1

    target_url = BASE_URL if calculated_page == 1 else f"{BASE_URL}/page/{calculated_page}/"
    return {"metas": parse_target_page(target_url)}

# 2. Re-mappable Meta Data Handshake Route
@app.get("/meta/series/{meta_id}.json")
@app.get("/meta/series/{meta_id}")
def get_meta(meta_id: str):
    clean_id = meta_id.replace(".json", "").replace("bs_", "")
    human_title = clean_id.replace("-", " ").title()
    
    return {
        "meta": {
            "id": f"bs_{clean_id}",
            "type": "series",
            "name": human_title,
            "poster": FAVICON,
            "background": FAVICON,
            "description": "Video streams available via Nuvio native interface decoder panels."
        }
    }

# 3. Stream Endpoint: Resolves the Actual Player Target
@app.get("/stream/series/{meta_id}.json")
@app.get("/stream/series/{meta_id}")
def get_stream(meta_id: str):
    clean_id = meta_id.replace(".json", "").replace("bs_", "")
    # Recreate the exact video landing page link
    target_video_url = f"{BASE_URL}/{clean_id}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    streams = []
    try:
        response = requests.get(target_video_url, headers=headers, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find video sources inside iframes or video players on the show page
            iframes = soup.find_all("iframe")
            for idx, iframe in enumerate(iframes):
                src = iframe.get("src", "")
                if "http" in src:
                    streams.append({
                        "title": f"Mirror Source Server {idx + 1}",
                        "url": src
                    })
                    
            # Check for generic native file tags inside the markup
            video_tags = soup.find_all("video")
            for idx, vid in enumerate(video_tags):
                src = vid.get("src", "")
                if src:
                    streams.append({
                        "title": f"Direct Stream Node {idx + 1}",
                        "url": src
                    })
    except Exception as e:
        print(f"Streaming link node crawl failure: {e}")

    # Fallback to absolute raw viewing link if programmatic frame capture is blocked by anti-bot rules
    if not streams:
        streams.append({
            "title": "Launch Direct Video Web View Player",
            "url": target_video_url
        })
        
    return {"streams": streams}
    
