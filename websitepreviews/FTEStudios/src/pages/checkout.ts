import { getCart, type CartItem } from "../components/cart";

export function renderCheckoutPage(): string {
  const items = getCart();
  const subtotal = items.reduce((sum, i) => sum + i.price * i.quantity, 0);
  const shipping = subtotal > 0 ? 9.99 : 0;
  const tax = subtotal * 0.08;
  const total = subtotal + shipping + tax;

  const cartSummaryHTML =
    items.length > 0
      ? items
          .map(
            (item) => `
        <div class="checkout-item">
          <div class="checkout-item-image">
            <img src="${item.image}" alt="${item.title}" />
            <span class="checkout-item-qty">${item.quantity}</span>
          </div>
          <div class="checkout-item-info">
            <p class="checkout-item-title">${item.title}</p>
            <p class="checkout-item-variant">Size: ${item.size}</p>
          </div>
          <p class="checkout-item-price">$${(item.price * item.quantity).toFixed(2)}</p>
        </div>
      `
          )
          .join("")
      : '<p style="color:var(--color-text-muted);text-align:center;padding:40px 0;">Your cart is empty</p>';

  return `
    <div class="checkout-page">
      <div class="checkout-left fade-in">
        <h1>Checkout</h1>

        <!-- Contact -->
        <div class="checkout-section">
          <h2>Contact</h2>
          <div class="form-group">
            <input type="email" id="checkout-email" placeholder="Email address" required />
          </div>
          <label class="checkout-checkbox">
            <input type="checkbox" checked />
            <span>Email me with news and offers</span>
          </label>
        </div>

        <!-- Shipping -->
        <div class="checkout-section">
          <h2>Shipping Address</h2>
          <div class="checkout-row">
            <div class="form-group">
              <input type="text" placeholder="First name" required />
            </div>
            <div class="form-group">
              <input type="text" placeholder="Last name" required />
            </div>
          </div>
          <div class="form-group">
            <input type="text" placeholder="Address" required />
          </div>
          <div class="form-group">
            <input type="text" placeholder="Apartment, suite, etc. (optional)" />
          </div>
          <div class="checkout-row checkout-row-3">
            <div class="form-group">
              <input type="text" placeholder="City" required />
            </div>
            <div class="form-group">
              <select required>
                <option value="" disabled selected>State</option>
                <option>Alabama</option><option>Alaska</option><option>Arizona</option>
                <option>Arkansas</option><option>California</option><option>Colorado</option>
                <option>Connecticut</option><option>Delaware</option><option>Florida</option>
                <option>Georgia</option><option>Hawaii</option><option>Idaho</option>
                <option>Illinois</option><option>Indiana</option><option>Iowa</option>
                <option>Kansas</option><option>Kentucky</option><option>Louisiana</option>
                <option>Maine</option><option>Maryland</option><option>Massachusetts</option>
                <option>Michigan</option><option>Minnesota</option><option>Mississippi</option>
                <option>Missouri</option><option>Montana</option><option>Nebraska</option>
                <option>Nevada</option><option>New Hampshire</option><option>New Jersey</option>
                <option>New Mexico</option><option>New York</option><option>North Carolina</option>
                <option>North Dakota</option><option>Ohio</option><option>Oklahoma</option>
                <option>Oregon</option><option>Pennsylvania</option><option>Rhode Island</option>
                <option>South Carolina</option><option>South Dakota</option><option>Tennessee</option>
                <option>Texas</option><option>Utah</option><option>Vermont</option>
                <option>Virginia</option><option>Washington</option><option>West Virginia</option>
                <option>Wisconsin</option><option>Wyoming</option>
              </select>
            </div>
            <div class="form-group">
              <input type="text" placeholder="ZIP code" required />
            </div>
          </div>
          <div class="form-group">
            <input type="tel" placeholder="Phone (optional)" />
          </div>
        </div>

        <!-- Shipping Method -->
        <div class="checkout-section">
          <h2>Shipping Method</h2>
          <div class="shipping-options">
            <label class="shipping-option selected">
              <input type="radio" name="shipping" value="standard" checked />
              <div class="shipping-option-info">
                <span class="shipping-option-name">Standard Shipping</span>
                <span class="shipping-option-time">5–8 business days</span>
              </div>
              <span class="shipping-option-price">$9.99</span>
            </label>
            <label class="shipping-option">
              <input type="radio" name="shipping" value="express" />
              <div class="shipping-option-info">
                <span class="shipping-option-name">Express Shipping</span>
                <span class="shipping-option-time">2–3 business days</span>
              </div>
              <span class="shipping-option-price">$19.99</span>
            </label>
          </div>
        </div>

        <!-- Payment -->
        <div class="checkout-section">
          <h2>Payment</h2>
          <p style="font-size:0.8rem;color:var(--color-text-muted);margin-bottom:16px;">All transactions are secure and encrypted.</p>
          <div class="payment-card-fields">
            <div class="form-group">
              <div class="input-with-icons">
                <input type="text" placeholder="Card number" id="card-number" maxlength="19" required />
                <div class="card-icons">
                  <img src="./icons/visa.png" alt="Visa" />
                  <img src="./icons/mastercard.png" alt="Mastercard" />
                  <img src="./icons/amex.png" alt="Amex" />
                </div>
              </div>
            </div>
            <div class="checkout-row">
              <div class="form-group">
                <input type="text" placeholder="Expiration (MM / YY)" maxlength="7" required />
              </div>
              <div class="form-group">
                <input type="text" placeholder="Security code" maxlength="4" required />
              </div>
            </div>
            <div class="form-group">
              <input type="text" placeholder="Name on card" required />
            </div>
          </div>
        </div>

        <button class="checkout-pay-btn" id="place-order-btn">
          Pay $${total.toFixed(2)} USD
        </button>

        <p class="checkout-disclaimer">
          This is a demo checkout. No real payment will be processed.
        </p>
      </div>

      <!-- Order Summary Sidebar -->
      <div class="checkout-right fade-in">
        <div class="checkout-summary">
          <h2>Order Summary</h2>
          <div class="checkout-items">
            ${cartSummaryHTML}
          </div>
          <div class="checkout-totals">
            <div class="checkout-total-row">
              <span>Subtotal</span>
              <span>$${subtotal.toFixed(2)}</span>
            </div>
            <div class="checkout-total-row">
              <span>Shipping</span>
              <span>${shipping > 0 ? "$" + shipping.toFixed(2) : "—"}</span>
            </div>
            <div class="checkout-total-row">
              <span>Estimated Tax</span>
              <span>$${tax.toFixed(2)}</span>
            </div>
            <div class="checkout-total-row checkout-total-final">
              <span>Total</span>
              <span>$${total.toFixed(2)} <small style="color:var(--color-text-muted);font-weight:400;">USD</small></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

export function initCheckoutPage(): void {
  // Card number formatting (adds spaces every 4 digits)
  const cardInput = document.getElementById("card-number") as HTMLInputElement;
  cardInput?.addEventListener("input", () => {
    let val = cardInput.value.replace(/\D/g, "");
    val = val.replace(/(.{4})/g, "$1 ").trim();
    cardInput.value = val;
  });

  // Shipping option selection highlighting
  const shippingOptions = document.querySelectorAll<HTMLLabelElement>(".shipping-option");
  shippingOptions.forEach((opt) => {
    const radio = opt.querySelector("input[type=radio]") as HTMLInputElement;
    radio?.addEventListener("change", () => {
      shippingOptions.forEach((o) => o.classList.remove("selected"));
      opt.classList.add("selected");
    });
  });

  // Place order button
  document.getElementById("place-order-btn")?.addEventListener("click", (e) => {
    e.preventDefault();
    const email = (document.getElementById("checkout-email") as HTMLInputElement)?.value;
    if (!email) {
      alert("Please enter your email address.");
      return;
    }
    // Demo confirmation
    window.location.hash = "#/order-confirmed";
  });
}
