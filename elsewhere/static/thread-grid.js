// X frames resize after loading. Place the next thread in the first free column.
const grid = document.querySelector(".thread-grid");
if (grid && "ResizeObserver" in window) {
  const cards = Array.from(grid.children);
  const fit = targets => {
    const gap = parseFloat(getComputedStyle(grid).columnGap);
    for (const card of targets) {
      card.style.gridRowEnd = "span " + Math.ceil(card.getBoundingClientRect().height + gap);
    }
  };
  fit(cards);
  grid.classList.add("packed");
  const observer = new ResizeObserver(entries => fit(entries.map(entry => entry.target)));
  cards.forEach(card => observer.observe(card));
}
