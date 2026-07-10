import os
import re
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable cross-origin resource sharing so Nuvio clients do not throw HTTP blocked rules
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://brokensilenze.net"
FAVICON = "https://brokensilenze.net"

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.seamless",
        "version": "1.5.0",
        "name": "BS Seamless Streamer",
        "description": "Natively listings and plays video tracks extracted directly from the web source layout.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "bs_complete_catalog",
                "name": "BS Full Stream Feed",
                "extra": [{"name": "skip", "isRequired": False}]
            }
        ],
        "resources": ["catalog", "meta", "stream"]
    }

# Memory-restricted web scraper routine safely scoped for Render free constraints
def scrape_catalog_nodes(url: str):
    metas = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
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
                
            # Create a clean item slug from the web path to keep metadata tracking solid
            clean_slug = post_url.rstrip("/").split("/")[-1]
            title = title_tag.text.strip() if title_tag else f"Show {idx + 1}"
            img_url = img_tag["src"] if img_tag else FAVICON
            
            metas.append({
                "id": f"bs_{clean_slug}",
                "type": "series",
                "name": title,
                "poster": img_url,
                "description": f"Source asset catalog row index node target."
            })
    except Exception as e:
        print(f"Server background worker warning: {e}")
    return metas

# 1. Catalog Endpoint: Translates Nuvio scrolling requests to site paginations
@app.get("/catalog/series/{catalog_id}.json")
@app.get("/catalog/series/{catalog_id}")
def get_catalog(catalog_id: str, skip: int = Query(0)):
    clean_catalog = catalog_id.replace(".json", "")
    if clean_catalog != "bs_complete_catalog":
        return {"metas": []}
        
    items_per_page = 12 
    calculated_page = (skip // items_per_page) + 1
    
    target_url = BASE_URL if calculated_page == 1 else f"{BASE_URL}/page/{calculated_page}/"
    return {"metas": scrape_catalog_nodes(target_url)}

# 2. Meta Endpoint: Formats catalog index records to look clean inside Nuvio
@app.get("/meta/series/{meta_id}.json")
@app.get("/meta/series/{meta_id}")
def get_meta(meta_id: str):
    clean_id = meta_id.replace(".json", "").replace("bs_", "")
    human_readable_title = clean_id.replace("-", " ").title()
    
    return {
        "meta": {
            "id": f"bs_{clean_id}",
            "type": "series",
            "name": human_readable_title,
            "poster": FAVICON,
            "background": FAVICON,
            "description": "Click any available player link below to launch direct video playback."
        }
    }

# 3. Stream Engine: Intercepts raw video sources to trigger internal Nuvio video playback
@app.get("/stream/series/{meta_id}.json")
@app.get("/stream/series/{meta_id}")
def get_stream(meta_id: str):
    clean_id = meta_id.replace(".json", "").replace("bs_", "")
    target_video_page = f"{BASE_URL}/{clean_id}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    streams = []
    try:
        response = requests.get(target_video_page, headers=headers, timeout=8)
        if response.status_code == 200:
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Match hidden streaming media file pointers (.mp4 / .m3u8 structures) inside javascript logic
            raw_media_links = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)', html_content)
            for idx, file_url in enumerate(set(raw_media_links)):
                streams.append({
                    "name": "⚡ AUTO-PLAY",
                    "title": f"Native Auto-Stream {idx + 1} (Direct File)",
                    "url": file_url
                })

            # Check standard raw HTML video elements
            for index, video in enumerate(soup.find_all("video")):
                src = video.get("src")
                if src and "http" in src:
                    streams.append({"name": "🎬 NATIVE", "title": f"Source Player Track {index + 1}", "url": src})
                for source in video.find_all("source"):
                    src_url = source.get("src")
                    if src_url and "http" in src_url:
                        streams.append({"name": "🎬 NATIVE", "title": f"Stream Track Quality ({source.get('res', 'Default')})", "url": src_url})

            # Extract iframe references to allow mirrors to operate
            for idx, iframe in enumerate(soup.find_all("iframe")):
                iframe_src = iframe.get("src", "")
                if "http" in iframe_src:
                    streams.append({
                        "name": "🔗 MIRROR",
                        "title": f"External Video Server Frame {idx + 1}",
                        "url": iframe_src
                    })
    except Exception as e:
        print(f"Playback router tracking mismatch: {e}")

    # Fallback element so you can still open the browser frame manually if bot scripts block parsing
    if not streams:
        streams.append({
            "name": "🌐 WEB VIEW",
            "title": "Launch Direct Video Web View Page",
            "url": target_video_page
        })
        
    return {"streams": streams}
    
