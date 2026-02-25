#!/bin/bash

# AI Kod Reviewer - Çalıştırma Script'i

set -e

# Sanal ortama gir
if [ ! -d "venv" ]; then
    echo "❌ venv klasörü bulunamadı. Lütfen ./setup.sh çalıştırın"
    exit 1
fi
source venv/bin/activate

# .env dosyasını yükle
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env dosyası bulunamadı"
    exit 1
fi

# Proxy'ları devre dışı bırak (corporate network sorunları için)
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY SOCKS_PROXY
unset NO_PROXY no_proxy

# Varsayılan değerler (eğer .env'de yoksa)
LMSTUDIO_BASE_URL=${LMSTUDIO_BASE_URL:-"http://localhost:8000/v1"}
BACKEND_URL=${BACKEND_URL:-"http://localhost:5000"}
BACKEND_HOST=${BACKEND_HOST:-"0.0.0.0"}
BACKEND_PORT=${BACKEND_PORT:-5000}
FRONTEND_PORT=${FRONTEND_PORT:-8501}

# Renklendirme
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          🤖 AI KOD REVIEWER - BAŞLATILIYOR 🤖             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

echo -e "${YELLOW}⚙️  Konfigürasyon:${NC}"
echo -e "  LMStudio: ${GREEN}${LMSTUDIO_BASE_URL}${NC}"
echo -e "  Backend:  ${GREEN}${BACKEND_URL}${NC}"
echo -e "  Frontend: ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
echo ""

echo -e "${YELLOW}📍 Ön kontroller yapılıyor...${NC}"
echo ""

if curl -s ${LMSTUDIO_BASE_URL}/models > /dev/null 2>&1; then
    echo -e "${GREEN}✅ LMStudio çalışıyor${NC}"
else
    echo -e "${RED}❌ LMStudio'ya bağlanılamıyor!${NC}"
    echo -e "${RED}   URL: ${LMSTUDIO_BASE_URL}${NC}"
    echo ""
    echo -e "${YELLOW}Lütfen yapın:${NC}"
    echo -e "${YELLOW}1. LMStudio uygulamasını aç${NC}"
    echo -e "${YELLOW}2. 'mistral-7b-instruct-v0.3' modelini indirip yükle${NC}"
    echo -e "${YELLOW}3. 'Local Server' seçeneği tıkla${NC}"
    echo -e "${YELLOW}4. .env dosyasında LMSTUDIO_BASE_URL'i kontrol et${NC}"
    echo ""
    exit 1
fi

if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${RED}❌ backend/ veya frontend/ klasörü bulunamadı${NC}"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo -e "${RED}❌ venv klasörü bulunamadı. Lütfen ./setup.sh çalıştırın${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Tüm ön kontroller başarılı${NC}"
echo ""
echo -e "${YELLOW}⏳ Backend ve Frontend başlatılıyor...${NC}"
echo ""

PID_FILE="/tmp/aikodreviewer.pids"
rm -f "$PID_FILE"

cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Kapatılıyor...${NC}"
    
    if [ -f "$PID_FILE" ]; then
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    
    echo -e "${GREEN}✅ Tüm process'ler kapatıldı${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Backend Başlıyor... (Port ${BACKEND_PORT})${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
(cd backend && python3 main.py --port ${BACKEND_PORT}) > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID >> "$PID_FILE"
echo -e "${GREEN}Backend PID: $BACKEND_PID${NC}"

sleep 3

if curl -s ${BACKEND_URL}/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend çalışıyor${NC}"
else
    echo -e "${YELLOW}⚠️  Backend başlatılıyor, biraz bekleyin...${NC}"
fi

echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Frontend Başlıyor... (Port ${FRONTEND_PORT})${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
export STREAMLIT_SERVER_PORT=${FRONTEND_PORT}
(cd frontend && streamlit run app.py --logger.level=warning) > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_FILE"
echo -e "${GREEN}Frontend PID: $FRONTEND_PID${NC}"

sleep 2

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}          ✅ TÜM SİSTEMLER BAŞLATILDI! ✅               ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Erişim Adresleri:${NC}"
echo -e "${BLUE}  🌐 Frontend: ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${BLUE}  🔗 Backend:  ${GREEN}${BACKEND_URL}${NC}"
echo -e "${BLUE}  📊 Docs:     ${GREEN}${BACKEND_URL}/docs${NC}"
echo ""
echo -e "${YELLOW}Log Dosyaları:${NC}"
echo -e "${BLUE}  📜 tail -f /tmp/backend.log${NC}"
echo -e "${BLUE}  📜 tail -f /tmp/frontend.log${NC}"
echo ""
echo -e "${YELLOW}Kapatmak için: Ctrl+C${NC}"
echo ""

while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo ""
        echo -e "${RED}❌ Process durdu${NC}"
        [ ! -f "$PID_FILE" ] || tail -30 /tmp/backend.log 2>/dev/null | head -15
        cleanup
    fi
    sleep 1
done
