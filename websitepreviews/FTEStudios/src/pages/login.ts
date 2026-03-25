export function renderLoginPage(): string {
  return `
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
  `;
}

export function initLoginPage(): void {
  const form = document.getElementById("login-form") as HTMLFormElement;
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const email = formData.get("email") as string;
    alert(`Welcome back, ${email}!`);
    form.reset();
    window.location.hash = "#/";
  });
}
