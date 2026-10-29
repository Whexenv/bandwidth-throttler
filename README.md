# ⚡ Bandwidth Throttler (İndirme Hızı Sınırlayıcı)

Modern arayüze (CustomTkinter) sahip, girilen indirme bağlantılarını (URL) kullanıcının belirlediği bant genişliği limitine (KB/s veya MB/s) göre dinamik olarak sınırlandırıp indiren masaüstü uygulaması.

---

## 🚀 Temel Özellikler

- **Hassas Hız Sınırlama (Throttling)**: `time.perf_counter()` ve dinamik boyutlandırılan chunk'lar ile mikro gecikmeler (`time.sleep`) hesaplayarak istenen indirme hızını hassasiyetle korur.
- **Dinamik Hız Değişimi**: İndirme devam ederken arayüzdeki hız çubuğu (slider) veya girdi kutusu üzerinden hız limitini anında artırıp azaltabilirsiniz; indirmeyi baştan başlatmanız gerekmez.
- **Gerçek Zamanlı Hız Grafiği (Canvas)**: Anlık indirme hızını ve hedef limit çizgisini 60 FPS akıcı ve neon temalı vektörel grafik üzerinde gösterir.
- **Duraklat / Devam Et / İptal Et**: İndirmeyi dilediğiniz zaman beklemeye alabilir, devam ettirebilir ya da iptal edebilirsiniz.
- **Modern Görsel Tasarım**: Windows 11 uyumlu modern kart tasarımı, Karanlık (Dark) ve Aydınlık (Light) tema geçiş desteği.
- **Detaylı Telemetri**: İlerleme yüzdesi, indirilen/toplam bayt, anlık hız, ortalama hız, geçen süre ve tahmini kalan süre (ETA).
- **Hızlı Test Desteği**: Tek tıkla Cloudflare 25 MB test dosyasını yükleyip hız sınırlandırmayı anında deneme imkanı.

---

## 📁 Proje Dosya Yapısı

```
bandwidth_throttler/
│
├── core/
│   ├── __init__.py           # Çekirdek modül tanımları
│   ├── downloader.py         # Thread tabanlı indirme motoru ve hız sınırlama mantığı
│   └── utils.py              # Boyut, hız ve süre formatlama yardımcı fonksiyonları
│
├── ui/
│   ├── __init__.py           # Arayüz modül tanımları
│   ├── app.py                # CustomTkinter ana pencere ve olay yöneticisi
│   └── speed_graph.py        # Akıcı, vektörel gerçek zamanlı hız grafiği bileşeni
│
├── requirements.txt          # Gerekli Python kütüphaneleri
├── run.py                    # Uygulamayı başlatan ana giriş dosyası
└── README.md                 # Detaylı dökümantasyon
```

---

## 🧠 Hız Sınırlama (Throttling) Çalışma Mantığı

Hız sınırlama, HTTP akışından parça parça (`chunk`) veri çekerken geçen süreyi ve bu verinin hedeflenen hızda ne kadar sürede inmesi gerektiğini hesaplama prensibine dayanır:

1. **Dinamik Parça Boyutu (Chunk Size)**:  
   Hedeflenen hız $R$ (bayt/saniye) olsun. Veri akışının takılmadan ve arayüzün saniyede 15-20 kez güncellenebilmesi için chunk boyutu otomatik ayarlanır:
   $$\text{chunk\_size} = \text{clamp}\left(1024, \frac{R}{15}, 65536\right)$$

2. **Gecikme (Sleep) Hesabı**:  
   Okunan veri boyutu $L$ bayt ve soketten okunurken geçen süre $\Delta t_{\text{read}}$ saniye ise, bu verinin hedef hızda indirilmesi gereken süre:
   $$T_{\text{hedef}} = \frac{L}{R}$$
   Eğer verinin okunması hedeflenen süreden daha kısa sürdüyse, aradaki fark kadar işlemci uyutulur (`time.sleep`):
   $$\text{sleep\_time} = T_{\text{hedef}} - \Delta t_{\text{read}}$$

3. **Duyarlı Uyku Döngüsü**:  
   Uzun süreli tek bir `sleep` yerine 15 milisaniyelik mikro dilimler kullanılır. Bu sayede kullanıcı **"Duraklat"**, **"İptal"** veya **"Hız Değiştir"** yaptığında uygulama beklemeden anında tepki verir.

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Gereksinimleri Yükleyin:
```bash
pip install -r requirements.txt
```

### 2. Uygulamayı Başlatın:
```bash
python run.py
```

---

## 🧪 Test Etme
1. Uygulamayı açın.
2. **"Örnek URL"** butonuna tıklayarak test bağlantısını otomatik doldurun.
3. Hız limitini örneğin **300 KB/s** olarak belirleyin.
4. **"İndirmeyi Başlat"** butonuna basın.
5. Grafikte hızın hızla 300 KB/s seviyesine oturmasını ve sabit kalmasını izleyin.
6. İndirme sürerken kaydırma çubuğunu (slider) 1 MB/s veya 100 KB/s seviyesine çekerek hız limitinin anında dinamik olarak güncellenmesini gözlemleyin.

