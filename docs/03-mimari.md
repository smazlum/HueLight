# 3. Mimari

## 3.1 Genel bakış

```
 ┌────────────── Tarayıcı (PC / telefon) ──────────────┐
 │  frontend/  (HTML + CSS + JS, derleme adımı yok)     │
 └───────┬───────────────────────────────▲─────────────┘
         │ REST (komutlar)               │ WebSocket (canlı durum)
 ┌───────▼───────────────────────────────┴─────────────┐
 │  backend/  FastAPI + uvicorn  (PC, port 8000)        │
 │                                                      │
 │  api/  ──►  DeviceManager  ──►  Bulb (her ampul 1)   │
 │               │    ▲              │  CommandQueue    │
 │      Discovery│    │ store.py     │  (kısma/birleş.) │
 └───────────────┼────┼──────────────┼──────────────────┘
       UDP multicast  data/config.json  TCP 55443 (JSON satırları)
                 ▼                    ▼
        ┌──────────────── Yeelight ampul(ler) ────────────────┐
        └─────────────────────────────────────────────────────┘
```

- **Tek süreç:** Backend hem API'yi hem arayüz dosyalarını sunar. Kullanıcı yalnızca `baslat.bat` çalıştırır.
- **Ampule tek kapı:** Her ampul için backend'de tek bir kalıcı TCP bağlantısı var. Kaç tarayıcı açık olursa olsun ampul tarafında 1 bağlantı kullanılır (ampulün sınırı 4).
- **Durumun tek kaynağı ampuldür:** Ampul her değişiklikte `props` bildirimi gönderir. Backend bunu WebSocket ile tüm açık arayüzlere iletir (F11). Telefondaki Yeelight uygulamasından yapılan değişiklikler de böylece görünür.

## 3.2 Teknoloji seçimi

| Katman | Seçim | Gerekçe |
|---|---|---|
| Dil | Python 3.14 (kurulu) | Ek kurulum yok, asyncio ile ağ işleri kolay |
| Web çatısı | FastAPI 0.161 + uvicorn 0.54 | REST + WebSocket tek pakette, otomatik API dokümanı (`/docs`), Pydantic doğrulama |
| Ampul protokolü | **Kendi yazdığımız** asyncio istemcisi | Hazır `yeelight` kütüphanesi senkron çalışıyor ve bildirimleri ayrı thread'de dinliyor. Protokol küçük (≈15 komut), kendimiz yazınca kısma, yeniden bağlanma ve test kontrolü bizde olur |
| Arayüz | Vanilla HTML/CSS/JS (ES modülleri) | Mockup doğrudan temel alınır, Node.js ve derleme adımı gerekmez |
| Kalıcı veri | `data/config.json` | Birkaç ampul ve sahne için veritabanı gereksiz |
| Test | pytest 9 + pytest-asyncio + httpx | Simülatöre karşı birim ve entegrasyon testleri |

Teknoloji denemesi: `.venv` oluşturuldu, paketler Python 3.14'te sorunsuz kuruldu (23.10.2026).

## 3.3 Bileşenler

| Modül | Sorumluluk |
|---|---|
| `yeelight/protocol.py` | Komut JSON'u üretme, cevap/bildirim ayrıştırma, renk dönüşümleri (hex ↔ int, ct sınırları), akış (flow) ifadesi oluşturma |
| `yeelight/discovery.py` | Tüm IPv4 arayüzlerinden SSDP `M-SEARCH`, gelen ilanları (`NOTIFY`) dinleme, ampul bilgisini (`id`, `model`, `ip`, `name`, `support`) ayrıştırma |
| `yeelight/bulb.py` | Ampul başına bağlantı: istek–cevap eşleştirme (`id`), bildirim işleme, yeniden bağlanma (1→2→4→…→30 sn), zaman aşımı (3 sn) |
| `yeelight/queue.py` | **CommandQueue:** hız sınırı ve sürgü komutlarını birleştirme (bkz. 3.5) |
| `yeelight/presets.py` | Hazır sahneler ve renk akışları |
| `manager.py` | Ampul kaydı (keşfedilen + elle eklenen), durum önbelleği, olayları WebSocket aboneliklerine dağıtma |
| `store.py` | `data/config.json` okuma/yazma (atomik yazma: geçici dosya + yeniden adlandırma) |
| `api/routes.py` | REST uçları |
| `api/ws.py` | WebSocket `/ws` |
| `security.py` | Yalnızca yerel ağ (özel IP) isteklerini kabul eden ara katman |
| `tools/sim_bulb.py` | Sahte ampul: TCP 55443 benzeri sunucu + SSDP cevabı, komutlara gerçek ampul gibi cevap verir ve bildirim yollar |

## 3.4 API sözleşmesi

Tüm uçlar `/api` altında. Cevaplar JSON. Ampul kimliği (`{id}`), ampulün SSDP'de verdiği `id` değeri (örn. `0x0000000012345678`), elle eklenenlerde `ip-192.168.1.50`.

### Ampuller

| Metot | Yol | Gövde | Açıklama | Gereksinim |
|---|---|---|---|---|
| GET | `/api/devices` | – | Tüm ampuller ve son durumları | F1 |
| POST | `/api/devices/scan` | – | Ağı yeniden tara (≈3 sn), bulunanları döner | F1 |
| POST | `/api/devices` | `{ip, name?}` | Elle ekle, bağlantıyı dener | F1 |
| DELETE | `/api/devices/{id}` | – | Listeden çıkar | F1 |
| PATCH | `/api/devices/{id}` | `{name}` | Yeniden adlandır (ampule `set_name` da gider) | F2 |

### Kontrol

| Metot | Yol | Gövde | Ampul komutu | Gereksinim |
|---|---|---|---|---|
| POST | `/api/devices/{id}/power` | `{on: bool}` | `set_power` | F3 |
| POST | `/api/devices/{id}/color` | `{hex: "#FF8A3D"}` | `set_rgb` | F4 |
| POST | `/api/devices/{id}/brightness` | `{value: 1..100}` | `set_bright` | F5 |
| POST | `/api/devices/{id}/temperature` | `{kelvin: 1700..6500}` | `set_ct_abx` | F6 |
| POST | `/api/devices/{id}/scene` | `{scene_id}` | `set_scene` | F7 |
| POST | `/api/devices/{id}/flow` | `{flow_id}` | `start_cf` | F9 |
| DELETE | `/api/devices/{id}/flow` | – | `stop_cf` | F9 |
| POST | `/api/devices/{id}/timer` | `{minutes: 1..1440}` | `cron_add` | F10 |
| DELETE | `/api/devices/{id}/timer` | – | `cron_del` | F10 |

Ampul kapalıyken renk/parlaklık/ton/sahne komutu gelirse, ampul önce açılır (`set_power on` + istenen mod tek komutta).

### Sahneler ve akışlar

| Metot | Yol | Gövde | Açıklama | Gereksinim |
|---|---|---|---|---|
| GET | `/api/scenes` | – | Hazır + kullanıcı sahneleri | F7 |
| POST | `/api/scenes` | `{name, mode, hex?, kelvin?, brightness}` | Kullanıcı sahnesi kaydet | F8 |
| DELETE | `/api/scenes/{scene_id}` | – | Kullanıcı sahnesini sil (hazırlar silinemez) | F8 |
| GET | `/api/flows` | – | Hazır akışlar | F9 |

### Sistem

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/info` | Sürüm, telefondan erişim adresi (örn. `http://192.168.1.9:8000`) |

### Durum nesnesi

```json
{
  "id": "0x0000000012345678",
  "name": "Ofis Ampulü",
  "model": "colorb",
  "ip": "192.168.1.50",
  "online": true,
  "power": true,
  "mode": "rgb",            // "rgb" | "ct" | "hsv" | "flow"
  "brightness": 80,
  "hex": "#FF8A3D",
  "kelvin": 4000,
  "flow_id": null,
  "timer_minutes_left": null
}
```

### WebSocket `/ws`

Bağlanınca sunucu tam listeyi gönderir, sonra yalnızca değişiklikleri:

```json
{"type": "snapshot", "devices": [ /* durum nesneleri */ ]}
{"type": "device",   "device": { /* tek ampulün güncel durumu */ }}
{"type": "removed",  "id": "..."}
{"type": "error",    "id": "...", "message": "Ampule ulaşılamıyor"}
```

Komutlar REST'ten gider, WebSocket yalnızca sunucudan istemciye akar. Böylece komut hataları HTTP durum koduyla, durum ise tek kanaldan gelir.

### Hata kodları

| Kod | Durum |
|---|---|
| 400 | Geçersiz değer (Pydantic doğrulaması) |
| 404 | Ampul / sahne yok |
| 409 | Hazır sahne silinmeye çalışıldı |
| 429 | Ampulün komut kotası doldu |
| 503 | Ampule ulaşılamıyor |
| 504 | Ampul 3 sn içinde cevap vermedi |

## 3.5 Hız sınırı ve kısma (N1, N2)

Ampul dakikada yaklaşık 60 komut kabul eder, aşılırsa komutu reddeder. Renk çarkı sürüklenirken bu sınır birkaç saniyede dolar. Çözüm iki katmanlı:

1. **Frontend:** Sürükleme sırasında en fazla 150 ms'de bir istek, bırakınca son değer kesin gönderilir.
2. **Backend `CommandQueue`** (ampul başına):
   - **Kova (token bucket):** Kapasite 10, saniyede 1 jeton dolar. Ortalama 60/dk sınırını korur, kısa süreli hızlı tıklamalara izin verir.
   - **Birleştirme:** Aynı türden (renk, parlaklık, ton) bekleyen komutun üstüne yenisi yazılır. Jeton beklenirken gelen 20 renk değişikliğinden yalnızca sonuncusu gönderilir, ampul her zaman son seçilen değere ulaşır.
   - Aç/kapa, akış ve zamanlayıcı komutları birleştirilmez, sırayla gider.

İleride müzik modu (ampulün PC'ye bağlandığı, sınırsız komut kabul eden mod) eklenirse sürükleme daha akıcı olur. Bu, sonraki sürüme bırakıldı.

## 3.6 Bağlantı yaşam döngüsü

```
 keşfedildi / eklendi ─► BAĞLANIYOR ─► BAĞLI ──(soket koptu / 3 komut üst üste zaman aşımı)──► KOPUK
                             ▲                                                                  │
                             └──────────── bekle 1, 2, 4, 8, 16, 30, 30… sn ◄─────────────────────┘
```

- `BAĞLI` olunca `get_prop` ile tam durum okunur, sonra bildirimlerle güncel tutulur.
- Arka planda 60 sn'de bir SSDP taraması yapılır. Ampulün IP'si değiştiyse (DHCP) kayıt güncellenir.
- Kopukken gelen komut hemen 503 döner, sıraya alınmaz.

## 3.7 Güvenlik (N8)

- Sunucu `0.0.0.0:8000` dinler (telefondan erişim için), ama `security.py` ara katmanı yalnızca **özel ağ adreslerinden** (127.0.0.0/8, 10/8, 172.16/12, 192.168/16) gelen istekleri kabul eder, diğerlerine 403 verir.
- Kimlik doğrulama yok: aynı ağdaki herkes ampulü kontrol edebilir (ev ağı için kabul edilebilir, Review aşamasında yeniden değerlendirilecek).
- Elle eklenen IP yalnızca özel ağ aralığında kabul edilir. Uygulama ampul dışında bir adrese bağlantı açmak için kullanılamaz.
- Kullanıcıdan gelen metinler (ampul/sahne adı) arayüzde `textContent` ile basılır, HTML olarak yorumlanmaz.

## 3.8 Klasör yapısı

```
HueLight/
├─ baslat.bat                 # venv kontrolü + sunucuyu başlatır, tarayıcıyı açar
├─ requirements.txt
├─ backend/
│  ├─ main.py                 # FastAPI uygulaması, statik dosyalar, başlangıç/kapanış
│  ├─ config.py               # port, yollar, sabitler
│  ├─ manager.py
│  ├─ store.py
│  ├─ security.py
│  ├─ api/  routes.py  ws.py  schemas.py
│  └─ yeelight/  protocol.py  discovery.py  bulb.py  queue.py  presets.py  miio.py
├─ frontend/
│  ├─ index.html
│  ├─ css/app.css
│  └─ js/  main.js  api.js  store.js  ui/(wheel.js, scenes.js, flows.js, timer.js, devices.js)
├─ tests/                     # pytest, simülatöre karşı
├─ tools/  probe.py  sim_bulb.py
├─ data/config.json           # çalışınca oluşur
├─ mockup/
└─ docs/
```

## 3.9 İlk kurulum (F13) — miIO protokolü

Sıfırlanmış ampul LAN Control protokolünü konuşmaz. Kurulum, Xiaomi'nin **miIO** protokolüyle yapılır (UDP `54321`, AES‑128‑CBC şifreli). Modül: `yeelight/miio.py`, ek bağımlılık: `cryptography` (AES için, standart kütüphanede yok).

| miIO ayrıntısı | Değer |
|---|---|
| Paket | 16 bayt başlık (`0x2131`, uzunluk, 0, cihaz no, zaman damgası) + 16 bayt sağlama + şifreli JSON |
| Anahtar | `key = MD5(token)`, `iv = MD5(key + token)`, PKCS7 dolgu |
| Sağlama | `MD5(başlık + token + şifreli veri)` |
| Token | Sıfırlanmış ampul `hello` cevabında token'ı açık verir. Kurulumdan sonra gizler, bu yüzden `data/config.json`'a kaydedilir |

Akış:

```
 1. Kullanıcı ampulü sıfırlar (5× aç/kapa) → ampul "yeelink-light-…" ağını yayınlar
 2. Kullanıcı PC'nin Wi‑Fi'sini bu ağa bağlar
 3. Arayüz → POST /api/setup/probe      : yayın (broadcast) hello → cihaz no + token
 4. Arayüz → POST /api/setup/provision  : set_ps ["cfg_lan_ctrl","1"]  (LAN Control aç)
                                          miIO.config_router {ssid, passwd, uid:0}
                                          token kaydedilir, Wi‑Fi şifresi KAYDEDİLMEZ
 5. Ampul ev ağına bağlanır. Kullanıcı PC'yi ev ağına geri bağlar
 6. Arayüz → POST /api/setup/finish     : ev ağında yayın hello → ampulün yeni IP'si
                                          set_ps cfg_lan_ctrl tekrar (ilk deneme tutmadıysa)
                                          SSDP taraması → ampul listeye düşer
```

| Uç | Gövde | Cevap |
|---|---|---|
| `GET /api/setup/networks` | – | `{live, networks: [{ssid, signal, supports_24, saved, home}]}`: ev ağı seçimi için. Windows Konum hizmetleri açıksa canlı tarama, değilse PC'de kayıtlı ağlar. Kurulum ağı (`yeelink-…`) listelenmez, PC'nin ev ağı başta gelir |
| `POST /api/setup/probe` | – | `{did, ip, model?}` ya da 404 "kurulum bekleyen ampul yok" |
| `POST /api/setup/provision` | `{ssid, password}` | `{did, lan_control: bool}` |
| `POST /api/setup/finish` | – | Bulunan ampuller (durum nesneleri) |

Riskler: Ampulün donanım yazılımı token'ı gizliyorsa (bazı yeni sürümler) kurulum yapılamaz, kullanıcıya anlaşılır hata gösterilir. Ev ağı 5 GHz ise ampul bağlanamaz ve birkaç dakika sonra tekrar kurulum ağını yayınlar.

## 3.10 Aşamalara etkisi

| Aşama | Bu mimariden aldığı |
|---|---|
| Backend | 3.3 modülleri, 3.4 sözleşmesi, 3.5 kuyruk, 3.6 yaşam döngüsü + simülatör |
| Frontend | Mockup + 3.4 REST/WebSocket sözleşmesi |
| QA | Simülatörle otomatik testler, gerçek ampulle 1.7 kabul kriterleri |
| Review | 3.7 güvenlik kararları, kimlik doğrulama ihtiyacı |
