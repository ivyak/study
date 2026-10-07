#!/usr/bin/env bash
# 解説資料の検算。
#   使い方: bash .claude/skills/explain/scripts/check_docs.sh <対象ディレクトリまたはファイル> [--max-lines N] [--root DIR]
#   対象は必須（この skill は既定の出力先を持たない）。既定の上限は 300 行。
#   --root はコード引用の解決に使うリポジトリルート。既定は git のトップ、無ければカレント。
#
# 見るもの:
#   1. 1 ファイルの行数が上限を超えていないか（超えたら分冊する）
#   2. 相対リンク ](./xxx.md) の飛び先が実在するか
#   3. コード引用の見出し `// path/to/file.ts:87` が実在し、行番号がファイルの行数の範囲内か
#   4. 目次ページ(_0) と全体目次(00_) から、その資料へのリンクがあるか
set -u

MAX_LINES=300
TARGET=""
ROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --max-lines) MAX_LINES="$2"; shift 2 ;;
    --root) ROOT="$2"; shift 2 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [ -z "$TARGET" ]; then
  echo "対象ディレクトリを指定してください（例: bash $0 docs/catch-up）" >&2
  sed -n '2,11p' "$0" >&2
  exit 2
fi

if [ -z "$ROOT" ]; then
  ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
fi
case "$TARGET" in /*) ;; *) TARGET="$ROOT/$TARGET" ;; esac

if [ -d "$TARGET" ]; then
  FILES=$(find "$TARGET" -name '*.md' | sort)
  DOCS_DIR="$TARGET"
elif [ -f "$TARGET" ]; then
  FILES="$TARGET"
  DOCS_DIR=$(dirname "$TARGET")
else
  echo "対象が見つかりません: $TARGET" >&2; exit 2
fi

ERRORS=0
WARNS=0
err()  { echo "🔴 $*"; ERRORS=$((ERRORS+1)); }
warn() { echo "🟡 $*"; WARNS=$((WARNS+1)); }

echo "== 対象: ${DOCS_DIR}（ルート: ${ROOT}） =="
echo
echo "== 1. 行数（上限 ${MAX_LINES} 行） =="
while IFS= read -r f; do
  [ -n "$f" ] || continue
  n=$(wc -l < "$f" | tr -d ' ')
  if [ "$n" -gt "$MAX_LINES" ]; then
    warn "$(basename "$f"): ${n} 行（上限 ${MAX_LINES}）— 内容を削らずに分冊する"
  fi
done <<< "$FILES"

echo
echo "== 2. 相対リンク =="
LINK_ERR=$(mktemp)
while IFS= read -r f; do
  [ -n "$f" ] || continue
  dir=$(dirname "$f")
  grep -oE '\]\(\.{1,2}/[^)#]+\)' "$f" 2>/dev/null | sed -E 's/^\]\(//; s/\)$//' | sort -u | \
  while IFS= read -r link; do
    [ -n "$link" ] || continue
    dec=$(printf '%b' "${link//%/\\x}")
    if [ ! -e "$dir/$dec" ] && [ ! -e "$dir/$link" ]; then
      echo "🔴 $(basename "$f") → $link が見つかりません"
    fi
  done
done <<< "$FILES" | tee "$LINK_ERR"
if [ -s "$LINK_ERR" ]; then ERRORS=$((ERRORS + $(wc -l < "$LINK_ERR" | tr -d ' '))); fi
rm -f "$LINK_ERR"

echo
echo "== 3. コード引用（ファイル:行） =="
# 資料の中では `# export.py:120` のように途中から省略した書き方も使う。
# リポジトリ相対で見つからなければ、末尾一致で 1 件に絞れるかを見る。
# git 管理下でなければ find でファイル一覧を作る。
INDEX_FILES=$(git -C "$ROOT" ls-files 2>/dev/null)
if [ -z "$INDEX_FILES" ]; then
  INDEX_FILES=$(cd "$ROOT" && find . -type f \
      -not -path './.git/*' -not -path '*/node_modules/*' \
      -not -path '*/.venv/*' -not -path '*/venv/*' \
      -not -path '*/__pycache__/*' -not -path '*/dist/*' -not -path '*/build/*' \
      2>/dev/null | sed 's@^\./@@')
fi
REF_ERR=$(mktemp)
while IFS= read -r f; do
  [ -n "$f" ] || continue
  grep -hoE '(^|[[:space:]])(//|#)[[:space:]]*[A-Za-z0-9_][A-Za-z0-9_./-]*\.(ts|tsx|js|jsx|mjs|py|rb|go|rs|java|kt|php|sh|sql|yml|yaml|json|toml|css|scss|html|vue|svelte|md):[0-9]+' "$f" 2>/dev/null \
    | sed -E 's@^.*(//|#)[[:space:]]*@@' | sort -u | \
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    path=${ref%:*}; line=${ref##*:}
    resolved=""
    if [ -f "$ROOT/$path" ]; then
      resolved="$ROOT/$path"
    else
      hits=$(printf '%s\n' "$INDEX_FILES" | grep -E "(^|/)${path}$" || true)
      n=$(printf '%s\n' "$hits" | grep -c . || true)
      if [ "$n" = "1" ]; then
        resolved="$ROOT/$hits"
      elif [ "$n" = "0" ]; then
        echo "🔴 $(basename "$f") が引用する $path が存在しません" >> "$REF_ERR"
        continue
      else
        continue   # 同名が複数。どれを指すか決められないので見逃す
      fi
    fi
    total=$(wc -l < "$resolved" | tr -d ' ')
    if [ "$line" -gt "$total" ]; then
      echo "🔴 $(basename "$f") の引用 $path:$line はファイル末尾（${total} 行）を超えています" >> "$REF_ERR"
    fi
  done
done <<< "$FILES"
sort -u "$REF_ERR" || true
if [ -s "$REF_ERR" ]; then ERRORS=$((ERRORS + $(sort -u "$REF_ERR" | wc -l | tr -d ' '))); fi
rm -f "$REF_ERR"

echo
echo "== 4. 目次からの導線 =="
INDEX=$(find "$DOCS_DIR" -maxdepth 1 -name '00_*.md' 2>/dev/null | head -1)
if [ -n "$INDEX" ]; then
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    b=$(basename "$f")
    case "$b" in 00_*) continue ;; esac
    # 分冊の本文（_1 以降）は _0 目次から張られていればよい
    if grep -qF "$b" "$INDEX"; then continue; fi
    prefix=$(echo "$b" | sed -E 's/^([0-9]+_[0-9]+)_.*/\1/')
    idx0=$(find "$DOCS_DIR" -maxdepth 1 \( -name "${prefix%_*}_0_*.md" -o -name "${prefix}_0_*.md" \) 2>/dev/null | head -1)
    if [ -n "$idx0" ] && grep -qF "$b" "$idx0"; then continue; fi
    warn "$b はどの目次からもリンクされていません"
  done <<< "$FILES"
else
  warn "全体目次 ${DOCS_DIR}/00_*.md が見つかりません"
fi

echo
echo "-----------------------------------------"
if [ "$ERRORS" -gt 0 ]; then
  echo "🔴 エラー ${ERRORS} 件 / 🟡 警告 ${WARNS} 件 — 直してから完了報告すること"
  exit 1
fi
echo "🟢 エラーなし / 🟡 警告 ${WARNS} 件"
