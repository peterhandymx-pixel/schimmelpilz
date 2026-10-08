import { useCallback, useEffect, useRef, useState } from 'react';
import { request } from './useCaseStorage.js';

export function useContacts(userId) {
  const owner = useRef(userId);
  useEffect(() => { owner.current = userId; }, [userId]);
  const [state, setState] = useState({ owner: null, items: [], loading: false, error: false });
  const reload = useCallback(async signal => {
    if (!userId) return;
    setState(current => ({ ...current, owner: userId, items: current.owner === userId ? current.items : [], loading: true, error: false }));
    try {
      const items = await request('/contacts', { signal });
      if (!signal?.aborted && owner.current === userId) setState({ owner: userId, items, loading: false, error: false });
    } catch (failure) {
      if (failure.name !== 'AbortError' && owner.current === userId) setState(current => ({ ...current, owner: userId, loading: false, error: true }));
    }
  }, [userId]);
  useEffect(() => {
    if (!userId) { setState({ owner: null, items: [], loading: false, error: false }); return; }
    const controller = new AbortController();
    reload(controller.signal);
    return () => controller.abort();
  }, [userId, reload]);
  const save = async (payload, existing) => {
    const value = await request(existing ? `/contacts/${existing.id}` : '/contacts', {
      method: existing ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, ...(existing ? { expected_version: existing.version } : {}) }),
    });
    if (owner.current === userId) setState(current => ({ ...current, owner: userId, loading: false, error: false, items: [...(current.owner === userId ? current.items.filter(item => item.id !== value.id) : []), value].sort((a,b) => a.name.localeCompare(b.name)) }));
    return value;
  };
  return { items: state.owner === userId ? state.items : [], loading: Boolean(userId) && (state.owner !== userId || state.loading), error: state.owner === userId && state.error, reload, save };
}
