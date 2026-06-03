"""
TikTok fetcher — xpoz SDK ProcessPoolExecutor ile gercek TikTok videolari ceker.
Dogru method: client.tiktok.search_posts(keyword, limit=N)
Field isimleri: id, username, nickname, description, video_thumbnail,
                like_count, comment_count, play_count, collect_count,
                forward_count, download_count
"""
import time
import random
import asyncio
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Dict, Optional


def _xpoz_tiktok_worker(api_key: str, keywords: List[str]) -> List[tuple]:
    """ProcessPoolExecutor worker — xpoz TikTok search_posts."""
    results = []
    try:
        from xpoz import XpozClient
        client = XpozClient(api_key=api_key, check_update=False)
        for keyword in keywords[:3]:
            try:
                result = client.tiktok.search_posts(keyword, limit=8)
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
                print(f"[TikTok/worker] '{keyword}' hata: {e}")
        client.close()
    except Exception as e:
        print(f"[TikTok/worker] Genel hata: {e}")
    return results


def _format_tiktok_post(post_dict: dict, keyword: str) -> Optional[Dict]:
    """
    xpoz TikTok post dict'ini kart formatına çevirir.
    Gerçek field isimleri: id, username, nickname, description,
    video_thumbnail (None olabilir), video_url,
    like_count, comment_count, play_count, forward_count,
    collect_count, download_count, created_at_timestamp
    """
    try:
        desc     = post_dict.get("description", post_dict.get("desc", ""))
        username = post_dict.get("username", "")
        nickname = post_dict.get("nickname", username)
        post_id  = str(post_dict.get("id", ""))

        # Avatar — TikTok API'de doğrudan avatar URL yok, dicebear kullan
        avatar = f"https://api.dicebear.com/7.x/fun-emoji/svg?seed={username}"

        # Timestamp
        ts = int(time.time())
        ts_val = post_dict.get("created_at_timestamp") or post_dict.get("create_time") or post_dict.get("created_at")
        if ts_val:
            try:
                ts = int(float(ts_val))
            except Exception:
                pass

        # Media — video_thumbnail genellikle None, video_url'yi thumbnail olarak kullan
        media = None
        thumb = post_dict.get("video_thumbnail")
        if thumb and isinstance(thumb, str) and thumb.startswith("http"):
            media = thumb
        elif thumb and isinstance(thumb, dict):
            urls = thumb.get("url_list", [])
            media = urls[0] if urls else None
        # video_thumbnail None ise video_url'yi başlat (poster gibi)
        if not media:
            video_url = post_dict.get("video_url", "")
            if video_url and str(video_url).startswith("http"):
                # video_url'yi doğrudan media olarak göster
                media = str(video_url)

        # Stats
        plays    = int(post_dict.get("play_count",    0) or 0)
        likes    = int(post_dict.get("like_count",    0) or 0)
        comments = int(post_dict.get("comment_count", 0) or 0)
        shares   = int(post_dict.get("forward_count", post_dict.get("share_count", 0)) or 0)

        url = f"https://www.tiktok.com/@{username}/video/{post_id}" if username and post_id else "https://tiktok.com"

        return {
            "id":       f"tt_{post_id}",
            "platform": "tiktok",
            "text":     str(desc)[:500] if desc else f"#{keyword}",
            "author":   str(nickname) or str(username),
            "username": f"@{username}" if username and not str(username).startswith("@") else str(username),
            "avatar":   avatar,
            "timestamp": ts,
            "url":      url,
            "likes":    likes,
            "shares":   shares,
            "plays":    plays,
            "keyword":  keyword,
            "media":    media,
            "is_demo":  False,
        }
    except Exception as e:
        print(f"[TikTok] Format hatası: {e}")
        return None


def _generate_demo_tiktok(keywords: List[str]) -> List[Dict]:
    authors = [
        ("TechCreator",  "techcreator_tr"),
        ("ViralContent", "viralcontent"),
        ("TrendMaker",   "trendmaker"),
    ]
    posts = []
    for keyword in keywords[:3]:
        for i, (name, uname) in enumerate(authors):
            ts    = int(time.time()) - random.randint(900, 28800)
            plays = random.randint(10000, 2000000)
            posts.append({
                "id": f"tt_demo_{keyword}_{i}_{ts}",
                "platform": "tiktok",
                "text": f"#{keyword} trending! Bu içerik çok konuşuluyor. #{keyword.replace(' ','')} #viral #fyp",
                "author": name,
                "username": f"@{uname}",
                "avatar": f"https://api.dicebear.com/7.x/fun-emoji/svg?seed={uname}",
                "timestamp": ts,
                "url": f"https://tiktok.com/@{uname}",
                "likes":  random.randint(500, 50000),
                "shares": random.randint(100, 10000),
                "plays":  plays,
                "keyword": keyword,
                "media":  f"https://picsum.photos/seed/tiktok{keyword}{i}/400/711",
                "is_demo": True,
            })
    return posts


async def fetch_tiktok(keywords: List[str], api_key: str = "") -> List[Dict]:
    """Ana TikTok fetch fonksiyonu."""
    all_posts = []

    if api_key:
        try:
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor(max_workers=1) as pool:
                raw_results = await asyncio.wait_for(
                    loop.run_in_executor(pool, _xpoz_tiktok_worker, api_key, keywords),
                    timeout=45,
                )
            for keyword, post_dict in raw_results:
                formatted = _format_tiktok_post(post_dict, keyword)
                if formatted:
                    all_posts.append(formatted)
            print(f"[TikTok] xpoz'dan {len(all_posts)} video çekildi")
        except asyncio.TimeoutError:
            print("[TikTok] timeout (45s) — demo'ya geçiliyor")
        except FutureTimeoutError:
            print("[TikTok] ProcessPool timeout — demo'ya geçiliyor")
        except Exception as e:
            print(f"[TikTok] xpoz hata: {e} — demo'ya geçiliyor")

    if not all_posts:
        print("[TikTok] Demo data kullanılıyor")
        all_posts = _generate_demo_tiktok(keywords)

    print(f"[TikTok] Toplam {len(all_posts)} video")
    return all_posts
