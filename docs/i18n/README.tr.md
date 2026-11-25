# Glyphbridge

**Sıradan bir 8 GB bilgisayarda çalışan, geniş kapsamlı, ücretsiz ve çevrimdışı çeviri altyapısı — tarihî yazılar (Osmanlıca, hiyeroglif, çivi yazısı) bugünkü bir özellik değil, hedef.**

🌐 [English](../../README.md) · **Türkçe** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Durum: erken önizleme (0.1.0.dev0).** Metin, DOCX, resim (OCR) ve ses çevirisi çalışıyor ve CI'da gerçek modellerle test ediliyor; ancak hiçbir şey üretime hazır değil. Kalite küçük test setleriyle ölçülüyor ([Ölçülen kalite](#ölçülen-kalite)), henüz tam benchmark yok. 📋 *Planlandı* işaretli özellikler henüz yok — onları birlikte yapmak için yardımınızı bekliyoruz.
>
> **Etiketler:** ✅ **Çalışıyor** — CI'da gerçek modellerle test ediliyor · 🧪 **Önizleme** — çalışıyor ama sınırlı ya da az test edilmiş · 🔬 **Deneysel** — isteğe bağlı, ölçüldü ama varsayılan değil · 📋 **Planlandı** — henüz yapılmadı.

## Neden Glyphbridge?

- **Sonsuza dek ücretsiz** — Apache 2.0 lisanslı açık kaynak, kayıt gerekmez; API anahtarı yalnızca kendi sunucunuzu ağa açarsanız kullanılır.
- **Gizli ve çevrimdışı** — her şey kendi bilgisayarınızda çalışır, belgeleriniz dışarı çıkmaz.
- **Hafif** — **8 GB RAM**'li sıradan bir bilgisayarda, ekran kartı olmadan verimli çalışacak şekilde tasarlanıyor.
- **Kalite konusunda dürüst** — her çeviri bir **güven puanıyla** gelir; amacımız tek bir reklam rakamı yerine her dil çifti için ölçülmüş kaliteyi (chrF / COMET) yayınlamak ([yardım bekleniyor](https://github.com/CooLSavaSs/glyphbridge/issues)).
- **Geniş dil kapsamı** — bugün düz metin, fotoğraftaki yazılar, belgeler ve konuşma; tarihî yazı sistemleri uzun vadeli hedef (yol haritasına bakın).

## Özellikler ve yol haritası

| Özellik | Durum |
|---|---|
| Ölçüme dayalı yönlendiricili metin çevirisi (Opus-MT, Hy-MT2, TranslateGemma, MADLAD-400) | ✅ Çalışıyor |
| Model kartları (yalnız gerekeni kur, sabit sürüm, SHA-256 denetimi), çevrimdışı mod | ✅ Çalışıyor |
| CLI, Python kütüphanesi, API anahtarlı REST API | ✅ Çalışıyor |
| Anlam denetçisi (LaBSE) ve güven puanı | ✅ Çalışıyor — doğruluk garantisi değil, bir işaret ([aşağıya bakın](#güven-puanı-ne-demek)) |
| MCP sunucusu, OpenAI uyumlu uç nokta | 🧪 Önizleme |
| DOCX yerinde çeviri (başlık, liste, tablo korunur) | 🧪 Önizleme — paragraf **içindeki** kalın/italik kaybolur ([sınırlar](#belge-sınırları)) |
| PDF → metin, TXT / MD | 🧪 Önizleme — yalnız PDF metin katmanı, düzen yok, taranmış PDF yok |
| Resimler (Tesseract OCR): her satır kutusunu (piksel) ve OCR güvenini taşır; güven düşükse daha yakından çekmeyi önerir; `--ocr-only` çeviriden önce düzeltilecek metni yazar | 🧪 Önizleme — Windows'ta gerçek Tesseract ile henüz denenmedi |
| Canlı kamera: `glyphbridge serve`, sonra `http://localhost:8080/camera` (webcam ya da https üzerinden telefon tarayıcısı); kareler `POST /v1/photo`'ya gider, çeviri her satırın üstüne çizilir | 🧪 Önizleme — çizim tarayıcıda denendi; gerçek kamerayla henüz denenmedi, kareler arası kutu takibi yok |
| Ses: Whisper → çeviri → espeak-ng (`--speak`), canlı mikrofon (`glyphbridge listen`) | 🧪 Önizleme — robotik ses |
| Düşük RAM modu (RAM'den büyük modeller diskten okunur) | 🔬 Deneysel |
| Duygu modülü (ton denetimi), yerleşik deyim belleği, anlam modu, bağlam penceresi (`GLYPHBRIDGE_CONTEXT=1`: LLM kartları önceki paragrafı görür; henüz ölçülmedi) | 🔬 Deneysel |
| PDF düzeni, doğal sesler, sözlüğü budanmış kartlar | 📋 Planlandı |
| **Osmanlıca, matbu**: sayfa → satırlar → Arap harfli metin (`glyphbridge ottoman sayfa.png`, kart `ota-ocr` = Azra 1-Mini 0.8B, Apache 2.0) | 🔬 Deneysel — model kartındaki 10 örnek satırda ölçüldü (bağımsız test seti değil): matbu nesihte **%96,9**, el yazısı rikada **%86,5** karakter doğruluğu, CPU'da satır başına ~1,5 sn; Arapça kef/ye Osmanlıca biçimine normalleştirilir |
| **Osmanlıca**: el yazısı (rika, divani), Latin harflerine transliterasyon, modern Türkçe | 📋 Planlandı — ağırlıkları açık ve lisansı uygun transliterasyon modeli henüz bulunamadı |
| Unicode metinden işaret listesi: `glyphbridge signs "𓀀𓂀"` → Gardiner kodları `A1-D58`; çivi yazısı → işaret adları (`A-ASH`) | 🔬 Deneysel — yalnız listeleme, okuma ya da çeviri değil; yalnız Unicode girdi |
| **Mısır hiyeroglifleri** (fotoğrafta işaret tanıma) ve **çivi yazısı** (Akadça transliterasyon) | 📋 Planlandı — uzmanlarla araştırma |

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

> Bu bir **önizleme**: metin, belgeler (DOCX, PDF metni), resimler (OCR) ve ses çalışıyor; PDF düzeni, doğal sesler ve tarihî yazılar henüz hazır değil. Kalite yalnızca küçük test setleriyle ölçüldü — bkz. [Ölçülen kalite](#ölçülen-kalite).

Temel paket hafiftir (birkaç MB) ve **tek başına çeviri motoru içermez**. Bir profil seçin:

| Profil | Kurulum | Python paketleri | Modeller (ilk çalıştırmada bir kez internet) | Ne için |
|---|---|---|---|---|
| **8 GB profili** (PyTorch yok) | `pip install "glyphbridge[8gb] @ git+https://github.com/CooLSavaSs/glyphbridge" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu` | CTranslate2 23 MB + llama.cpp CPU paketi (boyut sürüme göre değişir) | `madlad-int8` ~3,0 GB, `hymt2-q4` ~1,1 GB, `gemma-q4` ~2,5 GB (yalnız istediklerinizi kurun) | 8 GB PC'de 493 dil |
| **Opus-MT** (PyTorch) | `pip install torch --index-url https://download.pytorch.org/whl/cpu`, sonra `pip install "glyphbridge[transformers] @ git+..."` | ~130 MB indirme, **diskte ~0,7 GB** (PyTorch 559 MB + Transformers 120 MB, ölçüldü) | dil çifti başına ~300 MB | çift başına hızlı ve küçük; eski işlemcilerde çalışır |
| **Her şey** | `pip install torch --index-url https://download.pytorch.org/whl/cpu`, sonra `pip install "glyphbridge[all] @ git+..."` | diskte ~1 GB | yukarıdakiler + denetçi ~1,9 GB, Whisper ~1 GB, … | tüm özellikler |

- **Disk:** modeller Hugging Face önbelleğine (`~/.cache/huggingface`) iner. Yukarıdaki model boyutlarına ek ~1 GB boş yer ayırın; her kartın ve tipik setlerin ölçülen boyutları [docs/disk.md](../disk.md) belgesinde.
- **İnternet:** yalnızca bir kart ilk kez indirilirken (`glyphbridge cards install …` önceden indirir). Sonrasında `GLYPHBRIDGE_OFFLINE=1` hiçbir şey indirilmemesini garanti eder.
- **Eski işlemciler** (ör. 2015 dönemi Core i5): hazır llama.cpp paketi orada çöküyor, GGUF kartları (`hymt2-q4`, `gemma-q4`) atlanır — Opus-MT profilini ekleyin ya da llama.cpp'yi kendiniz derleyin (yukarıda *Eski işlemciler*).

```bash
# Örnek: en hafif iki kartla 8 GB profili
pip install "glyphbridge[8gb] @ git+https://github.com/CooLSavaSs/glyphbridge" \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
glyphbridge cards install hymt2-q4 madlad-int8

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

### Ölçülen kalite

Tüm puanlar **chrF** (0–100, yüksek iyi), insan çevirisi referanslara karşı CI'da ölçüldü. Bunlar **küçük test setleri**, tam benchmark değil: çift başına birkaç düzine cümle; 2–3 puanlık fark gürültü olabilir. Puan kurulu kartlara bağlı olduğu için her satırda hangi kartların kurulu olduğu yazıyor.

| Test seti | Boyut | Yön | Kurulu kartlar | Sonuç | Çalışma |
|---|---|---|---|---|---|
| golden-v2 | 230 cümle, 9 çift | X→İngilizce, en→tr | tüm 8 GB kartları, yönlendirme tablosu | tr→en **73,8**, en→tr 76,8, de→en 85,6, fr→en 80,1, es→en 88,9, ru→en 80,8, ar→en 90,5, zh→en 86,5, la→en 74,5 | CI #102 |
| golden-v2 | aynı | aynı | yalnız Opus-MT (varsayılan kurulum) | tr→en 73,2, en→tr 76,8, de→en 85,6, fr→en 80,1, es→en 86,9, ru→en 74,8, **ar→en 1,3 (bozuk, artık atlanıyor)**, zh→en 58,3, la→en 49,5 | CI #96 |
| golden-v3 | 344 cümle, 21 çift | İngilizce→X ve X→İngilizce | tüm 8 GB kartları | Hy-MT2 önde: ja→en 92,5, fa→en 86,9, ko→en 84,3, hi→en 78,1, en→ru 83,8, en→zh 50,6; Opus-MT önde: en→fr 96,3, en→de 88,7, en→es 86,9, en→ar 81,3 | yalnız rapor |
| golden-v3 düşük kaynak | çift başına 9 cümle | X→İngilizce | TranslateGemma 4-bit | sw→en 92,0, hi→en 88,1, fa→en 88,0, el→en 86,7 | CI #103 |
| FLORES-200 | 50 dil × ilk 20 devtest cümlesi | yalnız X→İngilizce | Hy-MT2 + TranslateGemma 4-bit + MADLAD int8, yönlendirme tablosu | **50/50 çevrildi, ortanca 60,8**; en iyi Maltaca 79,0, Galce 75,7; en zayıf Wolofça 35,7, Yorubaca 38,3, Tibetçe 39,3, Keçuva 39,3, İboca 47,5 | `flores.yml` |

Ölçümlerden öğrendiklerimiz:

- **Küçük setler yanıltır.** 18 cümlede Hy-MT2 tr→en'de Opus-MT'yi geçti (79,6'ya 75,6); 62 cümlede Opus-MT önde (73,2'ye 70,6). Yönlendirici sırası büyük setlerden geliyor.
- **Deyimler her modelin en zayıf yeri** (Opus-MT chrF 11–42). İstem talimatı ("anlam modu") onları yalnızca 0–1,7 chrF oynattı; çözüm veri: çeviri belleği (yerleşik deyim belleği, isteğe bağlı).
- **Bozuk modeller bulundu ve atlanıyor:** Opus-MT `ar-en` ile tc-big Yunanca ve Korece (yalnız noktalama). Harf içermeyen çeviri artık her zaman başarısız sayılır.
- **Latince:** MADLAD *Gallia est omnis divisa in partes tres*'i yanlış çeviriyor, TranslateGemma 4-bit doğru çeviriyor; bu yüzden Latince kuruluysa `gemma-q4`'e, değilse Opus-MT İtalik grup modeline gidiyor.
- **Kart bazlı yönlendirme** (`glyphbridge/routes.py`; bir kart ancak ≥ 3 chrF farkla öne geçer) FLORES'te Moğolcayı 32,5 → 59,0, Kazakçayı 42,9 → 59,1, Zuluyu 49,5 → 59,4'e çıkardı.
- **Henüz ölçülmedi:** FLORES'te İngilizce→X, dil başına 20'den fazla cümle, COMET, belge, OCR ve ses doğruluğu.

Kendiniz çalıştırın: `python scripts/golden.py tests/golden/v2/tr-en.tsv` ve `python scripts/flores.py --sentences 20`.

**Kapsam:** üç 8 GB kartı (`madlad-int8`, `gemma-q4`, `hymt2-q4`) kuruluyken `glyphbridge languages --all` **493 dil** listeliyor (MADLAD int8 492, TranslateGemma 4-bit 50, Hy-MT2 36). Bu kartlar olmadan kapsam yalnızca kurduğunuz Opus-MT çiftleridir. Listede olmak iyi çevirmek demek değil: yukarıdaki FLORES en zayıf dillerine bakın.

**Düşük RAM modu** (🔬, `GLYPHBRIDGE_LOW_RAM=1`, `pip install "glyphbridge[lowram]"`): 9,4 GB'lık tam TranslateGemma, takas alanı olmadan kesin **6 GB** bellek sınırında çalıştı; sığmayan katmanlar diskten okundu. Tepe RAM 3,4 GB, iki test cümlesi doğru çevrildi, yükleme dahil 44 sn (CI #103). Yavaş ama RAM'den büyük model çalışıyor.

**Gerçek bir 8 GB dizüstünde denendi** (Windows 10, 2015 dönemi bir Intel Core i5, 4 iş parçacığı, ekran kartı yok, başlangıçta 1,6 GB boş RAM): Opus-MT tr→en ilk indirmeden sonra cümle başına ~3 sn, 0,93 GB RAM. İki Windows sorunu bulunup düzeltildi: konsol ✓/⚠ işaretlerinde çöküyordu (artık gösteremediği yerde `?` yazıyor) ve llama.cpp'nin çalıştıramadığı bir GGUF kartı bütün çeviriyi çökertiyordu (artık o kart atlanıyor, sıradaki kart çeviriyor).

**Eski işlemciler:** hazır `llama-cpp-python` CPU paketi bu 2015 dönemi Core i5'te *geçersiz komut* hatasıyla duruyor (Windows hatası `0xc000001d`); bu yüzden orada GGUF kartları (`hymt2-q4`, `gemma-q4`) atlanıyor, Opus-MT / MADLAD çeviriyor. Bu kartları böyle bir işlemcide kullanmak için llama.cpp'yi o işlemciye göre derleyin: Visual Studio Build Tools (C++) kurun, sonra `set CMAKE_ARGS=-DGGML_NATIVE=ON` ve `pip install llama-cpp-python --no-binary llama-cpp-python`.

**Yerleşik deyim belleği** (🔬, `GLYPHBRIDGE_IDIOMS=1`): 40 yaygın Türkçe↔İngilizce atasözü ve deyim (halk sözleri, iki yönde), her modelden önce kullanılır; kendi bellek dosyalarınız bunların önüne geçer.

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

### Terim sözlüğü: belgenin tamamında aynı terim, aynı karşılık

Bellek bütün cümleleri sabitler; **sözlük** ise herhangi bir cümlenin içindeki *terimleri* sabitler. Terim nerede geçerse (eki ne olursa olsun: *Belediye'ye*, *vakıflar*) çıktıda sabit karşılığı bulunmalıdır. Sözlüğe uymayan cümle sıradaki karta gider; hiçbir kart uymazsa işaretlenir (`consistency_issues` içinde `glossary: 'Belediye' should be 'Municipality'`) ve incelemeye düşer. Sözlük denetler; modeli o kelimeyi kullanmaya zorlayamaz.

```text
# kaynak_dil<TAB>hedef_dil<TAB>terim<TAB>karşılık
tr	en	Belediye	Municipality
```

```bash
glyphbridge translate --file rapor.docx --to en --glossary terimler.tsv
export GLYPHBRIDGE_GLOSSARY=terimler.tsv   # API, MCP ve Python için
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
| v0.2 🔬 | **Düşük RAM modu** (`GLYPHBRIDGE_LOW_RAM=1`): katmanlar diskten okunur | 9,4 GB model 6 GB sınırında çalıştı, yavaş |

### Güven puanı ne demek?

`confidence` değeri (0–1) **çevirinin doğru olma olasılığı değildir.**

- `checker` kartı kuruluysa özgün metin ile çeviri arasındaki **anlam benzerliğidir** (LaBSE). Akıcı ama bir olumsuzluğu atlayan ya da bir sayıyı değiştiren çeviri yine yüksek alabilir; doğru ama serbest çeviri daha düşük alabilir.
- Kurulu değilse **modelin kendi kelime olasılığıdır** — modelin ne kadar emin olduğunu gösterir, haklı olup olmadığını değil.

Bir insanın önce neye bakması gerektiğini sıralamak için kullanın, kalite puanı olarak değil. Dil çifti başına ölçülen kalite [Ölçülen kalite](#ölçülen-kalite) bölümünde.

Her sonuç (`--json`, REST, MCP, Python) işaretleri ayrıca **ayrı alanlarda** taşır:

| Alan | Anlamı |
|---|---|
| `box` | fotoğraflar: satırın resimdeki yeri, piksel olarak (sol, üst, sağ, alt) |
| `detected_script` | kaynak metnin yazı sistemi (ISO 15924: `Latn`, `Arab`, `Cyrl`, `Hani`, `Egyp`, …) |
| `ocr_confidence` | yalnız resimler: o satır için Tesseract'ın ortalama kelime güveni (0–1) |
| `translation_confidence` | modelin kendi kelime olasılığı (0–1); kart vermiyorsa `null` |
| `similarity` | `checker` kartının anlam benzerliği (0–1); kart yoksa `null` |
| `consistency_issues` | kaybolan sayı ya da isim, boş çıktı, tekrar eden metin |
| `expert_review_required` | bir denetim başarısızsa, OCR güveni 0,70'in altındaysa ya da anlam denetimi yokken model olasılığı 0,50'nin altındaysa `true` (başlangıç eşikleri, henüz ölçülmedi) |

### Belge sınırları

- **DOCX:** her paragraf tek parça çevrilir. Başlıklar, listeler, tablolar ve paragraf stilleri korunur; ama paragraf **içindeki** biçim (kalın bir kelime, italik bir ifade, bağlantı, farklı yazı tipi) ilk parçanın biçimine birleşir.
- **PDF:** yalnızca **metin katmanı** okunur, sonuç düz metindir (`.txt`). Düzen, resimler ve tablolar korunmaz. Metin katmanı olmayan taranmış PDF'ler metin vermez — resim olarak OCR'dan geçirin.
- **Resimler:** Tesseract OCR; doğruluk fotoğrafa bağlı ve henüz ölçülmedi.

## Katkıda bulunun

- 🌍 Bu README'yi kendi dilinize çevirin — ideal bir ilk katkı
- 🧪 Ana dilinizdeki çevirileri test edip hataları bildirin
- 🐍 Python ile kod yazın — [`good first issue`](https://github.com/CooLSavaSs/glyphbridge/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) etiketli işlere bakın
- 📜 Dilbilimci, tarihçi ya da Mısırbilimciyseniz tarihî yazılar konusunda yardım edin

Ayrıntılar için [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Lisans

**Glyphbridge'in kodu** [Apache 2.0](../../LICENSE) lisanslıdır — ticari kullanım dahil, özgürce kullanın, değiştirin ve paylaşın.

**Modeller (kartlar) kodun parçası değildir**, her biri kendi lisansını taşır. Bir kartı kurmak onun şartlarını kabul etmek demektir:

| Kart | Model | Lisans |
|---|---|---|
| `opus:<kaynak>-<hedef>`, Opus-MT grup modelleri | Helsinki-NLP Opus-MT / tc-big | CC-BY 4.0 (atıf zorunlu) |
| `madlad`, `madlad-int8` | Google MADLAD-400 3B (int8: Nextcloud-AI) | Apache 2.0 |
| `hymt2-q4` | Tencent Hy-MT2 1.8B GGUF | Apache 2.0 |
| `gemma`, `gemma-q4` | Google TranslateGemma 4B (4-bit topluluk GGUF) | Gemma Kullanım Şartları (kullanım kısıtları var; tam modele erişim onay gerektirir) |
| `lid` | GlotLID | Apache 2.0 |
| `checker` | LaBSE | Apache 2.0 |
| `emotion` | çok dilli DistilBERT duygu modeli | Apache 2.0 |
| `whisper` | OpenAI Whisper small | MIT |
| `ota-ocr` | OttomanNLP Azra 1-Mini 0.8B (Osmanlıca OCR) | Apache 2.0 |
| OCR / ses çıkışı | Tesseract, espeak-ng (ayrıca kurulur) | Apache 2.0 / GPL-3.0 (ayrı programlar, pakete dahil değil) |

Lisansları ticari kullanımı yasakladığı için varsayılan olarak kullanılmayanlar: NLLB-200 (CC-BY-NC), Cohere North Small Translate (CC-BY-NC).

**493 dil** sayısı, 8 GB kartları (`madlad-int8`, `gemma-q4`, `hymt2-q4`) kuruluyken geçerlidir; varsayılan kurulum çok daha az dil kapsar.
