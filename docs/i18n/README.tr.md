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
| **v0.1** | Metin çevirisi, ilk 10–20 dil, komut satırı + basit arayüz, kuantize model (int8) | 🚧 Geliştiriliyor |
| **v0.2** | **Resimlerdeki** (OCR) ve **belgelerdeki** (PDF, DOCX) yazıları düzeni koruyarak çevirme; güven puanı filtresi | 📋 Planlanan |
| **v0.3** | **Sesli** çeviri: konuşma → metin → çeviri → ses | 📋 Planlanan |
| **v0.4** | **Osmanlıca**: matbu ve el yazısı (rika, divani) OCR, transliterasyon, modern Türkçe | 📋 Planlanan |
| **Deneysel** | **Mısır hiyeroglifleri** ve **çivi yazısı** (Akadca, Sümerce) — araştırmacılarla iş birliği içinde | 🔬 Araştırma |

## Her yerde kullanın (planlanan)

| Arayüz | Örnek |
|---|---|
| Python kütüphanesi | `glyphbridge.translate("Merhaba", to="en")` |
| Komut satırı | `glyphbridge translate dosya.pdf --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (isteğe bağlı API anahtarı) |
| Yapay zekâ ajanları (MCP) | Claude ve diğer yapay zekâ asistanlarından araç olarak kullanın |
| OpenAI uyumlu uç nokta | Mevcut yapay zekâ araçlarına kod değiştirmeden bağlayın |

Her şey kendi sisteminizde çalışır ve ücretsizdir. API anahtarları, sunucunuzu ağa veya internete açtığınızda onu korur.

## Nasıl çalışır?

Glyphbridge sıfırdan başlamak yerine kendini kanıtlamış açık modelleri temel alır ve onları yalnızca çeviri için ince ayarlar: çeviri için MADLAD-400 / Opus-MT (CTranslate2, int8), OCR için PaddleOCR / Tesseract, ses için Whisper ve Piper, kalite için COMET tabanlı güven puanı.

## Katkıda bulunun

- 🌍 Bu README'yi kendi dilinize çevirin — ideal bir ilk katkı
- 🧪 Ana dilinizdeki çevirileri test edip hataları bildirin
- 🐍 Python ile kod yazın — [`good first issue`](https://github.com/CooLSavaSs/glyphbridge/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) etiketli işlere bakın
- 📜 Dilbilimci, tarihçi ya da Mısırbilimciyseniz tarihî yazılar konusunda yardım edin

Ayrıntılar için [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Lisans

[Apache 2.0](../../LICENSE) — ticari kullanım dahil, özgürce kullanın, değiştirin ve paylaşın.
