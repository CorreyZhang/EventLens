/* EventLens host-side bridge for the official DeepSeek Harness session log.
 * This plugin observes real Session identities; it does not manipulate
 * the native Web UI, read secrets, or replace the Harness conversation.
 */
export const name = 'eventlens-session-bridge'
export const inject = ['sessions', 'deepseekLlmApiExtensions']

export function apply(ctx) {
  // Official model-hidden request metadata, consumed locally and stripped
  // before forwarding upstream. No log upload or prompt-text guessing.
  ctx.deepseekLlmApiExtensions.register('eventlens_context', {prepare(request) {
    if (!request.sessionId || request.purpose) return;
    const session = ctx.sessions.get(request.sessionId);
    if (!session) return;
    const human = Array.from(session.snapshotEvents()).reverse().find(
      e => e.type === 'user/message' && e.data?.source?.kind === 'user');
    if (!human) return;
    return {value:{session_id:String(session.id),user_seq:Number(human.seq)}};
  }});
  const endpoint = 'http://127.0.0.1:8765/api/workspace/session-event'
  let queue = Promise.resolve()

  function send(event) {
    // Serialize notifications to preserve created -> first message ordering.
    queue = queue.then(async () => {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(event),
        signal: AbortSignal.timeout(10000)
      })
      if (!response.ok) throw new Error('EventLens bridge HTTP '+response.status)
    }).catch(error => {
      console.warn('[EventLens] session bridge delivery failed', String(error))
    })
  }

  ctx.on('session/created', session => {
    // Only blank, newly-created conversations become draft studies. A restored
    // session with durable history must not create a duplicate research.
    const events = typeof session.snapshotEvents === 'function' ? Array.from(session.snapshotEvents()) : []
    // The log may already contain a non-message end-seed marker. Only a
    // human-authored message means this Session has really started.
    if (events.some(e => e.type === 'user/message' && e.data?.source?.kind === 'user')) return
    send({kind:'session_created', session_id:String(session.id),seq:0,text:''})
  })

  ctx.on('session/event', (session, event) => {
    if (event.type !== 'user/message' || event.data?.source?.kind !== 'user') return
    const text = (event.data.content || [])
      .filter(x => x && x.type === 'text' && typeof x.text === 'string')
      .map(x => x.text).join('\n').trim()
    if (!text) return
    send({
      kind: 'user_message', session_id:String(session.id),
      seq: Number(event.seq), text: text.slice(0,2000)
    })
  })
}
