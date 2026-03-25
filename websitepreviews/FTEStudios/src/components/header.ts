const LOGO_URL =
  "https://ftestudioz.myshopify.com/cdn/shop/files/fte_studios_cropped_gif_8a667b00-002b-4ddd-8504-da9fddd792db.gif?v=1749980240";

export function renderHeader(): void {
  const header = document.getElementById("site-header");
  if (!header) return;

  header.innerHTML = `
    <a href="#/" class="logo" aria-label="Home">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
        <polyline points="9 22 9 12 15 12 15 22"/>
      </svg>
    </a>
    <button class="mobile-menu-toggle" id="mobile-toggle" aria-label="Toggle menu">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>
    <nav id="main-nav">
      <a href="#/" data-nav="home">Home</a>
      <a href="#/catalog" data-nav="catalog">Catalog</a>
      <a href="#/contact" data-nav="contact">Contact</a>
    </nav>
    <div class="header-icons">
      <a href="#/login" class="header-auth-link" data-nav="login">Log In</a>
      <a href="#/signup" class="header-auth-link header-auth-signup" data-nav="signup">Sign Up</a>
      <button id="cart-toggle" aria-label="Open cart">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>
          <line x1="3" y1="6" x2="21" y2="6"/>
          <path d="M16 10a4 4 0 01-8 0"/>
        </svg>
      </button>
    </div>
  `;

  // Mobile toggle
  const toggle = document.getElementById("mobile-toggle");
  const nav = document.getElementById("main-nav");
  toggle?.addEventListener("click", () => {
    nav?.classList.toggle("open");
  });

  // Close nav on link click (mobile)
  nav?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("open");
    });
  });

  // Cart toggle
  document.getElementById("cart-toggle")?.addEventListener("click", () => {
    document.getElementById("cart-overlay")?.classList.toggle("open");
    document.getElementById("cart-drawer")?.classList.toggle("open");
  });
}

export function updateActiveNav(route: string): void {
  const navLinks = document.querySelectorAll<HTMLAnchorElement>("[data-nav]");
  navLinks.forEach((link) => {
    const nav = link.getAttribute("data-nav");
    if (
      (route === "/" && nav === "home") ||
      (route === "/catalog" && nav === "catalog") ||
      (route === "/contact" && nav === "contact")
    ) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
}
