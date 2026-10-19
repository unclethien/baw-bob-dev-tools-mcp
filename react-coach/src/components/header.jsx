// The screen's header in the app's theme: the banner's logo and product name, the title and the steps.
import { ProgressIndicator, ProgressStep } from '@carbon/react';

export function Brand({ banner, subtitle }) {
  banner = banner || {};
  return (
    <div className="pp-brand">
      {banner.logoData && <img className="pp-brand-logo" src={banner.logoData} alt="" />}
      <span className="pp-brand-mark">{banner.product || 'Business Automation Workflow'}</span>
      {subtitle && <span className="pp-brand-sub">{subtitle}</span>}
    </div>
  );
}

export function Steps({ steps, step }) {
  if (!(steps?.length > 1)) return null;
  return (
    <ProgressIndicator currentIndex={step} spaceEqually className="pp-progress">
      {steps.map((label) => <ProgressStep key={label} label={label} />)}
    </ProgressIndicator>
  );
}

export function Header({ theme, subtitle, title, steps, step }) {
  return (
    <header className="pp-header">
      <Brand banner={theme?.banner} subtitle={subtitle} />
      <h1>{title}</h1>
      <Steps steps={steps} step={step} />
    </header>
  );
}
