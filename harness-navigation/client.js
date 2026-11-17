/* Built against the official lazy-CJS client module contract. No DOM scraping,
 * cross-origin reads, credentials, model calls or third-party dependencies. */
window.__ModuleLoader__.load({
  id: '@eventlens/harness-navigation',
  factory: () => ({
    inject: ['sessions'],
    apply(ctx) {
      ctx.effect(() => {
        let timer, last = undefined;
        const publish = () => {
          const rows = Object.values(ctx.sessions.list.getSnapshot().byId);
          const visible = rows.filter(row => (row.retainedBy.mainView || 0) > 0);
          // An ambiguous/empty foreground must not retain somebody else's study.
          const id = visible.length === 1 ? String(visible[0].id) : null;
          if (id === last) return;
          last = id;
          window.parent.postMessage({type:'eventlens:session-active',session_id:id}, 'http://127.0.0.1:8765');
        };
        const schedule = () => { clearTimeout(timer); timer = setTimeout(publish, 60); };
        const unsubscribe = ctx.sessions.list.subscribe(schedule);
        schedule();
        return () => { clearTimeout(timer); unsubscribe(); };
      });
    }
  })
});
