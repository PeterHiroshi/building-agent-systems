#!/usr/bin/env bash
set -e

REPO="PeterHiroshi/building-agent-systems"
INSTALL_DIR="${HOME}/.claude/skills/building-agent-systems"
BRANCH="main"

echo "Installing building-agent-systems skill..."

# Check if already installed
if [ -d "$INSTALL_DIR" ]; then
  echo "Updating existing installation at $INSTALL_DIR"
  rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR/references"

# Download files via curl (no git required)
BASE_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

curl -fsSL "${BASE_URL}/SKILL.md" -o "${INSTALL_DIR}/SKILL.md"
curl -fsSL "${BASE_URL}/references/patterns-reference.md" -o "${INSTALL_DIR}/references/patterns-reference.md"
curl -fsSL "${BASE_URL}/references/context-engineering-reference.md" -o "${INSTALL_DIR}/references/context-engineering-reference.md"
curl -fsSL "${BASE_URL}/references/think-tool-reference.md" -o "${INSTALL_DIR}/references/think-tool-reference.md"
curl -fsSL "${BASE_URL}/references/evals-reference.md" -o "${INSTALL_DIR}/references/evals-reference.md"
curl -fsSL "${BASE_URL}/references/rag-reference.md" -o "${INSTALL_DIR}/references/rag-reference.md"

echo ""
echo "✓ Installed to ${INSTALL_DIR}"
echo ""
echo "Usage: In Claude Code or Cursor, this skill is now available as:"
echo "  building-agent-systems"
echo ""
echo "It activates automatically when you ask about:"
echo "  - Agent system design and architecture"
echo "  - Tool design for agents"
echo "  - Context engineering / context rot"
echo "  - Multi-agent orchestration"
echo "  - Evals for AI agents"
echo "  - RAG for knowledge-heavy agents"
