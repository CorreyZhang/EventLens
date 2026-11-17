# 部署与公开安全检查

## 当前状态（不要误认为已经上线）

本仓库有本机 **FastAPI + DeepSeek Harness + SQLite** 与已单独适配的 **Render Free 单服务研究页**。公网只运行 FastAPI 自带的独立研究链路，**不提供本机原生 Harness 双栏**。从 GitHub 连接 Render 并设置服务端 Key 之后才能创建 URL，见 [RENDER_DEPLOY.md](RENDER_DEPLOY.md)。独立访客隔离属于轻量演示防护，不是生产认证。

GitHub Pages 只能托管静态资源，**不能运行 Python 后端或安全保存 DeepSeek Key**。本仓库不是 GitHub Pages 离线演示替代品，避免将静态截图冒充 AI 产品。

## 云端上线前必做

1. 选择单服务公网架构：要么部署一个真正连接了 DeepSeek 的 FastAPI 独立研究入口；要么在受保护的服务器部署 Harness 并处理 WebSocket 与代理。不能依赖公网浏览器访问 `127.0.0.1:3080`。
2. 云端必须隔离不同访问者的所有研究 ID、历史、引用和可写接口，限制 API 消耗及请求频率；确认无法读取其他用户研究。
3. 配置 `DEEPSEEK_API_KEY` 等环境变量仅保留在服务端，不放网页 JS，不放 Git 或构建日志；轮换曾经暴露的 Key。
4. 检查扶摇/iFinD/DeepSeek 检索权限及转发合规性；不得公开受限原文缓存、私有 API 数据或授权材料。
5. Render 免费实例可能休眠且本地磁盘不持久；如需持久版本历史需配置持久化数据服务。
6. 部署后在浏览器无痕窗口和不同网络上操作：新建研究、真实搜索、引用、事件时间线、版本和异常；记录最终可访问 **https://** URL。
7. 在真实 URL 正常前，不把 `localhost`、空仓库、截图或本机录屏当作符合题目 08 的在线交付。

## 本地验证

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q tests
uvicorn app:app --host 127.0.0.1 --port 8765
```

本地 Harness 专用脚本：`sh scripts/start_eventlens.sh`（仅 macOS 及已安装依赖的工作机）。`harness.overlay.yaml` 若含本机绝对路径，需要按部署环境替换，切勿提交个人目录和密钥。

**正式提交页面需补：公开可访问的 Web URL、实际外网验收结果、独立源码仓库可读权限。**
