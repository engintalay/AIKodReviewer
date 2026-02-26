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
    UploadResponse, AnalysisResponse, QueryRequest, QueryResponse, CodeSnippet,
    SaveProjectRequest, LoginRequest
)
from indexer import CodeIndexer
from llm_client import LMStudioClient
from storage import Storage
from vector_store import VectorStore


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
LMSTUDIO_CONTEXT_LENGTH = int(os.getenv("LMSTUDIO_CONTEXT_LENGTH", 4096))

# Global nesneler
indexer = CodeIndexer()
llm_client = LMStudioClient(base_url=LMSTUDIO_BASE_URL, model=LMSTUDIO_MODEL, context_length=LMSTUDIO_CONTEXT_LENGTH)
storage = Storage()
vector_store = VectorStore()

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
        
        # Vector DB'ye indexle
        logger.info(f"🧠 Vector DB'ye indeksleniyor...")
        vector_store.index_project(
            project_id, 
            project_index.elements,
            indexer.code_snippets.get(project_id, {})
        )
        logger.info(f"✅ Vector DB indeksleme tamamlandı")
        
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

        # İlgili kod elementlerini ara (önceki sohbetten context ile)
        previous_elements = []
        if request.chat_history:
            for msg in request.chat_history[-2:]:
                if msg.get("references"):
                    previous_elements.extend([ref.get("element") for ref in msg.get("references", [])])
        
        # Vector search ile semantic arama
        logger.info("🔍 Vector search yapılıyor...")
        vector_results = vector_store.search(request.project_id, request.question, n_results=5)
        
        all_elements_data = []
        
        if vector_results:
            main_element_name = vector_results[0]['metadata']['name']
            logger.info(f"🎯 Ana element: {main_element_name}")
            
            # Ana element ve bağımlılıklarını getir
            deps_chain = vector_store.get_element_with_dependencies(
                request.project_id, 
                main_element_name, 
                max_depth=2
            )
            logger.info(f"🔗 {len(deps_chain)} element (bağımlılıklarla) bulundu")
            all_elements_data = deps_chain
        else:
            # Fallback: keyword search
            logger.info("⚠️ Vector search sonuç vermedi")
            relevant_elements = indexer.search_elements(
                request.project_id, 
                request.question, 
                search_mode=request.search_mode, 
                previous_elements=previous_elements
            )
            all_elements_data = [{"metadata": {
                "name": e.name,
                "type": e.type,
                "file_path": e.file_path,
                "start_line": e.start_line,
                "end_line": e.end_line,
                "dependencies": ""
            }, "depth": 0} for e in relevant_elements[:5]]
        
        logger.info(f"🔎 Toplam {len(all_elements_data)} kod elemanı bulundu")
        
        # Kod snippet'larını topla (kontekst boyutunu kontrol etmeyi etkinleştir)
        code_snippets = [
            CodeSnippet(
                file_path="PROJECT_METADATA",
                start_line=1,
                end_line=1,
                code=project_meta,
                element_name="project_metadata"
            )
        ]
        
        # İlgili elementlerin listesini ekle (snippet olmadan)
        if relevant_elements:
            elements_summary = "İLGİLİ KOD ELEMENTLERİ:\n"
            for i, elem in enumerate(relevant_elements[:20], 1):
                elements_summary += f"{i}. {elem.name} ({elem.type}) - {elem.file_path.split('/')[-1]}\n"
            if len(relevant_elements) > 20:
                elements_summary += f"... ve {len(relevant_elements) - 20} element daha\n"
            
            code_snippets.append(CodeSnippet(
                file_path="ELEMENTS_SUMMARY",
                start_line=1,
                end_line=1,
                code=elements_summary,
                element_name="elements_summary"
            ))
        
        # En fazla 3 element snippet göndermek için (context size kontrolü için)
        for element in relevant_elements[:3]:
            snippet = indexer.get_code_snippet(
                request.project_id,
                element.file_path,
                element.start_line,
                element.end_line
            )
            if snippet:
                code_snippets.append(snippet)
        
        logger.info(f"📝 {len(code_snippets)} kod snippet'ı toplandı")
        
        # LMStudio'ya soru sor (context kontrolü ile)
        logger.info("🤖 LMStudio'ya sorgu gönderiliyor...")
        answer, processing_time = llm_client.query_with_context(
            request.question,
            code_snippets,
            max_tokens=500,
            max_context_chars=8000,
            chat_history=request.chat_history
        )
        
        logger.info(f"✅ LMStudio cevap verdi ({processing_time:.2f}s)")
        logger.info(f"📢 Cevap: {answer[:150]}...")
        
        # Referansları çıkart
        element_dicts = [
            {
                "name": e['metadata']['name'],
                "file_path": e['metadata']['file_path'],
                "type": e['metadata']['type'],
                "start_line": e['metadata']['start_line'],
                "end_line": e['metadata']['end_line']
            }
            for e in all_elements_data
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


@app.post("/get_snippet")
async def get_snippet(request: dict):
    """Kod snippet'ını getir"""
    try:
        project_id = request.get("project_id")
        file_path = request.get("file_path")
        start_line = request.get("start_line")
        end_line = request.get("end_line")
        
        if not all([project_id, file_path, start_line, end_line]):
            raise HTTPException(status_code=400, detail="Eksik parametreler")
        
        snippet = indexer.get_code_snippet(project_id, file_path, start_line, end_line)
        
        if not snippet:
            raise HTTPException(status_code=404, detail="Snippet bulunamadı")
        
        return {
            "code": snippet.code,
            "file_path": snippet.file_path,
            "start_line": snippet.start_line,
            "end_line": snippet.end_line
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Snippet hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Snippet hatası: {str(e)}")


@app.post("/login")
async def login(request: LoginRequest):
    """Kullanıcı girişi"""
    # Önce kullanıcı var mı kontrol et
    if storage.verify_user(request.username, request.password):
        return {"status": "success", "username": request.username}
    
    # Kullanıcı yoksa, şifre ile yeni kullanıcı oluştur
    users = json.loads(storage.USERS_FILE.read_text())
    if request.username not in users:
        if storage.create_user(request.username, request.password):
            logger.info(f"👤 Yeni kullanıcı: {request.username}")
            return {"status": "success", "username": request.username, "new_user": True}
    
    raise HTTPException(status_code=401, detail="Şifre yanlış")


@app.post("/save_project")
async def save_project(request: SaveProjectRequest):
    """Projeyi kaydet"""
    try:
        if request.project_id not in indexer.projects:
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        project_index = indexer.get_project_index(request.project_id)
        project_path = PROJECT_STORE.get(request.project_id, "")
        
        storage.save_project(
            request.project_id,
            request.username,
            request.project_name,
            project_path,
            request.is_private,
            {
                "total_files": project_index.total_files,
                "supported_files": project_index.supported_files,
                "languages": project_index.languages,
                "total_elements": len(project_index.elements)
            }
        )
        
        logger.info(f"💾 Proje kaydedildi: {request.project_name} (User: {request.username}, ID: {request.project_id})")
        return {"status": "success", "message": "Proje kaydedildi"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Kaydetme hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Kaydetme hatası: {str(e)}")


@app.get("/saved_projects/{username}")
async def get_saved_projects(username: str):
    """Kullanıcının kayıtlı projelerini getir"""
    projects = storage.get_user_projects(username)
    return {"projects": projects}


@app.post("/load_project/{project_id}")
async def load_project(project_id: str):
    """Kayıtlı projeyi yükle"""
    try:
        project_data = storage.get_project(project_id)
        if not project_data:
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        project_path = project_data["project_path"]
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Proje dosyaları bulunamadı")
        
        # Projeyi indexle
        _, project_index = indexer.index_project(project_path)
        PROJECT_STORE[project_id] = project_path
        
        logger.info(f"📂 Proje yüklendi: {project_data['project_name']}")
        return {
            "status": "success",
            "project_id": project_id,
            "project_name": project_data["project_name"],
            "metadata": project_data["metadata"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Yükleme hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Yükleme hatası: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=BACKEND_HOST, help="Backend host")
    parser.add_argument("--port", type=int, default=BACKEND_PORT, help="Backend port")
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)
