// panel 是已在当前草稿核对过的可见上传区，ticket 为单文件助手回执。
// prepare 仅读取素材；重新同步后调用 select 才会通知页面选中了文件。
(async function mediaFileInput(phase, kind, panel, ticket, expectedInput) {
  const routes = {
    'https://channels.weixin.qq.com': /^\/platform\/post\/(create|edit)\/?$/,
    'https://creator.xiaohongshu.com': /^\/publish\/publish\/?$/,
    'https://creator.douyin.com': /^\/creator-micro\/content\/(upload|publish)(\/[^/]*)?\/?$/,
    'https://member.bilibili.com': /^\/platform\/upload\/video\/frame\/?$/,
  };
  const origin = location.origin;
  if (!routes[origin]?.test(location.pathname) || ticket.origin !== origin) {
    throw new Error('请核对创作者编辑页与单文件回执的来源');
  }
  const url = new URL(ticket.url);
  if (url.origin !== `http://127.0.0.1${url.port ? ':' + url.port : ''}` ||
      url.username || url.password || url.search || url.hash || !/^\/[A-Za-z0-9_-]{43}$/.test(url.pathname)) {
    throw new Error('需要单文件服务返回的本机地址');
  }
  const { name, size, type } = ticket;
  const mediaKind = kind === 'video' ? 'video/' : kind === 'cover' ? 'image/' : null;
  if (!mediaKind || typeof type !== 'string' || !type.startsWith(mediaKind) || typeof name !== 'string' || !name ||
      !Number.isSafeInteger(size) || size <= 0) {
    throw new Error('请核对回执的文件名、字节数和素材类型');
  }
  if (phase !== 'prepare' && phase !== 'select') throw new Error('操作应为 prepare 或 select');

  // 用实际落点确认这个卡片可接收操作，包括开放的 shadow root。遇到真实遮挡则留给原生界面处理。
  function currentInput() {
    if (!panel?.isConnected || panel.matches('html, body')) throw new Error('上传卡片已变化，请重新同步');
    if (panel.closest('[aria-busy="true"]')) throw new Error('上传区正在处理，请先查看平台进度');
    const progress = panel.querySelector('progress, [role="progressbar"]');
    if (progress?.getClientRects().length) throw new Error('上传区已有进度，请先查看平台回执');
    const rect = panel.getBoundingClientRect();
    const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
    let hit = document.elementFromPoint(x, y);
    while (hit?.shadowRoot?.elementFromPoint) {
      const inner = hit.shadowRoot.elementFromPoint(x, y);
      if (!inner || inner === hit) break;
      hit = inner;
    }
    if (!rect.width || !rect.height || !hit || !panel.contains(hit)) throw new Error('请让目标上传卡片可见并处理遮挡');
    const selector = 'input[type=file]';
    const inputs = panel.matches(selector) ? [panel] : panel.querySelectorAll(selector);
    if (inputs.length !== 1 || inputs[0].matches(':disabled') || (expectedInput && inputs[0] !== expectedInput)) {
      throw new Error('需要当前卡片内唯一且已核对的可用文件框');
    }
    const input = inputs[0];
    const accepts = input.accept.toLowerCase().split(',').map(s => s.trim()).filter(Boolean);
    const ext = name.includes('.') ? '.' + name.split('.').pop().toLowerCase() : '';
    if (accepts.length && !accepts.some(s => s === '*/*' || s === type || s === mediaKind + '*' || s === ext)) {
      throw new Error('文件格式与当前卡片不符');
    }
    return input;
  }

  const input = currentInput();
  const view = input.ownerDocument.defaultView;
  if (view?.location.origin !== origin) throw new Error('文件框与草稿不在同一平台');
  if (![view.File, view.DataTransfer, view.Event].every(ctor => typeof ctor === 'function')) {
    throw new Error('该编辑器需要使用原生文件选择');
  }
  const slot = Symbol.for('jack-media-publisher.media.file');
  const entry = input[slot];
  const existing = input.files[0];
  if (input.files.length > 1 || (existing && (existing.name !== name || existing.size !== size || existing.type !== type))) {
    throw new Error('文件框已有其他素材，请先核对当前草稿');
  }
  if (entry?.state === 'selected') {
    if (entry.name === name && entry.size === size && entry.type === type) return { state: 'already_selected', name, size };
    throw new Error('该入口已交付过其他素材，请先核对或在平台主动选择更换');
  }
  if (entry?.state === 'prepared' && entry.url !== url.href) throw new Error('该控件已有待选择的素材，请核对原回执');
  if (existing instanceof view.File) return { state: 'already_selected', name, size };

  if (phase === 'prepare') {
    if (entry?.url === url.href && entry.state === 'prepared') return { state: 'prepared', name, size };
    if (entry?.state === 'reading') throw new Error('正在读取本机素材');
    const pending = { url: url.href, state: 'reading', existing };
    input[slot] = pending;
    try {
      const response = await fetch(url, { credentials: 'omit', redirect: 'error', cache: 'no-store' });
      if (!response.ok) throw new Error(`读取本机素材失败（${response.status}）`);
      const blob = await response.blob();
      if (blob.size !== size || blob.type !== type) throw new Error('收到的素材与回执不符');
      // 跨窗口的 Blob 可以作为文件内容。由目标窗口构造 File，兼容 wujie 对 File 类型的检查。
      const file = new view.File([blob], name, { type });
      if (file.size !== size || input[slot] !== pending || !input.isConnected) throw new Error('素材或目标文件框已变化');
      input[slot] = { ...pending, state: 'prepared', file };
      return { state: 'prepared', name, size };
    } catch (err) {
      if (input[slot] === pending) delete input[slot];
      throw err;
    }
  }

  if (entry?.state !== 'prepared' || entry.url !== url.href || entry.existing !== existing ||
      entry.file.name !== name || entry.file.size !== size || entry.file.type !== type) {
    throw new Error('当前文件框缺少这次已核对的素材，请重新检查');
  }
  const transfer = new view.DataTransfer();
  transfer.items.add(entry.file);
  input.files = transfer.files;
  input[slot] = { state: 'selected', name, size, type };
  for (const event of ['input', 'change']) input.dispatchEvent(new view.Event(event, { bubbles: true, composed: true }));
  return { state: 'selected', name, size }; // 平台上传结果另外验收。
})
