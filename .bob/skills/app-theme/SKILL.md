---
name: app-theme
description: Write the theme file (work/<name>.theme.json) that gives a BAW app its look - colours, font, corner shape, field icon boxes, width, button placement, and the header's product name and logo - from the user's description of the look or from a screenshot, using the baw-dev-tools image tools. The same file styles the UI Toolkit coaches create_app builds and the React screens modernize_app adds. Use before writing an app spec or modernizing coaches, and whenever the user describes, names or changes a look, brand or colours.
---

# App theme

Every app spec and every coach spec names a **theme file**. `create_app` and `modernize_app` refuse a spec without one, and there is no default look. Never write CSS or edit `react-coach/src/styles.scss` to change a look: change the theme file.

## 1. Get the look

- **The user described a look** ("navy and white, rounded buttons, our logo on top"): use it. Fill in only what they left open, with values that fit their description.
- **A screenshot or mockup:** read the look from it (section 3).
- **An existing theme file** in `work/` or `app-specs/` that the user names, or that another app of theirs already uses: reuse it as it is.
- **Nothing given:** ask the user to describe the look, with these questions: main colour, button colour, page colour, font, square / rounded / pill corners, product name and logo in the header. Offer the example themes in `app-specs/*.theme.json` as starting points. Do not make up a look without asking.

## 2. Write the theme file

Path: `work/<name>.theme.json`, named after the look or the organisation, e.g. `work/acme.theme.json`. Several apps can share one file. Every key is optional:

| Key | Value |
|---|---|
| `primary` | `#rrggbb`: header strip, section bars, active tab, field icon boxes |
| `onPrimary` | Text and icons drawn on `primary`, usually `#ffffff` |
| `heading` | Header title and product name, when coloured differently from `onPrimary` |
| `button` | Main button (Next / Submit) and the active tab (default `primary`) |
| `secondaryButton` | Back / Cancel when filled with a colour (default: outlined) |
| `background` | Page behind the form |
| `font` | A font family such as `"Open Sans"`, `"Roboto"`, `"Arial"` |
| `shape` | `square`, `rounded` (default) or `pill` (rounded fields, pill buttons) |
| `fieldIcons` | `true`: an icon box before every input. Fields choose theirs with `icon` in the app spec |
| `width` | Most the form spreads to: pixels (600 to 3000) or `"full"` |
| `buttonAlign` | `left`, `center` or `right`: where the buttons sit |
| `banner` | `product`: product or system name shown in the header, e.g. `"QUOTE DESK"`. `logo`: an image file in `work/`, at most 200 KB |

```json
{
  "primary": "#2c4a6e", "onPrimary": "#ffffff", "button": "#2c4a6e", "background": "#eef1f5",
  "font": "Arial", "shape": "square", "buttonAlign": "right",
  "banner": { "product": "Acme Procurement Portal", "logo": "work/acme-logo.png" }
}
```

Each app's own header title and greeting stay in its app spec (`"banner": { "title": ..., "text": ... }`), not in the theme file.

Turning a description into values:

- A named colour ("navy", "forest green", "our orange") becomes a `#rrggbb` close to it. Use the exact value when the user gives one.
- When the user gives only one colour, use it for `primary` and `button`, a white `onPrimary`, and a very light tint of it, or `#f4f6f8`, for `background`.
- Keep text readable: `onPrimary` must contrast with `primary`, and the buttons must contrast with white text.
- The logo: follow "The logo" below.

## The logo

Never cut a logo out of a picture on your own. In this order:

1. **A logo file the user gives or names:** use it. An attached logo must be saved in `work/` first, since `banner.logo` needs a file.
2. **A logo file already in the project:** look for `banner.logo` in the theme files in `work/` and `app-specs/` for the same brand, and for image files with "logo" in the name in `work/` and in the screenshots' folder. Use the one that matches the brand and tell the user which file it is.
3. **None found:** leave `banner.logo` out and ask the user, at the design stop, to choose: save the official logo file in `work/`, have you cut it out of the screenshot with `crop_image`, or go without a logo.

Use `crop_image` only when the user asks for it, here or in their request ("cut out its logo"). Then save the crop in `work/` (e.g. `work/<name>-logo.png`), check it with `view_image`, and adjust the box until the whole logo is in and the edges are clean.

## 3. From a screenshot

Sample every colour with `image_colors` on the screenshot file. `box` is `[left, top, right, bottom]` as fractions of the image, so `[0, 0, 1, 0.15]` is the top 15 %. Draw the box tightly inside the element and take the colour with the largest share.

| In the screenshot | Theme setting |
|---|---|
| Header strip, section title bars, icon boxes | `primary` |
| Text and icons drawn on those | `onPrimary` |
| Title and product name in the header, when coloured differently | `heading` |
| Main button (Submit / Next) and the active tab | `button` |
| Second button (Cancel / Back) filled with a colour | `secondaryButton`; leave it out for an outlined button |
| Page behind the form | `background` |
| Font that looks like Open Sans, Roboto, Lato, Arial … | `font` |
| Corners: sharp / slightly rounded / fully round buttons | `shape`: `square` / `rounded` / `pill` |
| A small coloured square with an icon before each input | `"fieldIcons": true` |
| Form spread across a wide screen | `"width": "full"` (or a pixel width) |
| Buttons at the right / centre of the page | `"buttonAlign": "right"` / `"center"` |
| Product or system name in the header | `banner.product` |
| Logo in the header | `banner.logo`: a logo file, found or asked for as in "The logo" above. Cut it out with `crop_image` only when the user asks |

Keep screenshots and logos in `work/` (not committed), never in `app-specs/`.

## 4. Use it

- **App spec:** `"theme": "work/<name>.theme.json"`.
- **Coach spec** (before `modernize_app`): `"theme": "work/<name>.theme.json"`. Use the same file as the app spec, so the React screens match the classic ones, unless the user wants the React screens to look different.
- `create_app` and `modernize_app` check the file and list every problem; fix it and call them again.
- **To change the look later:** edit the theme file, then rebuild with a new snapshot. Every app and screen using the file follows it.

Tell the user which theme file you wrote or reused and the main values in it, so they can ask for changes.
