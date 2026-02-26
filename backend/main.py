import os
import shutil
import zipfile
import logging
import json
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from models import (
    UploadResponse, AnalysisResponse, QueryRequest, QueryResponse, CodeSnippet
)
from indexer import CodeIndexer
from llm_client import LMStudioClient


# Request Logging Middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """HTTP istek/yanıt logging'i için middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Request detaylarını log et
        request_id = datetime.now().isoformat()
        content_type = request.headers.get('content-type', 'N/A')
        
        # GET ve POST isteklerini farklı şekilde log et
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Content-Type'ı kontrol et
                if 'multipart/form-data' in content_type or 'application/octet-stream' in content_type:
                    # Binary/Multipart data için - body'yi log etme
                    logger.info(
                        f"📨 [{request.method}] {request.url.path}\n"
                        f"   🔷 Content-Type: {content_type}\n"
                        f"   🔶 Body: [BINARY DATA - File Upload]"
                    )
                    # Body'yi oku ama discard et (middleware'nin stream'i tüketmesi sorunu için)
                    body = await request.body()
                    
                    async def receive():
                        return {"type": "http.request", "body": body}
                    
                    request._receive = receive
                else:
                    # JSON/Text data için - body'yi decode et ve log et
                    body = await request.body()
                    try:
                        body_str = body.decode('utf-8') if body else ""
                    except:
                        body_str = f"[BINARY DATA - {len(body)} bytes]"
                    
                    logger.info(
                        f"📨 [{request.method}] {request.url.path}\n"
                        f"   🔷 Content-Type: {content_type}\n"
                        f"   🔶 Body: {body_str[:300] if body_str else 'empty'}"
                    )
                    
                    # Body'yi tekrar attach et
                    async def receive():
                        return {"type": "http.request", "body": body}
                    
                    request._receive = receive
                    
            except Exception as e:
                logger.warning(f"⚠️  Request body okunamadı: {str(e)}")
        else:
            logger.info(f"📥 [{request.method}] {request.url.path}")
        
        # Response'u al
        response = await call_next(request)
        
        # Response'u log et
        logger.info(f"📤 [{response.status_code}] {request.url.path}")
        
        return response


# FastAPI uygulamasını oluştur
app = FastAPI(
    title="AI Kod Reviewer",
    description="Proje kodunu analiz eden ve sorulara cevap veren AI uygulaması",
    version="1.0.0"
)

# Middleware'leri ekle (sıra önemlidir - Request logging önce gelsin)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konfigürasyon (.env dosyasinden)
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 5000))
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:8000/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "mistral-7b-instruct-v0.3")

# Global nesneler
indexer = CodeIndexer()
llm_client = LMStudioClient(base_url=LMSTUDIO_BASE_URL, model=LMSTUDIO_MODEL)

# Yüklenen projelerin geçici depolama yolları
UPLOAD_DIR = tempfile.mkdtemp(prefix="aikodreviewer_")
PROJECT_STORE = {}  # {project_id: project_path}


@app.on_event("startup")
async def startup_event():
    """Uygulamayı başlat"""
    logger.info("=" * 60)
    logger.info("🚀 AI KOD REVIEWER BAŞLATILIYOR 🚀")
    logger.info("=" * 60)
    logger.info(f"Backend Port: {BACKEND_PORT}")
    logger.info(f"LMStudio URL: {LMSTUDIO_BASE_URL}")
    logger.info(f"Model: {LMSTUDIO_MODEL}")
    logger.info("=" * 60)
    
    # LMStudio bağlantısını kontrol et
    if llm_client.check_connection():
        logger.info("✅ LMStudio bağlantısı başarılı")
        models = llm_client.get_available_models()
        if models:
            logger.info(f"📦 Mevcut modeller: {models}")
    else:
        logger.warning("⚠️  LMStudio bağlanılamadı - Lütfen LMStudio'yu başlatın")
        logger.warning(f"   Bağlantı yoluyla: {LMSTUDIO_BASE_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulamayı kapat"""
    logger.info("=" * 60)
    logger.info("🛑 KAPATILIYOR... 🛑")
    logger.info("=" * 60)
    
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        logger.info(f"🧹 Geçici dosyalar temizlendi: {UPLOAD_DIR}")
    
    logger.info("✅ Güvenle kapatıldı")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("📍 Root endpoint ziyareti")
    return {
        "message": "AI Kod Reviewer API",
        "endpoints": {
            "upload": "POST /upload",
            "analyze": "POST /analyze",
            "query": "POST /query",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health_check():
    """Sistem sağlığını kontrol et"""
    lm_connected = llm_client.check_connection()
    projects_count = len(indexer.projects)
    
    logger.debug(f"🏥 Sağlık kontrolü: LMStudio={'✅' if lm_connected else '❌'}, Projeler={projects_count}")
    
    return {
        "status": "ok",
        "lm_studio": {
            "connected": lm_connected,
            "base_url": llm_client.base_url,
            "model": llm_client.model
        },
        "projects_loaded": projects_count
    }


@app.post("/upload")
async def upload_project(file: UploadFile = File(...)):
    """Proje dosyasını (zip) yükle"""
    try:
        logger.info(f"📦 Yükleme başladı: {file.filename} (Size: {file.size} bytes)")
        
        # Geçici dosya oluştur
        temp_file = os.path.join(UPLOAD_DIR, file.filename)
        
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"💾 Dosya kaydedildi: {temp_file}")
        
        # ZIP'i aç
        extract_dir = os.path.join(UPLOAD_DIR, Path(file.filename).stem)
        
        if zipfile.is_zipfile(temp_file):
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            logger.info(f"📂 ZIP açıldı: {extract_dir}")
        else:
            # Eğer ZIP değilse, klasör olarak kabul et
            extract_dir = temp_file
        
        # Projeyi indexle
        logger.info(f"🔍 Proje indeksleniyor: {extract_dir}")
        project_id, project_index = indexer.index_project(extract_dir)
        PROJECT_STORE[project_id] = extract_dir
        
        logger.info(
            f"✅ Yükleme başarılı!\n"
            f"   📋 Project ID: {project_id}\n"
            f"   📁 Dosya sayısı: {project_index.total_files}\n"
            f"   🎯 Desteklenen: {project_index.supported_files}\n"
            f"   💾 Kod elemanı: {len(project_index.elements)}\n"
            f"   🗣️  Diller: {', '.join(project_index.languages)}"
        )
        
        return UploadResponse(
            project_id=project_id,
            status="success",
            message="Proje başarıyla yüklendi",
            file_count=project_index.supported_files
        )
    
    except Exception as e:
        logger.error(f"❌ Yükleme hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Yükleme hatası: {str(e)}")


@app.post("/analyze")
async def analyze_project(project_id: str):
    """Yüklenen projeyi analiz et"""
    try:
        logger.info(f"🔍 Analiz başlıyor: {project_id}")
        
        if project_id not in indexer.projects:
            logger.error(f"❌ Proje bulunamadı: {project_id}")
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        project_index = indexer.get_project_index(project_id)
        
        logger.info(
            f"✅ Analiz tamamlandı: {project_id}\n"
            f"   📊 Toplam element: {len(project_index.elements)}\n"
            f"   🗣️  Diller: {', '.join(project_index.languages)}"
        )
        
        return AnalysisResponse(
            project_id=project_id,
            status="success",
            total_elements=len(project_index.elements),
            languages_detected=project_index.languages,
            message=f"{len(project_index.elements)} kod elementi bulundu"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analiz hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Analiz hatası: {str(e)}")


@app.post("/query")
async def query_project(request: QueryRequest):
    """Projeye soru sor"""
    try:
        logger.info(
            f"❓ Sorgu başladı:\n"
            f"   🆔 Project ID: {request.project_id}\n"
            f"   ❓ Soru: {request.question[:100]}..."
        )
        
        if request.project_id not in indexer.projects:
            logger.error(f"❌ Proje bulunamadı: {request.project_id}")
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        # Proje bilgisini hazırla (dil ve eleman sayıları)
        project_index = indexer.get_project_index(request.project_id)
        lang_counts = {}
        for element in project_index.elements:
            lang_counts[element.language] = lang_counts.get(element.language, 0) + 1
        lang_summary = ", ".join(
            f"{lang}:{count}" for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])
        )
        project_meta = (
            "PROJE BILGISI:\n"
            f"Toplam dosya: {project_index.total_files}\n"
            f"Desteklenen dosya: {project_index.supported_files}\n"
            f"Diller: {', '.join(project_index.languages)}\n"
            f"Kod elemani sayisi (dillere gore): {lang_summary}\n"
        )

        # İlgili kod elementlerini ara
        relevant_elements = indexer.search_elements(request.project_id, request.question)
        logger.info(f"🔎 {len(relevant_elements)} ilgili kod elemanı bulundu")
        
        # Kod snippet'larını topla (daha fazla snippet)
        code_snippets = [
            CodeSnippet(
                file_path="PROJECT_METADATA",
                start_line=1,
                end_line=1,
                code=project_meta,
                element_name="project_metadata"
            )
        ]
        
        # En fazla 15 element göndermek için
        for element in relevant_elements[:15]:
            snippet = indexer.get_code_snippet(
                request.project_id,
                element.file_path,
                element.start_line,
                element.end_line
            )
            if snippet:
                code_snippets.append(snippet)
        
        logger.info(f"📝 {len(code_snippets)} kod snippet'ı toplandı")
        
        # LMStudio'ya soru sor
        logger.info("🤖 LMStudio'ya sorgu gönderiliyor...")
        answer, processing_time = llm_client.query_with_context(
            request.question,
            code_snippets
        )
        
        logger.info(f"✅ LMStudio cevap verdi ({processing_time:.2f}s)")
        logger.info(f"📢 Cevap: {answer[:150]}...")
        
        # Referansları çıkart
        element_dicts = [
            {
                "name": e.name,
                "file_path": e.file_path,
                "type": e.type,
                "start_line": e.start_line,
                "end_line": e.end_line
            }
            for e in relevant_elements
        ]
        references = llm_client.extract_references_from_response(
            request.question,
            element_dicts,
            answer
        )
        
        logger.info(f"🔗 {len(references)} referans bulundu")
        
        return QueryResponse(
            answer=answer,
            references=references,
            model_used=llm_client.model,
            processing_time=processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Sorgu hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Sorgu hatası: {str(e)}")


@app.get("/projects")
async def list_projects():
    """Yüklenen projeleri listele"""
    projects = []
    for project_id, project_index in indexer.projects.items():
        projects.append({
            "project_id": project_id,
            "languages": project_index.languages,
            "total_files": project_index.total_files,
            "total_elements": len(project_index.elements)
        })
    
    logger.info(f"📚 {len(projects)} proje listelendi")
    
    return {"projects": projects}


if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=BACKEND_HOST, help="Backend host")
    parser.add_argument("--port", type=int, default=BACKEND_PORT, help="Backend port")
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)
