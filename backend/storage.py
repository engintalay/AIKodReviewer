import json
import os
from pathlib import Path
from typing import Optional, List, Dict

STORAGE_DIR = Path("data/projects")
USERS_FILE = Path("data/users.json")


class Storage:
    """Basit dosya tabanlı storage"""
    
    def __init__(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not USERS_FILE.exists():
            USERS_FILE.write_text(json.dumps({}))
    
    def save_project(self, project_id: str, username: str, project_name: str, 
                     project_path: str, is_private: bool, metadata: dict):
        """Projeyi kaydet"""
        user_dir = STORAGE_DIR / username
        user_dir.mkdir(exist_ok=True)
        
        project_file = user_dir / f"{project_id}.json"
        project_file.write_text(json.dumps({
            "project_id": project_id,
            "username": username,
            "project_name": project_name,
            "project_path": project_path,
            "is_private": is_private,
            "metadata": metadata
        }))
    
    def get_user_projects(self, username: str, include_public: bool = True) -> List[Dict]:
        """Kullanıcının projelerini getir"""
        projects = []
        
        # Kullanıcının kendi projeleri
        user_dir = STORAGE_DIR / username
        if user_dir.exists():
            for f in user_dir.glob("*.json"):
                projects.append(json.loads(f.read_text()))
        
        # Public projeler
        if include_public:
            for user_folder in STORAGE_DIR.iterdir():
                if user_folder.name != username and user_folder.is_dir():
                    for f in user_folder.glob("*.json"):
                        data = json.loads(f.read_text())
                        if not data.get("is_private"):
                            projects.append(data)
        
        return projects
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        """Proje bilgisini getir"""
        for user_folder in STORAGE_DIR.iterdir():
            if user_folder.is_dir():
                project_file = user_folder / f"{project_id}.json"
                if project_file.exists():
                    return json.loads(project_file.read_text())
        return None
    
    def delete_project(self, project_id: str, username: str) -> bool:
        """Projeyi sil"""
        project_file = STORAGE_DIR / username / f"{project_id}.json"
        if project_file.exists():
            project_file.unlink()
            return True
        return False
    
    def verify_user(self, username: str, password: str) -> bool:
        """Kullanıcı doğrula (basit)"""
        users = json.loads(USERS_FILE.read_text())
        return users.get(username) == password
    
    def create_user(self, username: str, password: str) -> bool:
        """Kullanıcı oluştur"""
        users = json.loads(USERS_FILE.read_text())
        if username in users:
            return False
        users[username] = password
        USERS_FILE.write_text(json.dumps(users))
        return True
