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
pip install --no-cache-dir -r requirements.txt
cd ..
