import { products } from "../data/products";

const LOGO_URL =
  "https://ftestudioz.myshopify.com/cdn/shop/files/fte_studios_cropped_gif_8a667b00-002b-4ddd-8504-da9fddd792db.gif?v=1749980240";

function createParticles(): string {
  let particles = "";
  for (let i = 0; i < 40; i++) {
    const left = Math.random() * 100;
    const delay = Math.random() * 10;
    const duration = 6 + Math.random() * 8;
    const size = 1 + Math.random() * 2;
    particles += `<span style="left:${left}%;animation-delay:${delay}s;animation-duration:${duration}s;width:${size}px;height:${size}px;"></span>`;
  }
  return particles;
}

function getCountdown(): string {
  // Next drop: set to a future date
  const dropDate = new Date();
  dropDate.setDate(dropDate.getDate() + 3);
  dropDate.setHours(20, 0, 0, 0);
  return `
    <div class="countdown" id="countdown" data-target="${dropDate.toISOString()}">
      <div class="countdown-item"><span class="countdown-num" id="cd-days">00</span><span class="countdown-label">Days</span></div>
      <div class="countdown-sep">:</div>
      <div class="countdown-item"><span class="countdown-num" id="cd-hours">00</span><span class="countdown-label">Hours</span></div>
      <div class="countdown-sep">:</div>
      <div class="countdown-item"><span class="countdown-num" id="cd-mins">00</span><span class="countdown-label">Min</span></div>
      <div class="countdown-sep">:</div>
      <div class="countdown-item"><span class="countdown-num" id="cd-secs">00</span><span class="countdown-label">Sec</span></div>
    </div>
  `;
}

export function renderHomePage(): string {
  const featured = products[0];

  return `
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-particles">${createParticles()}</div>
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <img src="${LOGO_URL}" alt="FTE Studios" class="logo-large" />
        <img src="./ftestudiostextlogo.png" alt="FTE Studios" class="hero-text-logo" />
        <a href="#/catalog" class="hero-btn">View Collection</a>
      </div>
      <!-- Scroll indicator -->
      <div class="scroll-indicator">
        <div class="scroll-line"></div>
        <span>Scroll</span>
      </div>
    </section>

    <!-- Infinite Marquee Divider -->
    <div class="marquee-divider">
      <div class="marquee-track-large">
        <span>FTE STUDIOS \u2022 MIDNIGHT MOTION \u2022 PREMIUM STREETWEAR \u2022 CITY LIGHTS \u2022 AFTER DARK \u2022 VOL. 4 \u2022&nbsp;</span>
        <span>FTE STUDIOS \u2022 MIDNIGHT MOTION \u2022 PREMIUM STREETWEAR \u2022 CITY LIGHTS \u2022 AFTER DARK \u2022 VOL. 4 \u2022&nbsp;</span>
      </div>
    </div>

    <!-- Collection Categories (Hellstar-style) -->
    <section class="section collections-section">
      <div class="collections-grid">
        <a href="#/catalog" class="collection-card fade-in" data-tilt>
          <div class="collection-card-bg" style="background-image: url('${featured.images[0]}')"></div>
          <div class="collection-card-overlay"></div>
          <div class="collection-card-content">
            <h3>New Drops</h3>
            <p>Limited edition pieces. Once they're gone, they're gone.</p>
            <span class="collection-card-link">Explore &rarr;</span>
          </div>
        </a>
        <a href="#/catalog" class="collection-card fade-in" data-tilt>
          <div class="collection-card-bg" style="background-image: url('${featured.images[1] || featured.images[0]}')"></div>
          <div class="collection-card-overlay"></div>
          <div class="collection-card-content">
            <h3>Studio Collection</h3>
            <p>Core pieces built for the everyday grind.</p>
            <span class="collection-card-link">Explore &rarr;</span>
          </div>
        </a>
        <a href="#/catalog" class="collection-card collection-card-wide fade-in" data-tilt>
          <div class="collection-card-bg" style="background-image: url('${featured.images[2] || featured.images[0]}')"></div>
          <div class="collection-card-overlay"></div>
          <div class="collection-card-content">
            <h3>All Products</h3>
            <p>Browse the full FTE Studios catalog.</p>
            <span class="collection-card-link">Shop All &rarr;</span>
          </div>
        </a>
      </div>
    </section>

    <!-- Featured Drop with next drop countdown -->
    <section class="section">
      <div class="split-header">
        <div>
          <h2 class="section-title fade-in" style="text-align:left;">Latest Drop</h2>
          <p class="section-subtitle fade-in" style="text-align:left;">New arrivals hit different</p>
        </div>
        <a href="#/catalog" class="view-all-link fade-in">View All &rarr;</a>
      </div>
      <div class="section-divider" style="margin-left:0;"></div>
      <div class="product-grid">
        ${products
          .map(
            (p) => `
          <a href="#/product/${p.id}" class="product-card fade-in" data-tilt>
            <div class="product-card-image">
              <img src="${p.images[0]}" alt="${p.title}" loading="lazy" />
              ${p.badge ? `<span class="product-card-badge">${p.badge}</span>` : ""}
              <div class="product-card-quick">Quick View</div>
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
    </section>

    <!-- Lookbook / Editorial Section -->
    <section class="lookbook-section">
      <div class="lookbook-grid">
        <div class="lookbook-item lookbook-item-large fade-in">
          <img src="${featured.images[0]}" alt="Lookbook" loading="lazy" />
          <div class="lookbook-overlay">
            <span class="lookbook-tag">Lookbook</span>
            <h3>After Dark</h3>
          </div>
        </div>
        <div class="lookbook-item fade-in">
          <img src="${featured.images[1] || featured.images[0]}" alt="Lookbook" loading="lazy" />
          <div class="lookbook-overlay">
            <span class="lookbook-tag">Editorial</span>
            <h3>City Motion</h3>
          </div>
        </div>
        <div class="lookbook-item fade-in">
          <img src="${featured.images[2] || featured.images[0]}" alt="Lookbook" loading="lazy" />
          <div class="lookbook-overlay">
            <span class="lookbook-tag">Studio</span>
            <h3>Vol. 4</h3>
          </div>
        </div>
      </div>
    </section>

    <!-- Marquee Divider 2 -->
    <div class="marquee-divider marquee-reverse">
      <div class="marquee-track-large">
        <span>THE CITY NEVER SLEEPS \u2022 NEITHER DO WE \u2022 FTE STUDIOS \u2022 EST. 2024 \u2022 MIDNIGHT MOTION \u2022&nbsp;</span>
        <span>THE CITY NEVER SLEEPS \u2022 NEITHER DO WE \u2022 FTE STUDIOS \u2022 EST. 2024 \u2022 MIDNIGHT MOTION \u2022&nbsp;</span>
      </div>
    </div>

    <!-- Brand Story -->
    <section class="section brand-story">
      <div class="brand-story-inner fade-in">
        <span class="brand-eyebrow">About the Brand</span>
        <h2 class="section-title" style="margin-bottom: 24px;">The Vision</h2>
        <p>
          FTE Studios was born from the idea that style shouldn't stop when the sun goes down.
          We craft premium streetwear for those who move with purpose — from late-night sessions
          to city streets. Every piece is designed to make a statement without saying a word.
        </p>
      </div>
    </section>

    <!-- Next Drop Countdown -->
    <section class="section countdown-section">
      <div class="countdown-inner fade-in">
        <span class="brand-eyebrow">Coming Soon</span>
        <h2 class="section-title" style="margin-bottom:8px;">Next Drop</h2>
        <p class="section-subtitle" style="margin-bottom:32px;">Get notified when we drop</p>
        ${getCountdown()}
        <form class="notify-form" id="notify-form">
          <input type="email" placeholder="Enter your email to get notified" required />
          <button type="submit">Notify Me</button>
        </form>
      </div>
    </section>

    <!-- Featured Product Highlight -->
    <section class="section">
      <div class="product-spotlight">
        <div class="product-spotlight-image fade-in">
          <div class="spotlight-img-wrapper parallax-img" data-speed="0.05">
            <img src="${featured.images[1] || featured.images[0]}" alt="${featured.title}" loading="lazy" />
          </div>
        </div>
        <div class="product-spotlight-info fade-in">
          <span class="brand-eyebrow">Featured</span>
          <h2>${featured.title}</h2>
          <p class="spotlight-subtitle">"${featured.subtitle}"</p>
          <p class="spotlight-price">$${featured.price.toFixed(2)} ${featured.currency}</p>
          <ul class="spotlight-bullets">
            ${featured.description.bullets
              .map((b) => `<li><span>\u2014</span> ${b}</li>`)
              .join("")}
          </ul>
          <p class="spotlight-tagline">${featured.description.tagline}</p>
          <a href="#/product/${featured.id}" class="hero-btn">View Product</a>
        </div>
      </div>
    </section>
  `;
}

export function initHomePage(): void {
  // Countdown timer
  const countdownEl = document.getElementById("countdown");
  if (countdownEl) {
    const target = new Date(countdownEl.dataset.target || "").getTime();
    const update = () => {
      const now = Date.now();
      const diff = Math.max(0, target - now);
      const d = Math.floor(diff / (1000 * 60 * 60 * 24));
      const h = Math.floor((diff / (1000 * 60 * 60)) % 24);
      const m = Math.floor((diff / (1000 * 60)) % 60);
      const s = Math.floor((diff / 1000) % 60);
      const pad = (n: number) => String(n).padStart(2, "0");
      document.getElementById("cd-days")!.textContent = pad(d);
      document.getElementById("cd-hours")!.textContent = pad(h);
      document.getElementById("cd-mins")!.textContent = pad(m);
      document.getElementById("cd-secs")!.textContent = pad(s);
    };
    update();
    setInterval(update, 1000);
  }

  // Notify form
  document.getElementById("notify-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = (e.target as HTMLFormElement).querySelector("input") as HTMLInputElement;
    if (input.value) {
      input.value = "";
      alert("You'll be the first to know!");
    }
  });

  // Tilt effect on cards
  document.querySelectorAll<HTMLElement>("[data-tilt]").forEach((el) => {
    el.addEventListener("mousemove", (e) => {
      const rect = el.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
      const y = ((e.clientY - rect.top) / rect.height - 0.5) * -8;
      el.style.transform = `perspective(800px) rotateY(${x}deg) rotateX(${y}deg) scale(1.02)`;
    });
    el.addEventListener("mouseleave", () => {
      el.style.transform = "perspective(800px) rotateY(0) rotateX(0) scale(1)";
    });
  });

  // Parallax on scroll
  const parallaxEls = document.querySelectorAll<HTMLElement>(".parallax-img");
  if (parallaxEls.length) {
    const handleScroll = () => {
      parallaxEls.forEach((el) => {
        const speed = parseFloat(el.dataset.speed || "0.05");
        const rect = el.getBoundingClientRect();
        const offset = (rect.top - window.innerHeight / 2) * speed;
        el.style.transform = `translateY(${offset}px)`;
      });
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
  }
}
