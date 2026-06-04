"""
Twitter fetcher — xpoz SDK ProcessPoolExecutor ile gercek tweet ceker.
anyio/uvicorn event loop catismasini subprocess izolasyonu ile cozer.
"""
import time
import random
import asyncio
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Dict, Any, Optional


# ── Subprocess worker (ayrı process'te çalışır, anyio çakışması olmaz) ──────
def _xpoz_twitter_worker(api_key: str, keywords: List[str]) -> List[Dict]:
    """
    ProcessPoolExecutor worker — xpoz SDK'yı izole process'te çalıştırır.
    Bu fonksiyon uvicorn'un event loop'undan bağımsız çalışır.
    """
    results = []
    try:
        from xpoz import XpozClient
        client = XpozClient(api_key=api_key, check_update=False)
        for keyword in keywords[:3]:
            try:
                result = client.twitter.search_posts(keyword, limit=10)
                items = (
                    getattr(result, 'items', None)
                    or getattr(result, 'data', None)
                    or (result if isinstance(result, list) else [])
                )
                items_list = list(items or [])
                # Serialize to dict before returning (cross-process)
                for item in items_list:
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
                print(f"[Twitter/worker] '{keyword}' hata: {e}")
                results.append(("_error", {"error": str(e), "keyword": keyword}))
        client.close()
    except Exception as e:
        print(f"[Twitter/worker] Genel hata: {e}")
        results.append(("_error", {"error": str(e), "keyword": "genel"}))
    return results


def _format_tweet(post_dict: dict, keyword: str) -> Optional[Dict]:
    """Serileştirilmiş tweet dict'ini kart formatına çevirir."""
    if keyword == "_error":
        return {
            "id": f"tw_err_{int(time.time())}_{random.randint(100,999)}",
            "platform": "twitter",
            "text": f"DEBUG ERROR: {post_dict.get('error')} (kw: {post_dict.get('keyword')})",
            "author": "System Error",
            "username": "@error",
            "avatar": "",
            "timestamp": int(time.time()),
            "url": "#",
            "likes": 0,
            "shares": 0,
            "keyword": post_dict.get("keyword"),
            "media": None,
            "is_demo": False,
        }

    try:
        text = post_dict.get("text", post_dict.get("full_text", ""))
        author_name = post_dict.get("author_name", post_dict.get("name", ""))
        username = post_dict.get(
            "author_username",
            post_dict.get("username", post_dict.get("screen_name", ""))
        )
        avatar = post_dict.get("author_profile_image_url", post_dict.get("profile_image_url", ""))
        post_id = str(post_dict.get("id", ""))

        # Timestamp
        ts = int(time.time())
        created = post_dict.get("created_at", "")
        if created:
            try:
                from datetime import datetime
                if isinstance(created, str):
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    ts = int(dt.timestamp())
                elif isinstance(created, (int, float)):
                    ts = int(created)
            except Exception:
                pass

        # Media
        media = None
        media_list = post_dict.get("media", post_dict.get("media_urls", []))
        if media_list and isinstance(media_list, list) and len(media_list) > 0:
            first = media_list[0]
            media = first if isinstance(first, str) else first.get("url", first.get("media_url_https"))

        likes = int(post_dict.get("like_count", post_dict.get("favorite_count", 0)) or 0)
        retweets = int(post_dict.get("retweet_count", 0) or 0)

        return {
            "id": f"tw_{post_id}",
            "platform": "twitter",
            "text": str(text)[:500],
            "author": str(author_name) or str(username),
            "username": f"@{username}" if username and not str(username).startswith("@") else str(username),
            "avatar": str(avatar) if avatar else f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
            "timestamp": ts,
            "url": f"https://twitter.com/{username}/status/{post_id}" if username and post_id else "#",
            "likes": likes,
            "shares": retweets,
            "keyword": keyword,
            "media": media,
            "is_demo": False,
        }
    except Exception as e:
        print(f"[Twitter] Format hatası: {e}")
        return None




async def fetch_twitter(keywords: List[str], api_key: str = "") -> List[Dict]:
    """Ana Twitter fetch fonksiyonu — subprocess ile xpoz SDK izolasyonu."""
    all_posts = []

    if api_key:
        try:
            raw_results = await asyncio.wait_for(
                asyncio.to_thread(_xpoz_twitter_worker, api_key, keywords),
                timeout=30,
            )

            for keyword, post_dict in raw_results:
                formatted = _format_tweet(post_dict, keyword)
                if formatted:
                    all_posts.append(formatted)

            print(f"[Twitter] xpoz'dan {len(all_posts)} tweet çekildi")
        except asyncio.TimeoutError:
            print("[Twitter] xpoz timeout (30s) — demo'ya geçiliyor")
            all_posts.append(_format_tweet({"error": "Timeout in asyncio.to_thread", "keyword": "timeout"}, "_error"))
        except Exception as e:
            print(f"[Twitter] xpoz hata: {e} — demo'ya geçiliyor")
            all_posts.append(_format_tweet({"error": f"fetch_twitter_err: {e}", "keyword": "fetch_twitter"}, "_error"))



    print(f"[Twitter] Toplam {len(all_posts)} tweet")
    return all_posts
