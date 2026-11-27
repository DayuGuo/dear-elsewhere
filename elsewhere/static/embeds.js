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

function widget(element) {
  loadWidgets().then(api => api.widgets.createTweet(element.dataset.post, element, {
    cards: element.hasAttribute("data-photos") ? undefined : "hidden",
    conversation: "none",
    dnt: true,
    lang: document.documentElement.lang === "zh-CN" ? "zh-cn" : "en",
    align: "left"
  })).catch(() => { /* Keep the original link when X is unavailable. */ });
}

// Keep the post's text, line breaks and links without mounting remote HTML.
function readablePost(body) {
  const paragraph = document.createElement("p");
  paragraph.className = "post-body";
  paragraph.dir = "auto";
  for (const node of body.childNodes) {
    if (node.nodeName === "A" && /^https?:\/\//i.test(node.getAttribute("href") || "")) {
      const link = document.createElement("a");
      link.href = node.getAttribute("href");
      link.textContent = node.textContent;
      paragraph.append(" ", link);
    } else {
      paragraph.append(node.textContent);
    }
  }
  return paragraph;
}
async function embed(element) {
  const card = element.closest(".thread-card");
  if (element.hasAttribute("data-photos")) {
    widget(element);
    return;
  }
  const original = "https://x.com/i/web/status/" + element.dataset.post;
  const endpoint = new URL("https://publish.x.com/oembed");
  endpoint.search = new URLSearchParams({ url: "https://twitter.com/i/status/" + element.dataset.post, omit_script: "true", hide_thread: "true", dnt: "true" });
  try {
    const response = await fetch(endpoint, { credentials: "omit", cache: "no-store" });
    if (!response.ok) throw new Error("Preview unavailable");
    const post = await response.json();
    // Read text in an inert template. Never insert remote markup into the page.
    const template = document.createElement("template");
    template.innerHTML = post.html;
    const body = template.content.querySelector("blockquote p");
    if (!body || !body.textContent.trim()) throw new Error("Empty preview");
    body.querySelectorAll("br").forEach(br => br.replaceWith("\n"));
    if (!card) {
      element.replaceChildren(readablePost(body));
      element.classList.add("full-post");
      const source = element.nextElementSibling;
      if (source?.matches(".source") && post.author_name) {
        source.textContent = post.author_name + " · X ↗";
      }
      return;
    }
    const excerpt = document.createElement("a");
    excerpt.className = "excerpt";
    excerpt.href = element.closest(".thread-reply") ? original : card.querySelector(".task-label a").href;
    excerpt.textContent = body.textContent.trim();
    excerpt.dir = "auto";
    const author = document.createElement("a");
    author.className = "excerpt-author";
    author.href = original;
    author.textContent = post.author_name;
    element.classList.add("has-excerpt");
    element.replaceChildren(excerpt, author);
  } catch {
    widget(element);
  }
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
