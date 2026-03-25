(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const a of document.querySelectorAll('link[rel="modulepreload"]'))i(a);new MutationObserver(a=>{for(const n of a)if(n.type==="childList")for(const s of n.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&i(s)}).observe(document,{childList:!0,subtree:!0});function o(a){const n={};return a.integrity&&(n.integrity=a.integrity),a.referrerPolicy&&(n.referrerPolicy=a.referrerPolicy),a.crossOrigin==="use-credentials"?n.credentials="include":a.crossOrigin==="anonymous"?n.credentials="omit":n.credentials="same-origin",n}function i(a){if(a.ep)return;a.ep=!0;const n=o(a);fetch(a.href,n)}})();function w(){var i;const e=document.getElementById("site-header");if(!e)return;e.innerHTML=`
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
  `;const t=document.getElementById("mobile-toggle"),o=document.getElementById("main-nav");t==null||t.addEventListener("click",()=>{o==null||o.classList.toggle("open")}),o==null||o.querySelectorAll("a").forEach(a=>{a.addEventListener("click",()=>{o.classList.remove("open")})}),(i=document.getElementById("cart-toggle"))==null||i.addEventListener("click",()=>{var a,n;(a=document.getElementById("cart-overlay"))==null||a.classList.toggle("open"),(n=document.getElementById("cart-drawer"))==null||n.classList.toggle("open")})}function E(e){document.querySelectorAll("[data-nav]").forEach(o=>{const i=o.getAttribute("data-nav");e==="/"&&i==="home"||e==="/catalog"&&i==="catalog"||e==="/contact"&&i==="contact"?o.classList.add("active"):o.classList.remove("active")})}function k(){const e=document.getElementById("site-footer");if(!e)return;e.className="site-footer",e.innerHTML=`
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
  `;const t=e.querySelector(".subscribe-form");t==null||t.addEventListener("submit",o=>{o.preventDefault();const i=t.querySelector("input");i.value&&(i.value="",alert("Thank you for subscribing!"))})}let l=[];function x(){return l}function $(e){const t=l.find(o=>o.productId===e.productId&&o.size===e.size);t?t.quantity+=e.quantity:l.push({...e}),f(),S()}function L(e,t){l=l.filter(o=>!(o.productId===e&&o.size===t)),f()}function S(){var e,t;(e=document.getElementById("cart-overlay"))==null||e.classList.add("open"),(t=document.getElementById("cart-drawer"))==null||t.classList.add("open")}function h(){var e,t;(e=document.getElementById("cart-overlay"))==null||e.classList.remove("open"),(t=document.getElementById("cart-drawer"))==null||t.classList.remove("open")}function f(){var i,a;const e=document.getElementById("cart-drawer");if(!e)return;const t=l.reduce((n,s)=>n+s.quantity,0),o=l.reduce((n,s)=>n+s.price*s.quantity,0);e.innerHTML=`
    <div class="cart-drawer-header">
      <h2>Cart (${t})</h2>
      <button id="cart-close" aria-label="Close cart">&times;</button>
    </div>
    <div class="cart-drawer-body" style="${l.length?"display:block; align-items:stretch;":""}">
      ${l.length===0?'<p class="cart-empty">Your cart is empty</p>':l.map(n=>`
          <div class="cart-item">
            <img src="${n.image}" alt="${n.title}" />
            <div class="cart-item-info">
              <h4>${n.title}</h4>
              <p class="cart-item-details">Size: ${n.size} &middot; Qty: ${n.quantity}</p>
              <p class="cart-item-details">$${(n.price*n.quantity).toFixed(2)} USD</p>
              <button class="remove-cart-item" data-id="${n.productId}" data-size="${n.size}" style="background:none;color:#888;font-size:0.7rem;text-decoration:underline;margin-top:4px;font-family:inherit;cursor:pointer;">Remove</button>
            </div>
          </div>
        `).join("")}
    </div>
    ${l.length>0?`
      <div style="padding:24px;border-top:1px solid var(--color-border);">
        <div style="display:flex;justify-content:space-between;margin-bottom:16px;">
          <span style="font-family:var(--font-heading);font-size:0.8rem;letter-spacing:0.1em;text-transform:uppercase;">Total</span>
          <span style="font-weight:600;">$${o.toFixed(2)} USD</span>
        </div>
        <a href="#/checkout" class="add-to-cart-btn" style="width:100%;display:block;text-align:center;" id="checkout-link">Checkout</a>
      </div>
    `:""}
  `,(i=document.getElementById("cart-close"))==null||i.addEventListener("click",h),(a=document.getElementById("checkout-link"))==null||a.addEventListener("click",h),e.querySelectorAll(".remove-cart-item").forEach(n=>{n.addEventListener("click",()=>{const s=n.dataset.id,c=n.dataset.size;L(s,c)})})}function I(){var e;f(),(e=document.getElementById("cart-overlay"))==null||e.addEventListener("click",h)}const u=[{id:"midnight-motion-vol-4",title:"Midnight Motion Vol. 4",subtitle:"The city never sleeps, neither do we.",price:125,currency:"USD",images:["https://ftestudioz.myshopify.com/cdn/shop/files/447DA9F5-CA77-4CC4-AD4A-7E83DE28FCAA.jpg?v=1767939134&width=800","https://ftestudioz.myshopify.com/cdn/shop/files/CA0E4212-CEB4-4E5F-8DFD-A9856D5E943C.jpg?v=1767939134&width=800","https://ftestudioz.myshopify.com/cdn/shop/files/38B0FCC9-58F6-483E-B909-1DE2E0E4D547.jpg?v=1767939134&width=800"],sizes:[{label:"S",available:!1},{label:"M",available:!1},{label:"L",available:!0},{label:"XL",available:!0},{label:"2XL",available:!0}],badge:"New Drop",description:{bullets:["Full outfit set designed for movement after dark","Clean silhouette, bold presence","Made for late nights, city lights, and focused minds","Effortless fit that moves with confidence","Where style meets momentum"],tagline:"Midnight Motion isn't just an outfit — it's a mindset."}}],C="https://ftestudioz.myshopify.com/cdn/shop/files/fte_studios_cropped_gif_8a667b00-002b-4ddd-8504-da9fddd792db.gif?v=1749980240";function q(){let e="";for(let t=0;t<40;t++){const o=Math.random()*100,i=Math.random()*10,a=6+Math.random()*8,n=1+Math.random()*2;e+=`<span style="left:${o}%;animation-delay:${i}s;animation-duration:${a}s;width:${n}px;height:${n}px;"></span>`}return e}function D(){const e=new Date;return e.setDate(e.getDate()+3),e.setHours(20,0,0,0),`
    <div class="countdown" id="countdown" data-target="${e.toISOString()}">
      <div class="countdown-item"><span class="countdown-num" id="cd-days">00</span><span class="countdown-label">Days</span></div>
      <div class="countdown-sep">:</div>
      <div class="countdown-item"><span class="countdown-num" id="cd-hours">00</span><span class="countdown-label">Hours</span></div>
      <div class="countdown-sep">:</div>
      <div class="countdown-item"><span class="countdown-num" id="cd-mins">00</span><span class="countdown-label">Min</span></div>
      <div class="countdown-sep">:</div>
      <div class="countdown-item"><span class="countdown-num" id="cd-secs">00</span><span class="countdown-label">Sec</span></div>
    </div>
  `}function T(){const e=u[0];return`
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-particles">${q()}</div>
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <img src="${C}" alt="FTE Studios" class="logo-large" />
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
        <span>FTE STUDIOS • MIDNIGHT MOTION • PREMIUM STREETWEAR • CITY LIGHTS • AFTER DARK • VOL. 4 •&nbsp;</span>
        <span>FTE STUDIOS • MIDNIGHT MOTION • PREMIUM STREETWEAR • CITY LIGHTS • AFTER DARK • VOL. 4 •&nbsp;</span>
      </div>
    </div>

    <!-- Collection Categories (Hellstar-style) -->
    <section class="section collections-section">
      <div class="collections-grid">
        <a href="#/catalog" class="collection-card fade-in" data-tilt>
          <div class="collection-card-bg" style="background-image: url('${e.images[0]}')"></div>
          <div class="collection-card-overlay"></div>
          <div class="collection-card-content">
            <h3>New Drops</h3>
            <p>Limited edition pieces. Once they're gone, they're gone.</p>
            <span class="collection-card-link">Explore &rarr;</span>
          </div>
        </a>
        <a href="#/catalog" class="collection-card fade-in" data-tilt>
          <div class="collection-card-bg" style="background-image: url('${e.images[1]||e.images[0]}')"></div>
          <div class="collection-card-overlay"></div>
          <div class="collection-card-content">
            <h3>Studio Collection</h3>
            <p>Core pieces built for the everyday grind.</p>
            <span class="collection-card-link">Explore &rarr;</span>
          </div>
        </a>
        <a href="#/catalog" class="collection-card collection-card-wide fade-in" data-tilt>
          <div class="collection-card-bg" style="background-image: url('${e.images[2]||e.images[0]}')"></div>
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
        ${u.map(t=>`
          <a href="#/product/${t.id}" class="product-card fade-in" data-tilt>
            <div class="product-card-image">
              <img src="${t.images[0]}" alt="${t.title}" loading="lazy" />
              ${t.badge?`<span class="product-card-badge">${t.badge}</span>`:""}
              <div class="product-card-quick">Quick View</div>
            </div>
            <div class="product-card-info">
              <h3>${t.title}</h3>
              <p class="price">$<span class="amount">${t.price.toFixed(2)}</span> ${t.currency}</p>
            </div>
          </a>
        `).join("")}
      </div>
    </section>

    <!-- Lookbook / Editorial Section -->
    <section class="lookbook-section">
      <div class="lookbook-grid">
        <div class="lookbook-item lookbook-item-large fade-in">
          <img src="${e.images[0]}" alt="Lookbook" loading="lazy" />
          <div class="lookbook-overlay">
            <span class="lookbook-tag">Lookbook</span>
            <h3>After Dark</h3>
          </div>
        </div>
        <div class="lookbook-item fade-in">
          <img src="${e.images[1]||e.images[0]}" alt="Lookbook" loading="lazy" />
          <div class="lookbook-overlay">
            <span class="lookbook-tag">Editorial</span>
            <h3>City Motion</h3>
          </div>
        </div>
        <div class="lookbook-item fade-in">
          <img src="${e.images[2]||e.images[0]}" alt="Lookbook" loading="lazy" />
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
        <span>THE CITY NEVER SLEEPS • NEITHER DO WE • FTE STUDIOS • EST. 2024 • MIDNIGHT MOTION •&nbsp;</span>
        <span>THE CITY NEVER SLEEPS • NEITHER DO WE • FTE STUDIOS • EST. 2024 • MIDNIGHT MOTION •&nbsp;</span>
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
        ${D()}
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
            <img src="${e.images[1]||e.images[0]}" alt="${e.title}" loading="lazy" />
          </div>
        </div>
        <div class="product-spotlight-info fade-in">
          <span class="brand-eyebrow">Featured</span>
          <h2>${e.title}</h2>
          <p class="spotlight-subtitle">"${e.subtitle}"</p>
          <p class="spotlight-price">$${e.price.toFixed(2)} ${e.currency}</p>
          <ul class="spotlight-bullets">
            ${e.description.bullets.map(t=>`<li><span>—</span> ${t}</li>`).join("")}
          </ul>
          <p class="spotlight-tagline">${e.description.tagline}</p>
          <a href="#/product/${e.id}" class="hero-btn">View Product</a>
        </div>
      </div>
    </section>
  `}function M(){var o;const e=document.getElementById("countdown");if(e){const i=new Date(e.dataset.target||"").getTime(),a=()=>{const n=Date.now(),s=Math.max(0,i-n),c=Math.floor(s/(1e3*60*60*24)),p=Math.floor(s/(1e3*60*60)%24),m=Math.floor(s/(1e3*60)%60),v=Math.floor(s/1e3%60),d=r=>String(r).padStart(2,"0");document.getElementById("cd-days").textContent=d(c),document.getElementById("cd-hours").textContent=d(p),document.getElementById("cd-mins").textContent=d(m),document.getElementById("cd-secs").textContent=d(v)};a(),setInterval(a,1e3)}(o=document.getElementById("notify-form"))==null||o.addEventListener("submit",i=>{i.preventDefault();const a=i.target.querySelector("input");a.value&&(a.value="",alert("You'll be the first to know!"))}),document.querySelectorAll("[data-tilt]").forEach(i=>{i.addEventListener("mousemove",a=>{const n=i.getBoundingClientRect(),s=((a.clientX-n.left)/n.width-.5)*8,c=((a.clientY-n.top)/n.height-.5)*-8;i.style.transform=`perspective(800px) rotateY(${s}deg) rotateX(${c}deg) scale(1.02)`}),i.addEventListener("mouseleave",()=>{i.style.transform="perspective(800px) rotateY(0) rotateX(0) scale(1)"})});const t=document.querySelectorAll(".parallax-img");if(t.length){const i=()=>{t.forEach(a=>{const n=parseFloat(a.dataset.speed||"0.05"),c=(a.getBoundingClientRect().top-window.innerHeight/2)*n;a.style.transform=`translateY(${c}px)`})};window.addEventListener("scroll",i,{passive:!0})}}function B(){return`
    <section class="section" style="min-height: 60vh;">
      <h1 class="section-title fade-in">Catalog</h1>
      <p class="section-subtitle fade-in">Browse all products</p>
      <div class="section-divider"></div>
      <div class="product-grid">
        ${u.map(e=>`
          <a href="#/product/${e.id}" class="product-card fade-in">
            <div class="product-card-image">
              <img src="${e.images[0]}" alt="${e.title}" loading="lazy" />
              ${e.badge?`<span class="product-card-badge">${e.badge}</span>`:""}
            </div>
            <div class="product-card-info">
              <h3>${e.title}</h3>
              <p class="price">$<span class="amount">${e.price.toFixed(2)}</span> ${e.currency}</p>
            </div>
          </a>
        `).join("")}
      </div>
      ${u.length===0?'<p style="text-align:center;color:var(--color-text-muted);margin-top:40px;">No products yet. Check back soon!</p>':""}
    </section>
  `}function P(){return`
    <section class="contact-section">
      <h1 class="fade-in">Contact</h1>
      <form class="contact-form fade-in" id="contact-form">
        <div class="form-group">
          <label for="contact-name">Name</label>
          <input type="text" id="contact-name" name="name" placeholder="Your name" required />
        </div>
        <div class="form-group">
          <label for="contact-email">Email</label>
          <input type="email" id="contact-email" name="email" placeholder="you@example.com" required />
        </div>
        <div class="form-group">
          <label for="contact-phone">Phone Number</label>
          <input type="tel" id="contact-phone" name="phone" placeholder="+1 (555) 000-0000" />
        </div>
        <div class="form-group">
          <label for="contact-message">Comment</label>
          <textarea id="contact-message" name="message" placeholder="How can we help?" required></textarea>
        </div>
        <button type="submit" class="form-submit-btn">Send</button>
      </form>
    </section>
  `}function F(){const e=document.getElementById("contact-form");e==null||e.addEventListener("submit",t=>{t.preventDefault();const i=new FormData(e).get("name");alert(`Thank you ${i}! We'll be in touch soon.`),e.reset()})}function A(e){const t=u.find(o=>o.id===e);return t?`
    <div class="product-detail">
      <div class="product-gallery fade-in">
        <div class="product-gallery-main">
          <img id="main-product-image" src="${t.images[0]}" alt="${t.title}" />
        </div>
        <div class="product-gallery-thumbs">
          ${t.images.map((o,i)=>`<img src="${o}" alt="${t.title} ${i+1}" class="thumb ${i===0?"active":""}" data-index="${i}" />`).join("")}
        </div>
      </div>
      <div class="product-info fade-in">
        <h1>${t.title}</h1>
        <p style="color:var(--color-text-muted);font-style:italic;margin-bottom:16px;">"${t.subtitle}"</p>
        <p class="product-price">$${t.price.toFixed(2)} ${t.currency}</p>
        <p class="product-installments">
          Pay in 4 interest-free installments of $${(t.price/4).toFixed(2)} with Shop Pay
        </p>

        <div class="product-size-selector">
          <label>Size</label>
          <div class="size-options" id="size-options">
            ${t.sizes.map(o=>`<button class="size-option ${o.available?"":"sold-out"}" data-size="${o.label}" ${o.available?"":"disabled"}>${o.label}</button>`).join("")}
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
            ${t.description.bullets.map(o=>`<li>${o}</li>`).join("")}
          </ul>
          <p class="tagline">${t.description.tagline}</p>
        </div>
      </div>
    </div>
  `:`
      <section class="section" style="min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <h1 style="margin-bottom:16px;">Product Not Found</h1>
        <p style="color:var(--color-text-muted);margin-bottom:24px;">Sorry, we couldn't find that product.</p>
        <a href="#/catalog" class="hero-btn">Back to Catalog</a>
      </section>
    `}function z(e){var m,v,d;const t=u.find(r=>r.id===e);if(!t)return;const o=document.getElementById("main-product-image"),i=document.querySelectorAll(".thumb");i.forEach(r=>{r.addEventListener("click",()=>{const g=parseInt(r.dataset.index||"0");o.src=t.images[g],i.forEach(b=>b.classList.remove("active")),r.classList.add("active")})});let a="";const n=document.querySelectorAll("#size-options .size-option:not(.sold-out)");n.forEach(r=>{r.addEventListener("click",()=>{n.forEach(g=>g.classList.remove("active")),r.classList.add("active"),a=r.dataset.size||""})});const s=document.querySelector("#size-options .size-option:not(.sold-out)");s&&(s.classList.add("active"),a=s.dataset.size||"");let c=1;const p=document.getElementById("qty-display");(m=document.getElementById("qty-decrease"))==null||m.addEventListener("click",()=>{c>1&&(c--,p.textContent=String(c))}),(v=document.getElementById("qty-increase"))==null||v.addEventListener("click",()=>{c++,p.textContent=String(c)}),(d=document.getElementById("add-to-cart-btn"))==null||d.addEventListener("click",()=>{if(!a){alert("Please select a size");return}$({productId:t.id,title:t.title,size:a,price:t.price,quantity:c,image:t.images[0]})})}function N(){const e=x(),t=e.reduce((s,c)=>s+c.price*c.quantity,0),o=t>0?9.99:0,i=t*.08,a=t+o+i,n=e.length>0?e.map(s=>`
        <div class="checkout-item">
          <div class="checkout-item-image">
            <img src="${s.image}" alt="${s.title}" />
            <span class="checkout-item-qty">${s.quantity}</span>
          </div>
          <div class="checkout-item-info">
            <p class="checkout-item-title">${s.title}</p>
            <p class="checkout-item-variant">Size: ${s.size}</p>
          </div>
          <p class="checkout-item-price">$${(s.price*s.quantity).toFixed(2)}</p>
        </div>
      `).join(""):'<p style="color:var(--color-text-muted);text-align:center;padding:40px 0;">Your cart is empty</p>';return`
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
          Pay $${a.toFixed(2)} USD
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
            ${n}
          </div>
          <div class="checkout-totals">
            <div class="checkout-total-row">
              <span>Subtotal</span>
              <span>$${t.toFixed(2)}</span>
            </div>
            <div class="checkout-total-row">
              <span>Shipping</span>
              <span>${o>0?"$"+o.toFixed(2):"—"}</span>
            </div>
            <div class="checkout-total-row">
              <span>Estimated Tax</span>
              <span>$${i.toFixed(2)}</span>
            </div>
            <div class="checkout-total-row checkout-total-final">
              <span>Total</span>
              <span>$${a.toFixed(2)} <small style="color:var(--color-text-muted);font-weight:400;">USD</small></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `}function O(){var o;const e=document.getElementById("card-number");e==null||e.addEventListener("input",()=>{let i=e.value.replace(/\D/g,"");i=i.replace(/(.{4})/g,"$1 ").trim(),e.value=i});const t=document.querySelectorAll(".shipping-option");t.forEach(i=>{const a=i.querySelector("input[type=radio]");a==null||a.addEventListener("change",()=>{t.forEach(n=>n.classList.remove("selected")),i.classList.add("selected")})}),(o=document.getElementById("place-order-btn"))==null||o.addEventListener("click",i=>{var n;if(i.preventDefault(),!((n=document.getElementById("checkout-email"))==null?void 0:n.value)){alert("Please enter your email address.");return}window.location.hash="#/order-confirmed"})}function H(){return`
    <section class="order-confirmed">
      <div class="order-confirmed-inner fade-in">
        <div class="order-check">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 12l3 3 5-6" />
          </svg>
        </div>
        <h1>Order Confirmed</h1>
        <p class="order-number">Order #FTE-${Math.floor(1e5+Math.random()*9e5)}</p>
        <p class="order-thanks">
          Thank you for your purchase! This is a demo confirmation page —
          no real order was placed.
        </p>
        <div class="order-actions">
          <a href="#/" class="hero-btn">Continue Shopping</a>
        </div>
      </div>
    </section>
  `}function R(){return`
    <section class="auth-section">
      <div class="auth-card fade-in">
        <h1>Log In</h1>
        <form class="auth-form" id="login-form">
          <div class="form-group">
            <label for="login-email">Email</label>
            <input type="email" id="login-email" name="email" placeholder="you@example.com" required />
          </div>
          <div class="form-group">
            <label for="login-password">Password</label>
            <input type="password" id="login-password" name="password" placeholder="Your password" required />
          </div>
          <button type="submit" class="form-submit-btn">Log In</button>
        </form>
        <p class="auth-switch">Don't have an account? <a href="#/signup">Sign Up</a></p>
      </div>
    </section>
  `}function Y(){const e=document.getElementById("login-form");e==null||e.addEventListener("submit",t=>{t.preventDefault();const i=new FormData(e).get("email");alert(`Welcome back, ${i}!`),e.reset(),window.location.hash="#/"})}function U(){return`
    <section class="auth-section">
      <div class="auth-card fade-in">
        <h1>Sign Up</h1>
        <form class="auth-form" id="signup-form">
          <div class="form-group">
            <label for="signup-name">Name</label>
            <input type="text" id="signup-name" name="name" placeholder="Your name" required />
          </div>
          <div class="form-group">
            <label for="signup-email">Email</label>
            <input type="email" id="signup-email" name="email" placeholder="you@example.com" required />
          </div>
          <div class="form-group">
            <label for="signup-password">Password</label>
            <input type="password" id="signup-password" name="password" placeholder="Create a password" minlength="8" required />
          </div>
          <div class="form-group">
            <label for="signup-confirm">Confirm Password</label>
            <input type="password" id="signup-confirm" name="confirm" placeholder="Confirm your password" minlength="8" required />
          </div>
          <button type="submit" class="form-submit-btn">Sign Up</button>
        </form>
        <p class="auth-switch">Already have an account? <a href="#/login">Log In</a></p>
      </div>
    </section>
  `}function V(){const e=document.getElementById("signup-form");e==null||e.addEventListener("submit",t=>{t.preventDefault();const o=new FormData(e),i=o.get("password"),a=o.get("confirm");if(i!==a){alert("Passwords do not match.");return}const n=o.get("name");alert(`Welcome, ${n}! Your account has been created.`),e.reset(),window.location.hash="#/login"})}function j(){return(window.location.hash||"#/").replace("#","")||"/"}function W(e){const t=e.match(/^\/product\/(.+)$/);if(t){const o=t[1];return{render:()=>A(o),init:()=>z(o)}}switch(e){case"/catalog":return{render:B};case"/contact":return{render:P,init:F};case"/checkout":return{render:N,init:O};case"/order-confirmed":return{render:H};case"/login":return{render:R,init:Y};case"/signup":return{render:U,init:V};case"/":default:return{render:T,init:M}}}function G(){const e=new IntersectionObserver(t=>{t.forEach(o=>{o.isIntersecting&&(o.target.classList.add("visible"),e.unobserve(o.target))})},{threshold:.1});document.querySelectorAll(".fade-in").forEach(t=>e.observe(t))}function X(){const e=document.getElementById("app");function t(){const o=j(),i=W(o);e.classList.add("transitioning"),setTimeout(()=>{var a;e.innerHTML=i.render(),e.classList.remove("transitioning"),window.scrollTo(0,0),E(o),(a=i.init)==null||a.call(i),requestAnimationFrame(()=>{G()})},200)}window.addEventListener("hashchange",t),t()}function K(){const e=document.getElementById("custom-cursor"),t=document.getElementById("custom-cursor-dot");if(!e||!t)return;let o=0,i=0,a=0,n=0;document.addEventListener("mousemove",c=>{o=c.clientX,i=c.clientY,t.style.left=o+"px",t.style.top=i+"px"});const s=()=>{a+=(o-a)*.15,n+=(i-n)*.15,e.style.left=a+"px",e.style.top=n+"px",requestAnimationFrame(s)};s(),document.addEventListener("mouseover",c=>{c.target.closest("a, button, .product-card, [data-tilt]")&&(e.classList.add("cursor-hover"),t.classList.add("cursor-hover"))}),document.addEventListener("mouseout",c=>{c.target.closest("a, button, .product-card, [data-tilt]")&&(e.classList.remove("cursor-hover"),t.classList.remove("cursor-hover"))})}function _(){const e=document.getElementById("preloader");e&&window.addEventListener("load",()=>{setTimeout(()=>{e.classList.add("loaded"),setTimeout(()=>{e.style.display="none"},600)},800)})}function Q(){const e=document.getElementById("site-header"),t=document.getElementById("marquee-bar");if(!e)return;let o=0;window.addEventListener("scroll",()=>{const i=window.scrollY;i>80?(e.classList.add("header-scrolled"),t==null||t.classList.add("marquee-hidden"),i>o&&i>300?e.classList.add("header-hidden"):e.classList.remove("header-hidden")):(e.classList.remove("header-scrolled","header-hidden"),t==null||t.classList.remove("marquee-hidden")),o=i},{passive:!0})}function y(){_(),w(),k(),I(),X(),K(),Q()}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",y):y();
