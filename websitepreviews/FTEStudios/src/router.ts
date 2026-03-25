import { renderHomePage, initHomePage } from "./pages/home";
import { renderCatalogPage } from "./pages/catalog";
import { renderContactPage, initContactPage } from "./pages/contact";
import { renderProductPage, initProductPage } from "./pages/product";
import { renderCheckoutPage, initCheckoutPage } from "./pages/checkout";
import { renderOrderConfirmedPage } from "./pages/order-confirmed";
import { renderLoginPage, initLoginPage } from "./pages/login";
import { renderSignupPage, initSignupPage } from "./pages/signup";
import { updateActiveNav } from "./components/header";

type RouteHandler = {
  render: () => string;
  init?: () => void;
};

function getRoute(): string {
  const hash = window.location.hash || "#/";
  return hash.replace("#", "") || "/";
}

function matchRoute(path: string): RouteHandler {
  // Product detail
  const productMatch = path.match(/^\/product\/(.+)$/);
  if (productMatch) {
    const productId = productMatch[1];
    return {
      render: () => renderProductPage(productId),
      init: () => initProductPage(productId),
    };
  }

  switch (path) {
    case "/catalog":
      return { render: renderCatalogPage };
    case "/contact":
      return { render: renderContactPage, init: initContactPage };
    case "/checkout":
      return { render: renderCheckoutPage, init: initCheckoutPage };
    case "/order-confirmed":
      return { render: renderOrderConfirmedPage };
    case "/login":
      return { render: renderLoginPage, init: initLoginPage };
    case "/signup":
      return { render: renderSignupPage, init: initSignupPage };
    case "/":
    default:
      return { render: renderHomePage, init: initHomePage };
  }
}

function observeFadeIns(): void {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll(".fade-in").forEach((el) => observer.observe(el));
}

export function navigateTo(path: string): void {
  window.location.hash = path;
}

export function initRouter(): void {
  const app = document.getElementById("app")!;

  function handleRoute(): void {
    const path = getRoute();
    const route = matchRoute(path);

    // Page transition
    app.classList.add("transitioning");

    setTimeout(() => {
      app.innerHTML = route.render();
      app.classList.remove("transitioning");
      window.scrollTo(0, 0);

      // Update nav
      updateActiveNav(path);

      // Init page-specific JS
      route.init?.();

      // Observe fade-in elements
      requestAnimationFrame(() => {
        observeFadeIns();
      });
    }, 200);
  }

  window.addEventListener("hashchange", handleRoute);
  handleRoute();
}
