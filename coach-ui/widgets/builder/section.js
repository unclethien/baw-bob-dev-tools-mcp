// Section and Review List: a titled panel (the view's Label) with an optional intro; its content box holds the
// section's views. The markup is the UI Toolkit Panel's, so the theme CSS styles both alike.
function draw(root, o) {
  var head = root.querySelector(".abw-section > .panel-heading");
  var intro = root.querySelector(".abw-section > .panel-body > .abw-intro");
  if (head) {
    head.querySelector(".panel-title").textContent = o.label || "";
    head.style.display = o.labelVisibility === "HIDE" ? "none" : "";
  }
  if (intro) {
    intro.textContent = o.options.intro || "";
    intro.style.display = o.options.intro ? "" : "none";
  }
}
