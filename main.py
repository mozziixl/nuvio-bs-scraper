import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "community.brokensilenze.scraper",
        "version": "1.0.0",
        "name": "BrokenSilenze Live Scraper",
        "description": "Live custom web stream catalog scraper for Nuvio and Stremio.",
        "types": ["series"],
        "catalogs": [
            {
                "type": "series",
                "id": "brokensilenze_latest",
                "name": "BrokenSilenze Feed"
            }
        ],
        "resources": ["catalog", "stream"]
    }

# Unified Endpoint: This function now answers BOTH path configurations flawlessly
@app.get("/catalog/series/brokensilenze_latest.json")
@app.get("/catalog/series/brokensilenze_latest")
def get_catalog():
    metas = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get("https://brokensilenze.net", headers=headers, timeout=12)
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", limit=15)
        
        for idx, article in enumerate(articles):
            title_tag = article.find("h2")
            img_tag = article.find("img")
            link_tag = article.find("a")
            
            title = title_tag.text.strip() if title_tag else f"Latest Show {idx + 1}"
            img_url = img_tag["src"] if img_tag else "https://brokensilenze.netfavicon.ico"
            post_url = link_tag["href"] if link_tag else ""
            
            metas.append({
                "id": f"bs_show_{idx}",
                "type": "series",
                "name": title,
                "poster": img_url,
                "description": f"Stream links crawled live from web host nodes. Original: {post_url}"
            })
    except Exception as e:
        print(f"Background layout scrape error: {e}")
        
    return {"metas": metas}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
    
