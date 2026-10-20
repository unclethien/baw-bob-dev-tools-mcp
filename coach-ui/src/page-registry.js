// What the widgets on one coach page share, whatever framework draws them: the app's theme, and the fields a
// button checks before it fires its boundary event. Widgets must not register while drawn as Coach Designer
// previews, because several previews share the Designer page.
const listeners = new Set();
const fields = new Map();
let theme = {};
let errors = [];
const notify = () => listeners.forEach((listener) => listener());

export const page = {
  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  get theme() { return theme; },
  setTheme(next) {
    theme = next || {};
    notify();
  },
  // field: { validate(), element }; validate() returns { message, ... } or null. Returns the function that unregisters the field and
  // drops its error. A field registered again under the same id (the next coach) is left alone.
  register(id, field) {
    fields.set(id, field);
    return () => {
      if (fields.get(id) !== field) return;
      fields.delete(id);
      errors = errors.filter((error) => error.id !== id);
      markTabs();
      notify();
    };
  },
  get errors() { return errors; },
  // Errors in screen order: fields register as they mount, which need not be the order they appear in.
  validateAll() {
    errors = [...fields].map(([id, field]) => {
      const error = field.validate();
      return error && { ...error, id, element: field.element };
    }).filter(Boolean).sort(byPosition);
    markTabs();
    notify();
    return errors;
  },
};

function byPosition(a, b) {
  if (!a.element || !b.element) return 0;
  return a.element.compareDocumentPosition(b.element) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
}

// Shows a field that sits in a tab that is not selected, also inside nested tabs: selects each tab whose panel holds it,
// outermost first.
export function reveal(element) {
  const panels = [];
  for (let panel = element && element.closest('[role="tabpanel"]'); panel; panel = panel.parentElement?.closest('[role="tabpanel"]')) {
    panels.unshift(panel);
  }
  panels.forEach(selectTab);
}

function selectTab(panel) {
  // ARIA tabs (Carbon): the tab names its panel.
  const tab = panel.id && panel.ownerDocument.querySelector(`[role="tab"][aria-controls="${CSS.escape(panel.id)}"]`);
  if (tab) {
    if (tab.getAttribute('aria-selected') !== 'true') tab.click();
    return;
  }
  const link = tabSectionLink(panel);
  if (link && !link.parentElement.classList.contains('active')) link.click();
}

// BAW's Tab Section: its panes and the links of its tab strip come in the same order.
function tabSectionLink(panel) {
  const content = panel.classList.contains('tab-pane') && panel.closest('.tab-content');
  if (!content) return null;
  const panes = [...content.querySelectorAll('.tab-pane')].filter((pane) => pane.closest('.tab-content') === content);
  return content.parentElement.querySelectorAll(':scope > .nav-tabs-strip > li > a')[panes.indexOf(panel)] || null;
}

// BAW's Tab Section draws its own tabs, so each tab that holds an error gets the pp-tab-error class (styles.scss
// adds a dot to it), also the outer tabs of nested Tab Sections.
function markTabs() {
  if (typeof document === 'undefined') return;
  document.querySelectorAll('.pp-tab-error').forEach((tab) => tab.classList.remove('pp-tab-error'));
  for (const { element } of errors) {
    for (let panel = element && element.closest('[role="tabpanel"]'); panel; panel = panel.parentElement?.closest('[role="tabpanel"]')) {
      tabSectionLink(panel)?.parentElement.classList.add('pp-tab-error');
    }
  }
}
