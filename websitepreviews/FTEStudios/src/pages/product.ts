import { products } from "../data/products";
import { addToCart } from "../components/cart";
import type { Product } from "../data/products";

export function renderProductPage(productId: string): string {
  const product = products.find((p) => p.id === productId);

  if (!product) {
    return `
      <section class="section" style="min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <h1 style="margin-bottom:16px;">Product Not Found</h1>
        <p style="color:var(--color-text-muted);margin-bottom:24px;">Sorry, we couldn't find that product.</p>
        <a href="#/catalog" class="hero-btn">Back to Catalog</a>
      </section>
    `;
  }

  return `
    <div class="product-detail">
      <div class="product-gallery fade-in">
        <div class="product-gallery-main">
          <img id="main-product-image" src="${product.images[0]}" alt="${product.title}" />
        </div>
        <div class="product-gallery-thumbs">
          ${product.images
            .map(
              (img, i) =>
                `<img src="${img}" alt="${product.title} ${i + 1}" class="thumb ${i === 0 ? "active" : ""}" data-index="${i}" />`
            )
            .join("")}
        </div>
      </div>
      <div class="product-info fade-in">
        <h1>${product.title}</h1>
        <p style="color:var(--color-text-muted);font-style:italic;margin-bottom:16px;">"${product.subtitle}"</p>
        <p class="product-price">$${product.price.toFixed(2)} ${product.currency}</p>
        <p class="product-installments">
          Pay in 4 interest-free installments of $${(product.price / 4).toFixed(2)} with Shop Pay
        </p>

        <div class="product-size-selector">
          <label>Size</label>
          <div class="size-options" id="size-options">
            ${product.sizes
              .map(
                (s) =>
                  `<button class="size-option ${!s.available ? "sold-out" : ""}" data-size="${s.label}" ${!s.available ? "disabled" : ""}>${s.label}</button>`
              )
              .join("")}
          </div>
        </div>

        <div class="quantity-selector">
          <label>Quantity</label>
          <div class="quantity-controls">
            <button id="qty-decrease">&minus;</button>
            <span id="qty-display">1</span>
            <button id="qty-increase">+</button>
          </div>
        </div>

        <button class="add-to-cart-btn" id="add-to-cart-btn">Add to Cart</button>

        <div class="product-description">
          <h3>Description</h3>
          <ul>
            ${product.description.bullets
              .map((b) => `<li>${b}</li>`)
              .join("")}
          </ul>
          <p class="tagline">${product.description.tagline}</p>
        </div>
      </div>
    </div>
  `;
}

export function initProductPage(productId: string): void {
  const product = products.find((p) => p.id === productId);
  if (!product) return;

  // Thumbnail gallery
  const mainImage = document.getElementById(
    "main-product-image"
  ) as HTMLImageElement;
  const thumbs = document.querySelectorAll<HTMLImageElement>(".thumb");
  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      const index = parseInt(thumb.dataset.index || "0");
      mainImage.src = product.images[index];
      thumbs.forEach((t) => t.classList.remove("active"));
      thumb.classList.add("active");
    });
  });

  // Size selection
  let selectedSize = "";
  const sizeOptions = document.querySelectorAll<HTMLButtonElement>(
    "#size-options .size-option:not(.sold-out)"
  );
  sizeOptions.forEach((btn) => {
    btn.addEventListener("click", () => {
      sizeOptions.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedSize = btn.dataset.size || "";
    });
  });

  // Auto-select first available size
  const firstAvailable = document.querySelector<HTMLButtonElement>(
    "#size-options .size-option:not(.sold-out)"
  );
  if (firstAvailable) {
    firstAvailable.classList.add("active");
    selectedSize = firstAvailable.dataset.size || "";
  }

  // Quantity
  let quantity = 1;
  const qtyDisplay = document.getElementById("qty-display")!;
  document.getElementById("qty-decrease")?.addEventListener("click", () => {
    if (quantity > 1) {
      quantity--;
      qtyDisplay.textContent = String(quantity);
    }
  });
  document.getElementById("qty-increase")?.addEventListener("click", () => {
    quantity++;
    qtyDisplay.textContent = String(quantity);
  });

  // Add to cart
  document.getElementById("add-to-cart-btn")?.addEventListener("click", () => {
    if (!selectedSize) {
      alert("Please select a size");
      return;
    }
    addToCart({
      productId: product.id,
      title: product.title,
      size: selectedSize,
      price: product.price,
      quantity,
      image: product.images[0],
    });
  });
}
