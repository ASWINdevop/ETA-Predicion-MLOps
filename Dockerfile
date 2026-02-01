FROM python:3.11-slim

# 1. Install System Deps + Timezone
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Kolkata



# 3. Install other requirements
# (Pip will see torch is already installed and skip the heavy version)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Code & Models
COPY src/ src/
COPY onnx_manifest.json .
COPY cooking.onnx .
COPY allocation.onnx .
COPY delivery.onnx .

EXPOSE 8000
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]