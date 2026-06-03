"""
Instagram fetcher — xpoz SDK ProcessPoolExecutor ile gercek Instagram postlari ceker.
Field isimleri: id, username, full_name, caption, image_url, profile_pic_url, code_url, like_count
"""
import time
import random
import asyncio
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Dict, Optional


def _xpoz_instagram_worker(api_key: str, keywords: List[str]) -> List[tuple]:
    """ProcessPoolExecutor worker — xpoz Instagram search_posts."""
    results = []
    try:
        from xpoz import XpozClient
        client = XpozClient(api_key=api_key, check_update=False)
        for keyword in keywords[:3]:
            try:
                result = client.instagram.search_posts(keyword, limit=10)
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
                print(f"[Instagram/worker] '{keyword}' hata: {e}")
        client.close()
    except Exception as e:
        print(f"[Instagram/worker] Genel hata: {e}")
    return results


def _format_ig_post(post_dict: dict, keyword: str) -> Optional[Dict]:
    """
    xpoz Instagram post dict'ini kart formatına çevirir.
    Gerçek field isimleri: id, username, full_name, caption,
    image_url, video_url, profile_pic_url, code_url,
    like_count, comment_count
    """
    try:
        # Text
        caption = post_dict.get("caption", "")

        # Author
        username  = post_dict.get("username", "")
        full_name = post_dict.get("full_name", username)
        avatar    = post_dict.get("profile_pic_url", "")
        post_id   = str(post_dict.get("id", ""))

        # Timestamp
        ts = int(time.time())
        for ts_field in ("taken_at", "created_at", "timestamp"):
            val = post_dict.get(ts_field)
            if val:
                try:
                    ts = int(float(val))
                    break
                except Exception:
                    pass

        # Media — image_url önce, video_url fallback
        media = (
            post_dict.get("image_url")
            or post_dict.get("video_url")
            or post_dict.get("display_url")
            or post_dict.get("thumbnail_url")
        )
        if media:
            media = str(media)

        # URL — code_url veya shortcode
        code_url = post_dict.get("code_url", "")
        if code_url:
            url = str(code_url) if str(code_url).startswith("http") else f"https://instagram.com{code_url}"
        else:
            shortcode = post_dict.get("shortcode", post_id)
            url = f"https://instagram.com/p/{shortcode}" if shortcode else "https://instagram.com"

        likes    = int(post_dict.get("like_count",    0) or 0)
        comments = int(post_dict.get("comment_count", 0) or 0)

        return {
            "id":       f"ig_{post_id}",
            "platform": "instagram",
            "text":     str(caption)[:500] if caption else f"#{keyword}",
            "author":   str(full_name) or str(username),
            "username": f"@{username}" if username and not str(username).startswith("@") else str(username),
            "avatar":   str(avatar) if avatar else f"https://api.dicebear.com/7.x/lorelei/svg?seed={username}",
            "timestamp": ts,
            "url":      url,
            "likes":    likes,
            "shares":   comments,
            "keyword":  keyword,
            "media":    media,
            "is_demo":  False,
        }
    except Exception as e:
        print(f"[Instagram] Format hatası: {e}")
        return None


def _generate_demo_ig(keywords: List[str]) -> List[Dict]:
    authors = [
        ("Zeynep Aksoy",  "zeynepaksoy_ig"),
        ("Burak Çelik",   "burakcelik"),
        ("Selin Koç",     "selinkoc_photo"),
    ]
    posts = []
    for keyword in keywords[:3]:
        for i, (name, uname) in enumerate(authors):
            ts = int(time.time()) - random.randint(600, 10800)
            posts.append({
                "id": f"ig_demo_{keyword}_{i}_{ts}",
                "platform": "instagram",
                "text": f"#{keyword} ile ilgili harika bir an! #trending #{keyword}",
                "author": name,
                "username": f"@{uname}",
                "avatar": f"https://api.dicebear.com/7.x/lorelei/svg?seed={uname}",
                "timestamp": ts,
                "url": "https://instagram.com",
                "likes": random.randint(100, 2000),
                "shares": random.randint(5, 200),
                "keyword": keyword,
                "media": f"https://picsum.photos/seed/{keyword}{i}/400/400",
                "is_demo": True,
            })
    return posts


async def fetch_instagram(keywords: List[str], api_key: str = "") -> List[Dict]:
    """Ana Instagram fetch — timeout 60s (API ~12s sürüyor)."""
    all_posts = []

    if api_key:
        try:
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor(max_workers=1) as pool:
                raw_results = await asyncio.wait_for(
                    loop.run_in_executor(pool, _xpoz_instagram_worker, api_key, keywords),
                    timeout=60,   # 60s — Instagram ~12s/keyword
                )
            for keyword, post_dict in raw_results:
                formatted = _format_ig_post(post_dict, keyword)
                if formatted:
                    all_posts.append(formatted)
            print(f"[Instagram] xpoz'dan {len(all_posts)} post çekildi")
        except asyncio.TimeoutError:
            print("[Instagram] timeout (60s) — demo'ya geçiliyor")
        except FutureTimeoutError:
            print("[Instagram] ProcessPool timeout — demo'ya geçiliyor")
        except Exception as e:
            print(f"[Instagram] xpoz hata: {e} — demo'ya geçiliyor")

    if not all_posts:
        print("[Instagram] Demo data kullanılıyor")
        all_posts = _generate_demo_ig(keywords)

    print(f"[Instagram] Toplam {len(all_posts)} post")
    return all_posts
