"""
Fetcher'lar arası paylaşılan yardımcı fonksiyonlar.
Kod tekrarını önler, tek merkezi kaynak.
"""
import re
import time
import hashlib
from datetime import datetime


def parse_rss_date(date_str: str) -> int:
    """
    RSS tarih string'ini Unix timestamp'e çevirir.
    Çözümlenemezse 0 döndürür (post en sona düşer, üste çıkmaz).
    """
    if not date_str:
        return 0
    
    # 1) email.utils ile dene (RFC 2822 — en yaygın RSS formatı)
    try:
        import email.utils
        result = email.utils.parsedate_to_datetime(str(date_str))
        return int(result.timestamp())
    except Exception:
        pass

    # 2) Çeşitli strftime formatları
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]:
        try:
            return int(datetime.strptime(str(date_str).strip(), fmt).timestamp())
        except Exception:
            pass

    # 3) ISO format (Python 3.7+)
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        pass

    # Çözümlenemedi → 0 döndür (post en sona düşer)
    return 0


def clean_html(text: str) -> str:
    """HTML tag'larını temizler, boşlukları normalize eder."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]


def stable_id(prefix: str, seed: str) -> str:
    """
    Python restart'larında bile sabit kalacak ID üretir.
    hash() her restart'ta farklı sonuç verir, md5 vermez.
    """
    digest = hashlib.md5(str(seed).encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{prefix}_{digest}"
