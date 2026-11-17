import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mkdtemp, writeFile, unlink, rmdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../scripts/media-file-input.js', import.meta.url), 'utf8');
const origin = 'https://channels.weixin.qq.com';
const bytes = Uint8Array.of(13, 10, 21, 8);

// 模拟内嵌编辑器和外层网页拥有不同的 File、DataTransfer、Event 构造器。
function fixture() {
  class EditorFile extends File {}
  class EditorEvent extends Event {}
  class EditorTransfer {
    files = [];
    items = { add: file => { assert.ok(file instanceof EditorFile); this.files.push(file); } };
  }
  const page = { origin, pathname: '/platform/post/create' };
  const view = { File: EditorFile, Event: EditorEvent, DataTransfer: EditorTransfer, location: page };
  const ticket = { url: 'http://127.0.0.1:8511/' + 'a'.repeat(43), origin, name: "鹈鹕's #1.JPG", size: bytes.length, type: 'image/jpeg' };
  const events = [], reads = [];
  const input = {
    files: [], isConnected: true, accept: 'image/jpeg,image/png', ownerDocument: { defaultView: view }, matches: () => false,
    dispatchEvent(e) { assert.ok(e instanceof EditorEvent && e.bubbles && e.composed); events.push(e.type); },
  };
  const panel = { isConnected: true, contains: node => node === input, matches: () => false,
    closest: () => null, querySelector: () => null, querySelectorAll: () => [input],
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 40, height: 50 }) };
  const root = { elementFromPoint: () => input };
  const env = { URL, location: page, document: { elementFromPoint: () => ({ shadowRoot: root }) },
    fetch: async (url, options) => { reads.push(url.href); assert.equal(options.credentials, 'omit'); assert.equal(options.redirect, 'error'); return { ok: true, blob: async () => new Blob([bytes], { type: ticket.type }) }; } };
  const adapter = runInNewContext(source, env);
  const call = (step, asset = ticket, expected = input) => adapter(step, ticket.type.startsWith('image/') ? 'cover' : 'video', panel, asset, expected);
  return { call, view, page, ticket, events, reads, input, panel, root, env };
}

test('内嵌封面分两步交付，同一票据重试只读取并通知一次', async () => {
  const { call, input, ticket, events, reads, view } = fixture();
  input.files = [new File([bytes], ticket.name, { type: ticket.type })]; // 复现外层已选同名文件，内嵌编辑器没有接收。
  assert.equal((await call('prepare')).state, 'prepared');
  assert.equal((await call('prepare')).state, 'prepared');
  assert.deepEqual(events, []);
  assert.equal((await call('select')).state, 'selected');
  assert.ok(input.files[0] instanceof view.File);
  assert.deepEqual(new Uint8Array(await input.files[0].arrayBuffer()), bytes);
  input.files = []; // 某些上传器消费后会清空文件框。
  assert.equal((await call('select')).state, 'already_selected');
  const nextTicket = { ...ticket, url: ticket.url.replace(/a{43}$/, 'b'.repeat(43)) };
  assert.equal((await call('prepare', nextTicket)).state, 'already_selected');
  assert.equal(reads.length, 1);
  assert.deepEqual(events, ['input', 'change']);
});

test('支持原 MOV 和四个编辑页，星号 MIME 和扩展名都能匹配', async () => {
  for (const [site, path, accept] of [[origin, '/platform/post/create', 'video/*'],
    ['https://member.bilibili.com', '/platform/upload/video/frame', '.MOV,.mp4'],
    ['https://creator.douyin.com', '/creator-micro/content/upload', 'video/quicktime'],
    ['https://creator.xiaohongshu.com', '/publish/publish', '']]) {
    const { call, page, ticket, input } = fixture();
    Object.assign(page, { origin: site, pathname: path });
    Object.assign(ticket, { origin: site, name: '成片.mov', type: 'video/quicktime' });
    input.accept = accept;
    await call('prepare');
    assert.equal((await call('select')).state, 'selected');
    assert.equal(input.files[0].type, 'video/quicktime');
  }
});

test('来源、回执地址、控件、文件或落点不符时不读取素材', async () => {
  const cases = [f => { f.ticket.origin = 'https://example.org'; }, f => { f.page.pathname = '/platform/dashboard'; },
    f => { f.ticket.url = 'https://example.org/clip'; }, f => { f.ticket.url += '?extra=1'; },
    f => { f.panel.querySelectorAll = () => [f.input, f.input]; }, f => { f.root.elementFromPoint = () => ({}); },
    f => { f.input.matches = () => true; }, f => { f.input.accept = '.txt'; },
    f => { f.panel.closest = () => ({}); }, f => { f.panel.querySelector = () => ({ getClientRects: () => [{}] }); },
    f => { f.input.files = [new File([bytes], '另一张图.jpg', { type: 'image/jpeg' })]; }];
  for (const change of cases) {
    const f = fixture(); change(f);
    await assert.rejects(f.call('prepare'));
    assert.equal(f.reads.length, 0);
    assert.deepEqual(f.events, []);
  }
  const f = fixture();
  await assert.rejects(f.call('prepare', f.ticket, {}));
  assert.equal(f.reads.length, 0);
});

test('用户换了素材、控件被替换或字节数不符都不会选择文件', async () => {
  const f = fixture();
  await f.call('prepare');
  f.input.files = [new File([bytes], '用户的新文件.jpg', { type: 'image/jpeg' })];
  await assert.rejects(f.call('select'));
  f.input.files = [];
  const replacement = { ...f.input };
  f.panel.querySelectorAll = () => [replacement];
  await assert.rejects(f.call('select'));
  assert.deepEqual(f.events, []);
  const bad = fixture(); bad.ticket.size += 1;
  await assert.rejects(bad.call('prepare'), /不符/);
  await assert.rejects(bad.call('select'));
  assert.deepEqual(bad.events, []);
});

test('真实的单文件服务回执能驱动两阶段页面适配', { timeout: 10000 }, async () => {
  const dir = await mkdtemp(join(tmpdir(), 'jack-media-test-'));
  const f = fixture();
  const image = join(dir, f.ticket.name);
  await writeFile(image, bytes);
  const script = fileURLToPath(new URL('../scripts/inject-large-file.sh', import.meta.url));
  const proc = spawn(script, [image, '--serve-only', '--origin', origin, '--timeout', '5']);
  const exit = once(proc, 'exit');
  const lines = createInterface({ input: proc.stdout });
  try {
    const [line] = await once(lines, 'line');
    const receipt = JSON.parse(line);
    f.env.fetch = (url, init) => fetch(url, { ...init, headers: { Origin: f.page.origin } });
    assert.equal((await f.call('prepare', receipt)).state, 'prepared');
    assert.equal((await exit)[0], 0);
    assert.equal((await f.call('select', receipt)).state, 'selected');
    assert.deepEqual(new Uint8Array(await f.input.files[0].arrayBuffer()), bytes);
    assert.deepEqual(f.events, ['input', 'change']);
  } finally {
    lines.close();
    if (proc.exitCode === null && proc.signalCode === null) proc.kill();
    await exit;
    await unlink(image);
    await rmdir(dir);
  }
});
