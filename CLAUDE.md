# HueLight

Yeelight akıllı ampulü yerel ağdan (bulutsuz) kontrol eden PC uygulaması: Python FastAPI backend + tarayıcı arayüzü, telefondan da aynı ağdan erişilir. Gerçek bir proje; test uygulaması değil, gerçek ampule bağlanır.

**Önce oku:** `docs/04-devir-notu.md` (kaldığımız yer, açık sorunlar), sonra gerekiyorsa `docs/01-analiz.md` ve `docs/03-mimari.md`.

## Çalışma şekli

- Aşamalar: Analist → Mockup → Mimar → Backend → Frontend → QA → Review. Her aşama sonunda çıktıyı göster, **onay alıp** sonrakine geç. Sıradaki aşama: **Frontend**.
- Dokümanlar `docs/` altında, Türkçe. Kullanıcıyla Türkçe konuş.
- Kararlar `docs/00-proje-plani.md` → "Kararlar ve notlar" tablosuna yazılır.
- Frontend: `frontend/index.html` ve `frontend/kurulum.html` geçici; tasarımları **baştan** yapılacak (onaylı yön: `mockup/index.html`). Kurulum sayfası internetsiz açılmalı (dış kaynak/CDN yok) — PC kurulum sırasında ampulün ağında.
- Doğrulama gerçek ampulle yapılır; `tools/sim_bulb.py` yalnızca otomatik testler için. Gerçek ampulde görülen davranış simülatöre de yansıtılır.

## Güvenlik

- `data/` asla commit edilmez (ampul token'ı, ev ağı adı, ağ kayıtları).
- Wi‑Fi şifreleri hiçbir yere yazılmaz/loglanmaz. Kayıtlı Wi‑Fi şifresini okuyan kod (`netsh … key=clear`) şirket güvenlik yazılımını tetikledi — devir notundaki 1. açık sorun; yerine şifre okumayan bir yöntem önerilir.
- Sunucu yalnızca özel ağ adreslerinden gelen isteklere cevap verir (`backend/security.py`).

## Komutlar

- Çalıştır: `baslat.bat` (ya da `.venv\Scripts\python.exe -m backend.main --port 8000`)
- Test: `.venv\Scripts\python.exe -m pytest -q`
- Ampulsüz kurulum denemesi: `.venv\Scripts\python.exe -m tools.demo_setup` → `http://localhost:8001/kurulum`
