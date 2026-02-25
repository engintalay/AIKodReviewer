#!/bin/bash

# AI Kod Reviewer - Çalıştırma Script'i

set -e

# .env dosyasını yükle
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env dosyası bulunamadı"
    exit 1
fi

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
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          🤖 AI KOD REVIEWER - BAŞLATILIYOR 🤖             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Konfigürasyonu göster
echo -e "${YELLOW}⚙️  Konfigürasyon:${NC}"
echo -e "  LMStudio: ${GREEN}${LMSTUDIO_BASE_URL}${NC}"
echo -e "  Backend:  ${GREEN}${BACKEND_URL}${NC}"
echo -e "  Frontend: ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
echo ""

# LMStudio kontrol et
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

# Backend ve Frontend dizinlerinin varlığını kontrol et
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${RED}❌ backend/ veya frontend/ klasörü bulunamadı${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Tüm ön kontroller başarılı${NC}"
echo ""
echo -e "${YELLOW}⏳ Backend ve Frontend başlatılıyor...${NC}"
echo ""

# PID'leri saklayacak dosya
PID_FILE="/tmp/aikodreviewer.pids"
rm -f "$PID_FILE"

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Kapatılıyor...${NC}"
    
    if [ -f "$PID_FILE" ]; then
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                echo -e "${GREEN}  Process $pid kapatıldı${NC}"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    
    echo -e "${GREEN}✅ Tüm process'ler kapatıldı${NC}"
    exit 0
}

# Ctrl+C yakala
trap cleanup SIGINT SIGTERM

# Backend başlat
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Backend Başlıyor... (Port ${BACKEND_PORT})${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
cd backend
python3 main.py --port ${BACKEND_PORT} > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID >> "$PID_FILE"
echo -e "${GREEN}Backend PID: $BACKEND_PID${NC}"
cd ..

# Backend'in başlaması için biraz bekle
sleep 3

# Backend'e ping at
if curl -s ${BACKEND_URL}/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend çalışıyor${NC}"
else
    echo -e "${YELLOW}⚠️  Backend henüz yanıtlamıyor, biraz beklemek gerekli olabilir${NC}"
fi

echo ""

# Frontend başlat ve .env export et
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Frontend Başlıyor... (Port ${FRONTEND_PORT})${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
cd frontend
export STREAMLIT_SERVER_PORT=${FRONTEND_PORT}
streamlit run app.py --logger.level=warning > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_FILE"
echo -e "${GREEN}Frontend PID: $FRONTEND_PID${NC}"
cd ..

sleep 2

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}          ✅ TÜM SİSTEMLER BAŞLATILDI! ✅               ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Erişim Adresleri:${NC}"
echo -e "${BLUE}  🌐 Frontend (Web UI): ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${BLUE}  🔗 Backend API:       ${GREEN}${BACKEND_URL}${NC}"
echo -e "${BLUE}  📊 Backend Docs:      ${GREEN}${BACKEND_URL}/docs${NC}"
echo -e "${BLUE}  🤖 LMStudio:          ${GREEN}${LMSTUDIO_BASE_URL}${NC}"
echo ""
echo -e "${YELLOW}Log Dosyaları:${NC}"
echo -e "${BLUE}  📜 Backend:  /tmp/backend.log${NC}"
echo -e "${BLUE}  📜 Frontend: /tmp/frontend.log${NC}"
echo ""
echo -e "${YELLOW}Kapatmak için: Ctrl+C${NC}"
echo ""

# Process'lerin çalışmasını izle
while true; do
    # Eğer process'ler durmuşsa, exit et
    if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo ""
        echo -e "${RED}❌ Bir veya daha fazla process durmuş${NC}"
        
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo -e "${RED}Backend durdu - Log: /tmp/backend.log${NC}"
            echo -e "${YELLOW}Backend URL idi: ${BACKEND_URL}${NC}"
        fi
        
        if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            echo -e "${RED}Frontend durdu - Log: /tmp/frontend.log${NC}"
            echo -e "${YELLOW}Frontend Port'u idi: ${FRONTEND_PORT}${NC}"
        fi
        
        cleanup
    fi
    
    sleep 1
done
