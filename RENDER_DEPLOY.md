# 免费部署到 Render｜EventLens

本版本将**已有的 FastAPI 直接研究页**放到公网（入口 `/`），不把本机 DeepSeek Harness 的 `3080` 端口公开。云端只运行一个 Python Web Service。原生 Harness 双栏依旧是本机开发能力，不在公网版承诺。

## 操作

1. 在 [Render 控制台](https://dashboard.render.com/) 登录，连接已创建的独立 GitHub 仓库 `CorreyZhang/EventLens`（仍保持 Private，允许 Render 访问该仓库即可）。
2. 选择 **New → Blueprint**，选择该仓库的 `main` 和仓库根目录 `render.yaml`。配置声明一个 `Free` Python Web Service。
3. 首次创建时 Render 会提示输入 `DEEPSEEK_API_KEY`；仅在 Render 的**服务端环境变量**中填写，**不要**写入 GitHub、网页、README 或截图。使用可控余额/已设置消费上限的专用 Key；此前在聊天中暴露过的 Key 不应再使用。
4. 确认服务类型 **Free**，实际部署并等待状态 `Live`。Render 会生成独立的 `https://...onrender.com` 地址，无需购买域名。
5. **打开根网址 `/`**：选择“实时研究”，输入同花顺季度报告，观察真实检索、来源登记和时间线。再用无痕浏览器确认不能看到前一个访客的研究历史。演示页不使用 `/workstation`，原生 Harness 入口在云端明确关闭。
6. 核查没有错误的默认证券/伪造资料，资料不足时系统明确报错。测试完后将 URL 加入 README 和笔试提交表；将仓库 Public 前再次扫描敏感字段、第三方授权和个人资料。

## 免费能力与安全限制

- `EVENTLENS_PUBLIC_DEMO=1` 将每个访客绑定单独签名的 HttpOnly Cookie；研究列表、详情、判断修改只允许本人会话。会话映射在服务进程**内存**中，不是正式多用户认证。
- 禁止公共访问原生 Harness、MCP/工作台管理、手工证据注入、无限刷新；限制每访客至多2项研究和3次追问，整个服务实例默认最多12项研究和24次追问。上限仅为**单进程内限额**，随免费实例休眠/重启重置；**不能作为支付上限保证**。
- Render 免费服务空闲后会休眠、文件存储不持久。研究/版本可能在休眠或重新部署后丢失，须在答题说明中标注；这不是长期存储产品。
- DeepSeek 的模型与 Search/Fetch 请求可能收费。建议在 DeepSeek 管理后台设置独立账户余额/额度，部署后监控；要完全避免费用，暂不填写 Key，但此时无法演示完整实时 AI 主链。
- iFinD/Fuyao 的**本机授权代理不会迁移到免费云**；只在授权条件实际可用时显示市场行情，没有权限就明确不可用。不能把来源引用定位当成原站真实性验证。
- 更正/否认自动指向具体旧主张、完整 `supersedes/refutes` 结论替换仍不完整。仅展示候选、证据强度与保留版本；不得声称所有题目功能都已完成。

## 验收与故障排查

- 访问 `/api/health` 可确认 Web 服务在线，但并不表示 DeepSeek Key/余额、检索或真实事件已经成功。
- 出现 `DeepSeek HTTP 401/402/429` 等提示，请先查授权/余额/平台限制，不要在网页中输入 API Key。
- 如果首页能打开但工作台没有聊天，检查你打开的是**云端独立研究页**而不是本机 `/workstation`。该入口使用旧版独立交互，不应有原生 Harness iframe。
- 如果构建失败，看 Render **Build Logs** 和 Python 版本（`render.yaml` 固定3.11.11）；如运行失败，检查 **Deploy Logs** 的 import/端口/凭据错误，不要把密钥粘给他人。
- 只有实际从公网浏览器使用该 URL 成功创建研究、出现可信来源和可定位事件后，才标记必交第 1 项已完成。

参见 [完整四项交付检查](SUBMISSION_CHECKLIST.md) 和 [测试记录](TESTING.md)。
