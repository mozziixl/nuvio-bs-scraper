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

def clean_series_name(title_str: str) -> str:
    cleaned = re.sub(r'\s*(?:Season|S|Ep|Episode)\s*\d+.*', '', title_str, flags=re.IGNORECASE)
    return cleaned.strip()

def parse_episode_numbers(title_str: str):
    s_match = re.search(r'Season\s*(\d+)', title_str, re.IGNORECASE)
    e_match = re.search(r'Episode\s*(\d+)', title_str, re.IGNORECASE)
    s = int(s_match.group(1)) if s_match else 1
    e = int(e_match.group(1)) if e_match else 1
    return s, e

def parse_catalog_page(url: str):
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
                    
                show_name = clean_series_name(raw_title)
                safe_slug = post_url.rstrip("/").split("/")[-1]
                scraped_img = img_tag.get("src") or img_tag.get("data-src") or FAVICON
                
                metas.append({
                    "id": f"bs_show_{safe_slug}",
                    "type": "series",
                    "name": show_name,
                    "poster": scraped_img,
                    "background": scraped_img,
                    "description": f"Latest episode update: {raw_title}"
                })
    except Exception as e:
        print(f"Catalog collection error: {e}")
    return metas

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.cleanprotocol",
        "version": "14.0.0",
        "name": "BS Seamless Engine Pro",
        "description": "True episodic structures returning strict playable direct streaming URLs for VLC player.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "bs_master_feed",
                "name": "BS Library Feed",
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
    return {"metas": parse_catalog_page(target_url)}

# 2. META ENDPOINT
@app.get("/meta/series/{meta_id}.json")
@app.get("/meta/series/{meta_id}")
def get_meta(meta_id: str):
    clean_slug = meta_id.replace(".json", "").replace("bs_show_", "")
    target_page_url = f"{BASE_URL}/{clean_slug}/"
    
    show_title = clean_slug.replace("-", " ").title()
    poster_art = FAVICON
    videos = []
    
    try:
        res = requests.get(target_page_url, headers=SESSION_HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            title_header = soup.find("h1")
            img_tag = soup.find("img")
            if img_tag:
                poster_art = img_tag.get("src") or img_tag.get("data-src") or FAVICON
                
            page_title = title_header.text.strip() if title_header else show_title
            parent_show_name = clean_series_name(page_title)
            
            search_url = f"{BASE_URL}/?s={requests.utils.quote(parent_show_name)}"
            search_res = requests.get(search_url, headers=SESSION_HEADERS, timeout=8)
            
            if search_res.status_code == 200:
                search_soup = BeautifulSoup(search_res.text, "html.parser")
                for article in search_soup.find_all("article"):
                    ep_title_tag = article.find("h2") or article.find("h3")
                    ep_link_tag = article.find("a")
                    
                    if ep_title_tag and ep_link_tag:
                        ep_title = ep_title_tag.text.strip()
                        ep_slug = ep_link_tag["href"].rstrip("/").split("/")[-1]
                        s, e = parse_episode_numbers(ep_title)
                        
                        videos.append({
                            "id": f"bs_playnode_{ep_slug}",
                            "title": ep_title,
                            "season": s,
                            "episode": e,
                            "released": "2026-01-01T00:00:00.000Z"
                        })
    except Exception as e:
        print(f"Meta processing failed: {e}")
        
    if not videos:
        videos.append({"id": f"bs_playnode_{clean_slug}", "title": show_title, "season": 1, "episode": 1})

    videos.sort(key=lambda x: (x["season"], x["episode"]))

    return {
        "meta": {
            "id": meta_id,
            "type": "series",
            "name": parent_show_name if 'parent_show_name' in locals() else show_title,
            "poster": poster_art,
            "background": poster_art,
            "description": f"Dynamic internal series directories compiled for: {show_title}",
            "videos": videos
        }
    }

# 3. STREAM ENDPOINT - SYNTAX CHECKED AND FULLY CLOSED
@app.get("/stream/series/{video_id}.json")
@app.get("/stream/series/{video_id}")
def get_stream(video_id: str):
    clean_slug = video_id.replace(".json", "").replace("bs_playnode_", "")
    target_page_url = f"{BASE_URL}/{clean_slug}/"
    
    direct_media_links = set()
    embed_player_urls = []
    
    try:
        response = requests.get(target_page_url, headers=SESSION_HEADERS, timeout=10)
        if response.status_code == 200:
            html_text = response.text
            soup = BeautifulSoup(html_text, "html.parser")
            
            # Extract video/source tags
            for video in soup.find_all("video"):
                v_src = video.get("src")
                if v_src: 
                    direct_media_links.add(v_src)
            for source in soup.find_all("source"):
                s_src = source.get("src")
                if s_src: 
                    direct_media_links.add(s_src)
            
            # Find iframe servers
            for iframe in soup.find_all("iframe"):
                i_src = iframe.get("src")
                if i_src: 
                    embed_player_urls.append(i_src)
            
            # Regex scan script blobs
            regex_matches = re.findall(r'(https?:?//[^\s"\']+\.(?:m3u8|mp4|webm)[^\s"\']*)', html_text)
            for match in regex_matches:
                direct_media_links.add(match)

            # Follow external mirrors to unpack hidden stream urls dynamically
            for embed_url in embed_player_urls:
                if embed_url.startswith("//"):
                    embed_url = "https:" + embed_url
                try:
                    player_res = requests.get(embed_url, headers=SESSION_HEADERS, timeout=5)
                    if player_res.status_code == 200:
                        inner_html = player_res.text
                        deep_matches = re.findall(r'(https?:?//[^\s"\']+\.(?:m3u8|mp4|webm)[^\s"\']*)', inner_html)
                        for file_node in deep_matches:
                            direct_media_links.add(file_node)
                except Exception:
                    continue
    except Exception as e:
        print(f"Extraction pipeline failure trace: {e}")

    streams = []
    idx = 1
    
    for raw_url in direct_media_links:
        if any(x in raw_url for x in ["favicon", "logo", "wp-content", "theme", "assets"]):
            continue
            
        normalized_url = raw_url
        if normalized_url.startswith("//"):
            normalized_url = "https:" + normalized_url
        elif not normalized_url.startswith("http"):
            continue
            
        if normalized_url.startswith("http://"):
            normalized_url = normalized_url.replace("http://", "https://")

        # Strip URL parameters safely via split to provide a direct filename string
        clean_media_url = normalized_url.split("?")[0]

        # STREMIO ENFORCEMENT: Enforces direct stream files mapping inside 'url' payload index
        streams.append({
            "name": f"⚡ VLC Stream {idx}",
            "title": "Direct Media Stream (HLS/MP4 Track)",
            "url": clean_media_url,
            "behaviorHints": {
                "notWebReady": True,
                "proxyHeaders": {
                    "request": {
                        "User-Agent": SESSION_HEADERS["User-Agent"],
                        "Referer": BASE_URL + "/"
                    }
                }
            }
        })
        idx += 1
        
    return {"streams": streams}
    
