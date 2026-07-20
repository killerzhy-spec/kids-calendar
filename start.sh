#!/bin/bash
# ────────────────────────────────────────────────
# 孩子作业日历助手  一键启动脚本
# 使用方法：在终端中执行  bash start.sh
# ────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

# ── 检查 Python3 ──────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  未找到 python3，请先安装 Python 3.10+"
  exit 1
fi

# ── 虚拟环境 ──────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "📦  创建虚拟环境 .venv ..."
  python3 -m venv .venv
fi
source .venv/bin/activate

# ── 安装/更新依赖 ─────────────────────────────────
echo "📦  检查依赖..."
pip install -q -r requirements.txt

# ── 检查 .env ─────────────────────────────────────
if [ ! -f ".env" ]; then
  echo ""
  echo "⚠️   未找到 .env 文件"
  echo "   → AI 解析功能不可用，作业字段需手动填写"
  echo "   → 参考 .env.example 创建 .env 并填入 OPENAI_API_KEY 即可启用 AI"
  echo ""
fi

# ── 启动服务 ──────────────────────────────────────
echo "🚀  启动中... 浏览器将自动打开 http://localhost:5001"
sleep 0.5
open "http://localhost:5001" 2>/dev/null || true
python3 app.py
