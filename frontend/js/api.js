/* =========================================================
 * API 封装层：统一请求、鉴权头、错误处理与 SSE 流式解析
 * 后端接口（前缀 /api/v1）：
 *   POST   /chat                       发起对话（stream 可选）
 *   GET    /conversations              会话列表（分页）
 *   GET    /conversations/{id}/messages 会话历史
 *   DELETE /conversations/{id}         删除会话
 *   GET    /health                     健康检查（免鉴权）
 * ========================================================= */

const Api = (() => {
  // ---------- 配置持久化 ----------
  const LS_BASE = 'ds_api_base';
  const LS_KEY = 'ds_api_key';

  function getBase() {
    return localStorage.getItem(LS_BASE) || window.location.origin.replace(/\/+$/, '');
  }
  function setBase(v) {
    localStorage.setItem(LS_BASE, (v || '').trim().replace(/\/+$/, ''));
  }
  function getKey() {
    return localStorage.getItem(LS_KEY) || '';
  }
  function setKey(v) {
    localStorage.setItem(LS_KEY, (v || '').trim());
  }

  // ---------- 请求头 ----------
  function headers(json = true) {
    const h = {};
    const key = getKey();
    if (key) h['X-API-Key'] = key;
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }

  // ---------- 错误解析 ----------
  async function parseError(resp) {
    let detail = `HTTP ${resp.status}`;
    let code = '';
    try {
      const data = await resp.json();
      if (data.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
      if (data.code) code = data.code;
    } catch (_) { /* 忽略非 JSON 响应 */ }
    const err = new Error(detail);
    err.status = resp.status;
    err.code = code;
    return err;
  }

  // ---------- 通用请求 ----------
  async function request(path, options = {}) {
    const { json = true, auth = true, ...rest } = options;
    const url = `${getBase()}${path}`;
    const h = headers(json);
    if (!auth) delete h['X-API-Key'];
    const resp = await fetch(url, { ...rest, headers: h });
    if (!resp.ok) throw await parseError(resp);
    if (resp.status === 204) return null;
    return resp.json();
  }

  // ---------- 业务接口 ----------
  async function health() {
    return request('/health', { json: false, auth: false, method: 'GET' }).then((r) =>
      r ? r : null
    );
  }

  async function listConversations(limit = 20, offset = 0) {
    return request(`/api/v1/conversations?limit=${limit}&offset=${offset}`, { method: 'GET' });
  }

  async function getMessages(conversationId) {
    return request(`/api/v1/conversations/${conversationId}/messages`, { method: 'GET' });
  }

  async function deleteConversation(conversationId) {
    return request(`/api/v1/conversations/${conversationId}`, { method: 'DELETE' });
  }

  /**
   * 发起对话。payload: { message, conversation_id, stream, system_prompt, max_tokens, temperature }
   * handlers: { onDelta(content), onDone(event), onError(message) }
   * 非流式直接返回 { conversation_id, message_id, reply, model }
   */
  async function sendChat(payload, handlers = {}) {
    if (!payload.stream) {
      return request('/api/v1/chat', { method: 'POST', body: JSON.stringify(payload) });
    }

    // ---- SSE 流式 ----
    const url = `${getBase()}/api/v1/chat`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw await parseError(resp);
    if (!resp.body) {
      throw new Error('浏览器不支持流式响应（ReadableStream）');
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    // 解析并消费服务端 SSE 帧：data: {json}\n\n
    function consume() {
      let sepIndex;
      while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sepIndex).trim();
        buffer = buffer.slice(sepIndex + 2);
        if (!frame.startsWith('data:')) continue;
        const raw = frame.slice(5).trim();
        if (!raw) continue;
        let ev;
        try { ev = JSON.parse(raw); } catch (_) { continue; }
        if (ev.type === 'delta' && typeof ev.content === 'string') {
          if (handlers.onDelta) handlers.onDelta(ev.content);
        } else if (ev.type === 'done') {
          if (handlers.onDone) handlers.onDone(ev);
          return true; // 结束标记
        } else if (ev.type === 'error') {
          throw new Error(ev.message || '上游模型返回错误');
        }
      }
      return false;
    }

    let finished = false;
    while (!finished) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      finished = consume();
    }
    if (!finished) buffer += decoder.decode(); // flush 残留
    consume();
    return null;
  }

  return { getBase, setBase, getKey, setKey, health, listConversations, getMessages, deleteConversation, sendChat };
})();
