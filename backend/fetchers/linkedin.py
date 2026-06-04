"""
LinkedIn fetcher — Google News RSS (site:linkedin.com) üzerinden çalışır.
Geçmişe dönük (30 gün) ve alakalı gönderileri çeker.
"""
import time
import asyncio
import re
from typing import List, Dict
from datetime import datetime
import httpx
import feedparser

GOOGLE_NEWS_LI_RSS = "https://news.google.com/rss/search?q=site:linkedin.com+{keyword}+when:30d&hl=tr&gl=TR&ceid=TR:tr"


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


async def _fetch_li_google_rss(keyword: str, client: httpx.AsyncClient) -> List[Dict]:
    posts = []
    url = GOOGLE_NEWS_LI_RSS.format(keyword=keyword.replace(" ", "+"))
    try:
        resp = await client.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:15]:
                try:
                    title   = _clean_html(getattr(entry, "title", ""))
                    summary = _clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                    
                    # Başlıktaki "- linkedin.com" ekini temizle
                    title = re.sub(r'\s*-\s*linkedin\.com\s*$', '', title, flags=re.IGNORECASE)
                    
                    text    = f"{title}\n\n{summary}".strip() if summary else title
                    pub     = getattr(entry, "published", getattr(entry, "updated", ""))
                    ts      = _parse_rss_date(pub)
                    link    = getattr(entry, "link", "#")
                    entry_id = getattr(entry, "id", getattr(entry, "guid", link))

                    posts.append({
                        "id":       f"li_{abs(hash(str(entry_id))) % (10**12)}",
                        "platform": "linkedin",
                        "text":     text[:500],
                        "author":   "LinkedIn Gönderisi",
                        "username": "linkedin",
                        "avatar":   "https://www.google.com/s2/favicons?domain=linkedin.com&sz=64",
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
    except Exception as e:
        print(f"[LinkedIn] RSS çekme hatası: {e}")
    return posts


async def fetch_linkedin(keywords: List[str], api_key: str = "") -> List[Dict]:
    """Ana LinkedIn fetch fonksiyonu (Google News tabanlı)."""
    all_posts: List[Dict] = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        tasks = [_fetch_li_google_rss(kw, client) for kw in keywords[:4]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if not isinstance(result, list):
            continue
        for post in result:
            if post["id"] not in seen_ids:
                seen_ids.add(post["id"])
                all_posts.append(post)

    all_posts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    print(f"[LinkedIn] Toplam {len(all_posts)} post")
    return all_posts[:30]
