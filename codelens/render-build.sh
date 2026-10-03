#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing Node.js using NVM..."
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install 20
nvm use 20

echo "Building Frontend..."
cd frontend
npm install
export VITE_API_BASE_URL="/"
npm run build
cd ..

echo "Installing Python Dependencies..."
cd backend
pip install --upgrade pip
# MUST install cpu version explicitly to prevent 2.5GB CUDA download which OOMs
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
pip install --no-cache-dir -r requirements.txt

echo "Pre-downloading embedding models at build time..."
# Download models now so they are cached before any indexing request.
# This avoids timeouts and OOM issues during the first indexing call.
OMP_NUM_THREADS=1 python -c "
import os
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
print('Downloading bge-small-en-v1.5 ...')
from sentence_transformers import SentenceTransformer
SentenceTransformer('BAAI/bge-small-en-v1.5')
print('Downloading cross-encoder/ms-marco-MiniLM-L-6-v2 ...')
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('Models downloaded and cached.')
"
cd ..
