"""
Facebook fetcher — Gerçek içerik çekme stratejisi:

Meta Graph API, 2018'den beri public sayfa içerikleri için
üçüncü taraf erişimine kapalıdır. Bu nedenle aşağıdaki alternatif
kaynaklardan Facebook-odaklı içerik çekiyoruz:

1) Büyük Türk Facebook sayfalarının RSS besleme URL'leri
   (bazı sayfalarda RSS.bridge üzerinden)
2) Facebook haberlerinin yayınlandığı türk haber sitelerinden
   keyword araması (news fetcher ile entegre)
3) Facebook Ads Library RSS (mümkünse)

NOT: Gerçek Facebook post verisi için resmi Meta Business API
     veya lisanslı bir scraping servisi gerekmektedir.
     Bu kısıtlama Meta'nın teknik engelidir, API key ile aşılamaz.
"""
import time
import random
import asyncio
import re
from typing import List, Dict

import httpx
import feedparser


# Büyük Türk haber sayfalarının Facebook RSS'leri (RSS Bridge üzerinden)
# RSS Bridge: https://rss-bridge.org/bridge01/
FACEBOOK_RSS_BRIDGES = [
    # Format: (sayfa_adı, sayfa_url, kaynak_adı)
    # NOT: rss-bridge.org public instance kullanılıyor
]

# Facebook paylaşımlarını takip eden kaynaklar (Twitter hesapları üzerinden)
# Bu sayfaların FB paylaşımları Twitter'da da oluyor
TURKISH_FB_PAGES_TWITTER = {
    "Hürriyet":      "hurriyet",
    "Sabah":         "sabah",
    "CNN Türk":      "cnnturk",
    "NTV":           "ntv",
    "Habertürk":     "haberturk",
    "TRT Haber":     "trthaber",
    "A Haber":       "ahaber",
    "Cumhuriyet":    "cumhuriyetgzt",
    "Sözcü":         "sozcu",
}

# Facebook RSS (bazı gruplar için hâlâ çalışan yollar)
FACEBOOK_RSS_FEEDS = {
    "Meta Newsroom":  "https://about.fb.com/feed/",
    "Facebook TR":    "https://www.facebook.com/FacebookTurkey",  # doğrudan RSS yok
}


def _clean(text: str) -> str:
    return re.sub(r'<[^>]+>', '', str(text or '')).strip()


async def _fetch_twitter_as_fb(username: str, page_name: str, keyword: str,
                                api_key: str, client: httpx.AsyncClient) -> List[Dict]:
    """
    Büyük FB sayfasının Twitter hesabından son paylaşımları çeker.
    keyword filtresi YOK — hepsi FB içeriği olarak yansıtılır
    (bu hesapların paylaşımları FB'de de oluyor).
    """
    posts = []
    try:
        from concurrent.futures import ProcessPoolExecutor

        def _worker():
            from xpoz import XpozClient
            c = XpozClient(api_key=api_key, check_update=False)
            try:
                result = c.twitter.search_posts(keyword, limit=5)
                items = list(getattr(result, 'items', None) or getattr(result, 'data', None) or [])
                serialized = []
                for item in items:
                    try:
                        d = item.model_dump() if hasattr(item, 'model_dump') else dict(item.__dict__)
                        serialized.append(d)
                    except Exception:
                        pass
                return serialized
            finally:
                c.close()

        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor(max_workers=1) as pool:
            raw = await asyncio.wait_for(
                loop.run_in_executor(pool, _worker),
                timeout=25,
            )

        for d in raw:
            text = d.get("text", "")
            if keyword.lower() not in text.lower():
                continue
            post_id = str(d.get("id", ""))
            author  = str(d.get("author_username", d.get("username", "user")))
            ts = int(time.time())
            created = d.get("created_at", d.get("created_at_date", ""))
            if created:
                try:
                    from datetime import datetime
                    ts = int(datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp())
                except Exception:
                    pass
            posts.append({
                "id":       f"fb_tw_{post_id}",
                "platform": "facebook",
                "text":     str(text)[:500],
                "author":   str(d.get("author_name", author)),
                "username": f"facebook.com/{author}",
                "avatar":   f"https://www.google.com/s2/favicons?domain=facebook.com&sz=64",
                "timestamp": ts,
                "url":      f"https://twitter.com/{author}/status/{post_id}",
                "likes":    int(d.get("like_count", 0) or 0),
                "shares":   int(d.get("retweet_count", 0) or 0),
                "keyword":  keyword,
                "media":    None,
                "is_demo":  False,
            })
    except Exception as e:
        print(f"[Facebook/tw_mirror] Hata: {e}")
    return posts


async def _fetch_meta_newsroom_rss(keyword: str, client: httpx.AsyncClient) -> List[Dict]:
    """Meta Newsroom blog RSS'inden haberler çeker."""
    posts = []
    try:
        resp = await client.get("https://about.fb.com/feed/", timeout=8,
                                headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:10]:
                title   = _clean(getattr(entry, "title", ""))
                summary = _clean(getattr(entry, "summary", ""))
                full    = f"{title} {summary}"
                if keyword.lower() not in full.lower():
                    continue
                link = getattr(entry, "link", "#")
                pub  = getattr(entry, "published", "")
                ts   = int(time.time())
                if pub:
                    try:
                        import email.utils
                        ts = int(email.utils.parsedate_to_datetime(pub).timestamp())
                    except Exception:
                        pass
                posts.append({
                    "id":       f"fb_meta_{abs(hash(link)) % (10**10)}",
                    "platform": "facebook",
                    "text":     f"{title}\n\n{summary}".strip()[:500],
                    "author":   "Meta Newsroom",
                    "username": "facebook.com/Meta",
                    "avatar":   "https://www.google.com/s2/favicons?domain=about.fb.com&sz=64",
                    "timestamp": ts,
                    "url":      link,
                    "likes":    0,
                    "shares":   0,
                    "keyword":  keyword,
                    "media":    None,
                    "is_demo":  False,
                })
    except Exception:
        pass
    return posts





# Facebook'ta aktif olan büyük Türk haber sayfalarının RSS'leri
FACEBOOK_PAGE_RSS = {
    "Hürriyet":       "https://www.hurriyet.com.tr/rss/anasayfa",
    "Sabah":          "https://www.sabah.com.tr/rss/anasayfa.xml",
    "CNN Türk":       "https://www.cnnturk.com/feed/rss/all/news",
    "NTV":            "https://www.ntv.com.tr/son-dakika.rss",
    "TRT Haber":      "https://www.trthaber.com/sondakika.rss",
    "A Haber":        "https://www.ahaber.com.tr/rss/anasayfa.xml",
    "Habertürk":      "https://www.haberturk.com/rss",
    "AA Haber":       "https://www.aa.com.tr/tr/rss/default?cat=gunun-haberleri",
    "Sözcü":          "https://www.sozcu.com.tr/rss.xml",
    "Cumhuriyet":     "https://www.cumhuriyet.com.tr/rss/son_dakika.xml",
    "Gazete Duvar":   "https://www.gazeteduvar.com.tr/feed",
    "T24":            "https://t24.com.tr/rss",
    "Bianet":         "https://bianet.org/bianet/rss",
    "Meta Newsroom":  "https://about.fb.com/feed/",
}


async def _fetch_fb_rss(url: str, source_name: str, keywords: List[str],
                        client: httpx.AsyncClient) -> List[Dict]:
    """RSS çekip Facebook formatında döndür.
    Keyword eşleşmesi varsa o haberler, yoksa en güncel 3 haber."""
    posts = []
    try:
        resp = await client.get(url, timeout=8,
                                headers={"User-Agent": "Mozilla/5.0"},
                                follow_redirects=True)
        if resp.status_code != 200:
            return posts
        feed = feedparser.parse(resp.text)
        matched_posts = []
        fallback_posts = []
        for entry in feed.entries[:30]:
            try:
                title   = _clean(getattr(entry, "title", ""))
                summary = _clean(getattr(entry, "summary", ""))
                full    = f"{title} {summary}".lower()
                matched = next((kw for kw in keywords if kw.lower() in full), None)
                link = getattr(entry, "link", "#")
                pub  = getattr(entry, "published", getattr(entry, "updated", ""))
                ts   = int(time.time())
                if pub:
                    try:
                        import email.utils
                        ts = int(email.utils.parsedate_to_datetime(pub).timestamp())
                    except Exception:
                        try:
                            from datetime import datetime
                            ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                        except Exception:
                            pass
                media = None
                if hasattr(entry, "media_content") and entry.media_content:
                    media = entry.media_content[0].get("url")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    enc = entry.enclosures[0]
                    if enc.get("type", "").startswith("image"):
                        media = enc.get("url") or enc.get("href")
                domain = link.split("/")[2] if link.startswith("http") else "facebook.com"
                post = {
                    "id":       f"fb_{abs(hash(link)) % (10**12)}",
                    "platform": "facebook",
                    "text":     f"{title}\n\n{summary}".strip()[:500],
                    "author":   source_name,
                    "username": f"facebook.com/{source_name.lower().replace(' ','')}",
                    "avatar":   f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
                    "timestamp": ts,
                    "url":      link,
                    "likes":    0,
                    "shares":   0,
                    "keyword":  matched or (keywords[0] if keywords else ""),
                    "media":    media,
                    "is_demo":  False,
                }
                if matched:
                    matched_posts.append(post)
            except Exception:
                pass
        posts = matched_posts
    except Exception:
        pass
    return posts


async def fetch_facebook(keywords: List[str], api_key: str = "") -> List[Dict]:
    """
    Facebook içerik fetcher.
    Büyük Türk haber sayfaları RSS (Facebook'ta da aktif olan kaynaklar) + 
    keyword bazlı xpoz Twitter arama (ek kaynak).
    """
    all_posts: List[Dict] = []
    seen_ids: set = set()

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        # Tüm FB sayfa RSS'lerini keyword filtreli çek
        tasks = [
            _fetch_fb_rss(url, source_name, keywords[:4], client)
            for source_name, url in FACEBOOK_PAGE_RSS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if not isinstance(result, list):
            continue
        for post in result:
            if post.get("id") not in seen_ids:
                seen_ids.add(post["id"])
                all_posts.append(post)

    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    print(f"[Facebook] Toplam {len(all_posts)} post")
    return all_posts[:30]
