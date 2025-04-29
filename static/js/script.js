document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const currentTheme = localStorage.getItem('theme') || 'light'; // Default to light
    const body = document.body;

    // Apply the saved theme on initial load
    body.classList.remove('theme-light', 'theme-dark');
    body.classList.add(`theme-${currentTheme}`);
    if (themeToggle) {
        themeToggle.textContent = currentTheme === 'dark' ? 'Toggle Light Mode' : 'Toggle Dark Mode';
    }

    // Add event listener to the toggle button
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            let newTheme = 'light';
            if (body.classList.contains('theme-light')) {
                newTheme = 'dark';
            }

            body.classList.remove('theme-light', 'theme-dark');
            body.classList.add(`theme-${newTheme}`);
            localStorage.setItem('theme', newTheme);

            themeToggle.textContent = newTheme === 'dark' ? 'Toggle Light Mode' : 'Toggle Dark Mode';
        });
    }

    // --- Flash Message Handling (Optional but good UX) ---
    const flashMessages = document.querySelectorAll('.flash-message'); // Assuming you add this class to flash messages
    flashMessages.forEach(msg => {
        // Add a close button or hide after timeout
        setTimeout(() => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 500); // Remove after fade out
        }, 5000); // Hide after 5 seconds

        // Optional: Add a close button dynamically
        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'x';
        closeBtn.style.marginLeft = '15px';
        closeBtn.style.border = 'none';
        closeBtn.style.background = 'transparent';
        closeBtn.style.cursor = 'pointer';
        closeBtn.style.float = 'right'; // Or adjust styling as needed
        closeBtn.onclick = () => msg.remove();
        msg.prepend(closeBtn); // Add button to the start of the message
    });

}); 