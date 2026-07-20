#!/usr/bin/env bash
# Install SigNoz MCP server binary (pin v0.8.0 per docs/03).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="${SIGNOZ_MCP_VERSION:-v0.8.0}"
BIN_DIR="$ROOT/bin"
mkdir -p "$BIN_DIR"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64) ARCH=arm64 ;;
  x86_64|amd64) ARCH=amd64 ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac
case "$OS" in
  darwin) PLATFORM="darwin_${ARCH}" ;;
  linux) PLATFORM="linux_${ARCH}" ;;
  *) echo "unsupported os: $OS" >&2; exit 1 ;;
esac

ASSET="signoz-mcp-server_${PLATFORM}.tar.gz"
URL="https://github.com/SigNoz/signoz-mcp-server/releases/download/${VERSION}/${ASSET}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "fetching $URL"
curl -fsSL "$URL" -o "$TMP/$ASSET"
tar -xzf "$TMP/$ASSET" -C "$TMP"
# tarball may nest the binary
FOUND="$(find "$TMP" -type f -name 'signoz-mcp-server' | head -1)"
if [[ -z "$FOUND" ]]; then
  echo "binary not found in archive" >&2
  ls -laR "$TMP" >&2
  exit 1
fi
cp "$FOUND" "$BIN_DIR/signoz-mcp-server"
chmod +x "$BIN_DIR/signoz-mcp-server"
echo "installed $BIN_DIR/signoz-mcp-server ($VERSION)"
"$BIN_DIR/signoz-mcp-server" --help 2>&1 | head -20 || true
