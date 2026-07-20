# Imagem oficial da Playwright: já traz Chromium e todas as dependências de
# sistema (fonts, libs) necessárias para rodar em modo headless.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

WORKDIR /app

# Instala dependências Python primeiro (melhor cache de build).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# O browser já vem na imagem base; garante que está presente para esta versão.
RUN playwright install chromium

COPY app ./app

ENV HEADLESS=true \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# 1 worker: o navegador é compartilhado no processo e a concorrência é feita
# via contexts + semáforo (ver app/browser.py). Escala horizontalmente por
# réplicas de container, se necessário.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
