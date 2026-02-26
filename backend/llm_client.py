import requests
import json
import time
import logging
from typing import List, Dict, Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from models import CodeSnippet

# Logger
logger = logging.getLogger(__name__)


class LMStudioClient:
    """LMStudio OpenAI-compatible API istemcisi"""
    
    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "mistral-7b-instruct-v0.3"):
        self.base_url = base_url
        self.model = model
        self.chat_endpoint = f"{base_url}/chat/completions"
        self.models_endpoint = f"{base_url}/models"
        
        # Session setup with connection pooling
        self.session = requests.Session()
        
        # Proxy'ları devre dışı bırak (özellikle corporate networks için)
        self.session.trust_env = False
        self.session.proxies = {}
        
        # Retry strategy
        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        # Adapter configuration  
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=2,
            pool_maxsize=2,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def check_connection(self) -> bool:
        """LMStudio'ya bağlantı kontrolü yap"""
        try:
            response = self.session.get(self.models_endpoint, timeout=15)
            return response.status_code == 200
        except requests.exceptions.Timeout:
            print(f"⏱️  LMStudio bağlantı zaman aşımı (15s)")
            return False
        except requests.exceptions.ConnectionError:
            print(f"❌ LMStudio bağlanamıyor: {self.models_endpoint}")
            return False
        except Exception as e:
            print(f"⚠️  LMStudio hata: {e}")
            return False
    
    def get_available_models(self) -> List[str]:
        """Mevcut modelleri getir"""
        try:
            response = self.session.get(self.models_endpoint, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return [model.get("id", "") for model in data.get("data", [])]
        except requests.exceptions.Timeout:
            print(f"⏱️  Model listesi zaman aşımı")
        except Exception as e:
            print(f"Model listesi alınırken hata: {e}")
        return []
    
    def query_with_context(
        self, 
        question: str, 
        code_snippets: List[CodeSnippet],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> tuple[str, float]:
        """Kod konteksti ile sorgu yap"""
        
        # Konteksti hazırla
        context = self._build_context(code_snippets)
        
        # Prompt'u oluştur
        prompt = self._build_prompt(question, context)
        
        # API'ya iste gönder
        start_time = time.time()
        response_text = self._call_api(prompt, max_tokens, temperature)
        elapsed_time = time.time() - start_time
        
        return response_text, elapsed_time
    
    def _build_context(self, code_snippets: List[CodeSnippet]) -> str:
        """Kod parçacıklarından kontekst oluştur"""
        if not code_snippets:
            return ""
        
        context_parts = []
        for snippet in code_snippets:
            context_parts.append(f"--- File: {snippet.file_path} (Lines {snippet.start_line}-{snippet.end_line}) ---")
            context_parts.append(snippet.code)
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _build_prompt(self, question: str, context: str) -> str:
        """Prompt'u oluştur"""
        
        if context:
            prompt = f"""Aşağıdaki kod parçacıklarını ve konteksti dikkate alarak soruya cevap ver.

KONTEKST:
{context}

SORU: {question}

CEVAP:"""
        else:
            prompt = f"""Şu soruya cevap ver:

SORU: {question}

CEVAP:"""
        
        # Prompt'u log et
        logger.info(
            f"📋 PROMPT OLUŞTURULDU:\n"
            f"   ❓ Soru: {question[:80]}...\n"
            f"   📄 Kontekst: {len(context)} karakter"
        )
        logger.debug(f"   📝 Full Prompt:\n{prompt[:500]}...")
        
        return prompt
    
    def _call_api(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """LMStudio API'sını çağır"""
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            # Payload'ı log et
            logger.info(
                f"🔗 LMStudio API ÇAĞRISI:\n"
                f"   📍 URL: {self.chat_endpoint}\n"
                f"   🎯 Model: {self.model}\n"
                f"   🌡️  Temperature: {temperature}\n"
                f"   📏 Max Tokens: {max_tokens}"
            )
            logger.debug(f"   📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)[:1000]}")
            
            response = self.session.post(
                self.chat_endpoint,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    response_content = data["choices"][0]["message"]["content"]
                    logger.info(f"✅ API Cevaplandı (Status: {response.status_code})")
                    logger.debug(f"   📤 Response: {response_content[:300]}...")
                    return response_content
            else:
                error_msg = f"API Hatası: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                return error_msg
        
        except requests.exceptions.Timeout:
            error_msg = "❌ Hata: Sorgu zaman aşımı (Timeout - 120 saniye)"
            logger.error(error_msg)
            return error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "❌ Hata: LMStudio'ya bağlanılamıyor. Lütfen LMStudio'yu başlattığınızdan emin olun."
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Hata: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def extract_references_from_response(
        self,
        question: str,
        code_elements: List[Dict],
        response: str
    ) -> List[Dict]:
        """Cevaptan ilgili kod referanslarını çıkart"""
        
        references = []
        response_lower = response.lower()
        
        for element in code_elements:
            element_name_lower = element.get("name", "").lower()
            file_path = element.get("file_path", "")
            
            # Basit keyword matching
            if element_name_lower and element_name_lower in response_lower:
                references.append({
                    "file": file_path,
                    "element": element.get("name"),
                    "type": element.get("type"),
                    "lines": [element.get("start_line"), element.get("end_line")]
                })
        
        return references
