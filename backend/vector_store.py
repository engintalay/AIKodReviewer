import chromadb
from chromadb.config import Settings
import re
from typing import List, Dict, Set
from pathlib import Path
from models import CodeElement

BASE_DIR = Path(__file__).parent
CHROMA_DIR = BASE_DIR / "data" / "chroma"


class VectorStore:
    """Vector database for code elements"""
    
    def __init__(self):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    def index_project(self, project_id: str, elements: List[CodeElement], code_snippets: Dict[str, str]):
        """Projeyi vektör DB'ye indexle"""
        collection_name = f"project_{project_id}"
        
        # Koleksiyon varsa sil
        try:
            self.client.delete_collection(collection_name)
        except:
            pass
        
        collection = self.client.create_collection(collection_name)
        
        documents = []
        metadatas = []
        ids = []
        
        for i, elem in enumerate(elements):
            # Kod snippet'ını al
            code = code_snippets.get(elem.file_path, "")
            lines = code.split("\n")
            snippet = "\n".join(lines[elem.start_line-1:elem.end_line])
            
            # Dependency analizi
            dependencies = self._extract_dependencies(snippet, elem.language)
            
            # Document oluştur
            doc = f"{elem.name} {elem.type} {elem.signature}"
            
            documents.append(doc)
            metadatas.append({
                "name": elem.name,
                "type": elem.type,
                "file_path": elem.file_path,
                "start_line": elem.start_line,
                "end_line": elem.end_line,
                "language": elem.language,
                "dependencies": ",".join(dependencies),
                "full_snippet": snippet[:500]
            })
            ids.append(f"{project_id}_{i}")
        
        # Batch insert - büyük batch
        if documents:
            batch_size = 500
            for i in range(0, len(documents), batch_size):
                try:
                    collection.add(
                        documents=documents[i:i+batch_size],
                        metadatas=metadatas[i:i+batch_size],
                        ids=ids[i:i+batch_size]
                    )
                except Exception as e:
                    print(f"⚠️ Batch hatası: {e}")
    
    def search(self, project_id: str, query: str, n_results: int = 10) -> List[Dict]:
        """Semantic search"""
        collection_name = f"project_{project_id}"
        
        try:
            collection = self.client.get_collection(collection_name)
            results = collection.query(query_texts=[query], n_results=n_results)
            
            elements = []
            for i in range(len(results['ids'][0])):
                elements.append({
                    "metadata": results['metadatas'][0][i],
                    "document": results['documents'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else 0
                })
            
            return elements
        except:
            return []
    
    def get_element_with_dependencies(self, project_id: str, element_name: str, max_depth: int = 2) -> List[Dict]:
        """Element ve bağımlılıklarını getir"""
        collection_name = f"project_{project_id}"
        
        try:
            collection = self.client.get_collection(collection_name)
        except:
            return []
        
        visited = set()
        result = []
        
        def _get_recursive(name: str, depth: int):
            if depth > max_depth or name in visited:
                return
            
            visited.add(name)
            
            search_results = collection.query(query_texts=[name], n_results=1)
            if not search_results['ids'][0]:
                return
            
            metadata = search_results['metadatas'][0][0]
            document = search_results['documents'][0][0] if search_results['documents'][0] else ""
            
            result.append({
                "metadata": metadata,
                "document": document,
                "depth": depth
            })
            
            deps = metadata.get("dependencies", "").split(",")
            for dep in deps:
                if dep.strip():
                    _get_recursive(dep.strip(), depth + 1)
        
        _get_recursive(element_name, 0)
        return result
    
    def _extract_dependencies(self, code: str, language: str) -> Set[str]:
        """Kod içindeki fonksiyon çağrılarını çıkart"""
        deps = set()
        
        if language == "java":
            pattern = r'(\w+)\s*\('
            matches = re.findall(pattern, code)
            deps.update(matches)
        
        elif language == "python":
            pattern = r'(\w+)\s*\('
            matches = re.findall(pattern, code)
            deps.update(matches)
        
        builtins = {'if', 'for', 'while', 'return', 'new', 'this', 'super', 'print', 'len', 'str', 'int'}
        deps = deps - builtins
        
        return deps
