# ---- Stage 1: build React ----
FROM node:20-slim AS frontend
WORKDIR /app
COPY frontend-v2/package*.json ./
RUN npm install
COPY frontend-v2/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim
WORKDIR /app
COPY backend-v2/requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY backend-v2/ ./
COPY --from=frontend /app/dist ./static
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
