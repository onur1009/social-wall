"""
Türkiye ve dünya haber fetcher — 20+ RSS kaynağı + Google News + NewsAPI
keyword bazlı gerçek haber içeriği çeker.
"""
import time
import random
import asyncio
import re
from typing import List, Dict
from datetime import datetime

import httpx
import feedparser


# ─── TÜRK HABER RSS KAYNAKLARI ──────────────────────────────────────────────
STATIC_RSS_FEEDS = {
    # Büyük gazeteler
    "Hürriyet":         "https://www.hurriyet.com.tr/rss/anasayfa",
    "Sabah":            "https://www.sabah.com.tr/rss/anasayfa.xml",
    "Milliyet":         "https://www.milliyet.com.tr/rss/rssNew/gundemRss.aspx",
    "Cumhuriyet":       "https://www.cumhuriyet.com.tr/rss/son_dakika.xml",
    "Sözcü":            "https://www.sozcu.com.tr/rss.xml",
    "Posta":            "https://www.posta.com.tr/rss/anasayfa.xml",
    "Star":             "https://www.star.com.tr/rss/rss.asp",
    # TV kanalları
    "CNN Türk":         "https://www.cnnturk.com/feed/rss/all/news",
    "NTV":              "https://www.ntv.com.tr/son-dakika.rss",
    "Habertürk":        "https://www.haberturk.com/rss",
    "A Haber":          "https://www.ahaber.com.tr/rss/anasayfa.xml",
    "TRT Haber":        "https://www.trthaber.com/sondakika.rss",
    "Fox TV Haber":     "https://www.foxhaber.com/rss.xml",
    "Show TV Haber":    "https://www.showtv.com.tr/rss.xml",
    # Haber ajansları
    "AA (Anadolu)":     "https://www.aa.com.tr/tr/rss/default?cat=gunun-haberleri",
    "DHA":              "https://www.dha.com.tr/rss",
    "İHA":              "https://www.iha.com.tr/rss.asp",
    # İnternete özgü / dijital
    "Bianet":           "https://bianet.org/bianet/rss",
    "Gazete Duvar":     "https://www.gazeteduvar.com.tr/feed",
    "T24":              "https://t24.com.tr/rss",
    "Diken":            "https://www.diken.com.tr/feed/",
    "Medyascope":       "https://medyascope.tv/feed/",
    # Ekonomi / iş dünyası
    "Bloomberg HT":     "https://www.bloomberght.com/rss",
    "Dünya Gazetesi":   "https://www.dunya.com/rss.xml",
    "Para Analiz":      "https://www.paraanaliz.com/feed",
    "Ekonomist":        "https://www.ekonomist.com.tr/feed/",
    # Uluslararası (İngilizce)
    "BBC Türkçe":       "https://feeds.bbci.co.uk/turkish/rss.xml",
    "DW Türkçe":        "https://rss.dw.com/rdf/rss-tur-all",
    "Reuters":          "https://feeds.reuters.com/reuters/topNews",
    "TechCrunch":       "https://techcrunch.com/feed/",
    # Keyword bazlı dinamik
    "Google News TR":   "https://news.google.com/rss/search?q={keyword}+when:30d&hl=tr&gl=TR&ceid=TR:tr",
    "Google News EN":   "https://news.google.com/rss/search?q={keyword}+when:30d&hl=en&gl=TR&ceid=TR:en",
}

NEWSAPI_URL = "https://newsapi.org/v2/everything"


def _parse_rss_date(date_str: str) -> int:
    if not date_str:
        return int(time.time())
    try:
        import email.utils
        return int(email.utils.parsedate_to_datetime(str(date_str)).timestamp())
    except Exception:
        pass
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"]:
        try:
            return int(datetime.strptime(str(date_str).strip(), fmt).timestamp())
        except Exception:
            pass
    return int(time.time())


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:400]


def _format_rss_entry(entry, source_name: str, keyword: str, domain: str = "") -> Dict:
    title   = _clean_html(getattr(entry, "title", ""))
    summary = _clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
    text    = f"{title}\n\n{summary}".strip() if summary else title

    pub     = getattr(entry, "published", getattr(entry, "updated", ""))
    ts      = _parse_rss_date(pub)
    link    = getattr(entry, "link", "#")
    entry_id = getattr(entry, "id", getattr(entry, "guid", link))

    if not domain and link.startswith("http"):
        try:
            domain = link.split("/")[2]
        except Exception:
            domain = "news"

    # Favicon domain
    favicon_domain = domain or "news.google.com"

    # Media
    media = None
    if hasattr(entry, "media_content") and entry.media_content:
        media = entry.media_content[0].get("url")
    elif hasattr(entry, "enclosures") and entry.enclosures:
        m = entry.enclosures[0]
        if m.get("type", "").startswith("image"):
            media = m.get("url") or m.get("href")

    return {
        "id":       f"news_{abs(hash(str(entry_id))) % (10**12)}",
        "platform": "news",
        "text":     text[:500],
        "author":   source_name,
        "username": source_name.lower().replace(" ", "_"),
        "avatar":   f"https://www.google.com/s2/favicons?domain={favicon_domain}&sz=64",
        "timestamp": ts,
        "url":      link,
        "likes":    0,
        "shares":   0,
        "keyword":  keyword,
        "media":    media,
        "source":   source_name,
        "is_demo":  False,
    }


async def _fetch_rss(url: str, source_name: str, keyword: str, client: httpx.AsyncClient) -> List[Dict]:
    posts = []
    try:
        resp = await client.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:6]:
                try:
                    posts.append(_format_rss_entry(entry, source_name, keyword))
                except Exception:
                    pass
    except Exception as e:
        pass  # sessizce atla
    return posts


def _matches_keyword(text: str, keyword: str) -> bool:
    """Haberde keyword geçiyor mu kontrol et (büyük/küçük harf duyarsız)."""
    text_lower    = text.lower()
    keyword_lower = keyword.lower()
    # Tam kelime eşleşimi veya içerme
    return keyword_lower in text_lower


async def _fetch_newsapi(keyword: str, api_key: str, client: httpx.AsyncClient) -> List[Dict]:
    if not api_key or api_key in ("", "your_newsapi_key_here"):
        return []
    posts = []
    try:
        resp = await client.get(NEWSAPI_URL, timeout=8, params={
            "q": keyword,
            "apiKey": api_key,
            "sortBy": "publishedAt",
            "pageSize": 10,
        })
        if resp.status_code == 200:
            for article in resp.json().get("articles", [])[:10]:
                ts = int(time.time())
                pub = article.get("publishedAt", "")
                if pub:
                    try:
                        ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        pass
                source = article.get("source", {}).get("name", "NewsAPI")
                url    = article.get("url", "#")
                domain = url.split("/")[2] if url.startswith("http") else "news"
                posts.append({
                    "id":       f"news_api_{abs(hash(url)) % (10**12)}",
                    "platform": "news",
                    "text":     f"{article.get('title','')}\n\n{article.get('description','')[:300]}".strip(),
                    "author":   source,
                    "username": source.lower().replace(" ", "_"),
                    "avatar":   f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
                    "timestamp": ts,
                    "url":      url,
                    "likes":    0,
                    "shares":   0,
                    "keyword":  keyword,
                    "media":    article.get("urlToImage"),
                    "source":   source,
                    "is_demo":  False,
                })
    except Exception as e:
        print(f"[NewsAPI] Hata: {e}")
    return posts


async def fetch_news(keywords: List[str], api_key: str = "") -> List[Dict]:
    """
    Ana haber fetch fonksiyonu.
    1) Keyword bazlı: Google News TR + EN RSS
    2) Statik Türk kaynakları: Hürriyet, Sabah, CNN Türk, NTV, AA, vb.
       — keyword ile filtrele
    3) NewsAPI (key varsa)
    """
    all_posts: List[Dict] = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        tasks = []

        # ── 1) Keyword bazlı Google News RSS ──────────────────────
        for keyword in keywords[:5]:
            for feed_name in ("Google News TR", "Google News EN"):
                url = STATIC_RSS_FEEDS[feed_name].format(keyword=keyword.replace(" ", "+"))
                tasks.append(_fetch_rss(url, feed_name.replace(" {keyword}", ""), keyword, client))

        # ── 2) Statik Türk kaynaklarından keyword filtreli haberler ──
        static_sources = {k: v for k, v in STATIC_RSS_FEEDS.items()
                          if "{keyword}" not in v}

        for source_name, url in static_sources.items():
            # Her keyword için ayrı task değil — kaynağı bir kez çek, keyword filtrele
            tasks.append(_fetch_static_rss(url, source_name, keywords[:5], client))

        # ── 3) NewsAPI ──────────────────────────────────────────────
        for keyword in keywords[:3]:
            tasks.append(_fetch_newsapi(keyword, api_key, client))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if not isinstance(result, list):
            continue
        for post in result:
            if post.get("id") not in seen_ids:
                seen_ids.add(post["id"])
                all_posts.append(post)

    # Zaman damgasına göre sırala
    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    print(f"[News] Toplam {len(all_posts)} haber ({len(static_sources)} statik kaynak + Google News + NewsAPI)")
    return all_posts[:80]  # max 80


async def _fetch_static_rss(url: str, source_name: str, keywords: List[str], client: httpx.AsyncClient) -> List[Dict]:
    """Statik bir RSS kaynağından çek, keyword ile filtrele."""
    posts = []
    try:
        resp = await client.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code != 200:
            return posts
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:30]:
            try:
                title   = _clean_html(getattr(entry, "title", ""))
                summary = _clean_html(getattr(entry, "summary", ""))
                full    = f"{title} {summary}".lower()
                # En az bir keyword eşleşmeli
                matched_kw = next((kw for kw in keywords if kw.lower() in full), None)
                if matched_kw is None and keywords:
                    continue  # keyword yoksa bu haberi alma
                kw = matched_kw or keywords[0]
                posts.append(_format_rss_entry(entry, source_name, kw))
            except Exception:
                pass
    except Exception:
        pass
    return posts


