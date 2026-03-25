export function renderSignupPage(): string {
  return `
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
  `;
}

export function initSignupPage(): void {
  const form = document.getElementById("signup-form") as HTMLFormElement;
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const password = formData.get("password") as string;
    const confirm = formData.get("confirm") as string;

    if (password !== confirm) {
      alert("Passwords do not match.");
      return;
    }

    const name = formData.get("name") as string;
    alert(`Welcome, ${name}! Your account has been created.`);
    form.reset();
    window.location.hash = "#/login";
  });
}
