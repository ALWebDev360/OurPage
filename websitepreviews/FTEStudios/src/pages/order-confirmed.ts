export function renderOrderConfirmedPage(): string {
  return `
    <section class="order-confirmed">
      <div class="order-confirmed-inner fade-in">
        <div class="order-check">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 12l3 3 5-6" />
          </svg>
        </div>
        <h1>Order Confirmed</h1>
        <p class="order-number">Order #FTE-${Math.floor(100000 + Math.random() * 900000)}</p>
        <p class="order-thanks">
          Thank you for your purchase! This is a demo confirmation page —
          no real order was placed.
        </p>
        <div class="order-actions">
          <a href="#/" class="hero-btn">Continue Shopping</a>
        </div>
      </div>
    </section>
  `;
}
