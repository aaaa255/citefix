import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { TESTER_KEY, checkId, initialState, readEvents, reduce } from './check.js';

/* The check lives above the pages, so it survives a trip to the cover and back, and the menu's feedback form sees
   the same check as the checker page. */
const CheckContext = createContext(null);

const readTester = () => {
  try { return localStorage.getItem(TESTER_KEY) || ''; } catch { return ''; }
};

export function CheckProvider({ children }) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [text, setText] = useState('');
  const [exampleLoading, setExampleLoading] = useState(false);
  const [tester, setTesterState] = useState(readTester);
  const controller = useRef(null);
  const example = useRef({ text: null, load: null });
  const latest = useRef(null);
  latest.current = { state, text, exampleLoading };

  const setTester = useCallback((value) => {
    setTesterState(value);
    try { localStorage.setItem(TESTER_KEY, value); } catch { /* storage blocked: the name lasts this visit */ }
  }, []);

  /* The example is fetched as soon as the page opens, so Load example rarely has to wait. */
  const fetchExample = useCallback(() => {
    const ex = example.current;
    ex.load ||= fetch('/api/example')
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then((data) => { ex.text = data.text || ''; return ex.text; })
      .catch((err) => { ex.load = null; throw err; }); // the next click tries again
    return ex.load;
  }, []);

  useEffect(() => { fetchExample().catch(() => { /* Load example tries again and says so if it still fails */ }); }, [fetchExample]);

  /* Resolves true once the example is in the editor. */
  const loadExample = useCallback(async () => {
    if (example.current.text == null) {
      // Until the text is in the editor, a check would only find an empty passage.
      setExampleLoading(true);
      try {
        await fetchExample();
      } catch {
        dispatch({ type: 'warn', key: 'status.exampleFailed' });
        return false;
      } finally {
        setExampleLoading(false);
      }
    }
    setText(example.current.text);
    dispatch({ type: 'edit' });
    return true;
  }, [fetchExample]);

  /* Starts a check of the editor's text, or stops the one running. Resolves 'empty' when there is nothing to check. */
  const run = useCallback(async () => {
    const { state: now, text: passage, exampleLoading: loading } = latest.current;
    if (loading) return 'busy';
    if (now.check?.running) {
      controller.current?.abort();
      return 'stopped';
    }
    if (!passage.trim()) {
      if (now.mode === 'proof') dispatch({ type: 'edit' });
      dispatch({ type: 'warn', key: 'status.needText' });
      return 'empty';
    }
    const id = checkId();
    const abort = new AbortController();
    controller.current = abort;
    dispatch({ type: 'begin', id });
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: passage.trim(), repair: true }),
        signal: abort.signal,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        if (data.message) dispatch({ type: 'failed', text: data.message });
        else dispatch({ type: 'failed', key: 'status.serverError', params: { code: response.status } });
        return 'failed';
      }
      await readEvents(response.body, (event) => dispatch({ type: 'event', event }));
    } catch (err) {
      if (err.name === 'AbortError') dispatch({ type: 'aborted' });
      else if (err instanceof TypeError) dispatch({ type: 'failed', key: 'status.unreachable' });
      else dispatch({ type: 'failed', text: err.message });
    } finally {
      dispatch({ type: 'finished', id });
    }
    return 'done';
  }, []);

  const value = useMemo(() => ({
    state, dispatch, text, setText, exampleLoading, loadExample, run, tester, setTester,
  }), [state, text, exampleLoading, loadExample, run, tester, setTester]);
  return <CheckContext.Provider value={value}>{children}</CheckContext.Provider>;
}

export const useCheck = () => useContext(CheckContext);

/* Which panel of the menu is open, if any; the status line's "Rate this check" opens it on Feedback. */
const MenuContext = createContext({ menu: null, openMenu: () => {}, closeMenu: () => {} });

export function MenuProvider({ children }) {
  const [menu, setMenu] = useState(null); // null, or the open tab: 'about' | 'feedback' | 'settings'
  const openMenu = useCallback((tab = 'about') => setMenu(tab), []);
  const closeMenu = useCallback(() => setMenu(null), []);
  const value = useMemo(() => ({ menu, openMenu, closeMenu, setTab: setMenu }), [menu, openMenu, closeMenu]);
  return <MenuContext.Provider value={value}>{children}</MenuContext.Provider>;
}

export const useMenu = () => useContext(MenuContext);
