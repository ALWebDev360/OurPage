export function renderContactPage(): string {
  return `
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
  `;
}

export function initContactPage(): void {
  const form = document.getElementById("contact-form") as HTMLFormElement;
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const name = formData.get("name");
    alert(`Thank you ${name}! We'll be in touch soon.`);
    form.reset();
  });
}
