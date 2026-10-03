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

echo "Pre-downloading lightweight embedding models at build time..."
export HF_HOME="$PWD/.hf_cache"
OMP_NUM_THREADS=1 python -c "
import os
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
print('Downloading all-MiniLM-L6-v2 ...')
from sentence_transformers import SentenceTransformer
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Downloading cross-encoder/ms-marco-MiniLM-L-6-v2 ...')
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('Models pre-cached successfully.')
"
cd ..
