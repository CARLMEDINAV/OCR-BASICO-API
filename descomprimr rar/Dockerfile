# Imagen base con Python
FROM python:3.11-slim

# Instalar Tesseract OCR y dependencias de sistema
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt-get/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Exponer el puerto
EXPOSE 8000

# Comando para iniciar FastAPI
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]