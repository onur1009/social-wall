import os
import asyncio
from typing import List, Dict

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    openai = None

# Semaphore for rate limiting OpenAI API calls
_semaphore = asyncio.Semaphore(10)

async def _analyze_single_post(client, post: Dict) -> None:
    if post.get("sentiment"):
        return

    text = post.get("text", "")
    if not text.strip():
        post["sentiment"] = "neutral"
        return

    # Sadece ilk 300 karakteri analiz et (maliyet ve hiz acisindan)
    text_to_analyze = text[:300]

    try:
        async with _semaphore:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Sen profesyonel bir duygu analizi asistanısın. Sana verilen metnin genel duygu durumunu SADECE TEK BIR KELIME ile cevapla: 'olumlu', 'olumsuz' veya 'nötr'. Başka hiçbir şey yazma."},
                    {"role": "user", "content": f"Metin: {text_to_analyze}"}
                ],
                max_tokens=10,
                temperature=0.0
            )
            
            result = response.choices[0].message.content.strip().lower()
            
            if "olumlu" in result:
                post["sentiment"] = "positive"
            elif "olumsuz" in result:
                post["sentiment"] = "negative"
            else:
                post["sentiment"] = "neutral"
                
    except Exception as e:
        print(f"[Sentiment] Error for post {post.get('id')}: {e}")
        post["sentiment"] = "neutral"

async def analyze_sentiment_batch(posts: List[Dict]) -> None:
    """
    Verilen post listesindeki metinleri OpenAI kullanarak duygu analizine sokar.
    Sonuclari post["sentiment"] icerisine 'positive', 'negative' veya 'neutral' olarak yazar.
    API key yoksa hepsine 'neutral' atar.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if not api_key or not openai:
        for post in posts:
            if not post.get("sentiment"):
                post["sentiment"] = "neutral"
        return

    client = AsyncOpenAI(api_key=api_key)
    
    # Sadece sentiment atanmamis olanlari bul
    tasks = []
    for post in posts:
        if not post.get("sentiment"):
            tasks.append(_analyze_single_post(client, post))
            
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
