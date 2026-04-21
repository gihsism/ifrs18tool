FROM python:3.12-slim

# System packages Streamlit's PDF/image pipeline needs (same list as packages.txt).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements_deploy.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_BASE_URL_PATH=IFRS18analysis \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# Materialize .streamlit/secrets.toml from the $STREAMLIT_SECRETS env var
# that Fly injects at runtime, then start Streamlit.
CMD ["sh", "-c", "mkdir -p /app/.streamlit && printf '%s' \"$STREAMLIT_SECRETS\" > /app/.streamlit/secrets.toml && exec streamlit run app.py"]
