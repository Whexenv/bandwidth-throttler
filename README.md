# ⚡ Bandwidth Limiter (Görev Yöneticisi & Ağ Hız Kısıtlayıcı)

Windows için **Görev Yöneticisi** mantığıyla çalışan, arka planda hangi uygulamanın (Chrome, setup kurulumları, oyun istemcileri, vb.) ne kadar internet kullandığını canlı gösteren ve **tek tıkla seçtiğiniz uygulamanın internet hızını kısıtlamanızı** sağlayan modern masaüstü uygulaması.

---

## 🚀 Temel Özellikler

1. **📊 Canlı Görev Yöneticisi (Ağ Takibi):**
   - Bilgisayarda o an açık olan veya internet kullanan tüm uygulamaları listeler.
   - Her uygulamanın **Anlık İndirme Hızı (⬇ KB/s, MB/s)**, **Anlık Yükleme Hızı (⬆ KB/s)**, **Aktif TCP Bağlantı Sayısı** ve **Toplam Veri Transferini** saniyelik güncellemelerle gösterir.
   - En çok internet kullanan uygulamalar otomatik olarak en üste sıralanır.

2. **🎯 Tek Tıkla Uygulama Hızını Kısıtlama:**
   - Listeden hızını kısmak istediğiniz uygulamaya (`chrome.exe`, `setup.exe`, `steam.exe` vb.) tıklayın.
   - İstediğiniz hız limitini belirleyin (örneğin: `500 KB/s` veya `2 MB/s`).
   - **"⚡ Hızı Kısıtla"** butonuna basın; Windows Ağ İlkesi (QoS) üzerinden uygulamanın internet hızı anında kısıtlanır.

3. **🔍 Hızlı Arama ve Filtreleme:**
   - İsim veya uzantı ile arama çubuğundan anında arama yapabilirsiniz (örn: `setup`, `chrome`, `steam`).
   - *"Sadece Ağ Trafiği Olanlar"* filtresi ile boşta duran süreçleri gizleyip sadece aktif indirme yapanları görebilirsiniz.

4. **🛡️ Windows QoS Entegrasyonu:**
   - Harici riskli sürücüler yerine doğrudan Microsoft Windows Ağ İlkeleri (NetQosPolicy) ile güvenli ve kararlı hız sınırlama uygular.
   - İstenildiğinde tek tıkla sınır kaldırılabilir veya *"Tüm Limitleri Sıfırla"* butonuyla tüm kurallar temizlenebilir.

5. **🔗 Doğrudan URL İndirici (Opsiyonel Sekme):**
   - İstenirse tekil doğrudan bağlantıları indirip gerçek zamanlı neon grafikle takip edebileceğiniz indirme motoru da mevcuttur.

---

## 🛠️ Kurulum & Çalıştırma

### Gereksinimleri Yükleyin:
```bash
pip install -r requirements.txt
```

### Uygulamayı Başlatın:
```bash
python run.py
```
*(Veya masaüstünüzdeki **"Bandwidth Throttler"** kısayoluna çift tıklayarak konsolsuz başlatabilirsiniz).*
