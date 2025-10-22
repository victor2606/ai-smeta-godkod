#!/bin/bash
# Build script for Construction Estimator MCP Server
#
# Usage:
#   ./build.sh              # Build for current platform
#   ./build.sh --multi      # Build for multiple platforms
#   ./build.sh --test       # Build and run tests
#   ./build.sh --push       # Build and push to registry

set -e

# Configuration
IMAGE_NAME="ghcr.io/victor2606/construction-estimator-mcp"
VERSION=$(git describe --tags --always --dirty)
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
COMMIT_SHA=$(git rev-parse --short HEAD)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    log_info "Prerequisites OK"
}

# Verify database files are excluded
verify_exclusions() {
    log_info "Verifying database files are excluded from build context..."

    # Check if database exists locally (it's OK if it does)
    if [ -f "data/processed/estimates.db" ]; then
        log_warn "Database file exists locally (will be excluded by .dockerignore)"
    fi

    # Verify .dockerignore has correct patterns
    if ! grep -q "data/processed/estimates.db" .dockerignore; then
        log_error ".dockerignore missing database exclusion pattern!"
        exit 1
    fi

    log_info "Exclusions verified"
}

# Build Docker image
build_image() {
    local multi_platform=$1
    local push=$2

    log_info "Building Docker image..."
    log_info "  Image: ${IMAGE_NAME}"
    log_info "  Version: ${VERSION}"
    log_info "  Commit: ${COMMIT_SHA}"
    log_info "  Build Date: ${BUILD_DATE}"

    if [ "$multi_platform" = true ]; then
        log_info "Building for multiple platforms (linux/amd64, linux/arm64)..."
        docker buildx build \
            --platform linux/amd64,linux/arm64 \
            --tag "${IMAGE_NAME}:${VERSION}" \
            --tag "${IMAGE_NAME}:latest" \
            --label "org.opencontainers.image.created=${BUILD_DATE}" \
            --label "org.opencontainers.image.revision=${COMMIT_SHA}" \
            --label "org.opencontainers.image.version=${VERSION}" \
            $([ "$push" = true ] && echo "--push" || echo "--load") \
            .
    else
        log_info "Building for current platform..."
        docker build \
            --tag "${IMAGE_NAME}:${VERSION}" \
            --tag "${IMAGE_NAME}:latest" \
            --label "org.opencontainers.image.created=${BUILD_DATE}" \
            --label "org.opencontainers.image.revision=${COMMIT_SHA}" \
            --label "org.opencontainers.image.version=${VERSION}" \
            .
    fi

    log_info "Build completed successfully"
}

# Test image (verify database is NOT included)
test_image() {
    log_info "Testing Docker image..."

    # Test 1: Verify database is NOT in image
    log_info "Test 1: Verifying database file is excluded..."
    if docker run --rm "${IMAGE_NAME}:latest" sh -c "[ -f /app/data/processed/estimates.db ]"; then
        log_error "FAIL: Database file found in image!"
        exit 1
    fi
    log_info "✅ PASS: Database file correctly excluded"

    # Test 2: Verify directory structure exists
    log_info "Test 2: Verifying directory structure..."
    docker run --rm "${IMAGE_NAME}:latest" sh -c "
        set -e
        [ -d /app/data/processed ] || exit 1
        [ -d /app/data/logs ] || exit 1
        [ -f /app/mcp_server.py ] || exit 1
        [ -f /app/health_server.py ] || exit 1
        [ -d /app/src ] || exit 1
        echo 'Directory structure OK'
    "
    log_info "✅ PASS: Directory structure verified"

    # Test 3: Check Python dependencies
    log_info "Test 3: Verifying Python dependencies..."
    docker run --rm "${IMAGE_NAME}:latest" python -c "
import fastmcp
import pandas
import sqlite3
print('✅ Dependencies OK')
    "
    log_info "✅ PASS: Python dependencies verified"

    log_info "All tests passed! ✅"
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build Docker image for Construction Estimator MCP Server

OPTIONS:
    --multi         Build for multiple platforms (linux/amd64, linux/arm64)
    --test          Build and run tests
    --push          Build and push to registry (requires docker login)
    --help          Show this help message

EXAMPLES:
    # Build for current platform
    $0

    # Build and test
    $0 --test

    # Build for multiple platforms and push
    $0 --multi --push

    # Build specific version
    git tag v1.0.0
    $0 --push

NOTES:
    - Database files are NEVER included in the image
    - Users must mount estimates.db as a volume
    - See DEPLOYMENT_GUIDE.md for deployment instructions

EOF
}

# Main execution
main() {
    local multi_platform=false
    local run_tests=false
    local push=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --multi)
                multi_platform=true
                shift
                ;;
            --test)
                run_tests=true
                shift
                ;;
            --push)
                push=true
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    log_info "=== Building Construction Estimator MCP Server ==="

    check_prerequisites
    verify_exclusions
    build_image "$multi_platform" "$push"

    if [ "$run_tests" = true ]; then
        test_image
    fi

    log_info "=== Build Complete ==="
    log_info ""
    log_info "Image built: ${IMAGE_NAME}:${VERSION}"
    log_info "Image built: ${IMAGE_NAME}:latest"

    if [ "$push" = true ]; then
        log_info "Image pushed to registry"
    else
        log_info ""
        log_info "To push to registry, run:"
        log_info "  docker push ${IMAGE_NAME}:${VERSION}"
        log_info "  docker push ${IMAGE_NAME}:latest"
    fi

    log_info ""
    log_info "To run locally:"
    log_info "  docker run -v ./data/processed/estimates.db:/app/data/processed/estimates.db:ro -p 8002:8000 ${IMAGE_NAME}:latest"
}

main "$@"
