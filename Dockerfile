FROM python:3.12-slim
WORKDIR /opt/trazaunt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m -u 10001 traza
COPY app.py ./
COPY config ./config
COPY db ./db
COPY services ./services
COPY scripts ./scripts
COPY data/__init__.py data/generador_sintetico.py ./data/
COPY data/demo ./data/demo
COPY data/publicos ./data/publicos
COPY frontend/dist ./frontend/dist
COPY frontend/trazabilidad.html ./frontend/trazabilidad.html
RUN mkdir -p /var/lib/trazaunt && chown traza /var/lib/trazaunt
ENV DATABASE_URL=sqlite:////var/lib/trazaunt/trazaunt.sqlite3
ENV PYTHONDONTWRITEBYTECODE=1
USER traza
EXPOSE 8000
HEALTHCHECK --start-period=45s --interval=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"
CMD ["python","-m","uvicorn","app:app","--host","0.0.0.0","--port","8000","--workers","1"]
