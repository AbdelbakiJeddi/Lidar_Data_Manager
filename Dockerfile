FROM python:3.12-slim

# Install LasTools (native Linux binaries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt \
    && cd /opt \
    && wget -q https://downloads.rapidlasso.de/LAStools.tar.gz \
    && tar -xzf LAStools.tar.gz \
    && rm LAStools.tar.gz

ENV LASTOOLS_PATH="/opt/LAStools/bin"
ENV PATH="${LASTOOLS_PATH}:${PATH}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
