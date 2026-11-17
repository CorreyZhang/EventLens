#!/bin/sh
# One-time secure macOS Keychain setup. No keys in CLI argv, files or logs.
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "此脚本仅支持 macOS。" >&2
  exit 1
fi

ACCOUNT="$(id -un)"
SERVICE="com.eventlens.deepseek.api-key"

if /usr/bin/security find-generic-password -a "$ACCOUNT" -s "$SERVICE" >/dev/null 2>&1; then
  printf '%s\n' "钥匙串中已经有 EventLens DeepSeek Key。重新执行会替换旧值。"
fi

printf '%s\n' "将 DeepSeek API Key 写入当前 macOS 用户的登录钥匙串。"
printf '%s\n' "接下来系统会提示输入并确认 Key；不会显示字符，也不会写进项目文件。"
printf '%s\n' "请使用仍有效的 Key，不要使用曾公开在聊天或代码中的旧 Key。"
/usr/bin/security add-generic-password -U \
  -a "$ACCOUNT" \
  -s "$SERVICE" \
  -l "EventLens - DeepSeek API Key" \
  -w

echo "已保存至 macOS 钥匙串。之后只需运行：sh scripts/start_eventlens.sh"
