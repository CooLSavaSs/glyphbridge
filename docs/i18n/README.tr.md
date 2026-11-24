# Glyphbridge

**Her yazı sistemi için ücretsiz, çevrimdışı ve açık kaynak çeviri — modern dillerden Osmanlıcaya, hiyeroglife ve çivi yazısına kadar.**

🌐 [English](../../README.md) · **Türkçe** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Durum: erken önizleme (0.1.0.dev0).** Metin, DOCX, resim (OCR) ve ses çevirisi çalışıyor ve CI'da gerçek modellerle test ediliyor; ancak hiçbir şey üretime hazır değil ve kalite henüz ölçülmedi. *Planlanan* ya da *araştırma* olarak işaretli özellikler henüz yok — onları birlikte yapmak için yardımınızı bekliyoruz.

## Neden Glyphbridge?

- **Sonsuza dek ücretsiz** — Apache 2.0 lisanslı açık kaynak, kayıt gerekmez; API anahtarı yalnızca kendi sunucunuzu ağa açarsanız kullanılır.
- **Gizli ve çevrimdışı** — her şey kendi bilgisayarınızda çalışır, belgeleriniz dışarı çıkmaz.
- **Hafif** — **8 GB RAM**'li sıradan bir bilgisayarda, ekran kartı olmadan verimli çalışacak şekilde tasarlanıyor.
- **Kalite konusunda dürüst** — her çeviri bir **güven puanıyla** gelir; amacımız tek bir reklam rakamı yerine her dil çifti için ölçülmüş kaliteyi (chrF / COMET) yayınlamak ([yardım bekleniyor](https://github.com/CooLSavaSs/glyphbridge/issues)).
- **Her yazı için** — düz metnin yanında fotoğraflardaki yazılar, belgeler, konuşma ve tarihî yazı sistemleri.

## Özellikler ve yol haritası

| Sürüm | Özellik | Durum |
|---|---|---|
| **v0.1** | Model yönlendiricili metin çevirisi (Opus-MT → TranslateGemma → MADLAD-400), anlam denetçisi, sadece gerekeni kuran model kartları, CLI, API anahtarlı REST API, MCP sunucusu | 🧪 Önizleme |
| **v0.2** | **Belgeler**: DOCX yerinde çevrilir (başlık, liste, tablo korunur), PDF metni → metin, TXT/MD; **resimler** Tesseract OCR ile. Sırada: PDF düzeni, budanmış int8 kartlar | 🧪 Kısmen önizlemede |
| **v0.3** | **Ses**: Whisper ile konuşma → metin → çeviri → espeak-ng ile ses (`--speak`). canlı mikrofon modu (`glyphbridge listen`). Sırada: doğal sesler | 🧪 Önizleme |
| **v0.4** | **Osmanlıca**: matbu ve el yazısı (rika, divani) OCR, transliterasyon, modern Türkçe | 📋 Planlanan |
| **Deneysel** | **Mısır hiyeroglifleri** ve **çivi yazısı** (Akadca, Sümerce) — araştırmacılarla iş birliği içinde | 🔬 Araştırma |

## Her yerde kullanın

| Arayüz | Örnek |
|---|---|
| Python kütüphanesi | `glyphbridge.translate("Merhaba", to="en")` |
| Komut satırı | `glyphbridge translate --file notlar.txt --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (isteğe bağlı API anahtarı) |
| Yapay zekâ ajanları (MCP) | Claude ve diğer yapay zekâ asistanlarından araç olarak kullanın |
| OpenAI uyumlu uç nokta | `base_url=http://localhost:8080/v1`, `model="glyphbridge-en"` — mevcut OpenAI istemcileri değişmeden çalışır |

Her şey kendi sisteminizde çalışır ve ücretsizdir. API anahtarları, sunucunuzu ağa veya internete açtığınızda onu korur.

## Başlarken

> Bu bir **önizleme**: metin, belgeler (DOCX, PDF metni), resimler (OCR) ve ses çalışıyor; PDF düzeni, doğal sesler ve tarihî yazılar henüz hazır değil. Kalite henüz ölçülmedi.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "glyphbridge[all] @ git+https://github.com/CooLSavaSs/glyphbridge"

glyphbridge translate "Merhaba dünya" --from tr --to en
glyphbridge translate --file rapor.docx --to en      # -> rapor.en.docx
glyphbridge translate --file foto.jpg --from tr --to en  # OCR -> foto.en.txt
glyphbridge translate --file konusma.mp3 --to en --speak  # ses -> metin + konusma.en.wav
glyphbridge listen --from tr --to en                      # canlı mikrofon çevirisi
glyphbridge serve --port 8080 --api-key "uzun-rastgele-bir-anahtar"
```

İlk çalıştırmada gereken kart bir kez indirilir (ya da kartları önceden kurabilirsiniz); sonrasında her şey çevrimdışı çalışır. Ayrıntılar ve Python/MCP örnekleri için [İngilizce README](../../README.md#getting-started).

## Nasıl çalışır?

Glyphbridge kendini kanıtlamış açık modelleri kullanır. Bir **yönlendirici** her dil çifti için en iyi modeli seçer. **Anlam denetçisi** her çeviriyi özgün cümleyle karşılaştırır: tutmazsa cümle sıradaki modele gider, hiçbiri tutmazsa özgünüyle birlikte ⚠ işaretiyle gösterilir.

| Görev | Model (kart) | Diller | Lisans | RAM |
|---|---|---|---|---|
| Hızlı yol | Opus-MT / tc-big (`opus:<kaynak>-<hedef>`) | kart başına bir dil çifti | CC-BY 4.0 | ~600 MB |
| En yüksek kalite, **8 GB PC** *(isteğe bağlı)* | TranslateGemma 4B 4-bit GGUF (`gemma-q4`) | ~55 değerlendirilmiş | Gemma şartları | **4,6–4,8 GB ölçüldü** (tepe) |
| Nadir diller, **8 GB PC** | MADLAD-400 3B int8 CTranslate2 (`madlad-int8`) | 400+ | Apache 2.0 | **3,3–5,5 GB ölçüldü** (tepe) |
| En yüksek kalite, tam boy *(isteğe bağlı)* | TranslateGemma 4B (`gemma`) | ~55 değerlendirilmiş, resim de okur | Gemma şartları | **9,4 GB ölçüldü** (tepe) |
| Nadir diller, tam boy *(isteğe bağlı)* | MADLAD-400 3B (`madlad`) | 400+ (Latince, Süryanice…) | Apache 2.0 | **6,5 GB ölçüldü** |
| Dil tanıma | GlotLID (`lid`) | 1.600+ | Apache 2.0 | küçük |
| Anlam denetçisi | LaBSE (`checker`) | 109 | Apache 2.0 | ~1 GB |
| **En iyi ölçülen, 8 GB PC** *(kurunca açılır)* | Tencent Hy-MT2 1.8B 4-bit GGUF (`hymt2-q4`) | 36 (Türkçe dahil) | Apache 2.0 | **2,2 GB ölçüldü** (tepe) |
| Duygu modülü *(kurunca açılır)* | çok dilli DistilBERT duygu modeli (`emotion`) | çok dilli | Apache 2.0 | **0,8 GB ölçüldü** |

*Ölçüldü* yazan RAM değerleri, CI'da CPU üzerinde çeviri yapan bir sürecin tamamının (Python, kütüphaneler ve model) tepe değeridir; diğerleri tahmindir. Aralık, iki CI çalışmasının farklı tepe değerler verdiğini gösterir; yönlendirici yüksek olanla plan yapar. 8 GB'lık bir bilgisayarda 8 GB kartları sığar ama başka programlara az yer kalır.

**Şu ana kadarki kalite** (golden-v1: elle hazırlanmış küçük bir kontrol seti, benchmark değil): Opus-MT Türkçe→İngilizce'de chrF **75,6**, İngilizce→Türkçe'de **76,8** alıyor. İsimler, sayılar, olumsuzluk ve teknik metin iyi; deyimler zayıf (chrF 22–28) ve sıradaki iyileştirme konusu. Latincede MADLAD regresyon örneği *Gallia est omnis divisa in partes tres*'i yanlış çeviriyor (chrF 38,7), TranslateGemma 4-bit (`gemma-q4`) ise **84,9** alıyor; bu yüzden Latince artık kuruluysa `gemma-q4`'e gidiyor. Türkçede `gemma-q4` Opus-MT'den düşük puan aldı (68,6 / 64,4), bu yüzden Opus-MT önde kalıyor. `gemma-q4` yoksa Latince, Apache lisanslı Opus-MT İtalik grup modeline (`opus-mt-itc-en`, chrF **61,1**) gidiyor. Yönlendirici sırasını tahminler değil bu ölçümler belirliyor.

**Hy-MT2** (Tencent; Hugging Face'te en çok beğenilen çeviri modeli) Türkçe↔İngilizce için şimdiye kadar ölçülen en iyi kart: chrF **79,6** / **77,9** (Opus-MT 75,6 / 76,8), deyimlerde 46,8 (Opus-MT 28,4), tepe RAM 2,2 GB. Kurulunca (`glyphbridge cards install hymt2-q4`) ilk o denenir.

### Duygu modülü: tonu koruyun

`emotion` kartı kaynağın ve her çevirinin tonunu okur (olumlu, nötr, olumsuz). Açıkça olumlu bir cümle açıkça olumsuz dönerse (ya da tersi) çeviri işaretlenir (`tone changed: positive -> negative`) ve sıradaki kart denenir. Sonuçlarda kaynağın tonu `tone` alanında gelir. Diğerleri gibi bir karttır: `glyphbridge cards install emotion`, yaklaşık 0,8 GB RAM, yalnızca denetim sırasında yüklenir; `GLYPHBRIDGE_EMOTION=0` kapatır.

### Çeviri belleği: kendi çevirilerinizi sabitleyin

Deyimler ve kuruma özel terimler modellerin en çok yanıldığı yerlerdir. Bir çeviri belleği dosyası bir cümlenin ya da ifadenin nasıl çevrileceğini sabitler; her modelden önce kullanılır, eşleşmede büyük/küçük harf, fazla boşluk ve sondaki noktalama dikkate alınmaz:

```text
# kaynak_dil<TAB>hedef_dil<TAB>kaynak<TAB>çeviri
tr	en	Gözden ırak olan gönülden de ırak olur.	Out of sight, out of mind.
```

```bash
glyphbridge translate --memory deyimler.tsv --to en "Gözden ırak olan gönülden de ırak olur."
export GLYPHBRIDGE_MEMORY=deyimler.tsv   # API, MCP ve Python için
```

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
| v0.2 ✓ | **int8 / 4-bit kartlar** (`madlad-int8`, `gemma-q4`): büyük modellerin topluluk tarafından küçültülmüş sürümleri | yaklaşık yarı RAM |
| sırada | **Sözlüğü budanmış kartlar**: `tr-en` kartı yalnızca bu iki dilin kelimelerini tutar | daha da az RAM ve disk |
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
