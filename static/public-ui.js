// Public Render entrypoint: intentionally omits the local-only Harness iframe.
(() => {
  if (!document.body.classList.contains('public-demo')) return;
  const style = document.createElement('style');
  style.textContent = `
    body.public-demo #lensWorkbench { display: none !important; }
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
  }
})();
