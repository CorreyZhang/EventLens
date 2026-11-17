# EventLens — 投资事件情报与证据时间线

同花顺 AI 产品经理笔试 **题目 08**。核心问题：面对同一事件的公告、媒体、研报观点与市场传闻，让研究者识别来源、查看可核原文、比较证据权重、追踪时间和版本，不以 AI 代替投资判断。

> **交付状态：独立源码仓库已准备并通过 CI；已添加免费 Render 单服务云端配置，但尚未连接 Render 账户、创建公开 URL 或完成外网验收。** 本地版经过实际 Harness/DeepSeek 运行验证；公开演示网址只有在完成云端适配和外网验收后才能列为已交付。仓库不包含 API Key、授权原始数据、私有数据库和用户会话。

## 主要功能

- 自然语言提问、实际联网检索、结构化来源登记与可定位原文引用（依赖有效的 DeepSeek/授权检索）。
- 同一主体/行为/时间锚点的证据聚合与版本快照；传递式同源转载去重，保留来源和修订记录。
- 区分 **FACT / OPINION / SPECULATION / RUMOR**，以监管/一手/二手身份、独立来源组、引用状态解释证据强度，不输出虚构可信度百分比。
- 区分事件发生、原始披露、抓取、更新等时间字段；发生时点不明确时明确回退到披露日期。真实行情缺失时不生成假价格。
- 原生 DeepSeek Harness 双栏工作台：对话与研究绑定，选事件查看引用；历史会话切换；无证据或行情错误时显式显示空状态。
- 用户个人判断独立保存，不被模型或后续更新自动覆盖。

## 技术选型与 AI 的角色

Python 3.9+ / FastAPI / SQLite / Vanilla JS / DeepSeek Harness + DeepSeek API；轻量图表使用 Lightweight Charts（LICENSE/NOTICE 随仓库保留）。

DeepSeek 用于研究意图解析、真实资料检索、候选原子事实提取与自然语言解释；Python 负责来源ID、字段校验、原文定位、事件归并、版本快照、会话隔离和异常处理。候选来源、引用和事实并非自动证明真实或完整；需与一手材料逐条核实。

## 数据来源

- **DeepSeek** 的检索/抓取工具（有效凭据/权限下调用）。
- **iFinD MCP** 授权新闻/公告及跨市场数据：支持情况由实际调用决定；失败/空结果要区别标注。
- **扶摇** A 股价格、指数、交易日历：只在实际授权时显示；无行情不得用其他股票替换。
- 未附赠金融数据正文或 Key；遵守供应商使用、转载和公开发布许可。

## 本地运行

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q tests
uvicorn app:app --host 127.0.0.1 --port 8765
```

- 独立研究页面：`http://127.0.0.1:8765/`
- 原生 Harness 工作台：`http://127.0.0.1:8765/workstation`，**另外需要安装官方 DeepSeek Harness** 并完成本机配置；只启动 FastAPI 不会自动产生可用的聊天窗口。
- macOS 已配置钥匙串/官方 Harness 环境时，可以使用 `sh scripts/start_eventlens.sh`。此脚本为**macOS 本地工具**，不适合直接作为云端启动命令；`harness.overlay.yaml` 的本机可执行路径需按实际环境配置。

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 调用模型和检索；必须只在服务端设置，禁止提交、打印到网页 |
| `DEEPSEEK_MODEL` | 可选模型名，具体可用性由授权和提供方决定 |
| `EVENTLENS_DB` | SQLite 数据库路径，默认本地 `data/eventlens.sqlite3` |
| `FUYAO_API_KEY` | 可选扶摇授权 A 股接口；或通过已有本地进程内代理 |
| `ALPHAVANTAGE_API_KEY` | 可选美股行情备用渠道 |
| `EVENTLENS_IFIND_NEWS` | 是否使用有权限的 iFinD 新闻检索，`0` 时禁用 |

参见 `.env.example`。不要将真正的 `.env` 上传 Git。

## 验证记录与交付材料

- [AI 使用及人工修正](AI_VALIDATION.md)
- [测试和异常边界](TESTING.md)
- [真实本机验收及缺口](LIVE_VALIDATION_V05.md)
- [云端部署前必须检查](DEPLOYMENT.md)

## 已知边界与未做事项

1. **当前原版是本机单用户双服务架构**（FastAPI + Harness），尚不能仅将代码推到 GitHub Pages / Render 就获得可用的 AI 工作台；公共部署需独立会话/认证、后端密钥隔离、费用限流、可持续存储及许可证检查。
2. 现有证据规则可显示更正/否认**候选**与版本，但尚未完成对具体旧主张的 `supersedes/refutes` 关系及自动结论替换的完整状态机；不得宣称完全实现。
3. 引文在已抓取正文中定位成功，不等于**独立回源**或语义真实性；模型回答逐句的事实拒绝器尚不完善。
4. 任何主体可尝试研究，但不能保证所有公司/事件有可核证据、授权行情或上市代码。
5. 以新闻和股价同日出现不能推出因果；不作确定性价格预测、收益承诺或买卖建议。

此仓库是从私有开发工作区**选择性导出的源码快照**，不包含原工作区、私人会话或凭据。
## 免费云端版本（待创建服务）

根目录已提供 [render.yaml](render.yaml) 与 [Render 上线指南](RENDER_DEPLOY.md)：
- 使用 Python 3.11 的单个 Render Free Web Service，网页入口为 `/`；本机官方 Harness `/workstation` **不在公网开放**。
- 公网研究通过签名访客 Cookie 隔离；仅开放必要研究 API，限制单会话/单进程研究与追问次数。Render 空闲休眠后数据、计数和会话映射会重置；不是持久化生产系统。
- **实时 AI 必须在 Render 服务端配置有效 DeepSeek Key**；不绑定授权的 iFinD/扶摇本机代理；行情不能保证可用。
- [独立 CI：125 Python + 4 Node 通过（新版）](https://github.com/CorreyZhang/EventLens/actions/runs/44104234071)。仍需在新 commit 上重新验收，真实外网运行与第三方服务有效性不能由 CI 替代。
