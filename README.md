# 📡 Social Wall — Canlı Sosyal Medya Duvarı

Keyword bazlı, 1 dakikada bir otomatik güncellenen animasyonlu sosyal medya duvarı.

---

## 🚀 Hızlı Başlangıç

**`run.bat` dosyasına çift tıklayın** — gerisini otomatik yapar.

---

## 📋 Manuel Kurulum

```bash
# 1. Backend klasörüne geç
cd backend

# 2. Sanal ortam oluştur
python -m venv .venv
.venv\Scripts\activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. API'yi başlat
python main.py
```

Ardından `frontend/index.html` dosyasını tarayıcıda açın.

---

## ⚙️ Yapılandırma

`backend/.env` dosyasını düzenleyin:

```env
NEWS_API_KEY=your_key_here   # newsapi.org'dan ücretsiz alın
HOST=127.0.0.1
PORT=8765
```

---

## 🌐 Platform Desteği

| Platform  | Durum           | Kaynak         |
|-----------|-----------------|----------------|
| Twitter   | ✅ Aktif        | xpoz MCP API   |
| Instagram | ✅ Aktif        | xpoz MCP API   |
| Haberler  | ✅ Aktif        | Google News RSS + NewsAPI |
| Facebook  | 🔄 Demo         | API gelince aktif |
| LinkedIn  | 🔄 Demo         | API gelince aktif |

---

## 📁 Proje Yapısı

```
social-wall/
├── run.bat              ← Tek tıkla başlat
├── backend/
│   ├── main.py          ← FastAPI sunucusu
│   ├── cache.py         ← 60sn TTL önbellek
│   ├── .env             ← API anahtarları
│   ├── requirements.txt
│   └── fetchers/
│       ├── twitter.py   ← xpoz MCP
│       ├── instagram.py ← xpoz MCP
│       ├── news.py      ← RSS + NewsAPI
│       ├── facebook.py  ← Demo/Placeholder
│       └── linkedin.py  ← Demo/Placeholder
└── frontend/
    ├── index.html       ← Kontrol Paneli
    ├── wall.html        ← Canlı Duvar
    ├── css/
    │   ├── main.css     ← Global stiller
    │   └── wall.css     ← Kart animasyonları
    └── js/
        ├── app.js       ← Config paneli JS
        └── wall.js      ← Duvar mantığı
```

---

## 🎨 Özellikler

- **Dark Glassmorphism** tasarım
- **Masonry grid** düzeni
- **Platform bazlı renk kodlaması** (Twitter mavi, Instagram pembe, vb.)
- **Kart giriş animasyonları** (slide-in-top + highlight)
- **60 saniye countdown** ring
- **Yeni içerik butonu** — "▲ 5 yeni gönderi" gibi
- **Platform filtre chipleri** — topbar'da anlık filtre
- **Haber medyası** desteği (resimli kartlar)
- **Demo badge** — gerçek vs demo içerik ayırt edilir
- **Toast bildirimleri** — güncelleme durumu
- **Tam ekran modu** ⛶
