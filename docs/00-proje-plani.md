# Yeelight Kontrol — Proje Planı

**Amaç:** Yeelight Color Bulb 1S (ve ileride diğer Yeelight ampulleri) için PC'de çalışan, aynı Wi‑Fi'deki telefondan da tarayıcı üzerinden kullanılabilen bir kontrol uygulaması.

**Tarih:** 23.10.2026

## Ortam tespiti

| Konu | Durum |
|---|---|
| Python | ✅ 3.14.3 kurulu, pip 25.3 mevcut, proje sanal ortamı `.venv` hazır |
| Git | ❌ Kurulu değil (sürüm kontrolü için önerilir, zorunlu değil) |
| PC ağı | Wi‑Fi `192.168.1.9` (ev ağı) + Ethernet/VPN (ikinci ağ kartı) |
| Ampul keşfi (SSDP) | ❌ Henüz cevap yok. Ampulde **LAN Control** açılmalı (bkz. Analiz → Ön koşullar) |

## Aşamalar

| # | Aşama | Çıktı | Bitiş kriteri |
|---|---|---|---|
| 1 | **Analist** | `docs/01-analiz.md`: kapsam, kullanıcı senaryoları, gereksinimler, kısıtlar | Kapsam (MVP / sonraki sürüm) onaylandı |
| 2 | **Mockup** | `mockup/index.html`: tıklanabilir arayüz taslağı (masaüstü + telefon) | Ekranlar ve akış onaylandı |
| 3 | **Mimar** | `docs/03-mimari.md`: bileşenler, teknoloji seçimi, API sözleşmesi, klasör yapısı | API ve teknoloji seçimi netleşti |
| 4 | **Backend** | `backend/`: ampul keşfi, TCP komut katmanı, REST + canlı durum API'si | Gerçek ampule komut gidiyor, birim testleri geçiyor |
| 5 | **Frontend** | `frontend/`: mockup'a uygun web arayüzü | Tüm MVP özellikleri arayüzden kullanılabiliyor |
| 6 | **QA** | `docs/06-test-raporu.md` + otomatik testler (sahte ampul simülatörüyle) | Test senaryoları geçti, hatalar kayıt altında |
| 7 | **Review** | `docs/07-review.md`: kod incelemesi, güvenlik, iyileştirme listesi | Kritik bulgu kalmadı, kullanım kılavuzu hazır |

## Kararlar ve notlar

| Tarih | Not |
|---|---|
| 23.10.2026 | İlk kurulumu (Wi‑Fi + LAN Control) uygulama yapar, Yeelight uygulaması gerekmez (F13). |
| 23.10.2026 | **Bağlantı ve uygulama erişimleri tamamlandıktan sonra**, `baslat.bat` ile açılan ilk sayfa ve kurulum sayfalarının (`/kurulum`) önyüz tasarımları **baştan yapılacak**. Şu anki sayfalar yalnızca işlevi doğrulamak için. |

## Çalışma şekli

- Her aşamanın sonunda kısa bir **onay noktası** var: çıktıyı sana gösteriyorum, onay gelince sonraki aşamaya geçiyorum.
- Ampule erişim olmadan da ilerleyebilmek için Backend aşamasında **sahte ampul simülatörü** yazılacak. Böylece QA ampulden bağımsız çalışır, gerçek ampulle ayrıca uçtan uca test yapılır.
- Tüm dokümanlar `docs/` altında Türkçe tutulur.

## Riskler

| Risk | Etki | Önlem |
|---|---|---|
| LAN Control kapalı / ampul farklı ağda | Bağlantı yok | Analizde ön koşul. Keşif başarısız olursa elle IP girme seçeneği olacak |
| Ampul komut hız sınırı (dakikada ~60 komut) | Sürgü hızlı kaydırılınca komut reddi | Backend'de komut kısma (throttle), müzik modu ileride |
| PC'de iki ağ arayüzü (Wi‑Fi + VPN) | Keşif yanlış arayüze gidebilir | Keşif tüm arayüzlerden yapılır, ayarlardan seçilebilir |
| Windows Güvenlik Duvarı | Telefon PC'ye erişemez | Kurulum adımlarında güvenlik duvarı izni anlatılır |
