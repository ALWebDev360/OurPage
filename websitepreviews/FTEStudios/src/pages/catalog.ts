import { products } from "../data/products";

export function renderCatalogPage(): string {
  return `
    <section class="section" style="min-height: 60vh;">
      <h1 class="section-title fade-in">Catalog</h1>
      <p class="section-subtitle fade-in">Browse all products</p>
      <div class="section-divider"></div>
      <div class="product-grid">
        ${products
          .map(
            (p) => `
          <a href="#/product/${p.id}" class="product-card fade-in">
            <div class="product-card-image">
              <img src="${p.images[0]}" alt="${p.title}" loading="lazy" />
              ${p.badge ? `<span class="product-card-badge">${p.badge}</span>` : ""}
            </div>
            <div class="product-card-info">
              <h3>${p.title}</h3>
              <p class="price">$<span class="amount">${p.price.toFixed(2)}</span> ${p.currency}</p>
            </div>
          </a>
        `
          )
          .join("")}
      </div>
      ${
        products.length === 0
          ? '<p style="text-align:center;color:var(--color-text-muted);margin-top:40px;">No products yet. Check back soon!</p>'
          : ""
      }
    </section>
  `;
}
