"""
Reddit fetcher — xpoz SDK ProcessPoolExecutor ile gercek Reddit postlari ceker.
Dogru method: client.reddit.search_posts(keyword, limit=N)
Field isimleri: id, title, selftext, url, permalink, post_url,
                thumbnail, author_username, subreddit_name, score, num_comments
"""
import time
import random
import asyncio
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Dict, Optional


def _xpoz_reddit_worker(api_key: str, keywords: List[str]) -> List[tuple]:
    """ProcessPoolExecutor worker — xpoz Reddit search_posts."""
    results = []
    try:
        from xpoz import XpozClient
        client = XpozClient(api_key=api_key, check_update=False)
        for keyword in keywords[:3]:
            try:
                result = client.reddit.search_posts(keyword, limit=8)
                items = (
                    getattr(result, 'items', None)
                    or getattr(result, 'data', None)
                    or (result if isinstance(result, list) else [])
                )
                for item in list(items or []):
                    try:
                        if hasattr(item, 'model_dump'):
                            results.append((keyword, item.model_dump()))
                        elif hasattr(item, '__dict__'):
                            results.append((keyword, dict(item.__dict__)))
                        elif isinstance(item, dict):
                            results.append((keyword, item))
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Reddit/worker] '{keyword}' hata: {e}")
        client.close()
    except Exception as e:
        print(f"[Reddit/worker] Genel hata: {e}")
    return results


def _format_reddit_post(post_dict: dict, keyword: str) -> Optional[Dict]:
    """
    xpoz Reddit post dict'ini kart formatına çevirir.
    Gerçek field isimleri: id, title, selftext, url, permalink,
    post_url, thumbnail, author_username, subreddit_name,
    score, upvotes, comments_count, created_at_timestamp
    """
    try:
        title    = post_dict.get("title", "")
        selftext = post_dict.get("selftext", "")
        text     = f"{title}\n\n{selftext}".strip() if selftext and selftext not in ("[removed]", "[deleted]") else title

        author    = post_dict.get("author_username", post_dict.get("author", "redditor"))
        subreddit = post_dict.get("subreddit_name", post_dict.get("subreddit", ""))
        post_id   = str(post_dict.get("id", ""))

        # Timestamp
        ts = int(time.time())
        ts_val = post_dict.get("created_at_timestamp") or post_dict.get("created_at") or post_dict.get("created_utc")
        if ts_val:
            try:
                ts = int(float(ts_val))
            except Exception:
                pass

        # Media — thumbnail varsa kullan
        media = None
        thumb = post_dict.get("thumbnail", "")
        if thumb and str(thumb).startswith("http"):
            media = str(thumb)

        # URL
        permalink = post_dict.get("permalink", post_dict.get("post_url", post_dict.get("url", "")))
        if permalink and not str(permalink).startswith("http"):
            permalink = f"https://reddit.com{permalink}"
        if not permalink:
            permalink = f"https://reddit.com"

        score        = int(post_dict.get("score", post_dict.get("upvotes", 0)) or 0)
        num_comments = int(post_dict.get("comments_count", post_dict.get("num_comments", 0)) or 0)

        return {
            "id":       f"rd_{post_id}",
            "platform": "reddit",
            "text":     str(text)[:500],
            "author":   str(author),
            "username": f"u/{author}",
            "subtitle": f"r/{subreddit}" if subreddit else "",
            "avatar":   f"https://api.dicebear.com/7.x/bottts/svg?seed={author}",
            "timestamp": ts,
            "url":      permalink,
            "likes":    score,
            "shares":   num_comments,
            "keyword":  keyword,
            "media":    media,
            "is_demo":  False,
        }
    except Exception as e:
        print(f"[Reddit] Format hatası: {e}")
        return None


def _generate_demo_reddit(keywords: List[str]) -> List[Dict]:
    subreddits = ["technology", "worldnews", "science", "turkish", "programming"]
    authors    = ["techguru42", "newshunter", "datanerd", "curious_mind"]
    posts = []
    for keyword in keywords[:3]:
        for i in range(3):
            ts   = int(time.time()) - random.randint(1800, 86400)
            sub  = random.choice(subreddits)
            auth = random.choice(authors)
            posts.append({
                "id": f"rd_demo_{keyword}_{i}_{ts}",
                "platform": "reddit",
                "text": f"{keyword} hakkında ilginç bir tartışma toplulukta büyük ilgi görüyor.",
                "author": auth,
                "username": f"u/{auth}",
                "subtitle": f"r/{sub}",
                "avatar": f"https://api.dicebear.com/7.x/bottts/svg?seed={auth}",
                "timestamp": ts,
                "url": f"https://reddit.com/r/{sub}",
                "likes":  random.randint(50, 10000),
                "shares": random.randint(10, 300),
                "keyword": keyword,
                "media":   None,
                "is_demo": True,
            })
    return posts


async def fetch_reddit(keywords: List[str], api_key: str = "") -> List[Dict]:
    """Ana Reddit fetch fonksiyonu."""
    all_posts = []

    if api_key:
        try:
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor(max_workers=1) as pool:
                raw_results = await asyncio.wait_for(
                    loop.run_in_executor(pool, _xpoz_reddit_worker, api_key, keywords),
                    timeout=45,
                )
            for keyword, post_dict in raw_results:
                formatted = _format_reddit_post(post_dict, keyword)
                if formatted:
                    all_posts.append(formatted)
            print(f"[Reddit] xpoz'dan {len(all_posts)} post çekildi")
        except asyncio.TimeoutError:
            print("[Reddit] timeout (45s) — demo'ya geçiliyor")
        except FutureTimeoutError:
            print("[Reddit] ProcessPool timeout — demo'ya geçiliyor")
        except Exception as e:
            print(f"[Reddit] xpoz hata: {e} — demo'ya geçiliyor")

    if not all_posts:
        print("[Reddit] Demo data kullanılıyor")
        all_posts = _generate_demo_reddit(keywords)

    print(f"[Reddit] Toplam {len(all_posts)} post")
    return all_posts
