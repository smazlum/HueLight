# 4. Devir Notu (23.10.2026)

Proje şirket bilgisayarından kişisel bilgisayara taşınıyor. Bu not, kaldığımız yeri ve sıradaki işleri özetler.

## 4.1 Durum özeti

| Aşama | Durum |
|---|---|
| Analist | ✅ `docs/01-analiz.md` (F1–F13, N1–N8) |
| Mockup | ✅ `mockup/index.html`, onaylandı |
| Mimar | ✅ `docs/03-mimari.md` |
| Backend | ✅ Yazıldı, 33 otomatik test geçiyor, **gerçek ampulle doğrulandı** (aşağıda) |
| Frontend | ⏳ Başlamadı. Şu anki `frontend/index.html` ve `frontend/kurulum.html` **geçici**, tasarımları baştan yapılacak |
| QA | ⏳ |
| Review | ⏳ |

### Gerçek ampulle doğrulananlar (Yeelight, model `color`, SSID `yeelink-light-color3_miap…`)

- İlk kurulum (miIO): ampul kurulum ağında `192.168.10.1`, PC `192.168.10.2` alır. `hello` → token alındı, `set_ps cfg_lan_ctrl` + `miIO.config_router` gönderildi, ampul ev ağına katıldı (1. deneme).
- LAN Control ile: aç/kapa, renk, ton, parlaklık, sahne, akış, zamanlayıcı (kur/iptal) çalıştı; durum bildirimleri doğru işleniyor.
- Gerçek ampulden öğrenilenler (simülatör buna göre güncellendi):
  - `props` bildiriminde değerler **sayı** (`"color_mode": 1`), `get_prop` cevabında **metin** (`"1"`).
  - Kurulum ağı Xiaomi'nin bilinen `192.168.13.1` adresi değil: bu ampulde `192.168.10.1`. Yayın (broadcast) hello'ya cevap vermiyor, ağ geçidi adresine doğrudan hello gerekiyor.

## 4.2 Açık sorunlar (öncelik sırasıyla)

1. **Kayıtlı Wi‑Fi şifresini okuma (`backend/wifi.py` → `check_password`) — güvenlik riski.**
   Kurulumda girilen şifreyi doğrulamak için `netsh wlan show profile name=… key=clear` ile Windows'taki kayıtlı şifre okunup karşılaştırılıyor. Bu komut güvenlik yazılımlarının "kimlik bilgisi okuma" olarak işaretlediği bir kalıp; şirket bilgisayarında güvenlik duvarı/izleme yazılımı uyarı verdi.
   **Karar verilmeli:** Bu yöntem kaldırılmalı ya da isteğe bağlı yapılmalı. Önerilen yerine geçecek yol: şifreyi okumadan, kurulum sonrası ampulün ev ağına katılıp katılmadığını izlemek (katılamazsa ampul kurulum ağını yeniden yayınlar → "şifre yanlış olabilir" uyarısı). Uzunluk kontrolü (8–63) zararsız, kalabilir.
2. **İkinci kurulum denemesinde ampul bulunamadı.** Yanlış şifreyle gönderilen kurulumdan sonra ampul sıfırlandı; PC `192.168.10.2` aldı ama `POST /api/setup/probe` 404 döndü (ampul hello'ya cevap vermedi). İlk denemede aynı adımlar çalışmıştı. Bakılacaklar: `data/huelight.log` içindeki tanı satırları (hangi hedefe gönderildi, "port kapalı" geldi mi), ampulü tekrar sıfırlayıp birkaç saniye bekledikten sonra denemek, hello'yu birkaç saniye arayla tekrarlamak.
3. REST kontrol uçları, ampulün bildirimi gelmeden önceki durumu döndürüyor (bir adım geride). Arayüz WebSocket'ten güncel durumu alıyor; Frontend'de buna göre davranılmalı.
4. graphify bulgusu: `DeviceManager` çok iş yapıyor (düşük grup uyumu). Review aşamasında bölünmesi değerlendirilecek.
5. Uygulama PC açılışında kendiliğinden başlamıyor (`baslat.bat` elle çalıştırılıyor) — sonraki sürüm fikri.

## 4.3 Yeni bilgisayarda kurulum

1. Python 3.10+ kur (bu proje 3.14 ile geliştirildi).
2. Depoyu klonla: `git clone https://github.com/smazlum/HueLight`
3. `baslat.bat` çalıştır: ilk seferde `.venv` kurar, paketleri yükler, sunucuyu `http://localhost:8000` adresinde açar.
4. Testler: `.venv\Scripts\python.exe -m pytest -q`
5. Ampul: kayıtlar (`data/`) taşınmadı. Ampul ev ağındaysa ve LAN Control açıksa uygulama ağ taramasıyla kendisi bulur; değilse `/kurulum` ile yeniden kurulur.

Taşınmayanlar (bilerek):
- `data/` — ampul token'ı, ev ağı adı, tanı kayıtları (kişisel/gizli)
- `graphify-out/` — bu bilgisayarın yollarını içeriyor; `/graphify .` ile yeniden üretilir
- `.venv/` — `baslat.bat` yeniden kurar

## 4.4 Claude ile çalışma bağlamı

Önceki oturumdaki tercihler `CLAUDE.md`'de. Önceki bilgisayarda kurulu olan skill'ler (yeni bilgisayarda istenirse yeniden kurulmalı):
- **ponytail** — en küçük, yeterli değişiklik (github.com/DietrichGebert/ponytail, yalnızca `skills/ponytail/SKILL.md`)
- **graphify** — kod/doküman bilgi grafiği (`pip install graphifyy`, ardından `graphify install`)
- **caveman** — kısa cevap modu (github.com/juliusbrussee/caveman, yalnızca `skills/caveman` ve `skills/ultracave`)
