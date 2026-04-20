FROM continuumio/miniconda3:latest

# Install PDAL from conda-forge (officially supported distribution channel).
RUN conda install -n base -c conda-forge -y pdal \
    && conda clean -afy

ENV PDAL_BIN="pdal"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Fail image build early if PDAL CLI isn't available.
RUN pdal --version

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
