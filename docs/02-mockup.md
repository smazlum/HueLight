# 2. Mockup — Arayüz Taslağı

Dosya: `mockup/index.html` (tıklanabilir, gerçek ampule bağlanmaz)

## Yerleşim

| Bölge | Masaüstü | Telefon (< 860 px) |
|---|---|---|
| Ampul listesi | Sol kenar çubuğu, durum noktası (yeşil = bağlı) | Üstte açılır liste |
| Önizleme | Ampulün o anki rengi/parlaklığıyla parlayan daire + parlaklık sürgüsü | Aynı, üstte |
| Kontroller | Sekmeler: Renk, Beyaz, Sahneler, Akışlar, Zamanlayıcı | Sekmeler alt gezinme çubuğunda |
| Aç/kapa | Sağ üstte büyük düğme | Aynı |

## Gereksinim eşlemesi

| Gereksinim | Mockup'taki karşılığı |
|---|---|
| F1 Keşif + elle IP | "Ağı tara", "IP ile ekle" penceresi |
| F3 Aç/kapa | ⏻ düğmesi |
| F4 RGB | Renk çarkı + 8 hızlı renk |
| F5 Parlaklık | Önizleme altındaki sürgü |
| F6 Renk sıcaklığı | Beyaz sekmesi: sürgü + 4 hazır ton |
| F7, F8 Sahneler | Sahne kartları, "Şu anki ayarı kaydet", kullanıcı sahnesinde ✕ |
| F9 Akışlar | 5 akış kartı, çalışan kart vurgulu, "Akışı durdur" |
| F10 Zamanlayıcı | 15 dk / 30 dk / 1 sa / 2 sa + özel süre, geri sayım, iptal |
| F11 Canlı durum | Önizleme ve listedeki renk noktası ampul durumunu yansıtır |
| F12 Telefon | Responsive yerleşim, kenar çubuğunda telefon adresi |
| N5 Tema | ◐ açık/koyu |
| N2 Kısma | Çark sürüklenirken en fazla ~7 komut/sn |

## Notlar

- Alttaki **komut günlüğü** yalnızca mockup'ta var. Hangi işlemin ampule hangi komutu göndereceğini gösterir ve Mimar aşamasında API tasarımına girdi olur. Gerçek uygulamada kaldırılacak veya ayarlara taşınacak.
- Zamanlayıcı ampulün kendi `cron` özelliğini kullanır, PC kapansa da çalışır.
