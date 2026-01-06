#!/bin/bash
#
# IBC Installation Script for macOS
# ===================================
# Instala y configura IBC (IBKR Controller) para automatizar el login de TWS
#
# IBC Features:
# - Auto-login a TWS con username/password
# - Acepta disclaimers automáticamente
# - Mantiene conexión viva
# - Reinicia TWS si se desconecta
#
# Usage:
#   chmod +x install_ibc.sh
#   ./install_ibc.sh

set -e

echo "=================================================="
echo "IBC (IBKR Controller) Installation Script"
echo "=================================================="
echo ""

# Configuration
IBC_VERSION="3.23.0"
IBC_DOWNLOAD_URL="https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCMacos-${IBC_VERSION}.zip"
INSTALL_DIR="$HOME/ibc"
TWS_DIR="$HOME/Jts"  # Default TWS installation directory on Mac

# Check if Homebrew is installed (for unzip)
if ! command -v brew &> /dev/null; then
    echo "⚠️  Homebrew not found. Installing Homebrew first..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Ensure unzip is available
if ! command -v unzip &> /dev/null; then
    echo "📦 Installing unzip..."
    brew install unzip
fi

# Step 1: Download IBC
echo "📥 Downloading IBC ${IBC_VERSION}..."
cd /tmp
# Remove old file if exists
rm -f ibc.zip
# Use curl with proper flags: -L (follow redirects), -f (fail on error), -S (show errors), -s (silent except errors)
curl -L -f -S -s -o "ibc.zip" "$IBC_DOWNLOAD_URL" || {
    echo "❌ Download failed. Trying alternative method..."
    # Try with wget as fallback
    if command -v wget &> /dev/null; then
        wget -O ibc.zip "$IBC_DOWNLOAD_URL"
    else
        echo "❌ Both curl and wget failed. Please install wget or check your internet connection."
        exit 1
    fi
}

# Step 2: Extract IBC
echo "📂 Extracting IBC..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
unzip -q ibc.zip -d "$INSTALL_DIR"
rm ibc.zip

echo "✅ IBC extracted to: $INSTALL_DIR"

# Step 3: Make scripts executable
echo "🔧 Setting permissions..."
chmod +x "$INSTALL_DIR"/*.sh
chmod +x "$INSTALL_DIR"/scripts/*.sh 2>/dev/null || true

# Step 3.5: Fix IBC_PATH in startup scripts
echo "🔧 Configuring IBC paths..."
# Fix twsstartmacos.sh
if [ -f "$INSTALL_DIR/twsstartmacos.sh" ]; then
    sed -i '' 's|IBC_PATH=/opt/ibc|IBC_PATH=~/ibc|g' "$INSTALL_DIR/twsstartmacos.sh"
fi
# Fix gatewaystartmacos.sh
if [ -f "$INSTALL_DIR/gatewaystartmacos.sh" ]; then
    sed -i '' 's|IBC_PATH=/opt/ibc|IBC_PATH=~/ibc|g' "$INSTALL_DIR/gatewaystartmacos.sh"
fi

# Step 4: Create config template
echo "📝 Creating IBC configuration..."
cat > "$INSTALL_DIR/config.ini.template" << 'EOF'
# =============================================================================
# IBC Configuration Template
# =============================================================================
# IMPORTANT: Copy this to config.ini and fill in your IBKR credentials
#
# cp config.ini.template config.ini
# nano config.ini  # Edit with your credentials
#
# Security Note: Keep config.ini private (contains credentials)
# =============================================================================

# IBKR Credentials
IbLoginId=YOUR_USERNAME
IbPassword=YOUR_PASSWORD
FIX=no

# Trading Mode
TradingMode=paper
# TradingMode=live  # Uncomment for live trading (CAREFUL!)

# TWS/Gateway Settings
IbDir=$TWS_DIR
IbAutoClosedown=no

# Auto-restart on disconnect
AutoRestartTime=
ClosedownAt=

# Logging
LogToConsole=yes
LogComponents=yes

# Accept Incoming Connection (for API)
AcceptIncomingConnectionAction=accept

# Minimize window on startup
MinimizeMainWindow=no
ExistingSessionDetectedAction=manual

# Store Settings On Server
StoreSettingsOnServer=no

# Read-only Login (for safety)
ReadOnlyLogin=no

# Suppress Error Dialogs
SuppressInfoMessages=yes

# Wait for GUI
WaitForGUIInit=yes
EOF

echo ""
echo "=================================================="
echo "✅ IBC Installation Complete!"
echo "=================================================="
echo ""
echo "📍 Installation Directory: $INSTALL_DIR"
echo ""
echo "🔐 Next Steps:"
echo "   1. Create your configuration file:"
echo "      cd $INSTALL_DIR"
echo "      cp config.ini.template config.ini"
echo "      nano config.ini"
echo ""
echo "   2. Edit config.ini and set:"
echo "      - IbLoginId=YOUR_IBKR_USERNAME"
echo "      - IbPassword=YOUR_IBKR_PASSWORD"
echo "      - TradingMode=paper (or 'live' for real trading)"
echo ""
echo "   3. Test IBC manually:"
echo "      cd $INSTALL_DIR"
echo "      ./scripts/DisplayBannerAndLaunch.sh"
echo ""
echo "   4. If TWS is not in default location ($TWS_DIR),"
echo "      update IbDir in config.ini"
echo ""
echo "⚠️  SECURITY WARNING:"
echo "   config.ini contains your IBKR password in plain text."
echo "   Keep this file secure and never commit to git!"
echo ""
echo "=================================================="
