# use a lightweight python base image
FROM python:3.11-slim

# install native binaries needed for downloading and rendering
RUN apt-get update && apt-get install -y \
    wget \
    aria2 \
    ffmpeg \
    # playwright dependencies for chromium/firefox
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# set working directory
WORKDIR /app

# copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# install playwright's browser engine (firefox)
RUN playwright install firefox

# copy the actual app code
COPY app.py .
COPY miruro_dom.py .

# expose the port render expects
EXPOSE 8000

# run the server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
