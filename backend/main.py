"""
Social Wall Backend — FastAPI
Twitter, News, Facebook, LinkedIn
"""
import asyncio
import json
import time
import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

load_dotenv()

from fetchers.twitter   import fetch_twitter
from fetchers.news      import fetch_news, get_news_sources
from fetchers.facebook  import fetch_facebook
from fetchers.linkedin  import fetch_linkedin
from cache import Cache
from sentiment import analyze_sentiment_batch

# Frontend static dosyalar
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="Social Wall API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend CSS / JS dosyalarını serve et
if FRONTEND_DIR.exists():
    app.mount("/css",    StaticFiles(directory=str(FRONTEND_DIR / "css")),    name="css")
    app.mount("/js",     StaticFiles(directory=str(FRONTEND_DIR / "js")),     name="js")
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

cache = Cache(ttl=55)  # 55 saniye TTL

XPOZ_API_KEY = os.getenv("XPOZ_API_KEY", "")
NEWS_API_KEY  = os.getenv("NEWS_API_KEY", "")

PLATFORM_FETCHERS = {
    "twitter":  lambda kw, crss: fetch_twitter(kw, XPOZ_API_KEY),
    "news":     lambda kw, crss: fetch_news(kw, NEWS_API_KEY, crss),
    "facebook": lambda kw, crss: fetch_facebook(kw, XPOZ_API_KEY),
    "linkedin": lambda kw, crss: fetch_linkedin(kw, XPOZ_API_KEY),
}

DEFAULT_PLATFORMS = "twitter,news,facebook,linkedin"

ACTIVE_QUERIES = {}

async def _background_refresher():
    """Arkaplanda son 5 dk içinde aktif olan sorguları her 25sn'de bir günceller."""
    while True:
        try:
            now = time.time()
            # 5 dakikadan eski sorguları temizle
            expired = [k for k, v in list(ACTIVE_QUERIES.items()) if now - v["last_requested"] > 300]
            for k in expired:
                del ACTIVE_QUERIES[k]

            for cache_key, data in list(ACTIVE_QUERIES.items()):
                if now - data["last_fetched"] > 25:
                    tasks = []
                    task_names = []
                    for plat in data["platforms"]:
                        if plat in PLATFORM_FETCHERS:
                            tasks.append(PLATFORM_FETCHERS[plat](data["keywords"], data["custom_rss"]))
                            task_names.append(plat)

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    all_posts = []
                    for name, res in zip(task_names, results):
                        if isinstance(res, list):
                            all_posts.extend(res)

                    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
                    top_posts = all_posts[:data["limit"]]
                    await analyze_sentiment_batch(top_posts)
                    cache.set(cache_key, top_posts)
                    data["last_fetched"] = time.time()

        except Exception as e:
            print(f"[Background Refresh] Error: {e}")
        
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_background_refresher())

@app.get("/")
async def root():
    """Ana sayfa — index.html döndür."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "Social Wall API running", "version": "2.0.0"}


@app.get("/wall")
@app.get("/wall.html")
async def wall_page():
    """Wall sayfası."""
    wall = FRONTEND_DIR / "wall.html"
    if wall.exists():
        return FileResponse(str(wall))
    return {"error": "wall.html bulunamadı", "frontend_dir": str(FRONTEND_DIR), "exists": FRONTEND_DIR.exists()}


@app.get("/api/sources")
async def api_sources():
    """Kullanılabilir haber kaynaklarının listesini döner."""
    return {"sources": get_news_sources()}


@app.get("/api/posts")
async def get_posts(
    keywords:  str = Query(..., description="Comma-separated keywords"),
    platforms: str = Query(DEFAULT_PLATFORMS, description="Comma-separated platforms"),
    custom_rss: Optional[str] = Query(None, description="Comma-separated custom RSS URLs"),
    limit:     int = Query(80, ge=1, le=150),
):
    keyword_list  = [k.strip() for k in keywords.split(",")  if k.strip()]
    platform_list = [p.strip().lower() for p in platforms.split(",") if p.strip()]
    custom_rss_list = [r.strip() for r in custom_rss.split(",")] if custom_rss else []

    cache_key = f"{','.join(sorted(keyword_list))}|{','.join(sorted(platform_list))}|{','.join(sorted(custom_rss_list))}"
    
    # Arka plan yenileyiciye kaydet
    if cache_key not in ACTIVE_QUERIES:
        ACTIVE_QUERIES[cache_key] = {
            "keywords": keyword_list,
            "platforms": platform_list,
            "custom_rss": custom_rss_list,
            "limit": limit,
            "last_requested": time.time(),
            "last_fetched": 0
        }
    else:
        ACTIVE_QUERIES[cache_key]["last_requested"] = time.time()

    cached = cache.get(cache_key)
    if cached:
        return JSONResponse(content={
            "posts": cached, "cached": True,
            "timestamp": int(time.time()), "count": len(cached),
        })

    tasks = []
    task_names = []
    for plat in platform_list:
        if plat in PLATFORM_FETCHERS:
            tasks.append(PLATFORM_FETCHERS[plat](keyword_list, custom_rss_list))
            task_names.append(plat)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_posts = []
    for name, result in zip(task_names, results):
        if isinstance(result, Exception):
            import traceback
            print(f"[{name}] ❌ Fetch hatası: {result}")
            traceback.print_exception(type(result), result, result.__traceback__)
            continue
        if isinstance(result, list):
            print(f"[{name}] ✅ {len(result)} post çekildi")
            all_posts.extend(result)

    # Zaman damgasına göre sırala (yeniden eskiye)
    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    all_posts = all_posts[:limit]

    await analyze_sentiment_batch(all_posts)

    cache.set(cache_key, all_posts)
    if cache_key in ACTIVE_QUERIES:
        ACTIVE_QUERIES[cache_key]["last_fetched"] = time.time()

    return JSONResponse(content={
        "posts":     all_posts,
        "cached":    False,
        "timestamp": int(time.time()),
        "count":     len(all_posts),
    })


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": int(time.time()),
        "xpoz_key_set": bool(XPOZ_API_KEY),
        "platforms": list(PLATFORM_FETCHERS.keys()),
    }


class TranslateRequest(BaseModel):
    text: str

@app.post("/api/translate")
async def translate_text(req: TranslateRequest):
    if not req.text.strip():
        return {"translated_text": ""}
    if not GoogleTranslator:
        return {"error": "Translator unavailable", "translated_text": req.text}
    
    try:
        # Uzun metinler engellenebilir (Google Translate sınırı genelde 5000 karakter)
        text_to_translate = req.text[:4900]
        translated = await asyncio.to_thread(
            lambda: GoogleTranslator(source='auto', target='tr').translate(text_to_translate)
        )
        return {"translated_text": translated}
    except Exception as e:
        return {"error": str(e), "translated_text": req.text}

if __name__ == "__main__":
    import sys
    import uvicorn
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    host = os.getenv("HOST", "0.0.0.0")   # Railway için 0.0.0.0
    port = int(os.getenv("PORT", "8765"))
    print(f"\n[Social Wall v2] API başlatılıyor: http://{host}:{port}")
    print(f"[Social Wall v2] xpoz key: {'✅ Set' if XPOZ_API_KEY else '❌ Eksik'}")
    print(f"[Social Wall v2] Frontend: {FRONTEND_DIR}")
    uvicorn.run("main:app", host=host, port=port, reload=False)
