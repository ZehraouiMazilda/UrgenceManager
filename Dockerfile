FROM python:3.10-slim

WORKDIR /app

# Outils utiles (curl sert parfois au debug; tu peux retirer build-essential si tu n'as pas de libs à compiler)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le projet (views/, src/, app.py, etc.)
COPY . .

# Port Hugging Face (la plateforme expose un PORT via variable d'env)
EXPOSE 7860

# Lancer Streamlit
CMD ["bash", "-lc", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-7860}"]
