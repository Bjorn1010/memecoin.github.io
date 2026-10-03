# Laboratoire de recherche + paper trading. Aucune clé API n'est nécessaire ni copiée :
# les secrets éventuels passent par des variables d'environnement au lancement.
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY qt ./qt
COPY configs ./configs
COPY scripts ./scripts
COPY tests ./tests
RUN pip install --no-cache-dir -e '.[dev]'
ENV QT_DATA_DIR=/data
VOLUME ["/data", "/app/reports"]
# Par défaut : la suite de tests. Un cycle de recherche :
#   docker run -v $PWD/reports:/app/reports qt python scripts/research_cycle.py
CMD ["python", "-m", "pytest", "tests", "-q"]
