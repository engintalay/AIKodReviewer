import os
import shutil
import zipfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path

from models import (
    UploadResponse, AnalysisResponse, QueryRequest, QueryResponse
)
from indexer import CodeIndexer
from llm_client import LMStudioClient

# FastAPI uygulamasını oluştur
app = FastAPI(
    title="AI Kod Reviewer",
    description="Proje kodunu analiz eden ve sorulara cevap veren AI uygulaması",
    version="1.0.0"
)

# CORS middleware'i ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global nesneler
indexer = CodeIndexer()
llm_client = LMStudioClient()

# Yüklenen projelerin geçici depolama yolları
UPLOAD_DIR = tempfile.mkdtemp(prefix="aikodreviewer_")
PROJECT_STORE = {}  # {project_id: project_path}


@app.on_event("startup")
async def startup_event():
    """Uygulamayı başlat"""
    print("🚀 AI Kod Reviewer başlatılıyor...")
    
    # LMStudio bağlantısını kontrol et
    if llm_client.check_connection():
        print("✅ LMStudio bağlantısı başarılı")
        models = llm_client.get_available_models()
        if models:
            print(f"📦 Mevcut modeller: {models}")
    else:
        print("⚠️ LMStudio bağlanılamadı - Lütfen LMStudio'yu başlatın (http://localhost:8000)")


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulamayı kapat"""
    print("🛑 Temizlik yapılıyor...")
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    print("✅ Kapalı")


@app.get("/")
async def root():
    """Root endpoint"""
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
    
    return {
        "status": "ok",
        "lm_studio": {
            "connected": lm_connected,
            "base_url": llm_client.base_url,
            "model": llm_client.model
        },
        "projects_loaded": len(indexer.projects)
    }


@app.post("/upload")
async def upload_project(file: UploadFile = File(...)):
    """Proje dosyasını (zip) yükle"""
    try:
        # Geçici dosya oluştur
        temp_file = os.path.join(UPLOAD_DIR, file.filename)
        
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # ZIP'i aç
        extract_dir = os.path.join(UPLOAD_DIR, Path(file.filename).stem)
        
        if zipfile.is_zipfile(temp_file):
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        else:
            # Eğer ZIP değilse, klasör olarak kabul et
            extract_dir = temp_file
        
        # Projeyi indexle
        project_id, project_index = indexer.index_project(extract_dir)
        PROJECT_STORE[project_id] = extract_dir
        
        return UploadResponse(
            project_id=project_id,
            status="success",
            message="Proje başarıyla yüklendi",
            file_count=project_index.supported_files
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Yükleme hatası: {str(e)}")


@app.post("/analyze")
async def analyze_project(project_id: str):
    """Yüklenen projeyi analiz et"""
    try:
        if project_id not in indexer.projects:
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        project_index = indexer.get_project_index(project_id)
        
        return AnalysisResponse(
            project_id=project_id,
            status="success",
            total_elements=len(project_index.elements),
            languages_detected=project_index.languages,
            message=f"{len(project_index.elements)} kod elementi bulundu"
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analiz hatası: {str(e)}")


@app.post("/query")
async def query_project(request: QueryRequest):
    """Projeye soru sor"""
    try:
        if request.project_id not in indexer.projects:
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        # İlgili kod elementlerini ara
        relevant_elements = indexer.search_elements(request.project_id, request.question)
        
        # Kod snippet'larını topla
        code_snippets = []
        for element in relevant_elements[:5]:  # En fazla 5 element
            snippet = indexer.get_code_snippet(
                request.project_id,
                element.file_path,
                element.start_line,
                element.end_line
            )
            if snippet:
                code_snippets.append(snippet)
        
        # LMStudio'ya soru sor
        answer, processing_time = llm_client.query_with_context(
            request.question,
            code_snippets
        )
        
        # Referansları çıkart
        project_index = indexer.get_project_index(request.project_id)
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
        
        return QueryResponse(
            answer=answer,
            references=references,
            model_used=llm_client.model,
            processing_time=processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
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
    
    return {"projects": projects}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
