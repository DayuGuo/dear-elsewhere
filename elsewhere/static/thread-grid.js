// X frames resize after loading. Place the next thread in the first free column.
const grid = document.querySelector(".thread-grid");
if (grid && "ResizeObserver" in window) {
  const cards = Array.from(grid.children);
  const gap = parseFloat(getComputedStyle(grid).columnGap);
  const fit = card => {
    card.style.gridRowEnd = "span " + Math.ceil(card.getBoundingClientRect().height + gap);
  };
  cards.forEach(fit);
  grid.classList.add("packed");
  const observer = new ResizeObserver(entries => entries.forEach(entry => fit(entry.target)));
  cards.forEach(card => observer.observe(card));
}
