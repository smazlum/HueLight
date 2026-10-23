# 1. Analiz — Gereksinimler

## 1.1 Problem

Yeelight uygulaması yalnızca telefonda çalışıyor, bulut hesabı istiyor ve bilgisayardan hızlı kontrol sunmuyor. İstenen: ampulü **PC'den ve aynı ağdaki telefondan**, buluta gitmeden, yerel ağ üzerinden hızlıca yönetmek.

## 1.2 Cihaz bilgisi

| Özellik | Değer |
|---|---|
| Model | Yeelight Color Bulb 1S (`colorb`) |
| Bağlantı | Wi‑Fi 2.4 GHz (+ kurulum için Bluetooth) |
| Kontrol yolu | Yeelight **LAN Control** protokolü: TCP `55443`, satır sonlu JSON mesajlar |
| Keşif | SSDP benzeri multicast: `239.255.255.250:1982`, `ST: wifi_bulb` |
| Yetenekler | Aç/kapa, parlaklık 1–100, renk sıcaklığı 1700–6500 K, RGB, HSV, renk akışı (flow), zamanlı kapanma (cron), müzik modu |
| Kısıtlar | Ampul başına aynı anda en fazla 4 TCP bağlantısı, dakikada yaklaşık 60 komut |

Bluetooth kapsam dışı: protokolü kapalı ve şifreli, Wi‑Fi tüm ihtiyaçları karşılıyor.

## 1.3 Ön koşullar

> **Karar (23.10.2026):** Ampul sıfırlanmış durumda ve Yeelight uygulamasına bağlı değil. İlk kurulumu (ev Wi‑Fi'sine bağlama + LAN Control'ü açma) **bizim uygulama yapacak**, Yeelight uygulaması ve bulut hesabı hiç gerekmeyecek (F13).

1. Ampul sıfırlanmış olmalı: elektrik anahtarıyla 5 kez aç/kapa, ampul kendi Wi‑Fi ağını (`yeelink-light-colorb_miap…`) yayınlar
2. Ev Wi‑Fi'si **2.4 GHz** olmalı (ampul 5 GHz desteklemez)
3. Kurulum sırasında PC geçici olarak ampulün ağına bağlanır, sonra ev ağına döner
4. Telefondan kullanım için Windows Güvenlik Duvarı'nda uygulama portuna izin verilmeli

## 1.4 Kullanıcı senaryoları

| # | Senaryo |
|---|---|
| S1 | Uygulamayı açarım, ağdaki ampuller otomatik listelenir |
| S2 | Ampulü tek tıkla açar/kapatırım |
| S3 | Renk çarkından renk seçerim, ampul anında o renge geçer |
| S4 | Parlaklığı sürgüyle ayarlarım |
| S5 | Beyaz modunda sıcak ↔ soğuk tonu seçerim |
| S6 | Hazır sahnelerden birine ("Çalışma", "Film", "Gece") tıklarım |
| S7 | Mevcut ayarı kendi sahnem olarak kaydederim |
| S8 | Bir renk akışı başlatırım (örn. "Disko", "Mum ışığı", "Gün doğumu") |
| S9 | "30 dk sonra kapan" zamanlayıcısı kurarım |
| S10 | Telefonumun tarayıcısından aynı arayüze girerim |
| S11 | Ampulü telefondaki Yeelight uygulamasından değiştirirsem PC arayüzü de güncellenir |
| S12 | Yeni / sıfırlanmış ampulü uygulamadan ev ağıma eklerim |

## 1.5 Fonksiyonel gereksinimler

### MVP (ilk sürüm)

| Kod | Gereksinim | Senaryo |
|---|---|---|
| F1 | Otomatik keşif + elle IP ekleme | S1 |
| F2 | Ampule isim verme (cihazda saklanır, `set_name`) | S1 |
| F3 | Aç / kapat | S2 |
| F4 | RGB renk seçimi (renk çarkı + hazır renk paleti) | S3 |
| F5 | Parlaklık 1–100 | S4 |
| F6 | Renk sıcaklığı 1700–6500 K | S5 |
| F7 | Hazır sahneler (en az 4) | S6 |
| F8 | Kullanıcı sahnesi kaydet / sil | S7 |
| F9 | Renk akışları (en az 4 hazır akış) + durdurma | S8 |
| F10 | Zamanlı kapanma (dakika) | S9 |
| F11 | Ampulden gelen durum bildirimleriyle arayüzün canlı güncellenmesi | S11 |
| F12 | Telefona uygun (responsive) arayüz, ağdaki her cihazdan erişim | S10 |
| F13 | **İlk kurulum:** sıfırlanmış ampulü ev Wi‑Fi'sine bağlama ve LAN Control'ü açma (Yeelight uygulaması olmadan) | S12 |

### Sonraki sürüm (kapsam dışı, fikir havuzu)

- Müziğe göre ışık (mikrofon / sistem sesi)
- Ekran rengine göre ışık (ambilight)
- Gün doğumu alarmı, haftalık zamanlama
- Birden fazla ampulü gruplama
- PC açılışında otomatik başlama, sistem tepsisi ikonu
- Ana ekrana eklenebilir web uygulaması (PWA)

## 1.6 Fonksiyonel olmayan gereksinimler

| Kod | Gereksinim |
|---|---|
| N1 | Arayüzdeki değişiklik ampule **< 300 ms** içinde ulaşmalı |
| N2 | Sürgü/çark sürüklenirken komut hız sınırı aşılmamalı (kısma) |
| N3 | Tamamen yerel çalışmalı, internet ve bulut hesabı gerekmemeli |
| N4 | Kurulum: tek komutla başlatma (`baslat.bat` ya da `python -m ...`) |
| N5 | Arayüz Türkçe, açık/koyu tema |
| N6 | Ampul erişilemezse kullanıcıya anlaşılır hata gösterilmeli, uygulama çökmemeli |
| N7 | Ampul olmadan test edilebilmeli (simülatör) |
| N8 | Yalnızca yerel ağdan erişim. Varsayılan olarak dış ağa açık olmamalı |

## 1.7 Kabul kriterleri (MVP)

- Ampul LAN Control açıkken 5 sn içinde listede görünür
- F3–F10 arayüzden çalışır, gerçek ampulde gözle doğrulanır
- Telefon tarayıcısından aynı işlemler yapılabilir
- Ampul kapatılıp açıldığında (elektrik kesilmesi) uygulama yeniden bağlanır
- Otomatik testler simülatöre karşı geçer

## 1.8 Açık sorular

1. Evde başka Yeelight ampul var mı, olacak mı? (Gruplama önceliğini etkiler)
2. Hazır sahneler için tercihin var mı? Varsayılan: Çalışma (4000 K, %100), Okuma (3500 K, %80), Film (koyu mavi, %20), Gece (2700 K, %5)
