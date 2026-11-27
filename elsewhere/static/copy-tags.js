const statusLine = document.querySelector(".copy-status");
let clearStatus;

function showStatus(message) {
  clearTimeout(clearStatus);
  statusLine.textContent = message;
  clearStatus = setTimeout(() => { statusLine.textContent = ""; }, 3500);
}

for (const label of document.querySelectorAll(".hashtag")) {
  const tag = label.textContent;
  const button = document.createElement("button");
  button.type = "button";
  button.className = label.className;
  button.textContent = tag;
  button.dataset.action = label.dataset.action;
  const signature = label.closest(".copy-value");
  const text = signature ? signature.textContent : tag;
  button.title = button.dataset.action + " " + text;
  button.setAttribute("aria-label", button.title);
  label.replaceWith(button);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Keep the tag selected for manual copying if the browser also blocks legacy copy.
      const selection = window.getSelection();
      selection.selectAllChildren(signature || button);
      if (!document.execCommand("copy")) {
        showStatus(statusLine.dataset.manual);
        return;
      }
      selection.removeAllRanges();
    }
    showStatus(statusLine.dataset.copied + " " + text);
  }

  button.addEventListener("click", copy);
  if (signature) {
    const action = document.createElement("button");
    action.type = "button";
    action.className = "copy-signature";
    action.textContent = button.dataset.action;
    action.setAttribute("aria-label", button.title);
    action.addEventListener("click", copy);
    signature.after(action);
  }
}
