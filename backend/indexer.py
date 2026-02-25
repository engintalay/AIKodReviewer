import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from models import CodeElement, ProjectIndex, CodeSnippet
import hashlib

try:
    from tree_sitter import Language, Parser
    from tree_sitter_python import language as python_language
    from tree_sitter_javascript import language as javascript_language
    from tree_sitter_java import language as java_language
    from tree_sitter_php import language as php_language
    from tree_sitter_html import language as html_language
    from tree_sitter_css import language as css_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class CodeIndexer:
    """Kod İndexleyici - Tree-sitter ve Regex yöntemiyle kod parsing yapıyor"""
    
    def __init__(self):
        self.projects: Dict[str, ProjectIndex] = {}
        self.code_snippets: Dict[str, Dict[str, str]] = {}  # {project_id: {file: content}}
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """Tree-sitter Parser'larını başlat"""
        if not TREE_SITTER_AVAILABLE:
            print("⚠️ Tree-sitter kütüphanesi tam yüklü değil, fallback mode kullanılacak")
            return
        
        lang_map = {
            "python": python_language,
            "javascript": javascript_language,
            "typescript": javascript_language,
            "java": java_language,
            "php": php_language,
            "html": html_language,
            "css": css_language,
        }
        
        try:
            for lang_name, lang_module in lang_map.items():
                parser = Parser()
                parser.set_language(lang_module)
                self.parsers[lang_name] = parser
                self.languages[lang_name] = lang_module
        except Exception as e:
            print(f"⚠️ Parser başlatma hatası: {e}")
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """Dosyanın dilini algıla"""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".php": "php",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
        }
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext)
    
    def _extract_python_elements(self, code: str, file_path: str, language: str) -> List[CodeElement]:
        """Python kodundan fonksiyon/class'ları çıkart (Regex + Tree-sitter)"""
        elements = []
        
        # Tree-sitter kullan
        if language == "python" and "python" in self.parsers:
            try:
                parser = self.parsers["python"]
                tree = parser.parse(code.encode())
                elements.extend(self._walk_tree(tree.root_node, code, file_path, language))
                return elements
            except Exception as e:
                print(f"⚠️ Tree-sitter parsing hatası: {e}, fallback mode")
        
        # Fallback: Regex
        lines = code.split("\n")
        
        # Fonksiyonlar
        func_pattern = r"^def\s+(\w+)\s*\("
        class_pattern = r"^class\s+(\w+)\s*[:\(]"
        
        for i, line in enumerate(lines, 1):
            func_match = re.match(func_pattern, line)
            if func_match:
                elements.append(CodeElement(
                    name=func_match.group(1),
                    type="function",
                    file_path=file_path,
                    start_line=i,
                    end_line=self._find_end_line(lines, i),
                    language=language,
                    signature=line.strip()
                ))
            
            class_match = re.match(class_pattern, line)
            if class_match:
                elements.append(CodeElement(
                    name=class_match.group(1),
                    type="class",
                    file_path=file_path,
                    start_line=i,
                    end_line=self._find_end_line(lines, i),
                    language=language,
                    signature=line.strip()
                ))
        
        return elements
    
    def _extract_javascript_elements(self, code: str, file_path: str, language: str) -> List[CodeElement]:
        """JavaScript/TypeScript kodundan fonksiyon/class'ları çıkart"""
        elements = []
        
        lines = code.split("\n")
        
        # Fonksiyon patterns
        func_patterns = [
            r"function\s+(\w+)\s*\(",
            r"const\s+(\w+)\s*=\s*(?:async\s*)?\(",
            r"let\s+(\w+)\s*=\s*(?:async\s*)?\(",
            r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*{",
        ]
        
        class_pattern = r"class\s+(\w+)\s*(?:extends\s+\w+)?\s*{"
        
        for i, line in enumerate(lines, 1):
            for pattern in func_patterns:
                func_match = re.search(pattern, line)
                if func_match:
                    elements.append(CodeElement(
                        name=func_match.group(1),
                        type="function",
                        file_path=file_path,
                        start_line=i,
                        end_line=self._find_end_line(lines, i),
                        language=language,
                        signature=line.strip()
                    ))
                    break
            
            class_match = re.search(class_pattern, line)
            if class_match:
                elements.append(CodeElement(
                    name=class_match.group(1),
                    type="class",
                    file_path=file_path,
                    start_line=i,
                    end_line=self._find_end_line(lines, i),
                    language=language,
                    signature=line.strip()
                ))
        
        return elements
    
    def _extract_java_elements(self, code: str, file_path: str, language: str) -> List[CodeElement]:
        """Java kodundan fonksiyon/class'ları çıkart"""
        elements = []
        
        lines = code.split("\n")
        
        # Sınıf pattern
        class_pattern = r"(?:public|private)?\s*class\s+(\w+)"
        
        # Metod pattern
        method_pattern = r"(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\("
        
        for i, line in enumerate(lines, 1):
            class_match = re.search(class_pattern, line)
            if class_match:
                elements.append(CodeElement(
                    name=class_match.group(1),
                    type="class",
                    file_path=file_path,
                    start_line=i,
                    end_line=self._find_end_line(lines, i),
                    language=language,
                    signature=line.strip()
                ))
            
            method_match = re.search(method_pattern, line)
            if method_match:
                elements.append(CodeElement(
                    name=method_match.group(1),
                    type="method",
                    file_path=file_path,
                    start_line=i,
                    end_line=self._find_end_line(lines, i),
                    language=language,
                    signature=line.strip()
                ))
        
        return elements
    
    def _walk_tree(self, node, code: str, file_path: str, language: str) -> List[CodeElement]:
        """Tree-sitter AST'yi dolaş ve kod elementlerini çıkart"""
        elements = []
        lines = code.split("\n")
        
        if node.type in ["function_definition", "class_definition"]:
            name_node = None
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break
            
            if name_node:
                element_type = "function" if node.type == "function_definition" else "class"
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                
                signature = "\n".join(lines[node.start_point[0]:min(node.end_point[0] + 1, len(lines))])[:100]
                
                elements.append(CodeElement(
                    name=name_node.text.decode(),
                    type=element_type,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    language=language,
                    signature=signature
                ))
        
        for child in node.children:
            elements.extend(self._walk_tree(child, code, file_path, language))
        
        return elements
    
    def _find_end_line(self, lines: List[str], start_line: int) -> int:
        """Bir kod bloğunun bitiş satırını bul (indent bazlı)"""
        if start_line >= len(lines):
            return start_line + 1
        
        start_indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            if line.strip() and not line.strip().startswith("#"):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= start_indent and i > start_line - 1:
                    return i
        
        return len(lines)
    
    def index_project(self, project_path: str) -> Tuple[str, ProjectIndex]:
        """Projeyi index et ve ProjectIndex döndür"""
        
        project_id = hashlib.md5(project_path.encode()).hexdigest()[:12]
        elements = []
        languages_set = set()
        total_files = 0
        supported_files = 0
        
        # Proje dosyalarını oku
        for root, dirs, files in os.walk(project_path):
            # .git, __pycache__, node_modules vb. dışla
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.env', 'venv', '.venv'}]
            
            for file in files:
                file_path = os.path.join(root, file)
                total_files += 1
                
                language = self._detect_language(file_path)
                if not language:
                    continue
                
                supported_files += 1
                languages_set.add(language)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        code = f.read()
                    
                    # Dosya içeriğini kaydet
                    if project_id not in self.code_snippets:
                        self.code_snippets[project_id] = {}
                    
                    relative_path = os.path.relpath(file_path, project_path)
                    self.code_snippets[project_id][relative_path] = code
                    
                    # Kod elementlerini çıkart
                    if language == "python":
                        file_elements = self._extract_python_elements(code, relative_path, language)
                    elif language in ["javascript", "typescript"]:
                        file_elements = self._extract_javascript_elements(code, relative_path, language)
                    elif language == "java":
                        file_elements = self._extract_java_elements(code, relative_path, language)
                    else:
                        file_elements = []
                    
                    elements.extend(file_elements)
                
                except Exception as e:
                    print(f"⚠️ Dosya okunurken hata ({file_path}): {e}")
        
        # ProjectIndex oluştur
        project_index = ProjectIndex(
            project_id=project_id,
            total_files=total_files,
            supported_files=supported_files,
            languages=sorted(list(languages_set)),
            elements=elements
        )
        
        self.projects[project_id] = project_index
        return project_id, project_index
    
    def search_elements(self, project_id: str, query: str) -> List[CodeElement]:
        """Keyword ile kod elementlerini ara"""
        if project_id not in self.projects:
            return []
        
        elements = self.projects[project_id].elements
        query_lower = query.lower()
        
        results = []
        for element in elements:
            if (query_lower in element.name.lower() or 
                query_lower in (element.signature or "").lower()):
                results.append(element)
        
        return results
    
    def get_code_snippet(self, project_id: str, file_path: str, start_line: int, end_line: int) -> Optional[CodeSnippet]:
        """Belirtilen satırlar arası kod parçacığı getir"""
        if project_id not in self.code_snippets:
            return None
        
        if file_path not in self.code_snippets[project_id]:
            return None
        
        code = self.code_snippets[project_id][file_path]
        lines = code.split("\n")
        
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        snippet_code = "\n".join(lines[start_idx:end_idx])
        
        return CodeSnippet(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            code=snippet_code
        )
    
    def get_project_index(self, project_id: str) -> Optional[ProjectIndex]:
        """Proje indexini getir"""
        return self.projects.get(project_id)
