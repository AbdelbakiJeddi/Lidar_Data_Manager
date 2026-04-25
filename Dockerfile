FROM condaforge/miniforge3:latest

# Install PDAL using mamba (much faster C++ solver, guarantees conda-forge compatibility).
RUN mamba install -y pdal \
    && mamba clean -afy

ENV PDAL_BIN="pdal"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Fail image build early if PDAL CLI isn't available.
RUN pdal --version

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
