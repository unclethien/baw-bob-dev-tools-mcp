#!/usr/bin/env python3
"""
Theme support for generated coaches: the app spec's "theme" and "banner" become CSS and a
banner header inside each coach's Custom HTML, so classic UI Toolkit coaches can follow the
colours, shapes and header of a screenshot or a brand.

The CSS targets the markup BAW renders for UI Toolkit views: every view carries
data-viewid="<layout item id>" and data-type="...<View_Name>", inputs sit in .form-group >
.control-label + .input > .form-control, panels are .SPARKPanel with a .panel-heading, and
buttons are .btn (.btn-primary for the primary colour style).

    "theme": {
      "primary": "#7cbde2",          banner, section bars, active tab, field icon boxes
      "onPrimary": "#ffffff",        text and icons on primary
      "heading": "#2f6f9f",          banner title and product name (default onPrimary)
      "button": "#2f6db3",           forward / submit buttons (default primary)
      "secondaryButton": "#f0b45a",  back and cancel buttons (default: outlined)
      "background": "#f4f6f8",       page behind the form
      "font": "Open Sans",           font family; system fonts follow it
      "shape": "rounded",            square | rounded | pill (pill: rounded fields, pill buttons)
      "fieldIcons": true,            an icon box before every input (fields may set "icon")
      "width": 1400,                 max content width in px, or "full"
      "buttonAlign": "right"         left | center | right: where the button bar sits (default left)
    },
    "banner": { "title": "...", "product": "...", "text": "...", "logo": "screenshots/logo.png" }
"""

import base64
import html
import re
from pathlib import Path
from urllib.parse import quote

COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
FONT = re.compile(r"^[A-Za-z0-9 \-]{1,40}$")
SHAPES = {"square": ("0", "0", "0"), "rounded": ("4px", "8px", "6px"), "pill": ("6px", "10px", "999px")}  # field, panel, button
LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}
LOGO_LIMIT = 200_000
THEME_KEYS = {"primary", "onPrimary", "heading", "button", "secondaryButton", "background", "font", "shape", "fieldIcons", "width", "buttonAlign"}
BANNER_KEYS = {"title", "product", "text", "logo"}
ALIGN = {"left": "flex-start", "center": "center", "right": "flex-end"}

# 24px stroke icons (MIT-licensed Lucide shapes, simplified)
ICONS = {
    "text": '<path d="M4 6h16M4 12h16M4 18h10"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7.5M22 21a7 7 0 0 0-4-6.3"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "options": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/>',
    "check": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m8 12 3 3 5-6"/>',
    "hash": '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "id": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M15 9h3M15 13h3M6 16a3 3 0 0 1 6 0"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="1"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
    "dollar": '<path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    "briefcase": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>',
}
DEFAULT_ICONS = {"String": "text", "Text Area": "file", "Date": "calendar", "Select": "list", "Radio": "options",
                 "Boolean": "check", "Integer": "hash", "Decimal": "hash"}


def validate(spec, project: Path) -> list:
    """Check the theme and banner; returns error messages. Loads the banner logo into banner["logoData"]."""
    errors = []
    theme, banner = spec.get("theme"), spec.get("banner")
    if theme is not None:
        if not isinstance(theme, dict):
            return ["theme must be an object"]
        errors += [f"theme.{k} is not a theme setting; use {', '.join(sorted(THEME_KEYS))}" for k in theme if k not in THEME_KEYS]
        errors += [f"theme.{k} must be a colour like #1f70c1" for k in ("primary", "onPrimary", "heading", "button", "secondaryButton", "background")
                   if k in theme and not COLOR.match(str(theme[k]))]
        if "font" in theme and not FONT.match(str(theme["font"])):
            errors.append("theme.font must be a font family name such as \"Open Sans\"")
        if theme.get("shape", "rounded") not in SHAPES:
            errors.append(f"theme.shape must be one of {', '.join(SHAPES)}")
        if "width" in theme and theme["width"] != "full" and not (isinstance(theme["width"], int) and 600 <= theme["width"] <= 3000):
            errors.append('theme.width must be a number of pixels (600-3000) or "full"')
        if theme.get("buttonAlign", "left") not in ALIGN:
            errors.append(f"theme.buttonAlign must be one of {', '.join(ALIGN)}")
    if banner is not None:
        if not isinstance(banner, dict):
            return errors + ["banner must be an object"]
        errors += [f"banner.{k} is not a banner setting; use {', '.join(sorted(BANNER_KEYS))}" for k in banner if k not in BANNER_KEYS]
        if banner.get("logo"):
            path = (project / banner["logo"]).resolve()
            if project.resolve() not in path.parents or not path.is_file():
                errors.append(f"banner.logo {banner['logo']!r} must be an image file inside the project")
            elif path.suffix.lower() not in LOGO_TYPES:
                errors.append(f"banner.logo must be one of {', '.join(LOGO_TYPES)}")
            elif path.stat().st_size > LOGO_LIMIT:
                errors.append(f"banner.logo is larger than {LOGO_LIMIT // 1000} KB; crop or compress it")
            else:
                banner["logoData"] = f"data:{LOGO_TYPES[path.suffix.lower()]};base64,{base64.b64encode(path.read_bytes()).decode()}"
    return errors


def field_errors(f) -> list:
    if "icon" in f and f["icon"] not in ICONS:
        return [f"field {f.get('name')!r}: icon {f['icon']!r} is unknown; use one of {', '.join(ICONS)}"]
    return []


def icon_url(name, color):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
           f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    return f'url("data:image/svg+xml,{quote(svg)}")'


def banner_html(banner, title):
    """The banner replaces the plain coach title: logo, the coach title, product name and a short text."""
    esc = lambda s: html.escape(str(s or ""))
    logo = f'<img class="app-banner-logo" src="{banner["logoData"]}" alt="">' if banner.get("logoData") else ""
    return (f'<div class="app-banner"><div class="app-banner-brand">{logo}</div>'
            f'<div class="app-banner-title">{esc(banner.get("title") or title)}</div>'
            f'<div class="app-banner-product">{esc(banner.get("product"))}</div>'
            f'<div class="app-banner-text">{esc(banner.get("text"))}</div></div>')


def css(theme, inputs, width):
    """CSS for one coach. inputs: (layout item id, spec type, icon or None) of every input view on it."""
    primary = theme.get("primary", "#0f62fe")
    on_primary = theme.get("onPrimary", "#ffffff")
    heading = theme.get("heading", on_primary)
    button = theme.get("button", primary)
    secondary = theme.get("secondaryButton")
    field_r, panel_r, button_r = SHAPES[theme.get("shape", "rounded")]
    font = f'"{theme["font"]}", "Segoe UI", "Helvetica Neue", Arial, sans-serif' if theme.get("font") else "inherit"
    max_width = "none" if theme.get("width", width) == "full" else f'{theme.get("width", width)}px'
    rules = [
        f"body.spark-ui {{ background: {theme.get('background', '#f4f6f8')} !important; font-family: {font}; }}",
        f"div.body {{ max-width: {max_width} !important; }}",
        f".app-banner {{ display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 24px; margin: 0 0 16px;"
        f" padding: 12px 28px; min-height: 84px; background: {primary}; color: {on_primary}; border-radius: {panel_r}; }}",
        ".app-banner-logo { display: block; max-height: 64px; max-width: 280px; }",
        f".app-banner-title {{ text-align: center; font-size: 22px; font-weight: 600; color: {heading}; }}",
        f".app-banner-product {{ font-size: 26px; font-weight: 700; letter-spacing: 0.02em; color: {heading}; }}",
        ".app-banner-text { text-align: right; font-size: 16px; font-weight: 600; max-width: 260px; }",
        f".SPARKPanel.panel {{ background: #fff !important; border: 1px solid #d9dee3 !important; border-radius: {panel_r}; overflow: hidden;"
        " box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06); }",
        f".SPARKPanel.panel > .panel-heading {{ background: {primary} !important; border: 0 !important; padding: 10px 18px !important; }}",
        f".SPARKPanel.panel > .panel-heading .panel-title {{ color: {on_primary} !important; font-size: 15px; font-weight: 600; }}",
        ".SPARKPanel.panel > .panel-body { padding: 16px 18px 8px !important; }",
        ".control-label { font-weight: 600 !important; font-size: 13px !important; color: #3b4651 !important; }",
        f".form-control {{ background: #fff !important; border: 1px solid #cfd6dd !important; border-radius: {field_r} !important; box-shadow: none !important; min-height: 36px; }}",
        f".form-control:focus {{ border-color: {primary} !important; box-shadow: 0 0 0 3px color-mix(in srgb, {primary} 30%, transparent) !important; outline: none; }}",
        f".nav-tabs {{ border-bottom: 1px solid #d9dee3 !important; margin-bottom: 16px; }}",
        f".nav-tabs > li > a {{ color: #4a5560 !important; border: 0 !important; border-radius: 0 !important; padding: 10px 18px !important; background: transparent !important; }}",
        f".nav-tabs > li > a:hover {{ color: {button} !important; background: #fff !important; }}",
        f".nav-tabs > li.active > a, .nav-tabs > li.active > a:hover, .nav-tabs > li.active > a:focus {{ background: {button} !important; color: #fff !important; }}",
        f".btn {{ border-radius: {button_r} !important; padding: 8px 28px !important; font-weight: 600; min-width: 96px; }}",
        f".btn-primary {{ background: {button} !important; border-color: {button} !important; color: #fff !important; }}",
        ".btn-primary:hover { filter: brightness(1.08); }",
        (f".btn:not(.btn-primary) {{ background: {secondary} !important; border-color: {secondary} !important; color: #fff !important; }}" if secondary
         else f".btn:not(.btn-primary) {{ background: #fff !important; border: 1px solid {button} !important; color: {button} !important; }}"),
        # the bar's content box renders as a table, which ignores justify-content
        f'[data-viewid="Action_Bar"] > .ContentBox {{ display: flex !important; flex-wrap: wrap; align-items: center;'
        f' justify-content: {ALIGN[theme.get("buttonAlign", "left")]} !important; gap: 12px; padding: 8px 0; }}',
        '[data-viewid="Action_Bar"] > .ContentBox > .Button.CoachView { margin: 0 !important; }',
    ]
    if theme.get("fieldIcons"):
        # (layout item id, element that gets the icon box, icon); text-like inputs sit beside the box,
        # radio groups and checkboxes keep their own layout and get padding for it
        boxes = [(vid, ".checkbox3" if typ == "Boolean" else ".input", icon or DEFAULT_ICONS[typ], typ in ("Radio", "Boolean")) for vid, typ, icon in inputs]
        sel = lambda items, tail="": ", ".join(f'[data-viewid="{b[0]}"] {b[1]}{tail}' for b in items)
        inline, padded = [b for b in boxes if not b[3]], [b for b in boxes if b[3]]
        if inline:
            # the box joins the input like an input-group add-on
            rules += [f"{sel(inline)} {{ display: flex !important; align-items: stretch; }}",
                      f"{sel(inline, ' .form-control')} {{ flex: 1 1 auto; border-top-left-radius: 0 !important; border-bottom-left-radius: 0 !important; }}",
                      f"{sel(inline, '::before')} {{ flex: 0 0 36px; border-radius: {field_r} 0 0 {field_r} !important; }}"]
        if padded:
            rules += [f"{sel(padded)} {{ position: relative; display: flex; flex-direction: column; justify-content: center; padding-left: 44px; min-height: 36px; }}",
                      f"{sel(padded, '::before')} {{ position: absolute; left: 0; top: 0; bottom: 0; width: 36px; }}"]
        if boxes:
            rules.append(f"{sel(boxes, '::before')} {{ content: \"\"; min-height: 36px; background: {primary} center / 18px no-repeat; border-radius: {field_r}; }}")
            for name in sorted({b[2] for b in boxes}):
                rules.append(f"{sel([b for b in boxes if b[2] == name], '::before')} {{ background-image: {icon_url(name, on_primary)}; }}")
    return "\n".join(rules)
