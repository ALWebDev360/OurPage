export interface CartItem {
  productId: string;
  title: string;
  size: string;
  price: number;
  quantity: number;
  image: string;
}

let cartItems: CartItem[] = [];

export function getCart(): CartItem[] {
  return cartItems;
}

export function addToCart(item: CartItem): void {
  const existing = cartItems.find(
    (i) => i.productId === item.productId && i.size === item.size
  );
  if (existing) {
    existing.quantity += item.quantity;
  } else {
    cartItems.push({ ...item });
  }
  renderCartDrawer();
  openCart();
}

export function removeFromCart(productId: string, size: string): void {
  cartItems = cartItems.filter(
    (i) => !(i.productId === productId && i.size === size)
  );
  renderCartDrawer();
}

export function openCart(): void {
  document.getElementById("cart-overlay")?.classList.add("open");
  document.getElementById("cart-drawer")?.classList.add("open");
}

export function closeCart(): void {
  document.getElementById("cart-overlay")?.classList.remove("open");
  document.getElementById("cart-drawer")?.classList.remove("open");
}

export function renderCartDrawer(): void {
  const drawer = document.getElementById("cart-drawer");
  if (!drawer) return;

  const count = cartItems.reduce((sum, i) => sum + i.quantity, 0);
  const total = cartItems.reduce((sum, i) => sum + i.price * i.quantity, 0);

  drawer.innerHTML = `
    <div class="cart-drawer-header">
      <h2>Cart (${count})</h2>
      <button id="cart-close" aria-label="Close cart">&times;</button>
    </div>
    <div class="cart-drawer-body" style="${cartItems.length ? "display:block; align-items:stretch;" : ""}">
      ${
        cartItems.length === 0
          ? '<p class="cart-empty">Your cart is empty</p>'
          : cartItems
              .map(
                (item) => `
          <div class="cart-item">
            <img src="${item.image}" alt="${item.title}" />
            <div class="cart-item-info">
              <h4>${item.title}</h4>
              <p class="cart-item-details">Size: ${item.size} &middot; Qty: ${item.quantity}</p>
              <p class="cart-item-details">$${(item.price * item.quantity).toFixed(2)} USD</p>
              <button class="remove-cart-item" data-id="${item.productId}" data-size="${item.size}" style="background:none;color:#888;font-size:0.7rem;text-decoration:underline;margin-top:4px;font-family:inherit;cursor:pointer;">Remove</button>
            </div>
          </div>
        `
              )
              .join("")
      }
    </div>
    ${
      cartItems.length > 0
        ? `
      <div style="padding:24px;border-top:1px solid var(--color-border);">
        <div style="display:flex;justify-content:space-between;margin-bottom:16px;">
          <span style="font-family:var(--font-heading);font-size:0.8rem;letter-spacing:0.1em;text-transform:uppercase;">Total</span>
          <span style="font-weight:600;">$${total.toFixed(2)} USD</span>
        </div>
        <a href="#/checkout" class="add-to-cart-btn" style="width:100%;display:block;text-align:center;" id="checkout-link">Checkout</a>
      </div>
    `
        : ""
    }
  `;

  // Close button
  document.getElementById("cart-close")?.addEventListener("click", closeCart);

  // Checkout link closes the drawer
  document.getElementById("checkout-link")?.addEventListener("click", closeCart);

  // Remove buttons
  drawer.querySelectorAll(".remove-cart-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = (btn as HTMLElement).dataset.id!;
      const size = (btn as HTMLElement).dataset.size!;
      removeFromCart(id, size);
    });
  });
}

export function initCart(): void {
  renderCartDrawer();

  // Close on overlay click
  document.getElementById("cart-overlay")?.addEventListener("click", closeCart);
}
