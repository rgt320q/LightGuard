![lightguard_logo](https://github.com/user-attachments/assets/8bd7e70c-12f0-4a2d-9723-2c149c6ae005)

LightGuard
🔆 Göz Sağlığı Odaklı Akıllı Monitör Parlaklık ve Kontrast Ayarlama Uygulaması

📌 Tanıtım
LightGuard, monitör parlaklığını ve kontrastını gün ışığı koşullarına göre otomatik ayarlayan bir Windows uygulamasıdır.
Gündüz parlaklığı artırarak netlik sağlar, gece göz yorgunluğunu önlemek için ekran ışığını azaltır.

🚀 Özellikle uyku sonrası monitör ışığı otomatik olarak geri yüklenir!

🔧 Özellikler
✅ Göz Sağlığını Koruma: Monitör ışığını gündüz/gece durumuna göre otomatik ayarlar
✅ Uyku Sonrası Parlaklık Geri Yükleme: Sistemi uyandırdıktan sonra önceki parlaklık ayarlarını uygular
✅ Sistem Tepsi İkonu ile Yönetim: Arka planda çalışarak pratik bir kullanım sunar
✅ DDC/CI Desteği Kontrolü: Eğer monitör desteklemiyorsa, kullanıcıya mesaj gösterir

📌 Kurulum Adımları
1️⃣ Gerekli Bağımlılıkları Yükle
LightGuard çalıştırılmadan önce aşağıdaki kütüphanelerin yüklenmesi gerekmektedir:
Tüm kütüphaneler için requirements.txt dosyası oluşturulmuştur.
Projeyi indirdikten sonra 
"pip install -r requirements.txt"

2️⃣ Uygulamayı Çalıştır
Python scriptini çalıştırarak sistemi başlatabilirsin:
python lightguard.py

3️⃣ Sistem Tepsi Arayüzü ile Kullanım
LightGuard, sistem tepsisinde küçük bir ikon olarak çalışır ve burada parlaklık ile kontrast ayarlarını kontrol edebilirsin.

🎯 Kullanım Talimatları

1️⃣ Gündüz/Gece Ayarı
- LightGuard, gün ışığını baz alarak parlaklık seviyesini otomatik değiştirir.
- Kullanıcı tarafından manuel olarak parlaklık ve kontrast ayarlanabilir.

2️⃣ Uyku Modundan Sonra Parlaklık Geri Yükleme
💡 LightGuard, sistem uyku moduna geçtiğinde parlaklık değerlerini kaydeder ve uyandıktan sonra otomatik olarak uygular.

🔥 Olası Sorunlar ve Çözümler

1️⃣ Uyandıktan Sonra Ayarlar Uygulanmıyor
🔹 Windows Event Log üzerinden uyandırma olaylarını takip ettiğimizden, bazen sistemin uyandığını tam olarak algılamayabilir.
✅ Çözüm: Ayarların uygulanması için uygulamayı yeniden başlat.

2️⃣ DDC/CI Hatası
🔹 Eğer uygulama başlatıldığında "Bu monitör DDC/CI desteklemiyor" hatası alıyorsanız:
✅ Çözüm: Monitörün DDC/CI desteğini açmayı deneyin veya alternatif olarak Windows API ile parlaklık kontrolü yapabilirsiniz.

📌 Geliştirici Bilgileri
🚀 LightGuard, göz sağlığını koruyan ekran parlaklık optimizasyonu sağlamak için geliştirildi.
📌 Geliştirici: Ömer
📌 Versiyon: 1.0.0
📌 Platform: Windows
