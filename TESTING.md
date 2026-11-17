# 测试说明与运行方法

## 运行命令

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
node --check static/app.js
node --check static/workbench.js
node --check harness-navigation/client.js
node --check harness_session_bridge.mjs
node --test tests/js/navigation.test.cjs
```

## 覆盖矩阵

| 场景 | 测试/机制 | 边界 |
|---|---|---|
| 主链路：提问→检索→引用→同一事件归并→版本 | `tests/test_research.py`, `test_v03.py`, `test_event_assessment.py`; 本机 Harness 真实操作见 `LIVE_VALIDATION_V05.md` | 多源语义是否完全同事件仍需人工核对 |
| 事实/观点/推测/传闻、证据强度、转载同源 | `test_event_assessment.py`、`test_research.py` | 证据分类不是事实自动认证 |
| 发生/披露/抓取/更新及交易会话 | `test_chronological_timeline.py`, `test_v03.py` | 缺少原文时间时不能猜测 |
| 更正、否认、冲突、版本 | `test_event_assessment.py` 处理候选及旧版本保留 | **完整旧新结论 supersedes/refutes 状态机仍未实现** |
| 数据缺失、授权或日历失败 | `test_market.py`, `test_fuyao.py`, `test_catl_fallback.py` | 行情无数据时不造价格或指数代理 |
| 未知实体、切换公司、历史对话、不串来源 | `test_research_focus.py`, `test_workspace_bridge.py`, `test_v05.py`, `tests/js/navigation.test.cjs` | 原生公共多用户同时在线隔离尚未实测 |
| 极端/合规：伪造 source_id、非法kind、乱码JSON、空正文、重复提交、失败预算 | `test_v05.py`, `test_research.py`; 本机 HTTP 422/409/429 | 正确拒绝异常 ≠ 正常检索通过 |
| 合规：价格口径/买卖建议/无依据因果 | `marketdata.py` 数据校验与模型提示，人工问答纠错 | 原生模型逐句语义拒绝仍未完成 |
| 出处抽查/真实供应商 | `LIVE_VALIDATION_V05.md` | iFinD 本机一次真实调用失败；3条独立原站复核未匹配 |

## 历史记录（不能替代本仓库新运行）

用户 Mac v0.5 最终回执：**121 passed in 1.83s**（Python），**4 passed**（Node）。实际浏览器操作与离线 fixtures 分别记载。**新仓库独立 CI 已通过**：[GitHub Actions 运行 #44101895960](https://github.com/CorreyZhang/EventLens/actions/runs/44101895960)。Python **121 passed（5 warnings）**，Node **4 passed**，JS 语法检查与 Python 编译均通过。该结果只覆盖无密钥自动化测试，不是公网真实金融源或多用户安全验收。

## 提交前手工验收

- 新对话查同花顺季度报告，左侧实际产生原始引文和按时间排序事件。
- 同一研究补充媒体资料，检查同一事件的不同来源及版本快照。
- 选择“更正/否认候选”，确认 UI 准确标记**待人工复核**，不可谎称已自动撤销旧结论。
- 换另一公司，旧公司新闻、行情、引用全部清除；缺数据有明确提示。
- 无模型 Key 或上游失败，不得生成“正常”的事实和价格。
- 以外网地址、无痕模式测试，确认不得读取其他访客研究、私人数据或 API Key。

## 公网版隔离与预算回归（追加）

新增 `tests/test_public_access.py`，检查不同浏览器的研究列表与详情隔离、伪造 Cookie 不得取走研究、公开禁用 Harness / 工作区管理接口、禁止手动证据写入或无限增量刷新、跨站/非 JSON 写入拒绝、整个实例研究上限、云端独立研究入口的 HTML 装载。

2026-11-17 独立仓库 GitHub Actions 上一轮已通过 **126 Python + 4 Node**，见 [Actions](https://github.com/CorreyZhang/EventLens/actions/runs/44104640091)；后续更新以新提交的 Actions 为准。该回归不包含带真实密钥的 Render 端到端实验。
