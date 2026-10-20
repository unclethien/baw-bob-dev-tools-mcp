// Bridge between a BAW Coach View and a React screen.
//
// The Coach View's load handler calls window.CoachScreens.mount(element, name, ctx), where
// ctx exposes the bound business object (read/write by dotted path), the boundary-event
// trigger, fire(viewId) to press one of the coach's own buttons, and the screen options (the app's theme, field list). React state lives in BAW's binding, so the coach flow, variables and
// server-side logic stay native; React only owns rendering.
import { createRoot } from 'react-dom/client';
import { ClassPrefix } from '@carbon/react';
import { useSyncExternalStore } from 'react';
import './styles.scss';

const screens = {};
const widgets = {};

export function registerScreen(name, component) {
  screens[name] = component;
}

// A widget is one Coach View of the Modernizer Widgets toolkit, bound to a single value.
export function registerWidget(kind, component) {
  widgets[kind] = component;
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

// The app's theme file (server/coach_theme.py) as CSS variables that styles.scss and Carbon read.
const RADII = { square: ['0', '0'], rounded: ['4px', '6px'], pill: ['6px', '999px'] }; // fields, buttons
const ALIGN = { left: 'flex-start', center: 'center', right: 'flex-end' };
const darker = (colour, percent) => `color-mix(in srgb, ${colour} ${percent}%, black)`;

export function themeStyle(theme = {}) {
  const primary = theme.primary || '#0f62fe';
  const onPrimary = theme.onPrimary || '#ffffff';
  const button = theme.button || primary;
  const secondary = theme.secondaryButton || '#393939';
  const [fieldRadius, buttonRadius] = RADII[theme.shape] || RADII.rounded;
  return {
    '--pp-theme-primary': primary,
    '--pp-theme-on-primary': onPrimary,
    '--pp-theme-heading': theme.heading || onPrimary,
    '--pp-theme-field-radius': fieldRadius,
    '--pp-theme-button-radius': buttonRadius,
    '--pp-theme-align': ALIGN[theme.buttonAlign] || 'flex-end',
    '--pp-background': theme.background || '#f4f4f4',
    '--pp-interactive': primary,
    '--pp-focus': primary,
    '--pp-border-interactive': primary,
    '--pp-link-primary': button,
    '--pp-button-primary': button,
    '--pp-button-primary-hover': darker(button, 88),
    '--pp-button-primary-active': darker(button, 75),
    '--pp-button-secondary': secondary,
    '--pp-button-secondary-hover': darker(secondary, 88),
    '--pp-button-secondary-active': darker(secondary, 75),
    ...(theme.font && { fontFamily: `"${theme.font}", 'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif` }),
    ...(theme.width && { maxWidth: theme.width === 'full' ? 'none' : `${theme.width}px` }),
  };
}

function Host({ screen: Screen, store, ctx }) {
  useSyncExternalStore(store.subscribe, store.snapshot);
  const field = (prop) => ({ value: store.read(prop), set: (value) => store.write(prop, value) });
  return (
    <ClassPrefix prefix="pp">
      <div className="pp-app" style={themeStyle(ctx.options.theme)}>
        <Screen field={field} read={store.read} boundary={ctx.boundary} fire={ctx.fire} options={ctx.options} />
      </div>
    </ClassPrefix>
  );
}

function WidgetHost({ widget: Widget, store, ctx }) {
  useSyncExternalStore(store.subscribe, store.snapshot);
  const props = ctx.read();
  if (props.visibility === 'HIDDEN' || props.visibility === 'NONE') return null;
  const binding = { value: ctx.binding.get(), set: (value) => { ctx.binding.set(value); store.notify(); } };
  return (
    <ClassPrefix prefix="pp">
      <div className="pp-app pp-widget" style={themeStyle(props.theme)}>
        <Widget {...props} binding={binding} trigger={ctx.trigger} />
      </div>
    </ClassPrefix>
  );
}

// ctx: read() -> { label, helpText, visibility, options, preview, theme }, binding { get, set }, trigger().
// The Coach View (or the Coach Designer preview) owns the context, so this stays free of BAW APIs.
export function mountWidget(element, kind, ctx) {
  const Widget = widgets[kind];
  if (!Widget) throw new Error(`Modernizer Widgets: no widget named "${kind}"`);
  const container = document.createElement('div');
  element.appendChild(container);
  const store = createStore(ctx);
  const root = createRoot(container);
  root.render(<WidgetHost widget={Widget} store={store} ctx={ctx} />);
  return {
    update: () => store.notify(),
    unmount() {
      root.unmount();
      container.remove();
    },
  };
}

export function mount(element, name, ctx) {
  const Screen = screens[name];
  if (!Screen) throw new Error(`Coach screens: no screen named "${name}"`);
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
