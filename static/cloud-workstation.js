/* Public twin of the original Harness shell: preserve the same two-pane
   layout and actual EventLens evidence timeline, but DO NOT expose native
   Harness's privileged filesystem/terminal agents to anonymous visitors. */
(() => {
  const left = document.querySelector('#research');
  const right = document.querySelector('#agent');
  const overlay = document.querySelector('#studyOverlay');
  const selection = document.querySelector('#selection');
  const title = document.querySelector('#studyTitle');
  const status = document.querySelector('#bridgeStatus');
  const tray = document.querySelector('#referenceTray');
  let current = null;

  function setStudy(id, question) {
    if (!/^[a-f0-9]{32}$/.test(String(id || ''))) return;
    if (current !== id) {
      current = id;
      left.src = '/?embedded=1&cloud=1#' + encodeURIComponent(id);
    }
    selection.textContent = question || '研究已连接 · 可在左侧点选证据';
    title.textContent = question || '当前事件研究';
    overlay.classList.remove('visible');
  }

  function showNotice(message) {
    status.textContent = message;
    status.classList.toggle('visible', Boolean(message));
  }
  overlay.classList.add('visible');
  document.querySelector('#overlayTitle').textContent = '新的研究';
  document.querySelector('#overlayMessage').textContent =
    '在右侧提问，左侧将显示原版 EventLens 的真实事件时间线、证据与行情状态。';
  document.querySelector('#agentSelection').textContent =
    '实际 DeepSeek 检索 · 不包含原生 Harness 的本地文件/终端权限';
  tray.classList.remove('visible');

  window.addEventListener('message', (event) => {
    if (event.origin !== location.origin) return;
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;
    if (event.source === right.contentWindow && msg.type === 'eventlens:cloud-study') {
      setStudy(msg.research_id, msg.question);
    }
    if (event.source === left.contentWindow && msg.type === 'eventlens:quote') {
      if (!msg.reference || msg.reference.research_id !== current) return;
      right.contentWindow.postMessage(
        {type:'eventlens:cloud-quote', reference:msg.reference}, location.origin
      );
      showNotice('已将这条原文证据附在右侧对话的下一次追问中。');
    }
  });
  document.querySelectorAll('button[data-pane]').forEach(button => {
    button.onclick = () => {
      document.body.dataset.pane = button.dataset.pane;
      document.querySelectorAll('button[data-pane]').forEach(b =>
        b.classList.toggle('active', b === button));
    };
  });
})();
