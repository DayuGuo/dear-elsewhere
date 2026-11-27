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
  element.classList.add("uses-widget");
  loadWidgets().then(api => api.widgets.createTweet(element.dataset.post, element, {
    cards: element.hasAttribute("data-photos") ? undefined : "hidden",
    conversation: "none",
    dnt: true,
    lang: document.documentElement.lang === "zh-CN" ? "zh-cn" : "en",
    align: "left"
  })).catch(() => { /* Keep the original link when X is unavailable. */ });
}

// oEmbed puts the post language on its paragraph. Keep it when rebuilding the DOM.
function applyPostTypography(target, body) {
  const text = body.textContent;
  const lang = body.lang;
  const hasChinese = !/^(ja|ko)(-|$)/i.test(lang)
    && /\p{Script=Han}/u.test(text)
    && !/[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(text);
  target.dir = "auto";
  target.lang = (!lang || lang === "und") && hasChinese ? "zh" : lang || "und";
  target.classList.toggle("has-han", hasChinese);
}

// Keep the post's text, line breaks and links without mounting remote HTML.
function readablePost(body) {
  const paragraph = document.createElement("p");
  paragraph.className = "post-body";
  applyPostTypography(paragraph, body);
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
  if (!card && element.hasAttribute("data-photos")) {
    widget(element);
    return;
  }
  const photo = element.querySelector(".photo-thumb");
  const img = photo?.querySelector("img");
  if (img) {
    img.addEventListener("error", () => photo.remove(), { once: true });
    if (img.complete && !img.naturalWidth) photo.remove();
  }
  const original = "https://x.com/i/web/status/" + element.dataset.post;
  const endpoint = new URL("https://publish.x.com/oembed");
  endpoint.search = new URLSearchParams({ url: "https://twitter.com/i/status/" + element.dataset.post, omit_script: "true", hide_thread: "true", dnt: "true" });
  try {
    const response = await fetch(endpoint, { credentials: "omit", cache: "no-store" });
    if (!response.ok) {
      if ([403, 404, 410].includes(response.status)) photo?.remove();
      throw new Error("Preview unavailable");
    }
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
    if (photo) {
      for (const link of body.querySelectorAll("a")) {
        if (/^pic\.(twitter|x)\.com\//i.test(link.textContent.trim())) link.remove();
      }
    }
    const excerpt = document.createElement("a");
    excerpt.className = "excerpt";
    excerpt.href = element.closest(".thread-reply") ? original : card.querySelector(".task-label a").href;
    excerpt.textContent = body.textContent.trim();
    applyPostTypography(excerpt, body);
    const author = document.createElement("a");
    author.className = "excerpt-author";
    author.href = original;
    author.textContent = post.author_name;
    element.prepend(excerpt);
    element.append(author);
  } catch {
    if (!card) return widget(element);
    const link = document.createElement("a");
    link.className = "excerpt-author";
    link.href = original;
    link.textContent = document.documentElement.lang === "zh-CN" ? "在 X 阅读原帖 ↗" : "Read on X ↗";
    element.prepend(link);
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
