import { Tab, TabList, TabPanel, TabPanels, Tabs } from '@carbon/react';

// One contained tab per section; a tab with errors gets a dot. body(section) draws a section without its title.
export function SectionTabs({ sections, label, tab, onTab, errors, body }) {
  return (
    <Tabs selectedIndex={tab} onChange={({ selectedIndex }) => onTab(selectedIndex)}>
      <TabList aria-label={label} contained>
        {sections.map((s, i) => <Tab key={s.title || i}>{s.title}{errors.some((e) => e.tab === i) ? ' •' : ''}</Tab>)}
      </TabList>
      <TabPanels>
        {sections.map((s, i) => <TabPanel key={s.title || i} className="pp-panel">{body({ ...s, title: '' })}</TabPanel>)}
      </TabPanels>
    </Tabs>
  );
}
