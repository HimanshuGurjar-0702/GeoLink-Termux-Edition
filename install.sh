
#!/data/data/com.termux/files/usr/bin/bash

set -e

echo "================================"
echo "     GeoLink v2 Installer"
echo "================================"

pkg update -y
pkg install python git termux-api curl -y

echo ""
echo "Installing Python dependencies..."

python -m pip install -r requirements.txt

mkdir -p data
touch data/.gitkeep

chmod +x install.sh

echo ""
echo "================================"
echo " Installation completed!"
echo "================================"
echo "Run: python main.py"
