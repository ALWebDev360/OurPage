import { renderHeader } from "./components/header";
import { renderFooter } from "./components/footer";
import { initCart } from "./components/cart";
import { initRouter } from "./router";

// Custom cursor
function initCursor(): void {
  const cursor = document.getElementById("custom-cursor");
  const dot = document.getElementById("custom-cursor-dot");
  if (!cursor || !dot) return;

  let mouseX = 0, mouseY = 0;
  let cursorX = 0, cursorY = 0;

  document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    dot.style.left = mouseX + "px";
    dot.style.top = mouseY + "px";
  });

  const animate = () => {
    cursorX += (mouseX - cursorX) * 0.15;
    cursorY += (mouseY - cursorY) * 0.15;
    cursor.style.left = cursorX + "px";
    cursor.style.top = cursorY + "px";
    requestAnimationFrame(animate);
  };
  animate();

  // Hover effect on interactive elements
  document.addEventListener("mouseover", (e) => {
    const target = e.target as HTMLElement;
    if (target.closest("a, button, .product-card, [data-tilt]")) {
      cursor.classList.add("cursor-hover");
      dot.classList.add("cursor-hover");
    }
  });
  document.addEventListener("mouseout", (e) => {
    const target = e.target as HTMLElement;
    if (target.closest("a, button, .product-card, [data-tilt]")) {
      cursor.classList.remove("cursor-hover");
      dot.classList.remove("cursor-hover");
    }
  });
}

// Preloader
function initPreloader(): void {
  const preloader = document.getElementById("preloader");
  if (!preloader) return;

  window.addEventListener("load", () => {
    setTimeout(() => {
      preloader.classList.add("loaded");
      setTimeout(() => { preloader.style.display = "none"; }, 600);
    }, 800);
  });
}

// Smooth header hide/show on scroll
function initHeaderScroll(): void {
  const header = document.getElementById("site-header");
  const marquee = document.getElementById("marquee-bar");
  if (!header) return;

  let lastScroll = 0;
  window.addEventListener("scroll", () => {
    const currentScroll = window.scrollY;
    if (currentScroll > 80) {
      header.classList.add("header-scrolled");
      marquee?.classList.add("marquee-hidden");
      if (currentScroll > lastScroll && currentScroll > 300) {
        header.classList.add("header-hidden");
      } else {
        header.classList.remove("header-hidden");
      }
    } else {
      header.classList.remove("header-scrolled", "header-hidden");
      marquee?.classList.remove("marquee-hidden");
    }
    lastScroll = currentScroll;
  }, { passive: true });
}

// Initialize app
function init(): void {
  initPreloader();
  renderHeader();
  renderFooter();
  initCart();
  initRouter();
  initCursor();
  initHeaderScroll();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
