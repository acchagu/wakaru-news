let allNews = [];
let currentCategory = "国内";

const newsEl = document.getElementById("news");
const statusEl = document.getElementById("status");

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentCategory = btn.dataset.category;
    render();
  });
});

function esc(s=""){
  return s.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function render(){
  const items = allNews.filter(x => x.category === currentCategory);
  statusEl.textContent = items.length ? `${currentCategory}：${items.length}件` : currentCategory;

  if (!items.length){
    const msg = (currentCategory === "海外" || currentCategory === "ゲーム・IT")
      ? "このカテゴリは次のバージョンで追加します。"
      : "まだニュースデータがありません。GitHub Actionsを実行すると取得されます。";
    newsEl.innerHTML = `<div class="empty">${msg}</div>`;
    return;
  }

  newsEl.innerHTML = items.map(x => `
    <article class="card">
      <div class="meta">${esc(x.source)} ・ ${esc(x.date || "")}</div>
      <h2>${esc(x.title)}</h2>
      <a href="${x.link}" target="_blank" rel="noopener noreferrer">元情報を見る</a>
    </article>
  `).join("");
}

fetch("data/news.json?v=" + Date.now())
  .then(r => {
    if (!r.ok) throw new Error("news.json not found");
    return r.json();
  })
  .then(data => {
    allNews = Array.isArray(data.items) ? data.items : [];
    render();
  })
  .catch(() => {
    allNews = [];
    render();
  });
