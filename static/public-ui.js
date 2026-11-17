// Public Render entrypoint: intentionally omits the local-only Harness iframe.
(() => {
  if (!document.body.classList.contains('public-demo')) return;
  // Legacy evidence cards are the actual FastAPI research UI. In v0.3 they
  // are hidden by default because the local Harness workbench replaces them.
  // The cloud does not run Harness, so enable the existing real results UI.
  document.body.classList.add('show-legacy');
  const style = document.createElement('style');
  style.textContent = `
    html { min-height: 100%; background: var(--canvas); }
    body.public-demo { min-height: 100vh; background: var(--canvas); }
    body.public-demo main { min-height: 100vh; }
    body.public-demo #lensWorkbench { display: none !important; }
    body.public-demo #workspace:not([hidden]) .tabs { display: flex !important; }
    body.public-demo #workspace:not([hidden]) .columns { display: grid !important; grid-template-columns: minmax(0, 1fr) 280px !important; }
    body.public-demo #refresh { display: none !important; }
    body.public-demo #askRefresh, body.public-demo #askForm label:has(#askRefresh) { display: none !important; }
    body.public-demo .intro { max-width: 820px; }
    body.public-demo .intro h1 { white-space: normal; }
    body.public-demo #workspace { max-width: 1200px; margin: 0 auto; }
    body.public-demo #workspace .columns > div, body.public-demo #workspace .columns > aside { min-width: 0; }
    body.public-demo #workspace .view { min-height: 130px; }
    body.public-demo #workspace .judgment { display: block; }
    body.public-demo #workspace .judgment textarea { min-height: 95px; }
    @media(max-width: 900px) {
      body.public-demo #workspace:not([hidden]) .columns { grid-template-columns: 1fr !important; }
      body.public-demo #workspace .judgment { position: static; }
    }
    body.public-demo .intro { padding-bottom: 8px; }
    body.public-demo .public-demo-note {
      margin-top: 14px; padding: 12px 14px; max-width: 820px;
      border: 1px solid #cad8d5; border-radius: 12px;
      background: rgba(240, 247, 244, .75); color: #38564d;
      font-size: 13px; line-height: 1.7;
    }
    body.public-demo .public-demo-note strong { display: block; margin-bottom: 3px; }
  `;
  document.head.appendChild(style);
  const workspace = document.querySelector('#workspace');
  const syncWorkspaceVisibility = () => {
    document.body.classList.toggle('has-result', !!workspace && !workspace.hidden);
  };
  if (workspace) {
    new MutationObserver(syncWorkspaceVisibility).observe(workspace, {attributes:true, attributeFilter:['hidden']});
    syncWorkspaceVisibility();
  }
  const intro = document.querySelector('.intro');
  if (intro) {
    const note = document.createElement('div');
    note.className = 'public-demo-note';
    const title = document.createElement('strong');
    title.textContent = '在线研究演示 · 独立 Web 版';
    note.appendChild(title);
    note.appendChild(document.createTextNode(
      '输入投资事件，查看 AI 检索、引用、事件来源和版本。证据分类不等于事实认证；' +
      '已授权行情可能不可用。体验有调用次数限制，页面空闲后历史可能因免费服务器休眠丢失。' +
      '本页不连接 Mac 上的原生 DeepSeek Harness。'
    ));
    intro.appendChild(note);
    // Prompt an actual investment question, rather than a general greeting:
    // the model extracts verifiable event evidence and may reject small talk.
    const input = document.querySelector('#question');
    if (input) input.placeholder = '例如：同花顺2026年三季报有哪些关键事实？先找原始公告';
  }
})();
