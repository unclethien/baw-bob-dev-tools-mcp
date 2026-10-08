// Bridge between a BAW Coach View and a React screen.
//
// The Coach View's load handler calls window.PPReact.mount(element, name, ctx), where
// ctx exposes the bound business object (read/write by dotted path), the boundary-event
// trigger, fire(viewId) to press one of the coach's own buttons, and the screen options (theme, field list). React state lives in BAW's binding, so the coach flow, variables and
// server-side logic stay native; React only owns rendering.
import { createRoot } from 'react-dom/client';
import { ClassPrefix } from '@carbon/react';
import { useSyncExternalStore } from 'react';
import './styles.scss';

const screens = {};

export function registerScreen(name, component) {
  screens[name] = component;
}

function createStore(ctx) {
  const listeners = new Set();
  let version = 0;
  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    snapshot: () => version,
    notify() {
      version += 1;
      listeners.forEach((listener) => listener());
    },
    read: (prop) => ctx.read(prop),
    write(prop, value) {
      ctx.write(prop, value);
      this.notify();
    },
  };
}

function Host({ screen: Screen, store, ctx }) {
  useSyncExternalStore(store.subscribe, store.snapshot);
  const field = (prop) => ({ value: store.read(prop), set: (value) => store.write(prop, value) });
  return (
    <ClassPrefix prefix="pp">
      <div className={`pp-app pp-theme-${ctx.options.theme}`}>
        <Screen field={field} read={store.read} boundary={ctx.boundary} fire={ctx.fire} options={ctx.options} />
      </div>
    </ClassPrefix>
  );
}

export function mount(element, name, ctx) {
  const Screen = screens[name];
  if (!Screen) throw new Error(`PPReact: no screen named "${name}"`);
  const container = document.createElement('div');
  element.appendChild(container);
  const store = createStore(ctx);
  const root = createRoot(container);
  root.render(<Host screen={Screen} store={store} ctx={ctx} />);
  return {
    update: () => store.notify(),
    unmount() {
      root.unmount();
      container.remove();
    },
  };
}
