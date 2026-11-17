# EventLens · 投资事件情报与证据时间线（Demo）

> **项目定位：24 小时 AI 产品经理笔试 Demo / 技术验证原型，不是完整交付或生产级金融产品。**
>
> **实际进度（2026-11-18）：Mac 本地原生双栏版本已基本跑通，并完成过真实 DeepSeek Harness 对话、证据提交和浏览器场景验证；仍有功能缺口与个别外部接口失败。** Render 公网服务已创建并出现过 Live，但公网功能尚未完成可靠的端到端验收，云端双栏适配版曾出现无法使用的情况。不能将公网页面能打开或 CI 全绿等同于产品全部完成。

这是同花顺 AI 产品经理笔试题目 08 的个人 Demo。尝试解决的问题是：同一投资事件被公告、新闻、观点与传闻反复提及时，如何帮助使用者区分来源、整理证据、识别冲突和版本变化，而不是只拿到一段 AI 总结。

## 体验入口：本地较完整，公网仍是实验版

| 版本 | 入口 | 真实状态 |
| --- | --- | --- |
| **Mac 本地原生 Harness 版** | http://127.0.0.1:8765/workstation | **已基本跑通**。双栏对话、研究时间线、证据引用、研究切换等在本机做过实际验证；使用需要自行配置环境、Key 和授权数据。 |
| Render 公网独立研究 Demo | https://eventlens-research-demo.onrender.com/ | **已部署，但完整真实研究主链路未确认稳定可用**。只使用 FastAPI 独立研究界面；非原生 Harness。 |
| Render 公网双栏适配试验 | https://eventlens-research-demo.onrender.com/cloud-workstation | **实验性、曾反馈不能正常使用**。保留双栏布局，但右侧是云端 API 适配，不是原生 Harness，不能当作已验收的正式体验。 |

**交付判断：本机 Demo 基本成功；公网的“可实际操作 Web 产品”要求仍有风险，不能声称完全满足题目。**

## 已实现的 Demo 能力

- **研究入口与部分真实主链路**：自然语言提出公司、政策或事件问题；本地原生 DeepSeek Harness 能检索、提交抓取材料并由后端保存研究；网页查看事件和原始来源。缺少有效证据时应显示失败或空状态。
- **候选事件归并**：按主体、行为、时间线索聚合资料；识别部分同源转载，保留来源 ID、逐字引文位置及研究版本。语义上是否属于同一事件仍需复核。
- **证据分类**：将候选陈述分为 FACT / OPINION / SPECULATION / RUMOR；结合原始/二手来源、同源关系和引文校验呈现依据。**FACT 表示陈述类型，不表示已获独立事实认证。**
- **时间维度**：区分发生、披露、抓取、更新时间；缺失时说明依据，不把搜索收录时间冒充首次披露。
- **更正、否认与版本**：展示部分冲突、更正候选和历史版本；**尚未实现针对具体旧陈述自动撤销/替换结论的完整逻辑**。
- **关联与行情**：尝试显示有引文支持的业务关联和已授权行情；数据不可用时明确说明，不以无关股票替代。
- **个人判断**：用户自行编辑、保存研究判断，AI 更新资料时不自动覆盖。

## 技术架构与 AI 的角色

- **前端**：HTML、CSS、JavaScript；Lightweight Charts（含许可文件）。
- **服务端**：Python、FastAPI、SQLite；负责研究、来源、事件、历史版本及人工判断存储和程序性引文校验。
- **原生本地对话**：DeepSeek Harness、会话桥接与 MCP 适配，Mac 上独立运行；Render 免费版不直接运行原生 Harness。
- **AI**：DeepSeek 用于问题规划、检索辅助、候选陈述抽取和自然语言解释；模型内容必须以实际来源校验，不直接认定为事实。
- **资料**：实际获授权时可尝试使用 iFinD MCP / 扶摇接口。Mac 本地权限、数据和会话不会自动出现在 Render 云端。

设计原则：**有可定位引文再整理事件；资料不足承认未知；保留人的独立判断。** 这些原则有部分程序校验和测试，不等于所有模型输出已被验证。

## 本地运行

建议 macOS、Python 3.11、Node.js/npm、已安装的官方 DeepSeek Harness，以及有效且获授权的 DeepSeek 账号。本仓库提供源码，不附赠 Python 虚拟环境、原生 Harness 运行时、数据库、私人会话或密钥。

### 仅启动 FastAPI

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8765
~~~

浏览器访问 http://127.0.0.1:8765/ 。这只是独立研究页，**不是原生双栏 Harness**。

### 启动 Mac 原生双栏

需要先完成本机官方 Harness 安装、harness.overlay.yaml 的路径适配、会话插件配置及 Keychain 设置。已有配置的 Mac 可以直接启动：

~~~bash
# 首次使用时，仅在自己的 Mac 上存储密钥；已有钥匙串记录则无需再次设置
sh scripts/setup_keychain.sh
# 启动 FastAPI 8765 + Harness 3080
sh scripts/start_eventlens.sh
~~~

浏览器访问 http://127.0.0.1:8765/workstation 。

**这不是零配置安装包。** 原生 Harness 和 npm 运行环境及本地绝对路径需按机器调整；只运行 FastAPI 并不会启动官方对话宿主。启动脚本会检查端口，不主动终止其它进程。

### 环境变量

| 变量 | 用途 |
| --- | --- |
| DEEPSEEK_API_KEY | 模型/检索授权；仅在服务端或本机钥匙串配置 |
| DEEPSEEK_MODEL | 模型名称，须由对应 DeepSeek API 实际支持 |
| EVENTLENS_DB | SQLite 路径；本地默认忽略的 data 目录 |
| FUYAO_API_KEY | 可选扶摇市场数据权限 |
| ALPHAVANTAGE_API_KEY | 可选行情接口 |
| EVENTLENS_IFIND_NEWS | iFinD 新闻检索开关 |
| EVENTLENS_PUBLIC_DEMO | 公开演示模式开关，不是生产级多租户认证 |

详见 [.env.example](.env.example) 与 [RENDER_DEPLOY.md](RENDER_DEPLOY.md)。不要提交真实 API Key、.env、私有数据库、授权原文全文或聊天会话。

## 验证、AI 使用与缺陷修正

- **真实本机操作**：对宁德时代、海天味业、欧盟政策、同花顺财报、历史会话和虚构文件名等做过实际研究与错误修正，见 [LIVE_VALIDATION_V05.md](LIVE_VALIDATION_V05.md)。
- **AI 参与和人工纠错**：ChatGPT/Codex 参与需求拆解、实现、审阅和测试；DeepSeek 参与检索与候选信息提取；人工修复过跨公司污染、引用 422、来源同源重复、研究焦点和历史切换问题，见 [AI_VALIDATION.md](AI_VALIDATION.md)。
- **自动化**：最近已确认的 main 版本 [GitHub Actions 成功记录](https://github.com/CorreyZhang/EventLens/actions/runs/44124015166)。覆盖代码主链路与安全边界的无密钥测试，**不能证明联网模型、第三方金融接口或 Render 端到端正常**。
- **不成功的验证也保留**：一次 iFinD 新闻真实调用失败，公告检索为空；三条原站二次回源未能匹配引用（403、动态页面等），因此不能宣称三条均获独立核验。

运行测试：

~~~bash
.venv/bin/python -m pytest -q tests
node --test tests/js/navigation.test.cjs
node --check static/app.js
node --check static/workbench.js
~~~

详细场景与限制见 [TESTING.md](TESTING.md)。

## 明确未做完的部分

1. **题目核心功能仍有缺口**：否认、更正、过期消息如何精确关联旧主张并自动改变当前结论的完整 supersedes/refutes 状态机没有完成；目前只能显示候选冲突和版本变化，不能算要求 3 全部实现。
2. **公网体验未完整通过**：Render 可访问不代表一次完整的真实研究能走通；云端双栏适配曾反馈无法正常使用。原生 Harness 只在本机基本跑通。
3. **模型真实性边界**：引用定位成功不代表来源独立验证、语义正确或因果成立；模型回答逐句事实约束不完整。
4. **外部服务**：iFinD/扶摇因授权、配置和网络可能失败；真实检索结果无法保证，空结果不表示事件不存在。
5. **云端工程**：Render Free 会休眠、磁盘不持久；访客隔离/调用限制仍为轻量演示性质，进程重启可重置，不具备生产认证或费用硬上限。
6. **其他**：尚未实现长期事件持续监测、完整多用户协作、全市场授权数据覆盖和商业级可靠性。不得输出确定性涨跌预测、收益承诺或直接买卖建议。

## 对照题目交付物

| 必交要求 | 本仓库中的内容 | 如实状态 |
| --- | --- | --- |
| 可实际操作的 Web URL | [Render 网页](https://eventlens-research-demo.onrender.com/) | **已有地址，但公网主要功能未完整验收，可能不符合完整要求** |
| 源代码仓库与 README | 本仓库 main + 当前 README | **文件已齐**。如仓库仍为 Private，评审不能直接访问，需要处理读权限 |
| AI 使用、人工修正和验证 | [AI_VALIDATION.md](AI_VALIDATION.md)、[LIVE_VALIDATION_V05.md](LIVE_VALIDATION_V05.md) | **文件已齐**，含失败与纠错记录 |
| 主链路、缺数据、接口失败、合规边界测试说明 | [TESTING.md](TESTING.md)、[tests/](tests/) | **文件已齐**，包含离线回归和已知局限 |
| 可选 60–180 秒演示视频 | 未提供 | **可选，不是必交文件** |

提交情况与待处理项：[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)。部署说明：[DEPLOYMENT.md](DEPLOYMENT.md) / [RENDER_DEPLOY.md](RENDER_DEPLOY.md)。

**总结：这是本机基本可用、仍在补全的 Demo，而不是完全完成的投资情报产品。** 该仓库是从私人开发工作区筛选出的源代码快照；Mac 本地尚未推送的改动不在仓库内。未上传真实密钥、个人会话及本地授权数据。
