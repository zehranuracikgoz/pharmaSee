**Language:** [🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

**Live demo:** [pharma-see.vercel.app](https://pharma-see.vercel.app)
---

<a name="english"></a>

# PharmaSee — Pharma & Biotech Intelligence Platform

PharmaSee is a full-stack platform for tracking publicly traded pharmaceutical and biotech companies. It pulls real-time stock data via yfinance, syncs company listings from the FDA, and provides momentum analysis and multi-ticker comparison tools. Built with a FastAPI backend and a Next.js frontend deployed on Vercel and Render.

---

## Technologies

- **Python 3.11, FastAPI, SQLAlchemy, SQLite**
- **yfinance** — real-time and historical stock data
- **FDA Open API** — pharma company listings
- **Next.js 14, TypeScript, Tailwind CSS**
- **Recharts** — stock price charts
- **pytest, pytest-asyncio, httpx**
- **GitHub Actions** — CI/CD
- **Docker, Vercel, Render**

---

## Features

- Real-time stock info and price history for pharma/biotech tickers
- FDA-synced company database with search
- Momentum analysis around drug approval events
- Multi-ticker comparison with overlaid price charts
- FDA calendar — upcoming approval dates
- Watchlist for tracking selected companies
- 24h server-side cache to reduce API load
- Full async backend with SQLite

---

## The Process

The project started with an FDA sync endpoint that populates a local database with pharma company tickers. Stock data is fetched on demand via yfinance and cached for 24 hours. The momentum endpoint calculates price change around a given event date, enabling analysis of how FDA decisions affect stock performance. The frontend uses a Clinical White theme — clean and institutional — built with Tailwind and Recharts. CI runs backend tests and a Next.js production build in parallel on every push.

---

## Installation

```bash
# Backend
cd backend
pip install -r requirements.txt
# .env: DATABASE_URL, DEBUG

uvicorn app.main:app --reload
```

```bash
# Frontend
cd frontend
npm install
# .env.local: NEXT_PUBLIC_API_URL

npm run dev
```

### Tests

```bash
cd backend
python -m pytest tests/ -v
```

---

---

<a name="türkçe"></a>

# PharmaSee — Farma ve Biyoteknoloji İstihbarat Platformu

PharmaSee, halka açık ilaç ve biyoteknoloji şirketlerini takip etmek için geliştirilmiş bir platformdur. yfinance üzerinden gerçek zamanlı hisse verisi çeker, şirket listelerini FDA'dan senkronize eder ve momentum analizi ile çoklu ticker karşılaştırma araçları sunar. FastAPI backend ve Next.js frontend'den oluşur; Vercel ve Render üzerinde yayındadır.

---

## Teknolojiler

- **Python 3.11, FastAPI, SQLAlchemy, SQLite**
- **yfinance** — gerçek zamanlı ve geçmiş hisse verisi
- **FDA Open API** — farma şirket listeleri
- **Next.js 14, TypeScript, Tailwind CSS**
- **Recharts** — hisse fiyat grafikleri
- **pytest, pytest-asyncio, httpx**
- **GitHub Actions** — CI/CD
- **Docker, Vercel, Render**

---

## Özellikler

- Farma/biyoteknoloji tickerları için gerçek zamanlı hisse bilgisi ve fiyat geçmişi
- FDA senkronizasyonlu şirket veritabanı ve arama
- İlaç onay olayları etrafında momentum analizi
- Üst üste bindirilmiş fiyat grafikleriyle çoklu ticker karşılaştırması
- FDA takvimi — yaklaşan onay tarihleri
- Seçili şirketleri takip etmek için izleme listesi
- API yükünü azaltmak için 24 saatlik sunucu taraflı önbellekleme
- SQLite ile tam async backend

---

## Süreç

Proje, yerel bir veritabanını farma şirketi tickerlarıyla dolduran bir FDA senkronizasyon endpoint'iyle başladı. Hisse verileri yfinance aracılığıyla talep üzerine çekilir ve 24 saat önbelleklenir. Momentum endpoint'i, belirli bir olay tarihi etrafındaki fiyat değişimini hesaplar; bu sayede FDA kararlarının hisse performansına etkisi analiz edilebilir. Frontend, Tailwind ve Recharts ile oluşturulmuş kurumsal bir görünüm sunan Clinical White temasını kullanır. CI, her push'ta backend testlerini ve Next.js production build'ini paralel olarak çalıştırır.

---

## Kurulum

```bash
# Backend
cd backend
pip install -r requirements.txt
# .env: DATABASE_URL, DEBUG

uvicorn app.main:app --reload
```

```bash
# Frontend
cd frontend
npm install
# .env.local: NEXT_PUBLIC_API_URL

npm run dev
```

### Testler

```bash
cd backend
python -m pytest tests/ -v
```