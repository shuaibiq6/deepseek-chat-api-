/* =========================================================
 * 应用逻辑：状态管理、渲染、事件绑定、子功能跳转
 * 覆盖后端全部能力：
 *   - 对话（流式 / 非流式 + 多轮上下文）
 *   - 会话列表（分页加载）
 *   - 历史消息查看
 *   - 删除会话
 *   - 健康检查
 * ========================================================= */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ---------------- 状态 ---------------- */
  const state = {
    conversations: [],
    total: 0,
    offset: 0,
    limit: 20,
    currentConvId: null,
    currentTitle: '开始新对话',
    messages: [],
    sending: false,
    systemPrompt: localStorage.getItem('ds_system_prompt') || '',
    temperature: parseFloat(localStorage.getItem('ds_temperature') || '0.7'),
    maxTokens: parseInt(localStorage.getItem('ds_max_tokens') || '2048', 10),
    stream: localStorage.getItem('ds_stream') !== '0',
  };

  /* ---------------- 工具函数 ---------------- */
  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function toast(message, type = 'info', duration = 2600) {
    const el = $('#toast');
    el.textContent = message;
    el.className = `toast ${type}`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add('hidden'), duration);
  }

  function setBusy(busy) {
    state.sending = busy;
    $('#btnSend').disabled = busy || !$('#messageInput').value.trim();
    $('#btnSend').textContent = busy ? '生成中…' : '发送';
  }

  function scrollToBottom(smooth = true) {
    const el = $('#messages');
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
  }

  function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 180) + 'px';
  }

  /* ---------------- 健康检查 ---------------- */
  async function checkHealth() {
    const badge = $('#healthBadge');
    const text = $('#healthText');
    badge.className = 'health-badge is-checking';
    text.textContent = '检测服务状态…';
    try {
      const data = await Api.health();
      badge.className = 'health-badge ok';
      text.textContent = `服务在线 · v${data.version}`;
    } catch (e) {
      badge.className = 'health-badge err';
      text.textContent = `服务离线：${e.message}`;
    }
  }

  /* ---------------- 会话列表 ---------------- */
  async function loadConversations(append = false) {
    if (!append) { state.offset = 0; state.conversations = []; }
    try {
      const data = await Api.listConversations(state.limit, state.offset);
      state.total = data.total;
      const items = data.items || [];
      if (append) {
        // 追加时按 id 去重：新会话会插入列表顶部，陈旧 offset 可能导致重复
        const seen = new Set(state.conversations.map((c) => c.id));
        state.conversations = state.conversations.concat(
          items.filter((c) => !seen.has(c.id))
        );
      } else {
        state.conversations = items;
      }
      state.offset = state.conversations.length;
      renderConversations();
      $('#btnLoadMore').classList.toggle('hidden', state.offset >= state.total);
    } catch (e) {
      toast(`加载会话失败：${e.message}`, 'error');
    }
  }

  function renderConversations() {
    const list = $('#convList');
    if (state.conversations.length === 0) {
      list.innerHTML = `<div class="conv-empty" style="text-align:center;color:var(--text-3);font-size:13px;padding:24px 0;">暂无会话<br>点击「新建对话」开始</div>`;
      return;
    }
    list.innerHTML = state.conversations.map((c) => `
      <div class="conv-item ${c.id === state.currentConvId ? 'active' : ''}" data-id="${c.id}">
        <span class="conv-icon">💬</span>
        <div class="conv-body">
          <div class="conv-title">${escapeHtml(c.title || '未命名会话')}</div>
          <div class="conv-preview">${escapeHtml(c.last_message || '（空会话）')}</div>
        </div>
        <span class="conv-count">${c.message_count}</span>
        <button class="conv-del" data-del="${c.id}" title="删除会话">🗑</button>
      </div>
    `).join('');
  }

  /* ---------------- 消息渲染 ---------------- */
  function addMessageEl(role, content, isStreaming = false) {
    const wrap = $('#messages');
    const el = document.createElement('div');
    el.className = `msg ${role}`;
    const avatar = role === 'user' ? '🧑' : '🤖';
    el.innerHTML = `
      <div class="msg-avatar">${avatar}</div>
      <div class="msg-body">
        <div class="msg-bubble ${isStreaming ? 'md' : 'md'}">${isStreaming ? '' : renderMarkdown(content)}</div>
        <div class="msg-role-tag">${role === 'user' ? '你' : 'DeepSeek'}</div>
      </div>
    `;
    wrap.appendChild(el);
    return el.querySelector('.msg-bubble');
  }

  function renderMessages() {
    const wrap = $('#messages');
    wrap.innerHTML = '';
    if (state.messages.length === 0) {
      wrap.innerHTML = `<div class="welcome"><div class="welcome-icon">✦</div>
        <h2>${escapeHtml(state.currentTitle || '开始新对话')}</h2>
        <p>该会话暂无消息，输入内容开始对话。</p></div>`;
      return;
    }
    state.messages.forEach((m) => {
      const el = addMessageEl(m.role === 'user' ? 'user' : 'assistant', m.content);
      if (m.role === 'error') el.closest('.msg').classList.add('error');
    });
    scrollToBottom(false);
  }

  /* ---------------- 选中会话 / 历史 ---------------- */
  async function selectConversation(id) {
    state.currentConvId = id;
    renderConversations();
    $('#welcome')?.remove();
    $('#messages').innerHTML = '<div style="text-align:center;color:var(--text-3);padding:40px;">加载历史消息…</div>';
    try {
      const data = await Api.getMessages(id);
      state.messages = data.messages || [];
      state.currentTitle = (state.conversations.find((c) => c.id === id) || {}).title || '会话';
      renderMessages();
      updateChatMeta();
    } catch (e) {
      toast(`加载历史失败：${e.message}`, 'error');
      renderMessages();
    }
  }

  function updateChatMeta() {
    const count = state.messages.length;
    $('#chatMeta').textContent = count === 0
      ? '— 尚未发送消息'
      : `${count} 条消息 · conversation_id=${state.currentConvId ?? '（新建）'}`;
  }

  /* ---------------- 新建对话 ---------------- */
  function newConversation() {
    if (state.sending) return;
    state.currentConvId = null;
    state.currentTitle = '开始新对话';
    state.messages = [];
    renderConversations();
    renderMessages();
    updateChatMeta();
    $('#chatTitle').textContent = '开始新对话';
    $('#messageInput').value = '';
    autoResize($('#messageInput'));
    $('#messageInput').focus();
    toast('已开始新对话（发送时不携带 conversation_id）');
  }

  /* ---------------- 发送消息 ---------------- */
  async function sendMessage() {
    if (state.sending) return;
    const input = $('#messageInput');
    const text = input.value.trim();
    if (!text) return;
    if (!navigator.onLine) { toast('当前网络不可用', 'error'); return; }

    input.value = '';
    autoResize(input);
    $('#welcome')?.remove();
    setBusy(true);
    $('#chatTitle').textContent = state.currentTitle;

    const payload = {
      message: text,
      conversation_id: state.currentConvId,
      stream: state.stream,
      system_prompt: state.systemPrompt || undefined,
      max_tokens: state.maxTokens,
      temperature: state.temperature,
    };
    // 清理 undefined 字段
    Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);

    // 渲染用户消息
    addMessageEl('user', text);
    state.messages.push({ role: 'user', content: text });

    // 助手消息（流式时增量更新）
    const bubble = addMessageEl('assistant', '', true);
    bubble.innerHTML = '<span class="caret"></span>';
    let full = '';
    const updateTitleAndMeta = () => {
      if (state.currentConvId) $('#chatTitle').textContent = state.currentTitle;
    };

    try {
      if (payload.stream) {
        await Api.sendChat(payload, {
          onDelta: (chunk) => {
            full += chunk;
            bubble.innerHTML = renderMarkdown(full) + '<span class="caret"></span>';
            scrollToBottom();
          },
          onDone: (ev) => {
            bubble.innerHTML = renderMarkdown(full);
            state.currentConvId = ev.conversation_id;
            state.messages.push({ role: 'assistant', content: full });
            updateTitleAndMeta();
            updateChatMeta();
          },
        });
      } else {
        const data = await Api.sendChat(payload);
        full = data.reply || '';
        bubble.innerHTML = renderMarkdown(full);
        state.currentConvId = data.conversation_id;
        state.messages.push({ role: 'assistant', content: full });
        updateTitleAndMeta();
        updateChatMeta();
      }
    } catch (e) {
      bubble.closest('.msg').classList.add('error');
      bubble.innerHTML = `⚠ ${escapeHtml(e.message)}`;
      toast(`请求失败：${e.message}`, 'error');
    } finally {
      setBusy(false);
      scrollToBottom();
      loadConversations(); // 全量刷新侧栏（新会话插入顶部，标题/计数/预览最新）
    }
  }

  /* ---------------- 删除会话 ---------------- */
  function confirmDelete(id) {
    const conv = state.conversations.find((c) => c.id === id);
    const title = conv ? conv.title : `#${id}`;
    openConfirm(
      '删除会话',
      `确定删除「${title}」吗？该会话及其全部消息将被永久删除（DELETE /api/v1/conversations/${id}）。`,
      async () => {
        try {
          await Api.deleteConversation(id);
          toast('会话已删除', 'success');
          if (state.currentConvId === id) newConversation();
          await loadConversations();
        } catch (e) {
          toast(`删除失败：${e.message}`, 'error');
        }
      }
    );
  }

  /* ---------------- 弹窗通用 ---------------- */
  function openModal(id) { $(`#${id}`).classList.remove('hidden'); }
  function closeModal(id) { $(`#${id}`).classList.add('hidden'); }

  function openConfirm(title, text, onOk) {
    $('#confirmTitle').textContent = title;
    $('#confirmText').textContent = text;
    openModal('confirmModal');
    confirmModal._onOk = onOk;
  }

  /* ---------------- Markdown 渲染（安全子集） ---------------- */
  function renderMarkdown(text) {
    let out = escapeHtml(text);

    // 代码块（先保护占位符）
    const blocks = [];
    out = out.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      blocks.push(`<pre><code>${code.trim()}</code></pre>`);
      return `\u0000${blocks.length - 1}\u0000`;
    });

    // 行内代码
    out = out.replace(/`([^`\n]+)`/g, '<code>$1</code>');

    // 标题
    out = out.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
    out = out.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
    out = out.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');

    // 引用
    out = out.replace(/^&gt;\s?(.*)$/gm, '<blockquote>$1</blockquote>');

    // 加粗 / 斜体
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // 链接（仅 http/https/mailto，安全过滤）
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // 列表
    const listify = (re, tag) =>
      out.replace(re, (m) => {
        const items = m.split('\n').map((l) => l.replace(/^[-*]\s+|\^\s+\d+\.\s+/, '')).filter(Boolean);
        return `<${tag}>${items.map((i) => `<li>${i}</li>`).join('')}</${tag}>`;
      });
    out = listify(/(?:^[-*]\s+.*(?:\n|$))+/gm, 'ul');
    out = listify(/(?:^\d+\.\s+.*(?:\n|$))+/gm, 'ol');

    // 空行 -> 段落分隔
    out = out.replace(/\n{2,}/g, '\n\n');

    // 恢复代码块
    out = out.replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[Number(i)]);

    // 换行
    out = out.replace(/([^\n])\n(?=[^\n])/g, '$1<br>');

    return out || '<em>（空回复）</em>';
  }

  /* ---------------- 事件绑定 ---------------- */
  function bindEvents() {
    // 新建对话
    $('#btnNewChat').addEventListener('click', newConversation);

    // 发送
    $('#btnSend').addEventListener('click', sendMessage);
    $('#messageInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        if (!$('#btnSend').disabled) sendMessage();
      }
    });
    $('#messageInput').addEventListener('input', (e) => {
      autoResize(e.target);
      $('#btnSend').disabled = state.sending || !e.target.value.trim();
    });

    // 会话列表事件委托
    $('#convList').addEventListener('click', (e) => {
      const del = e.target.closest('[data-del]');
      if (del) { e.stopPropagation(); confirmDelete(Number(del.dataset.del)); return; }
      const item = e.target.closest('.conv-item');
      if (item) selectConversation(Number(item.dataset.id));
    });
    $('#btnRefresh').addEventListener('click', () => loadConversations());
    $('#btnLoadMore').addEventListener('click', () => loadConversations(true));

    // 流式开关
    $('#streamToggle').addEventListener('change', (e) => {
      state.stream = e.target.checked;
      localStorage.setItem('ds_stream', state.stream ? '1' : '0');
    });

    // 主题切换
    $('#btnTheme').addEventListener('click', () => {
      const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
      document.documentElement.dataset.theme = next;
      localStorage.setItem('ds_theme', next);
    });

    // 健康检查点击刷新
    $('#healthBadge').addEventListener('click', checkHealth);

    // 弹窗关闭
    $$('[data-close]').forEach((btn) =>
      btn.addEventListener('click', () => closeModal(btn.dataset.close))
    );
    $$('.modal-mask').forEach((mask) =>
      mask.addEventListener('click', (e) => {
        if (e.target === mask) mask.classList.add('hidden');
      })
    );

    // 系统提示词
    $('#btnSystemPrompt').addEventListener('click', () => {
      $('#promptInput').value = state.systemPrompt;
      openModal('promptModal');
    });
    $('#btnSavePrompt').addEventListener('click', () => {
      state.systemPrompt = $('#promptInput').value.trim();
      localStorage.setItem('ds_system_prompt', state.systemPrompt);
      closeModal('promptModal');
      updateParamsSummary();
      toast(state.systemPrompt ? '系统提示词已保存' : '已清空系统提示词', 'success');
    });

    // 生成参数
    $('#btnParams').addEventListener('click', () => {
      $('#tempInput').value = state.temperature;
      $('#tokenInput').value = state.maxTokens;
      $('#tempValue').textContent = state.temperature.toFixed(1);
      $('#tokenValue').textContent = state.maxTokens;
      openModal('paramsModal');
    });
    $('#tempInput').addEventListener('input', (e) => {
      $('#tempValue').textContent = Number(e.target.value).toFixed(1);
    });
    $('#tokenInput').addEventListener('input', (e) => {
      $('#tokenValue').textContent = e.target.value;
    });
    $('#btnSaveParams').addEventListener('click', () => {
      state.temperature = parseFloat($('#tempInput').value);
      state.maxTokens = parseInt($('#tokenInput').value, 10);
      localStorage.setItem('ds_temperature', state.temperature);
      localStorage.setItem('ds_max_tokens', state.maxTokens);
      closeModal('paramsModal');
      updateParamsSummary();
      toast('生成参数已保存', 'success');
    });

    // 设置
    $('#btnSettings').addEventListener('click', () => {
      $('#setApiBase').value = Api.getBase();
      $('#setApiKey').value = Api.getKey();
      $('#setStream').checked = state.stream;
      $('#setTheme').value = document.documentElement.dataset.theme;
      openModal('settingsModal');
    });
    $('#btnSaveSettings').addEventListener('click', () => {
      Api.setBase($('#setApiBase').value);
      Api.setKey($('#setApiKey').value);
      state.stream = $('#setStream').checked;
      localStorage.setItem('ds_stream', state.stream ? '1' : '0');
      document.documentElement.dataset.theme = $('#setTheme').value;
      localStorage.setItem('ds_theme', $('#setTheme').value);
      $('#apiKeyInput').value = Api.getKey();
      $('#streamToggle').checked = state.stream;
      closeModal('settingsModal');
      checkHealth();
      loadConversations();
      toast('设置已保存', 'success');
    });

    // API Key 快捷保存
    $('#btnSaveKey').addEventListener('click', () => {
      Api.setKey($('#apiKeyInput').value);
      toast('API Key 已保存', 'success');
      checkHealth();
    });
    $('#apiKeyInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') $('#btnSaveKey').click();
    });

    // 确认弹窗
    $('#btnConfirmOk').addEventListener('click', async () => {
      closeModal('confirmModal');
      if (confirmModal._onOk) { const fn = confirmModal._onOk; confirmModal._onOk = null; await fn(); }
    });

    // 清空当前视图（仅本地，不影响后端）
    $('#btnClearView').addEventListener('click', () => {
      if (state.sending) return;
      state.currentConvId = null;
      state.messages = [];
      state.currentTitle = '开始新对话';
      renderMessages();
      updateChatMeta();
    });
  }

  /* ---------------- 参数摘要 ---------------- */
  function updateParamsSummary() {
    const parts = [];
    if (state.systemPrompt) parts.push(`📋 ${state.systemPrompt.slice(0, 14)}${state.systemPrompt.length > 14 ? '…' : ''}`);
    parts.push(`temp=${state.temperature}`);
    parts.push(`max_tokens=${state.maxTokens}`);
    $('#paramsSummary').textContent = parts.join(' · ');
  }

  /* ---------------- 初始化 ---------------- */
  async function init() {
    // 恢复主题
    const theme = localStorage.getItem('ds_theme') || 'light';
    document.documentElement.dataset.theme = theme;

    // 恢复 API Key / 开关
    $('#apiKeyInput').value = Api.getKey();
    $('#streamToggle').checked = state.stream;
    updateParamsSummary();

    bindEvents();
    updateChatMeta();
    checkHealth();
    await loadConversations();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
