"""
Türkiye ve dünya haber fetcher — 20+ RSS kaynağı + Google News + NewsAPI
keyword bazlı gerçek haber içeriği çeker.
"""
import time
import asyncio
from typing import List, Dict
from datetime import datetime

import httpx
import feedparser

from fetchers.utils import parse_rss_date, clean_html, stable_id


# ─── TÜRK HABER RSS KAYNAKLARI (statik) ─────────────────────────────────────
STATIC_RSS_FEEDS = {
    "Hürriyet":         "https://www.hurriyet.com.tr/rss/anasayfa",
    "Sabah":            "https://www.sabah.com.tr/rss/anasayfa.xml",
    "Milliyet":         "https://www.milliyet.com.tr/rss/rssNew/gundemRss.aspx",
    "Cumhuriyet":       "https://www.cumhuriyet.com.tr/rss/son_dakika.xml",
    "Sözcü":            "https://www.sozcu.com.tr/rss.xml",
    "Posta":            "https://www.posta.com.tr/rss/anasayfa.xml",
    "Star":             "https://www.star.com.tr/rss/rss.asp",
    "CNN Türk":         "https://www.cnnturk.com/feed/rss/all/news",
    "NTV":              "https://www.ntv.com.tr/son-dakika.rss",
    "Habertürk":        "https://www.haberturk.com/rss",
    "A Haber":          "https://www.ahaber.com.tr/rss/anasayfa.xml",
    "TRT Haber":        "https://www.trthaber.com/sondakika.rss",
    "AA (Anadolu)":     "https://www.aa.com.tr/tr/rss/default?cat=gunun-haberleri",
    "DHA":              "https://www.dha.com.tr/rss",
    "İHA":              "https://www.iha.com.tr/rss.asp",
    "Bianet":           "https://bianet.org/bianet/rss",
    "Gazete Duvar":     "https://www.gazeteduvar.com.tr/feed",
    "T24":              "https://t24.com.tr/rss",
    "Diken":            "https://www.diken.com.tr/feed/",
    "Medyascope":       "https://medyascope.tv/feed/",
    "Bloomberg HT":     "https://www.bloomberght.com/rss",
    "Dünya Gazetesi":   "https://www.dunya.com/rss.xml",
    "BBC Türkçe":       "https://feeds.bbci.co.uk/turkish/rss.xml",
    "DW Türkçe":        "https://rss.dw.com/rdf/rss-tur-all",
    "Reuters":          "https://feeds.reuters.com/reuters/topNews",
}

# Keyword bazlı dinamik kaynaklar
DYNAMIC_RSS_FEEDS = {
    "Google News TR": "https://news.google.com/rss/search?q={keyword}+when:30d&hl=tr&gl=TR&ceid=TR:tr",
    "Google News EN": "https://news.google.com/rss/search?q={keyword}+when:30d&hl=en&gl=TR&ceid=TR:en",
}

NEWSAPI_URL = "https://newsapi.org/v2/everything"


def _format_rss_entry(entry, source_name: str, keyword: str, domain: str = "") -> Dict:
    """Tek bir RSS entry'sini standart post formatına çevirir."""
    title   = clean_html(getattr(entry, "title", ""))
    summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
    text    = f"{title}\n\n{summary}".strip() if summary else title

    pub     = getattr(entry, "published", getattr(entry, "updated", ""))
    ts      = parse_rss_date(pub)
    link    = getattr(entry, "link", "#")
    entry_id = getattr(entry, "id", getattr(entry, "guid", link))

    if not domain and link.startswith("http"):
        try:
            domain = link.split("/")[2]
        except Exception:
            domain = "news"

    real_source = source_name
    real_domain = domain

    # Google News <source> tag'inden gerçek kaynağı çıkar
    if hasattr(entry, "source"):
        try:
            if isinstance(entry.source, dict):
                real_source = entry.source.get("title", real_source)
                s_url = entry.source.get("href", entry.source.get("url", ""))
            else:
                real_source = getattr(entry.source, "title", real_source)
                s_url = getattr(entry.source, "href", getattr(entry.source, "url", ""))
            if s_url and s_url.startswith("http"):
                try:
                    real_domain = s_url.split("/")[2]
                except Exception:
                    pass
        except Exception:
            pass

    favicon_domain = real_domain or "news.google.com"

    # Media
    media = None
    if hasattr(entry, "media_content") and entry.media_content:
        media = entry.media_content[0].get("url")
    elif hasattr(entry, "enclosures") and entry.enclosures:
        m = entry.enclosures[0]
        if m.get("type", "").startswith("image"):
            media = m.get("url") or m.get("href")

    return {
        "id":       stable_id("news", str(entry_id)),
        "platform": "news",
        "text":     text[:500],
        "author":   real_source,
        "username": real_source.lower().replace(" ", "_"),
        "avatar":   f"https://www.google.com/s2/favicons?domain={favicon_domain}&sz=64",
        "timestamp": ts,
        "url":      link,
        "likes":    0,
        "shares":   0,
        "keyword":  keyword,
        "media":    media,
        "source":   real_source,
        "is_demo":  False,
    }


async def _fetch_static_rss(url: str, source_name: str, keywords: List[str], client: httpx.AsyncClient) -> List[Dict]:
    """Statik bir RSS kaynağından çek, keyword ile filtrele."""
    posts = []
    try:
        resp = await client.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code != 200:
            return posts
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:30]:
            try:
                title   = clean_html(getattr(entry, "title", ""))
                summary = clean_html(getattr(entry, "summary", ""))
                full    = f"{title} {summary}".lower()
                matched_kw = next((kw for kw in keywords if kw.lower() in full), None)
                if matched_kw is None and keywords:
                    continue
                kw = matched_kw or keywords[0]
                posts.append(_format_rss_entry(entry, source_name, kw))
            except Exception:
                pass
    except Exception as e:
        print(f"[News] Statik RSS hatası ({source_name}): {e}")
    return posts


async def _fetch_rss(url: str, source_name: str, keyword: str, client: httpx.AsyncClient) -> List[Dict]:
    """Dinamik (keyword bazlı) RSS kaynağından çeker."""
    posts = []
    try:
        resp = await client.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:8]:
                try:
                    posts.append(_format_rss_entry(entry, source_name, keyword))
                except Exception:
                    pass
    except Exception as e:
        print(f"[News] RSS hatası ({source_name}): {e}")
    return posts


async def _fetch_newsapi(keyword: str, api_key: str, client: httpx.AsyncClient) -> List[Dict]:
    """NewsAPI'den çeker (opsiyonel, key varsa)."""
    if not api_key or api_key in ("", "your_newsapi_key_here"):
        return []
    posts = []
    try:
        resp = await client.get(NEWSAPI_URL, timeout=10, params={
            "q": keyword, "apiKey": api_key,
            "sortBy": "publishedAt", "pageSize": 10,
        })
        if resp.status_code == 200:
            for article in resp.json().get("articles", [])[:10]:
                pub = article.get("publishedAt", "")
                ts = parse_rss_date(pub)
                source = article.get("source", {}).get("name", "NewsAPI")
                url    = article.get("url", "#")
                domain = url.split("/")[2] if url.startswith("http") else "news"
                posts.append({
                    "id":       stable_id("newsapi", url),
                    "platform": "news",
                    "text":     f"{article.get('title','')}\n\n{article.get('description','')[:300]}".strip(),
                    "author":   source,
                    "username": source.lower().replace(" ", "_"),
                    "avatar":   f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
                    "timestamp": ts,
                    "url":      url,
                    "likes":    0, "shares": 0,
                    "keyword":  keyword,
                    "media":    article.get("urlToImage"),
                    "source":   source,
                    "is_demo":  False,
                })
    except Exception as e:
        print(f"[NewsAPI] Hata: {e}")
    return posts


def get_news_sources() -> List[str]:
    """Tüm haber kaynaklarının isimlerini döndürür."""
    return sorted(list(STATIC_RSS_FEEDS.keys()) + list(DYNAMIC_RSS_FEEDS.keys()))


async def fetch_news(keywords: List[str], api_key: str = "", custom_rss: List[str] = None) -> List[Dict]:
    """
    Ana haber fetch fonksiyonu.
    1) Keyword bazlı: Google News TR + EN RSS
    2) Statik Türk kaynakları
    3) NewsAPI (key varsa)
    4) Özel (Custom) RSS kaynakları
    """
    if custom_rss is None:
        custom_rss = []

    all_posts: List[Dict] = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        tasks = []

        # 1) Google News (keyword bazlı)
        for keyword in keywords[:5]:
            for feed_name, feed_url in DYNAMIC_RSS_FEEDS.items():
                url = feed_url.format(keyword=keyword.replace(" ", "+"))
                tasks.append(_fetch_rss(url, feed_name, keyword, client))

        # 2) Statik Türk kaynakları
        for source_name, url in STATIC_RSS_FEEDS.items():
            tasks.append(_fetch_static_rss(url, source_name, keywords[:5], client))

        # 3) NewsAPI
        for keyword in keywords[:3]:
            tasks.append(_fetch_newsapi(keyword, api_key, client))

        # 4) Özel RSS
        for rss_url in custom_rss:
            try:
                custom_name = rss_url.split("/")[2] if rss_url.startswith("http") else "Özel RSS"
            except Exception:
                custom_name = "Özel RSS"
            tasks.append(_fetch_static_rss(rss_url, custom_name, keywords[:5], client))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            print(f"[News] Task hatası: {result}")
            continue
        if not isinstance(result, list):
            continue
        for post in result:
            pid = post.get("id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_posts.append(post)

    # Timestamp 0 olanları en sona at, geri kalanları yeniden eskiye sırala
    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    print(f"[News] Toplam {len(all_posts)} haber ({len(STATIC_RSS_FEEDS)} statik + Google News + NewsAPI)")
    return all_posts[:80]
