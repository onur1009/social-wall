"""
LinkedIn fetcher — Google News RSS (site:linkedin.com) üzerinden çalışır.
"""
import asyncio
import re
from typing import List, Dict
import httpx
import feedparser

from fetchers.utils import parse_rss_date, clean_html, stable_id

GOOGLE_NEWS_LI_RSS = "https://news.google.com/rss/search?q=site:linkedin.com+{keyword}+when:30d&hl=tr&gl=TR&ceid=TR:tr"


async def _fetch_li_google_rss(keyword: str, client: httpx.AsyncClient) -> List[Dict]:
    posts = []
    url = GOOGLE_NEWS_LI_RSS.format(keyword=keyword.replace(" ", "+"))
    try:
        resp = await client.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:15]:
                try:
                    title   = clean_html(getattr(entry, "title", ""))
                    summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                    title = re.sub(r'\s*-\s*linkedin\.com\s*$', '', title, flags=re.IGNORECASE)

                    text    = f"{title}\n\n{summary}".strip() if summary else title
                    pub     = getattr(entry, "published", getattr(entry, "updated", ""))
                    ts      = parse_rss_date(pub)
                    link    = getattr(entry, "link", "#")
                    entry_id = getattr(entry, "id", getattr(entry, "guid", link))

                    # Gerçek kaynağı Google News <source> tag'inden çıkar
                    author = "LinkedIn Gönderisi"
                    avatar_domain = "linkedin.com"
                    if hasattr(entry, "source"):
                        try:
                            if isinstance(entry.source, dict):
                                author = entry.source.get("title", author)
                                s_url = entry.source.get("href", "")
                            else:
                                author = getattr(entry.source, "title", author)
                                s_url = getattr(entry.source, "href", "")
                            if s_url and s_url.startswith("http"):
                                avatar_domain = s_url.split("/")[2]
                        except Exception:
                            pass

                    posts.append({
                        "id":       stable_id("li", str(entry_id)),
                        "platform": "linkedin",
                        "text":     text[:500],
                        "author":   author,
                        "username": "linkedin",
                        "avatar":   f"https://www.google.com/s2/favicons?domain={avatar_domain}&sz=64",
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
