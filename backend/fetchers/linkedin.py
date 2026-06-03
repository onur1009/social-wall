"""
LinkedIn fetcher — Gerçek içerik çekme stratejisi:

LinkedIn API, üçüncü taraf arama/okuma erişimine kapalıdır.
(Sadece kendi hesabınızın verilerine OAuth ile erişilebilir.)

Alternatif gerçek içerik kaynakları:
1) LinkedIn Newsroom RSS / blog RSS
2) LinkedIn'in öne çıkan içeriklerini yayımlayan TR sitelerinden RSS
3) LinkedIn paylaşımlarını Twitter'da da yapan iş dünyası hesapları
4) İş dünyası / kariyer odaklı haber RSS'leri (ekonomi + iş haberleri)
"""
import time
import random
import asyncio
import re
from typing import List, Dict

import httpx
import feedparser


# LinkedIn bağlantılı gerçek içerik kaynakları
LINKEDIN_ADJACENT_RSS = {
    "LinkedIn Blog":       "https://www.linkedin.com/blog/feed",
    "LinkedIn Newsroom":   "https://news.linkedin.com/feed",
    "Harvard Business":    "https://hbr.org/feed",
    "Dünya Gazetesi":      "https://www.dunya.com/rss.xml",
    "Bloomberg HT":        "https://www.bloomberght.com/rss",
    "Ekonomist":           "https://www.ekonomist.com.tr/feed/",
    "Para Analiz":         "https://www.paraanaliz.com/feed",
    "İnsan Kaynakları":    "https://www.insankaynaklari.com/feed/",
    "Kariyer.net Blog":    "https://blog.kariyer.net/feed/",
    "Webrazzi":            "https://webrazzi.com/feed/",
    "ShiftDelete":         "https://shiftdelete.net/feed",
    "Donanimhaber":        "https://www.donanimhaber.com/rss.xml",
}

# LinkedIn'i aktif kullanan iş dünyası Twitter hesapları
LINKEDIN_TWITTER_ACCOUNTS = {
    "TÜSİAD":      "TUSIAD",
    "Deloitte TR":  "DeloitteTurkiye",
    "PwC Türkiye":  "PwCTurkiye",
    "TBMM":        "tbmm_iletisim",
}


def _clean(text: str) -> str:
    return re.sub(r'<[^>]+>', '', str(text or '')).strip()


def _parse_date(date_str: str) -> int:
    if not date_str:
        return int(time.time())
    try:
        import email.utils
        return int(email.utils.parsedate_to_datetime(str(date_str)).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(str(date_str).replace("Z", "+00:00")).timestamp())
    except Exception:
        pass
    return int(time.time())


async def _fetch_rss_feed(url: str, source_name: str, keywords: List[str],
                          client: httpx.AsyncClient) -> List[Dict]:
    """RSS çekip LinkedIn formatında döndür.
    Keyword eşleşmesi varsa o içerikler, yoksa en güncel 3 içerik."""
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
                kw   = matched or (keywords[0] if keywords else "")
                link = getattr(entry, "link", "#")
                pub  = getattr(entry, "published", getattr(entry, "updated", ""))
                ts   = _parse_date(pub)

                # Media
                media = None
                if hasattr(entry, "media_content") and entry.media_content:
                    media = entry.media_content[0].get("url")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    enc = entry.enclosures[0]
                    if enc.get("type", "").startswith("image"):
                        media = enc.get("url") or enc.get("href")

                domain = link.split("/")[2] if link.startswith("http") else "linkedin.com"
                post = {
                    "id":       f"li_{abs(hash(link)) % (10**12)}",
                    "platform": "linkedin",
                    "text":     f"{title}\n\n{summary}".strip()[:500],
                    "author":   source_name,
                    "username": source_name.lower().replace(" ", ""),
                    "avatar":   f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
                    "timestamp": ts,
                    "url":      link,
                    "likes":    0,
                    "shares":   0,
                    "keyword":  kw,
                    "media":    media,
                    "is_demo":  False,
                }
                if matched:
                    matched_posts.append(post)
                else:
                    fallback_posts.append(post)
            except Exception:
                pass
        # Önce keyword eşleşenleri al, yoksa en güncel 3 içeriği göster
        posts = matched_posts if matched_posts else fallback_posts[:3]
    except Exception:
        pass
    return posts


async def _fetch_twitter_as_linkedin(username: str, account_name: str,
                                      keyword: str, api_key: str) -> List[Dict]:
    """İş dünyası hesaplarının Twitter'daki paylaşımlarını LinkedIn içeriği olarak çek."""
    posts = []
    try:
        from concurrent.futures import ProcessPoolExecutor

        def _worker():
            from xpoz import XpozClient
            c = XpozClient(api_key=api_key, check_update=False)
            try:
                result = c.twitter.get_posts_by_author(username, limit=15)
                items  = list(getattr(result, 'items', None) or getattr(result, 'data', None) or [])
                out    = []
                for item in items:
                    try:
                        d = item.model_dump() if hasattr(item, 'model_dump') else dict(item.__dict__)
                        out.append(d)
                    except Exception:
                        pass
                return out
            finally:
                c.close()

        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor(max_workers=1) as pool:
            raw = await asyncio.wait_for(
                loop.run_in_executor(pool, _worker),
                timeout=20,
            )

        for d in raw:
            text = d.get("text", "")
            if keyword.lower() not in text.lower():
                continue
            post_id = str(d.get("id", ""))
            ts = int(time.time())
            created = d.get("created_at", "")
            if created:
                try:
                    from datetime import datetime
                    ts = int(datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pass
            posts.append({
                "id":       f"li_{username}_{post_id}",
                "platform": "linkedin",
                "text":     str(text)[:500],
                "author":   account_name,
                "username": f"linkedin.com/company/{username}",
                "avatar":   f"https://www.google.com/s2/favicons?domain=linkedin.com&sz=64",
                "timestamp": ts,
                "url":      f"https://twitter.com/{username}/status/{post_id}",
                "likes":    int(d.get("like_count", 0) or 0),
                "shares":   int(d.get("retweet_count", 0) or 0),
                "keyword":  keyword,
                "media":    None,
                "is_demo":  False,
            })
    except Exception:
        pass
    return posts


def _generate_demo_linkedin(keywords: List[str]) -> List[Dict]:
    companies = [
        ("Microsoft Türkiye",   "microsoft_tr",   "💼"),
        ("Google Türkiye",      "google_tr",      "🔍"),
        ("Türk Telekom",        "turktelekom",     "📡"),
        ("Arçelik",             "arcelik",         "🏭"),
        ("Getir",               "getir",           "🛵"),
    ]
    posts = []
    for keyword in keywords[:3]:
        for i, (name, slug, icon) in enumerate(companies[:3]):
            ts = int(time.time()) - random.randint(7200, 172800)
            posts.append({
                "id":       f"li_demo_{keyword}_{i}_{ts}",
                "platform": "linkedin",
                "text":     f"{icon} {name} olarak {keyword} alanındaki son gelişmeleri yakından takip ediyoruz. Bu önemli konuda ekibimizle çalışmalar yürütüyoruz. #LinkedInTR #{keyword.replace(' ', '')}",
                "author":   name,
                "username": f"linkedin.com/company/{slug}",
                "avatar":   f"https://www.google.com/s2/favicons?domain=linkedin.com&sz=64",
                "timestamp": ts,
                "url":      f"https://linkedin.com/company/{slug}",
                "likes":    random.randint(50, 3000),
                "shares":   random.randint(10, 300),
                "keyword":  keyword,
                "media":    None,
                "is_demo":  True,
            })
    return posts


async def fetch_linkedin(keywords: List[str], api_key: str = "") -> List[Dict]:
    """
    LinkedIn içerik fetcher — iş dünyası RSS kaynakları (keyword filtreli).
    Webrazzi, Bloomberg HT, ShiftDelete, Harvard Business, Dünya Gazetesi, vb.
    """
    all_posts: List[Dict] = []
    seen_ids: set = set()

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        tasks = [
            _fetch_rss_feed(url, source_name, keywords[:4], client)
            for source_name, url in LINKEDIN_ADJACENT_RSS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if not isinstance(result, list):
            continue
        for post in result:
            if post["id"] not in seen_ids:
                seen_ids.add(post["id"])
                all_posts.append(post)

    if not all_posts:
        print("[LinkedIn] Gerçek veri çekilemedi — demo data kullanılıyor")
        all_posts = _generate_demo_linkedin(keywords)

    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    print(f"[LinkedIn] Toplam {len(all_posts)} post")
    return all_posts[:30]
