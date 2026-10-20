// Theme: the app's look as CSS, built from the app's theme file by coach_theme.py, added to the coach. It draws
// nothing on the page; in Coach Designer it shows a marker so the author can find and select it.
function draw(root, o, preview) {
  var doc = root.ownerDocument;
  if (preview) {
    root.innerHTML = '<div style="padding: 8px; font-size: 12px; color: #525252; border: 1px dashed #c6c6c6">Theme</div>';
    return;
  }
  var style = root.querySelector("style.abw-theme") || root.appendChild(doc.createElement("style"));
  style.className = "abw-theme";
  style.textContent = o.options.css || "";
}
