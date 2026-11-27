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
  button.title = button.dataset.action + " " + tag;
  button.setAttribute("aria-label", button.title);
  label.replaceWith(button);

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(tag);
    } catch {
      // Keep the tag selected for manual copying if the browser also blocks legacy copy.
      const selection = window.getSelection();
      selection.selectAllChildren(button);
      if (!document.execCommand("copy")) {
        showStatus(statusLine.dataset.manual);
        return;
      }
      selection.removeAllRanges();
    }
    showStatus(statusLine.dataset.copied + " " + tag);
  });
}
