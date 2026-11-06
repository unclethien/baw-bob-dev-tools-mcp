// Section and Review List: a titled panel (the view's Label) with an optional intro; its content box holds the
// section's views. The markup is the UI Toolkit Panel's, so the theme CSS styles both alike.
// With an Edit label the heading also carries a small button that unlocks the view at the Edit target path.
function draw(root, o, preview) {
  var head = root.querySelector(".abw-section > .panel-heading");
  var intro = root.querySelector(".abw-section > .panel-body > .abw-intro");
  if (head) {
    head.querySelector(".panel-title").textContent = o.label || "";
    head.style.display = o.labelVisibility === "HIDE" ? "none" : "";
    drawEdit(head, o, preview);
  }
  if (intro) {
    intro.textContent = o.options.intro || "";
    intro.style.display = o.options.intro ? "" : "none";
  }
}

function drawEdit(head, o, preview) {
  var old = head.querySelector(".abw-edit");
  if (old) head.removeChild(old);
  var text = o.options.editLabel;
  if (!text) return;
  var button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-default btn-sm abw-edit";
  button.style.cssFloat = "right";
  button.textContent = text;
  button.setAttribute("aria-label", text + " " + (o.label || ""));
  if (!preview) {
    button.onclick = function () {
      var path = o.options.editTarget;
      var finder = window.bpmext && bpmext.ui && bpmext.ui.getView;
      var view = path && finder ? bpmext.ui.getView(path) : null;
      if (!view) return false;
      view.context.options._metadata.visibility.set("value", "EDITABLE");
      button.style.display = "none";
      return false;
    };
  }
  head.appendChild(button);
}
