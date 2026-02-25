from pydantic import BaseModel
from typing import Optional, List


class CodeElement(BaseModel):
    """Kod Elementinin (Fonksiyon, Class, vb.) Modeli"""
    name: str
    type: str  # "function", "class", "method", "variable", etc.
    file_path: str
    start_line: int
    end_line: int
    language: str
    signature: Optional[str] = None
    docstring: Optional[str] = None


class ProjectIndex(BaseModel):
    """Proje İndeksi Modeli"""
    project_id: str
    total_files: int
    supported_files: int
    languages: List[str]
    elements: List[CodeElement]


class CodeSnippet(BaseModel):
    """Kod Parçacığı Modeli"""
    file_path: str
    start_line: int
    end_line: int
    code: str
    element_name: Optional[str] = None


class QueryRequest(BaseModel):
    """Sorgu İsteği Modeli"""
    project_id: str
    question: str
    include_snippets: bool = True


class QueryResponse(BaseModel):
    """Sorgu Cevap Modeli"""
    answer: str
    references: List[dict]  # [{"file": "file.py", "lines": [10, 25], "snippet": "..."}]
    model_used: str
    processing_time: float


class UploadResponse(BaseModel):
    """Yükleme Cevap Modeli"""
    project_id: str
    status: str
    message: str
    file_count: int


class AnalysisResponse(BaseModel):
    """Analiz Cevap Modeli"""
    project_id: str
    status: str
    total_elements: int
    languages_detected: List[str]
    message: str
