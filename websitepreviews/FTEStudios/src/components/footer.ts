export function renderFooter(): void {
  const footer = document.getElementById("site-footer");
  if (!footer) return;

  footer.className = "site-footer";
  footer.innerHTML = `
    <div class="subscribe-section" style="border-top: none; padding-top: 0;">
      <span class="brand-eyebrow" style="display:block;margin-bottom:8px;">Stay Connected</span>
      <h2>Get Notified of Drops</h2>
      <p style="color:var(--color-text-muted);font-size:0.85rem;margin-bottom:20px;max-width:400px;margin-left:auto;margin-right:auto;">Subscribe to our newsletter and never miss a release.</p>
      <form class="subscribe-form" onsubmit="return false;">
        <input type="email" placeholder="Email" aria-label="Email address" required />
        <button type="submit">Subscribe</button>
      </form>
    </div>
    <div class="footer-payments">
      <img src="./icons/amex.png" alt="American Express" />
      <img src="./icons/applepay.png" alt="Apple Pay" />
      <img src="./icons/discover.png" alt="Discover" />
      <img src="./icons/mastercard.png" alt="Mastercard" />
      <img src="./icons/paypal.png" alt="PayPal" />
      <img src="./icons/visa.png" alt="Visa" />
    </div>
    <p class="footer-copy">&copy; ${new Date().getFullYear()} FTE Studios. All Rights Reserved.</p>
    <p class="footer-powered">Powered By Love</p>
    <div class="footer-links">
      <a href="#/privacy">Privacy Policy</a>
    </div>
  `;

  // Subscribe handler
  const form = footer.querySelector(".subscribe-form");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = form.querySelector("input") as HTMLInputElement;
    if (input.value) {
      input.value = "";
      alert("Thank you for subscribing!");
    }
  });
}
