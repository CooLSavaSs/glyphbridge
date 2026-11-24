# Glyphbridge

**Her yazı sistemi için ücretsiz, çevrimdışı ve açık kaynak çeviri — modern dillerden Osmanlıcaya, hiyeroglife ve çivi yazısına kadar.**

🌐 [English](../../README.md) · **Türkçe** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Durum: erken geliştirme aşamasında.** Glyphbridge herkese açık olarak geliştiriliyor. *Planlanan* olarak işaretli özellikler henüz yok — onları birlikte yapmak için yardımınızı bekliyoruz.

## Neden Glyphbridge?

- **Sonsuza dek ücretsiz** — Apache 2.0 lisanslı açık kaynak, kayıt gerekmez; API anahtarı yalnızca kendi sunucunuzu ağa açarsanız kullanılır.
- **Gizli ve çevrimdışı** — her şey kendi bilgisayarınızda çalışır, belgeleriniz dışarı çıkmaz.
- **Hafif** — **8 GB RAM**'li sıradan bir bilgisayarda, ekran kartı olmadan verimli çalışacak şekilde tasarlanıyor.
- **Kalite konusunda dürüst** — her çeviri bir **güven puanıyla** gelir; tek bir reklam rakamı yerine her dil çifti için ölçülmüş kaliteyi (COMET / chrF) yayınlarız.
- **Her yazı için** — düz metnin yanında fotoğraflardaki yazılar, belgeler, konuşma ve tarihî yazı sistemleri.

## Özellikler ve yol haritası

| Sürüm | Özellik | Durum |
|---|---|---|
| **v0.1** | Model yönlendiricili metin çevirisi (Opus-MT → TranslateGemma → MADLAD-400), anlam denetçisi, sadece gerekeni kuran model kartları, CLI, API anahtarlı REST API, MCP sunucusu | 🧪 Önizleme |
| **v0.2** | **Belgeler**: DOCX yerinde çevrilir (başlık, liste, tablo korunur), PDF metni → metin, TXT/MD; **resimler** Tesseract OCR ile. Sırada: PDF düzeni, budanmış int8 kartlar | 🧪 Kısmen önizlemede |
| **v0.3** | **Sesli** çeviri: konuşma → metin → çeviri → ses | 📋 Planlanan |
| **v0.4** | **Osmanlıca**: matbu ve el yazısı (rika, divani) OCR, transliterasyon, modern Türkçe | 📋 Planlanan |
| **Deneysel** | **Mısır hiyeroglifleri** ve **çivi yazısı** (Akadca, Sümerce) — araştırmacılarla iş birliği içinde | 🔬 Araştırma |

## Her yerde kullanın

| Arayüz | Örnek |
|---|---|
| Python kütüphanesi | `glyphbridge.translate("Merhaba", to="en")` |
| Komut satırı | `glyphbridge translate --file notlar.txt --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (isteğe bağlı API anahtarı) |
| Yapay zekâ ajanları (MCP) | Claude ve diğer yapay zekâ asistanlarından araç olarak kullanın |
| OpenAI uyumlu uç nokta *(planlanan)* | Mevcut yapay zekâ araçlarına kod değiştirmeden bağlayın |

Her şey kendi sisteminizde çalışır ve ücretsizdir. API anahtarları, sunucunuzu ağa veya internete açtığınızda onu korur.

## Başlarken

> v0.1 bir **önizleme**: metin çevirisi çalışıyor; resim, belge, ses ve tarihî yazılar sonraki sürümlerde gelecek.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "glyphbridge[all] @ git+https://github.com/CooLSavaSs/glyphbridge"

glyphbridge translate "Merhaba dünya" --from tr --to en
glyphbridge translate --file rapor.docx --to en      # -> rapor.en.docx
glyphbridge translate --file foto.jpg --from tr --to en  # OCR -> foto.en.txt
glyphbridge serve --port 8080 --api-key "uzun-rastgele-bir-anahtar"
```

İlk çalıştırmada gereken kart bir kez indirilir (ya da kartları önceden kurabilirsiniz); sonrasında her şey çevrimdışı çalışır. Ayrıntılar ve Python/MCP örnekleri için [İngilizce README](../../README.md#getting-started).

## Nasıl çalışır?

Glyphbridge kendini kanıtlamış açık modelleri kullanır. Bir **yönlendirici** her dil çifti için en iyi modeli seçer. **Anlam denetçisi** her çeviriyi özgün cümleyle karşılaştırır: tutmazsa cümle sıradaki modele gider, hiçbiri tutmazsa özgünüyle birlikte ⚠ işaretiyle gösterilir.

| Görev | Model (kart) | Diller | Lisans | RAM (tahmini) |
|---|---|---|---|---|
| Hızlı yol | Opus-MT / tc-big (`opus:<kaynak>-<hedef>`) | kart başına bir dil çifti | CC-BY 4.0 | ~600 MB |
| En yüksek kalite *(isteğe bağlı)* | TranslateGemma 4B (`gemma`) | ~55 değerlendirilmiş, resim de okur | Gemma şartları | şimdilik ~9 GB, 4-bit kart planlanıyor |
| Nadir diller | MADLAD-400 3B (`madlad`) | 400+ (Latince, Süryanice…) | Apache 2.0 | şimdilik ~6,5 GB, int8 kart planlanıyor |
| Dil tanıma | GlotLID (`lid`) | 1.600+ | Apache 2.0 | küçük |
| Anlam denetçisi | LaBSE (`checker`) | 109 | Apache 2.0 | ~1 GB |

### Model kartları: yalnızca gereken çalışır

Her model bir **kart**tır. Sadece ihtiyacınız olan kartları kurarsınız; çeviri sırasında yalnızca o cümlenin gerektirdiği kart belleğe yüklenir, RAM bütçesi dolunca en eski kart bellekten çıkarılır. 8 GB RAM'li bilgisayarda böyle rahat çalışır.

```bash
glyphbridge cards
glyphbridge cards install opus:tr-en opus:en-tr lid checker
glyphbridge cards remove madlad
```

### Yol haritası: kartları küçültmek

Amaç, büyük bir modelin bilgisini, tamamını çalıştırmadan kullanmak:

| Adım | Yöntem | Etkisi |
|---|---|---|
| v0.2 | **Sözlüğü budanmış + int8 kartlar**: `tr-en` kartı yalnızca bu iki dilin kelimelerini tutar | çok daha az RAM ve disk, kalite neredeyse aynı |
| v0.3 | **Taban + adaptör kartları**: küçük ortak model bellekte kalır, dil/görev başına 10–50 MB'lık LoRA adaptörleri takılıp çıkarılır | dil değiştirmek neredeyse hiç RAM harcamaz |
| v0.3 | **Damıtılmış kartlar**: büyük model, dil çiftine özel küçük modeli eğitir | MB başına en iyi kalite |
| sonra | **`--low-ram` modu**: katmanlar diskten tek tek okunur | çok büyük modeller küçük PC'de çalışır, ama yavaş |

## Katkıda bulunun

- 🌍 Bu README'yi kendi dilinize çevirin — ideal bir ilk katkı
- 🧪 Ana dilinizdeki çevirileri test edip hataları bildirin
- 🐍 Python ile kod yazın — [`good first issue`](https://github.com/CooLSavaSs/glyphbridge/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) etiketli işlere bakın
- 📜 Dilbilimci, tarihçi ya da Mısırbilimciyseniz tarihî yazılar konusunda yardım edin

Ayrıntılar için [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Lisans

[Apache 2.0](../../LICENSE) — ticari kullanım dahil, özgürce kullanın, değiştirin ve paylaşın.
