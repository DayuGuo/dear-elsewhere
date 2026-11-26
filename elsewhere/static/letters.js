// Keep the same letters unfolded on refresh, sharing, and language changes.
const letters = document.querySelectorAll("details[data-letter-id]");
const languageLinks = document.querySelectorAll(".languages a");

function withOpenLetters(href, ids) {
  const url = new URL(href);
  if (ids.length) {
    url.searchParams.set("open", ids.join(","));
  } else {
    url.searchParams.delete("open");
  }
  return url;
}

function rememberFolds() {
  const ids = Array.from(letters).filter(letter => letter.open).map(letter => letter.dataset.letterId);
  const current = withOpenLetters(location.href, ids);
  if (current.href !== location.href) history.replaceState(history.state, "", current);
  for (const link of languageLinks) link.href = withOpenLetters(link.href, ids);
}

for (const letter of letters) letter.addEventListener("toggle", rememberFolds);
