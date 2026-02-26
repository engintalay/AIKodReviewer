import streamlit as st
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Konfigürasyon
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

# Streamlit sayfasını konfigüre et
st.set_page_config(
    page_title="AI Kod Reviewer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🤖 AI Kod Reviewer")
st.markdown("Projenizi analiz et ve kod hakkında sorular sor!")

# Session state'i başlat
if "project_id" not in st.session_state:
    st.session_state.project_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "project_info" not in st.session_state:
    st.session_state.project_info = None
if "username" not in st.session_state:
    st.session_state.username = None
if "saved_projects" not in st.session_state:
    st.session_state.saved_projects = []


def check_backend_health():
    """Backend sağlığını kontrol et"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def upload_project(uploaded_file):
    """Projeyi yükle"""
    try:
        with st.spinner("Proje yükleniyor..."):
            files = {"file": (uploaded_file.name, uploaded_file.getbuffer())}
            response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.project_id = data["project_id"]
                
                # Proje bilgisini analiz et
                analyze_response = requests.post(
                    f"{BACKEND_URL}/analyze",
                    params={"project_id": st.session_state.project_id}
                )
                
                if analyze_response.status_code == 200:
                    st.session_state.project_info = analyze_response.json()
                    st.success(f"✅ Proje yüklendi! {data['file_count']} dosya bulundu")
            else:
                st.error(f"❌ Yükleme hatası: {response.text}")
    
    except Exception as e:
        st.error(f"❌ Hata: {str(e)}")


def query_project(question, search_mode="fast"):
    """Projeye soru sor"""
    try:
        with st.spinner("Sorgu işleniyor..."):
            response = requests.post(
                f"{BACKEND_URL}/query",
                json={
                    "project_id": st.session_state.project_id,
                    "question": question,
                    "search_mode": search_mode,
                    "include_snippets": True,
                    "chat_history": st.session_state.chat_history
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                st.error(f"❌ Sorgu hatası: {response.text}")
    
    except Exception as e:
        st.error(f"❌ Hata: {str(e)}")
    
    return None


# Sidebar
with st.sidebar:
    st.header("📋 Proje Yöneticisi")
    
    # Kullanıcı girişi
    if not st.session_state.username:
        st.subheader("🔐 Giriş Yap")
        username = st.text_input("Kullanıcı adı:")
        password = st.text_input("Şifre:", type="password")
        
        if st.button("Giriş"):
            if username and password:
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/login",
                        json={"username": username, "password": password},
                        timeout=5
                    )
                    if response.status_code == 200:
                        st.session_state.username = username
                        st.success("✅ Giriş başarılı!")
                        st.rerun()
                    else:
                        st.error(f"❌ {response.json().get('detail', 'Giriş başarısız')}")
                except Exception as e:
                    st.error(f"❌ Hata: {e}")
            else:
                st.warning("Kullanıcı adı ve şifre girin")
        
        st.stop()
    
    # Kullanıcı bilgisi
    st.success(f"👤 {st.session_state.username}")
    if st.button("🚪 Çıkış"):
        st.session_state.username = None
        st.session_state.project_id = None
        st.session_state.saved_projects = []
        st.rerun()
    
    st.divider()
    
    # Backend durumu
    backend_ok = check_backend_health()
    if backend_ok:
        st.success("✅ Backend bağlantılı")
    else:
        st.error("❌ Backend bağlanılamadı")
        st.info(f"Lütfen backend'i başlatın: `python backend/main.py`")
    
    st.divider()
    
    # Kayıtlı projeler
    st.subheader("💾 Kayıtlı Projeler")
    
    if st.button("🔄 Yenile"):
        st.session_state.saved_projects = []
    
    if not st.session_state.saved_projects:
        try:
            response = requests.get(f"{BACKEND_URL}/saved_projects/{st.session_state.username}", timeout=3)
            if response.status_code == 200:
                st.session_state.saved_projects = response.json()["projects"]
        except:
            pass
    
    if st.session_state.saved_projects:
        for proj in st.session_state.saved_projects:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{'🔒' if proj['is_private'] else '🌐'} {proj['project_name']}")
            with col2:
                if st.button("📂", key=f"load_{proj['project_id']}"):
                    load_response = requests.post(f"{BACKEND_URL}/load_project/{proj['project_id']}", timeout=10)
                    if load_response.status_code == 200:
                        data = load_response.json()
                        st.session_state.project_id = proj['project_id']
                        st.session_state.project_info = {
                            "total_elements": proj['metadata']['total_elements'],
                            "languages_detected": proj['metadata']['languages'],
                            "message": f"{proj['metadata']['total_elements']} element"
                        }
                        st.success(f"✅ {proj['project_name']} yüklendi")
                        st.rerun()
    else:
        st.info("Henüz kayıtlı proje yok")
    
    st.divider()
    
    # Proje yükleme
    st.subheader("Proje Yükle")
    uploaded_file = st.file_uploader("ZIP dosyasını seç", type=["zip"])
    
    if uploaded_file is not None:
        if st.button("📤 Yükle"):
            upload_project(uploaded_file)
    
    # Alternatif: Yerel klasörden yükle
    st.subheader("Veya Yerel Klasörden Yükle")
    project_path = st.text_input("Proje klasörü yolu:")
    
    if project_path and st.button("📂 Klasörü Yükle"):
        if os.path.exists(project_path):
            try:
                with st.spinner("Klasör indexleniyor..."):
                    # Backend'e klasör path'ini gönder
                    import zipfile
                    import tempfile
                    
                    # Geçici ZIP oluştur
                    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                    with zipfile.ZipFile(temp_zip, 'w') as zipf:
                        for root, dirs, files in os.walk(project_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, project_path)
                                zipf.write(file_path, arcname)
                    
                    temp_zip.close()
                    
                    # Yükle
                    with open(temp_zip.name, 'rb') as f:
                        files = {"file": (Path(project_path).name + ".zip", f)}
                        response = requests.post(f"{BACKEND_URL}/upload", files=files)
                        
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.project_id = data["project_id"]
                            
                            analyze_response = requests.post(
                                f"{BACKEND_URL}/analyze",
                                params={"project_id": st.session_state.project_id}
                            )
                            
                            if analyze_response.status_code == 200:
                                st.session_state.project_info = analyze_response.json()
                                st.success(f"✅ Proje yüklendi! {data['file_count']} dosya bulundu")
                    
                    os.unlink(temp_zip.name)
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
        else:
            st.error("❌ Klasör bulunamadı")
    
    st.divider()
    
    # Yüklenen proje bilgisi
    if st.session_state.project_id:
        st.subheader("📊 Proje Bilgisi")
        if st.session_state.project_info:
            info = st.session_state.project_info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Kod Elemanları", info["total_elements"])
            with col2:
                st.metric("Diller", len(info["languages_detected"]))
            
            st.write("**Desteklenen Diller:**")
            st.write(", ".join(info["languages_detected"]))
        
        st.warning(f"**Proje ID:** `{st.session_state.project_id[:12]}`")
        
        # Projeyi kaydet
        with st.expander("💾 Projeyi Kaydet"):
            project_name = st.text_input("Proje adı:")
            is_private = st.checkbox("Özel proje (sadece sen görebilirsin)")
            
            if st.button("Kaydet"):
                if project_name:
                    try:
                        response = requests.post(
                            f"{BACKEND_URL}/save_project",
                            json={
                                "project_id": st.session_state.project_id,
                                "username": st.session_state.username,
                                "project_name": project_name,
                                "is_private": is_private
                            },
                            timeout=5
                        )
                        if response.status_code == 200:
                            st.success("✅ Proje kaydedildi!")
                            st.session_state.saved_projects = []  # Cache'i temizle
                        else:
                            st.error(f"❌ {response.json().get('detail', 'Kaydetme başarısız')}")
                    except Exception as e:
                        st.error(f"❌ Hata: {e}")
                else:
                    st.warning("Proje adı girin")
    
    st.divider()
    
    # Ayarlar
    st.subheader("⚙️ Ayarlar")
    backend_url = st.text_input("Backend URL:", BACKEND_URL)


# Ana içerik
if not st.session_state.project_id:
    st.info("👈 Soldan bir proje yükleyerek başlayın")
    
    st.markdown("""
    ### 🎯 Nasıl Kullanılır?
    
    1. **Proje Yükle**: ZIP dosyası veya yerel klasör
    2. **Soru Sor**: Kod hakkında soru sorma
    3. **Cevap Al**: AI modeli kontekst ile cevaplar
    4. **Referans Gör**: Kaynakça ile hangi dosyadan esinlenildiğini öğren
    
    ### ✨ Özellikler
    
    - 💻 **Çoklu Dil**: Python, JavaScript, Java, PHP, HTML, CSS...
    - 🧠 **AI Powered**: Mistral 7B model (local çalışan)
    - 📚 **Kod İndeksleme**: AST parsing ile hızlı arama
    - 🔍 **Kaynakça**: Her cevaba referans eklenmesi
    """)
else:
    # Seçili proje bilgisini başında göster
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown(f"### 📂 Seçili Proje")
        st.markdown(f"**ID:** `{st.session_state.project_id}`")
    
    with col2:
        if st.session_state.project_info:
            info = st.session_state.project_info
            st.metric("📊 Elemanlar", info["total_elements"])
    
    with col3:
        if st.session_state.project_info:
            info = st.session_state.project_info
            st.metric("🗣️ Diller", len(info["languages_detected"]))
    
    # Proje detayları
    if st.session_state.project_info:
        with st.expander("📋 Proje Detayları"):
            info = st.session_state.project_info
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Desteklenen Diller:**")
                for lang in info["languages_detected"]:
                    st.write(f"  • {lang.upper()}")
            with col2:
                st.write("**Proje İstatistikleri:**")
                st.write(f"  • Toplam elemanlar: {info['total_elements']}")
                st.write(f"  • Dil sayısı: {len(info['languages_detected'])}")
                st.write(f"  • Mesaj: {info['message']}")
    
    st.divider()
    
    # Chat arayüzü
    st.subheader("💬 Kod Hakkında Sor")
    
    # Chat geçmişini göster
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
                
                # Referansları göster
                if "references" in message:
                    with st.expander("📚 Referanslar"):
                        for ref in message["references"]:
                            st.code(
                                f"**{ref['element']}** ({ref['type']})\n"
                                f"📄 {ref['file']}\n"
                                f"📍 Satır: {ref['lines'][0]}-{ref['lines'][1]}"
                            )
    
    # Arama Kalitesi Seçimi
    search_mode_label = st.radio(
        "🔍 Arama Kalitesi:",
        options=["Hızlı Arama", "Derin Arama"],
        horizontal=True,
        help="Hızlı Arama: Sadece fonksiyon ve sınıfları tarar. Derin Arama: Tüm dosya içeriklerini tarar (daha yavaş)."
    )
    search_mode = "fast" if search_mode_label == "Hızlı Arama" else "deep"
    
    # Sorgu input
    question = st.chat_input("Sorunuzu yazın...")
    
    if question:
        # Soru gönder
        st.session_state.chat_history.append({
            "role": "user",
            "content": question
        })
        
        with st.chat_message("user"):
            st.write(question)
        
        # Cevap al
        result = query_project(question, search_mode=search_mode)
        
        if result:
            with st.chat_message("assistant"):
                st.write(result["answer"])
                
                # Referansları göster
                if result.get("references"):
                    with st.expander("📚 Referanslar"):
                        for ref in result["references"]:
                            st.markdown(
                                f"**{ref['element']}** ({ref['type']})\n\n"
                                f"📄 `{ref['file']}`\n\n"
                                f"📍 Satır: {ref['lines'][0]}-{ref['lines'][1]}"
                            )
                            
                            # Kod içeriğini göster
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/get_snippet",
                                    json={
                                        "project_id": st.session_state.project_id,
                                        "file_path": ref['file'],
                                        "start_line": ref['lines'][0],
                                        "end_line": ref['lines'][1]
                                    }
                                )
                                if response.status_code == 200:
                                    snippet_data = response.json()
                                    st.code(snippet_data['code'], language='java')
                            except:
                                pass
                            
                            st.divider()
                
                # Geçmişe ekle
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "references": result.get("references", [])
                })
                
                # Processing time'ı göster
                st.caption(f"⏱️ {result['processing_time']:.2f}s | Model: {result['model_used']}")
