// Hydrate nearby letters only. The server-rendered original links always work.
let widgetsReady;

function loadWidgets() {
  if (!widgetsReady) {
    widgetsReady = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://platform.twitter.com/widgets.js";
      script.onload = () => window.twttr.ready(resolve);
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  return widgetsReady;
}

function embed(element) {
  loadWidgets().then(api => api.widgets.createTweet(element.dataset.post, element, {
    conversation: "none",
    dnt: true,
    lang: document.documentElement.lang === "zh-CN" ? "zh-cn" : "en",
    align: "left"
  })).catch(() => { /* Keep the original link when X is unavailable. */ });
}

const posts = document.querySelectorAll("[data-post]");
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => {
    for (const { target, isIntersecting } of entries) {
      if (isIntersecting) {
        observer.unobserve(target);
        embed(target);
      }
    }
  }, { rootMargin: "200px" });
  posts.forEach(post => observer.observe(post));
} else {
  posts.forEach(embed);
}
