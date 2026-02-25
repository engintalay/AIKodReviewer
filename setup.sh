#!/bin/bash

# AI Kod Reviewer - Kurulum Script'i
# Sanal ortam (venv) kullanır - sistem genelini etkilemez

set -e

# Proxy'ları devre dışı bırak (corporate network sorunları için)
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY SOCKS_PROXY
unset NO_PROXY no_proxy

echo "🚀 AI Kod Reviewer Kurulumu Başlatılıyor..."
echo ""

# Renklendirme
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Python versiyonunu kontrol et
echo -e "${YELLOW}📍 Python versiyonu kontrol ediliyor...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 bulunamadı. Lütfen Python 3.8+ kurun.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✅ Python ${PYTHON_VERSION} bulundu${NC}"
echo ""

# Sanal ortam oluştur
echo -e "${YELLOW}📍 Sanal ortam (venv) oluşturuluyor...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✅ Sanal ortam oluşturuldu${NC}"
else
    echo -e "${GREEN}✅ Sanal ortam zaten var${NC}"
fi
echo ""

# Sanal ortamı aktifleştir
echo -e "${YELLOW}📍 Sanal ortam aktifleştiriliyor...${NC}"
source venv/bin/activate
echo -e "${GREEN}✅ Sanal ortam aktif${NC}"
echo ""

# pip'i güncelle
echo -e "${YELLOW}📍 pip güncelleniyor...${NC}"
python3 -m pip install --upgrade pip --quiet
echo -e "${GREEN}✅ pip güncellendi${NC}"
echo ""

# Backend kurulumu
echo -e "${YELLOW}📍 Backend Dependencies Kuruluyor...${NC}"
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt --quiet
    echo -e "${GREEN}✅ Backend kurulumu tamamlandı${NC}"
else
    echo -e "${RED}❌ backend/requirements.txt bulunamadı${NC}"
    exit 1
fi
echo ""

# Frontend kurulumu
echo -e "${YELLOW}📍 Frontend Dependencies Kuruluyor...${NC}"
if [ -f "frontend/requirements.txt" ]; then
    pip install -r frontend/requirements.txt --quiet
    echo -e "${GREEN}✅ Frontend kurulumu tamamlandı${NC}"
else
    echo -e "${RED}❌ frontend/requirements.txt bulunamadı${NC}"
    exit 1
fi
echo ""

# Sanal ortamı deaktif et
deactivate || true
echo ""

# LMStudio kontrolü
echo -e "${YELLOW}📍 LMStudio Kontrolü...${NC}"
if curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
    echo -e "${GREEN}✅ LMStudio çalışıyor (localhost:8000)${NC}"
else
    echo -e "${YELLOW}⚠️  LMStudio'ya erişilemiyor (http://localhost:8000)${NC}"
    echo -e "${YELLOW}   Lütfen LMStudio'yu başlatın:${NC}"
    echo -e "${YELLOW}   1. LMStudio uygulamasını aç${NC}"
    echo -e "${YELLOW}   2. Mistral 7B Instruct v0.3 modelini indirip yükle${NC}"
    echo -e "${YELLOW}   3. 'Local Server' çalıştır (port 8000)${NC}"
    echo ""
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Kurulum Tamamlandı!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}📁 Sanal ortam: ./venv${NC}"
echo -e "${YELLOW}💾 Dependencies kurulma yeri: ./venv/lib/python3.x/site-packages${NC}"
echo ""
echo -e "${YELLOW}Başlatmak için:${NC}"
echo -e "${GREEN}  ./run.sh${NC}"
echo ""
echo -e "${YELLOW}Sistemden kaldırmak için:${NC}"
echo -e "${GREEN}  rm -rf venv/${NC}"
echo ""
