document.addEventListener('DOMContentLoaded', () => {
    // Password visibility toggle
    const passwordAddon = document.getElementById('password-addon');
    if (passwordAddon) {
        passwordAddon.addEventListener('click', function () {
            const passwordInput = document.getElementById("password-input");
            if (passwordInput.type === "password") {
                passwordInput.type = "text";
            } else {
                passwordInput.type = "password";
            }
        });
    }

    const loginForm = document.getElementById('login-form');
    if (!loginForm) return;

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = document.getElementById('username').value;
        const password = document.getElementById('password-input').value;
        const btnLogin = document.getElementById('btn-login');
        const spinner = document.getElementById('login-spinner');
        const errorMsg = document.getElementById('error-msg');

        // Reset UI
        errorMsg.classList.add('d-none');
        btnLogin.disabled = true;
        btnLogin.innerHTML = 'Signing In... <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

        try {
            const formData = new URLSearchParams();
            formData.append('username', email); // OAuth2 expects 'username' (which is our email)
            formData.append('password', password);

            const response = await fetch(`${window.AppConfig.API_BASE_URL}/auth/jwt/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                const token = data.access_token;

                // Save Token
                localStorage.setItem('access_token', token);

                // Fetch User Details & Client ID
                try {
                    const userResponse = await fetch(`${window.AppConfig.API_BASE_URL}/users/me`, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });

                    if (userResponse.ok) {
                        const userData = await userResponse.json();
                        localStorage.setItem('user_profile', JSON.stringify(userData));

                        // Extract Client ID (assuming first tenant for now)
                        if (userData.tenants && userData.tenants.length > 0) {
                            const masterClient = userData.tenants[0];
                            localStorage.setItem('client_id', masterClient.client_id);
                            localStorage.setItem('role_id', masterClient.role_id);
                            console.log('Session initialized for Client:', masterClient.client_id);
                        } else {
                            console.warn('User has no tenants assigned.');
                        }
                    }
                } catch (e) {
                    console.error('Failed to fetch user profile:', e);
                }

                // Redirect
                window.location.href = '/';
            } else {
                // Error
                errorMsg.textContent = "Invalid email or password.";
                errorMsg.classList.remove('d-none');
                btnLogin.disabled = false;
                btnLogin.innerHTML = 'Sign In';
            }
        } catch (error) {
            console.error('Login Error:', error);
            errorMsg.textContent = "Network error. Please try again.";
            errorMsg.classList.remove('d-none');
            btnLogin.disabled = false;
            btnLogin.innerHTML = 'Sign In';
        }
    });
});
