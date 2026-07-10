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
            img_url = img_tag.get("src") or img_tag.get("data-src") or FAVICON
            
            metas.append({
                "id": f"bs_{clean_slug}",
                "type": "series",
                "name": raw_title,
                "poster": img_url,
                "description": "Select this title to view available episodes."
            })
    except Exception as e:
        print(f"Catalog collection issue: {e}")
    return metas

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.browserfallback",
        "version": "4.2.0",
        "name": "BS Seamless Engine",
        "description": "Infinite continuous scrolling catalog with external system browser routing.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "bs_master_feed",
                "name": "BS Complete Directory",
                "extra": [{"name": "skip", "isRequired": False}]
            }
        ],
        "resources": ["catalog", "meta", "stream"]
    }

# 1. CATALOG ENDPOINT
@app.get("/catalog/series/{catalog_id}.json")
@app.get("/catalog/series/{catalog_id}")
def get_catalog(catalog_id: str, skip: int = Query(0)):
    items_per_page = 12
    page_number = (skip // items_per_page) + 1
    target_url = BASE_URL if page_number == 1 else f"{BASE_URL}/page/{page_number}/"
    return {"metas": parse_complete_catalog(target_url)}

# 2. META ENDPOINT
@app.get("/meta/series/{meta_id}.json")
@app.get("/meta/series/{meta_id}")
def get_meta(meta_id: str):
    clean_id = meta_id.replace(".json", "").replace("bs_", "")
    display_title = clean_id.replace("-", " ").title()
    
    episodes_list = []
    for i in range(1, 25):  
        episodes_list.append({
            "id": f"bs_vid_{clean_id}_ep{i}",
            "title": f"Episode {i}",
            "season": 1,
            "episode": i,
            "released": f"2026-01-{i:02d}T00:00:00.000Z"
        })
        
    return {
        "meta": {
            "id": f"bs_{clean_id}",
            "type": "series",
            "name": display_title,
            "poster": FAVICON,
            "background": FAVICON,
            "description": f"Full streaming database index for {display_title}.",
            "videos": episodes_list
        }
    }

# 3. STREAM ENDPOINT - OPTIMIZED FOR EXTERNAL WEB WEB PLAYER DEPLOYMENTS
@app.get("/stream/series/{video_id}.json")
@app.get("/stream/series/{video_id}")
def get_stream(video_id: str):
    clean_video_id = video_id.replace(".json", "").replace("bs_vid_", "")
    base_slug = clean_video_id.split("_ep")
    target_page_url = f"{BASE_URL}/{base_slug}/"
    
    # CRITICAL SECURITY BYPASS FIX: Uses 'externalUrl' dictionary structure
    # This prevents the app from feeding layout code to VLC and forcing a system crash.
    # Instead, Nuvio launches the episode cleanly inside your standard device browser.
    return {
        "streams": [
            {
                "name": "🌐 BROWSER VIEW",
                "title": "Launch Direct Video Web View Page",
                "externalUrl": target_page_url
            }
        ]
    }
    
