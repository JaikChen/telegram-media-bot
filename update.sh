#!/bin/bash
set -e
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "$APP_DIR/scripts/deploy.sh"
exec bash "$APP_DIR/scripts/deploy.sh" "$@"