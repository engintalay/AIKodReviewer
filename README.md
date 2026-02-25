# 🤖 AI Kod Reviewer

Yazılım projelerinizi analiz eden ve kod hakkında sorular sormanıza olanak sağlayan AI destekli bir uygulamadır.

## ✨ Özellikler

- 💻 **Çoklu Dil Desteği**: Python, JavaScript, TypeScript, Java, PHP, HTML, CSS ve daha fazlası
- 🧠 **Çalışması**: Mistral 7B (local LMStudio) - kaynak tasarruflu, hızlı
- 📚 **Kod İndeksleme**: Tree-sitter AST parsing ile hızlı ve doğru arama
- 🔍 **Kaynakça**: Her cevaba hangi dosyadan esinlenildiğini gösteren referanslar
- 🌐 **Web Arayüzü**: Streamlit tabanlı, kullanıcı dostu chat interface
- 🚀 **API**: FastAPI tabanlı RESTful backend

## 📋 Gereksinimler

### Donanım
- GPU: NVIDIA (CUDA kompatible) veya CPU
- RAM: Minimum 4 GB (8 GB önerilir)
- VRAM: T1000 gibi 1.2-4 GB VRAM

### Yazılım
- Python 3.8+
- LMStudio (http://localhost:8000)
- pip

## 🚀 Kurulum

### 1. LMStudio Kurulumu

1. [LMStudio](https://lmstudio.ai/) indirin ve kurun
2. Aşağıdaki modeli indirin:
   - **Mistral 7B Instruct v0.3** (GGUF Q4 quantized - ~1.2 GB)
3. LMStudio'da **Local Server** başlatın (varsayılan port: 8000)

### 2. Proje Kurulumu

```bash
# Depoyu klonla
cd /home/engin/projects/AIKodReviewer

# Backend kurulumu
cd backend
pip install -r requirements.txt

# Frontend kurulumu
cd ../frontend
pip install -r requirements.txt
```

### 3. Konfigürasyon

`.env` dosyasını açın ve gerekirse ayarları yapın:

```env
LMSTUDIO_BASE_URL=http://localhost:8000/v1
LMSTUDIO_MODEL=mistral-7b-instruct-v0.3
BACKEND_URL=http://localhost:5000
```

## 🏃 Çalıştırma

### Terminal 1: Backend

```bash
cd backend
python main.py
```

Backend `http://localhost:5000` adresinde başlayacak.

### Terminal 2: Frontend

```bash
cd frontend
streamlit run app.py
```

Frontend `http://localhost:8501` adresinde açılacak.

### LMStudio

LMStudio'yu çalıştırın ve **Local Server** seçeneğini etkinleştirin (port 8000).

## 📖 Kullanım

1. **Web arayüzünü aç**: `http://localhost:8501`
2. **Proje yükle**: ZIP dosyasını yükle veya yerel klasör yolunu gir
3. **Analiz et**: Proje otomatik olarak indekslenir
4. **Soru sor**: Chat kutusunda kod hakkında sorular sor
5. **Cevap ve referans görüntüle**: AI modeli cevaplar ve kaynakça gösterir

### Örnek Sorular

- "Bu projede main fonksiyonu nerede tanımlanmış?"
- "DatabaseConnection class'ı nasıl kullanılıyor?"
- "API endpoints'leri nelerdir?"
- "Error handling nasıl yapılmış?"

## 🏗️ Proje Yapısı

```
AIKodReviewer/
├── backend/
│   ├── main.py              # FastAPI uygulaması
│   ├── indexer.py           # Tree-sitter kod indexer
│   ├── llm_client.py        # LMStudio API wrapper
│   ├── models.py            # Pydantic veri modelleri
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── app.py               # Streamlit arayüzü
│   └── requirements.txt      # Frontend dependencies
├── .env                      # Konfigürasyon dosyası
└── README.md               # Bu dosya
```

## 🔌 API Endpoints

### Backend API

#### `POST /upload`
Proje dosyasını (ZIP) yükle

```bash
curl -X POST -F "file=@project.zip" http://localhost:5000/upload
```

**Yanıt:**
```json
{
  "project_id": "abc123def456",
  "status": "success",
  "message": "Proje başarıyla yüklendi",
  "file_count": 45
}
```

#### `POST /analyze`
Yüklenen projeyi analiz et

```bash
curl -X POST http://localhost:5000/analyze?project_id=abc123def456
```

#### `POST /query`
Projeye soru sor

```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "abc123def456",
    "question": "Main fonksiyonu nerede?",
    "include_snippets": true
  }'
```

**Yanıt:**
```json
{
  "answer": "Main fonksiyonu app.py dosyasında 45. satırda tanımlanmıştır...",
  "references": [
    {
      "file": "app.py",
      "element": "main",
      "type": "function",
      "lines": [45, 62]
    }
  ],
  "model_used": "mistral-7b-instruct-v0.3",
  "processing_time": 2.34
}
```

#### `GET /health`
Sistem sağlığını kontrol et

```bash
curl http://localhost:5000/health
```

## 🧠 Desteklenen Diller

Tree-sitter aracılığıyla desteklenen diller:

- ✅ Python
- ✅ JavaScript / TypeScript
- ✅ Java
- ✅ PHP
- ✅ HTML
- ✅ CSS
- ✅ C / C++
- ✅ Go
- ✅ Rust
- *ve daha fazlası...*

## ⚙️ Gelişmiş Konfigürasyon

### LMStudio Port'unu Değiştirme

`.env` dosyasında:
```env
LMSTUDIO_BASE_URL=http://localhost:9000/v1
```

### Backend Port'unu Değiştirme

`.env` dosyasında:
```env
BACKEND_PORT=5001
```

Sonra:
```bash
python backend/main.py --port 5001
```

### Farklı Model Kullanma

`.env` dosyasında:
```env
LMSTUDIO_MODEL=neural-chat-7b-v3-1
```

## 🐛 Sorun Giderme

### "LMStudio'ya bağlanılamıyor"
- LMStudio çalışıyor mu kontrol et
- Port 8000 kullanılıyor mu kontrol et
- `.env` dosyasında `LMSTUDIO_BASE_URL` kontrolü

### "Tree-sitter parsing hatası"
- Tree-sitter kütüphaneleri kurulu mu kontrol et
- `pip install tree-sitter tree-sitter-python ...`

### "Proje işleme süresi uzun"
- Büyük projeler daha fazla zaman alır
- Model yanıt süresi kontrol et (LMStudio ayarları)

## 📊 Performans

- **Küçük projeler** (<1000 dosya): ~2-5 saniye
- **Orta projeler** (1000-5000 dosya): ~5-15 saniye
- **Büyük projeler** (>5000 dosya): ~15-60 saniye
- **Model yanıt süresi**: Mistral 7B Q4 ~1-3 saniye (GPU hızlı, CPU yavaş)

## 🔐 Güvenlik Notu

- LMStudio local çalışır, veriler internet'e gitmez
- Yüklenen dosyalar geçici olarak depolanır ve işlem sonrası silinir
- CORS tüm origins'e açıktır (development için)

## 📝 Lisans

MIT

## 🤝 Katkıdalar

Katkılar hoş karşılanır! Issues ve Pull Requests açabilirsiniz.

## 📧 İletişim

Sorular ve öneriler için issues açınız.

---

**Yapımcı**: AI Kod Reviewer Team
**Son Güncelleme**: 25 Şubat 2026
