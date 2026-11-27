# GitHub Actions Kaynak ve Maliyet Koruma Raporu

**Proje:** CooLSavaSs/glyphbridge  
**Tarih:** 25 Kasım 2026  
**Değişiklik dalı:** `chore/actions-resource-guardrails`  
**Durum:** Değişiklikler ayrı dala işlendi; ana dala henüz birleştirilmedi. Pull Request ve CI doğrulaması bekleniyor.

## 1. Başlangıçta tespit edilen durum

- Depo herkese açık (`public`).
- CI, Cards ve FLORES iş akışları standart `ubuntu-latest` runner kullanıyor.
- Cards ve FLORES ayrı concurrency gruplarındaydı; ağır model indirme/çıkarım işleri eşzamanlı başlayabiliyordu.
- CI içindeki gerçek çeviri smoke testi, ağır model kullanmasına rağmen ayrı bir kaynak kilidi kullanmıyordu.
- Cards iş akışındaki dört ağır job birbirinden bağımsızdı; aynı workflow içinde paralel çalışabiliyorlardı.
- İncelenen üç workflow dosyasında `actions/upload-artifact` adımı bulunmadı. Bu nedenle bu dosyaların ürettiği saklanan Actions artifact'leri için retention süresi ayarlanacak bir yükleme adımı mevcut değildi.

## 2. Yapılan değişiklikler

### Ortak ağır iş kilidi

Cards, FLORES ve CI gerçek model smoke testi aynı concurrency grubuna alındı:

`glyphbridge-heavy-models`

`cancel-in-progress: false` kullanıldı. Böylece devam eden ağır test yeni bir commit geldi diye otomatik iptal edilmiyor; aynı gruptaki işler sıraya alınabiliyor. GitHub concurrency davranışı aynı grup için bir çalışan ve en fazla bir bekleyen çalışmaya izin verir; daha fazla bekleyen tetikleme önceki bekleyeni değiştirebilir.

### Süre sınırları

| Workflow / job | Süre sınırı |
|---|---:|
| CI unit tests | 20 dakika |
| CI gerçek çeviri smoke testi | 60 dakika |
| Cards: small-cards | 120 dakika |
| Cards: MADLAD | 120 dakika |
| Cards: TranslateGemma full | 180 dakika |
| Cards: small-8gb | 180 dakika |
| FLORES | 340 dakika (mevcut sınır korundu) |

30 dakika her test için uygulanmadı. Model indirme ve çok dilli FLORES değerlendirmesi için bu sınır gerçekçi olmayabilir ve yararlı testleri gereksiz yere kesebilir.

### Cards job sıralaması

Ağır Cards işleri şu sıraya alındı:

1. small-cards
2. MADLAD
3. TranslateGemma full
4. small-8gb

TranslateGemma gated job'u `HF_TOKEN` yoksa atlanabildiğinden, son job'un bu normal atlanma durumunda yine çalışabilmesi için koşul eklendi. Önceki zorunlu işler başarısızsa son job çalışmaz.

## 3. Artifact ve depolama

İncelenen `.github/workflows/ci.yml`, `.github/workflows/cards.yml` ve `.github/workflows/flores.yml` dosyalarında artifact yükleme adımı bulunmadı. Bu nedenle rastgele bir retention ayarı eklenmedi ve eski artifact'ler silinmedi.

İleride JSON benchmark raporları veya log çıktıları Actions artifact olarak yüklenirse, `actions/upload-artifact` adımına örneğin `retention-days: 7` eklenebilir. Bu değişiklik, artifact gerçekten kullanılmaya başlandığında yapılmalıdır.

## 4. Maliyet hakkında not

Public depoda standart GitHub-hosted runner kullanımı için GitHub Actions dakika ücretlendirmesi uygulanmaz. Bununla birlikte:
- Larger runner veya farklı ücretli hizmetler ayrı kurallara tabi olabilir.
- Artifact depolaması ve diğer GitHub ürünlerinin limitleri ayrıca değerlendirilmelidir.
- Bu düzenlemeler maliyeti azaltmaktan çok gereksiz paralelliği, beklenmedik kaynak tüketimini ve test çakışmasını önlemeye yöneliktir.

## 5. Henüz yapılmayanlar / doğrulama

- Değişiklikler `main` dalına birleştirilmedi.
- Pull Request açıldıktan sonra CI'nin çalışması ve YAML/workflow davranışının doğrulanması gerekiyor.
- Bu rapor hazırlanırken yeni workflow çalıştırmalarının tamamlandığı iddia edilmiyor.
- Halihazırda çalışan eski bir FLORES/Card run'ı, yeni concurrency grubuna otomatik olarak taşınmaz veya durdurulmaz.

## 6. Değişen dosyalar

- `.github/workflows/ci.yml`
- `.github/workflows/cards.yml`
- `.github/workflows/flores.yml`

## 7. Önerilen sonraki adım

Pull Request kontrolleri başarılı olduktan sonra PR'ı gözden geçirip `main` dalına birleştirmek. Artifact üretimi eklendiğinde 7 günlük saklama süresini ayrıca uygulamak.
