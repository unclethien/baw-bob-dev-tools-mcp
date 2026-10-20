// App Header: the app's banner (the theme's product name and logo, the app's own title and text), or a plain
// title when the app has no banner, then the coach's intro text.
function draw(root, o) {
  var doc = root.ownerDocument, opts = o.options, banner = null;
  try {
    banner = opts.banner ? JSON.parse(opts.banner) : null;
  } catch (e) {
    banner = null;
  }
  function el(tag, className, text) {
    var e = doc.createElement(tag);
    e.className = className;
    if (text) e.textContent = text;
    return e;
  }
  root.textContent = "";
  if (banner) {
    var box = el("div", "app-banner"), brand = el("div", "app-banner-brand");
    if (banner.logoData) {
      var logo = el("img", "app-banner-logo");
      logo.src = banner.logoData;
      logo.alt = "";
      brand.appendChild(logo);
    }
    box.appendChild(brand);
    box.appendChild(el("div", "app-banner-title", banner.title || opts.title));
    box.appendChild(el("div", "app-banner-product", banner.product));
    box.appendChild(el("div", "app-banner-text", banner.text));
    root.appendChild(box);
  } else {
    root.appendChild(el("div", "app-title", opts.title));
  }
  if (opts.intro) root.appendChild(el("div", "app-intro", opts.intro));
}
