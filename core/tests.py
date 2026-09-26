from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.dashboard_url = reverse('dashboard')
        self.landing_url = reverse('landing')
        
        self.test_email = "alex@example.com"
        self.test_password = "SecurePassword123!"
        self.test_name = "Alex Morgan"
        
    def test_landing_page_accessible(self):
        response = self.client.get(self.landing_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ReCode")

    def test_user_registration_success_with_name(self):
        response = self.client.post(self.register_url, {
            'name': self.test_name,
            'email': self.test_email,
            'password': self.test_password,
            'confirm_password': self.test_password,
        }, follow=True)
        
        user = User.objects.filter(email=self.test_email).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, self.test_name)
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue(response.context['user'].is_authenticated)
        # Dashboard greeting should display user's name
        self.assertContains(response, self.test_name)

    def test_user_registration_without_name(self):
        response = self.client.post(self.register_url, {
            'name': '',
            'email': "noname@example.com",
            'password': self.test_password,
            'confirm_password': self.test_password,
        }, follow=True)
        self.assertFalse(User.objects.filter(email="noname@example.com").exists())
        self.assertRedirects(response, f"{self.landing_url}?tab=signup")
        messages = list(response.context['messages'])
        self.assertTrue(any("Please enter your name." in str(m) for m in messages))

    def test_registration_password_mismatch(self):
        response = self.client.post(self.register_url, {
            'name': self.test_name,
            'email': self.test_email,
            'password': self.test_password,
            'confirm_password': "DifferentPassword123!",
        }, follow=True)
        self.assertFalse(User.objects.filter(email=self.test_email).exists())
        self.assertRedirects(response, f"{self.landing_url}?tab=signup")
        messages = list(response.context['messages'])
        self.assertTrue(any("Passwords do not match." in str(m) for m in messages))
        # Ensure user inputs are preserved for UX
        self.assertEqual(response.context['saved_name'], self.test_name)
        self.assertEqual(response.context['saved_email'], self.test_email)

    def test_registration_duplicate_email(self):
        User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        response = self.client.post(self.register_url, {
            'name': "Another Person",
            'email': self.test_email.upper(),  # Test case-insensitivity
            'password': self.test_password,
            'confirm_password': self.test_password,
        }, follow=True)
        self.assertRedirects(response, f"{self.landing_url}?tab=signup")
        messages = list(response.context['messages'])
        self.assertTrue(any("already exists" in str(m) for m in messages))

    def test_user_login_success(self):
        User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        
        # Test case-insensitivity in email login
        response = self.client.post(self.login_url, {
            'email': "ALEX@Example.com",
            'password': self.test_password,
        }, follow=True)
        
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_user_login_invalid_password(self):
        User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        
        response = self.client.post(self.login_url, {
            'email': self.test_email,
            'password': "WrongPassword!",
        }, follow=True)
        self.assertRedirects(response, f"{self.landing_url}?tab=signin")
        messages = list(response.context['messages'])
        self.assertTrue(any("Invalid email or password" in str(m) for m in messages))
        # Ensure email is preserved for UX
        self.assertEqual(response.context['saved_email'], self.test_email)

    def test_user_login_deactivated_account(self):
        user = User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        user.is_active = False
        user.save()

        response = self.client.post(self.login_url, {
            'email': self.test_email,
            'password': self.test_password,
        }, follow=True)
        self.assertRedirects(response, f"{self.landing_url}?tab=signin")
        messages = list(response.context['messages'])
        self.assertTrue(any("deactivated" in str(m) for m in messages))

    def test_open_redirect_protection_on_login(self):
        User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        
        # Malicious external redirect attempt
        response = self.client.post(f"{self.login_url}?next=https://evil.com", {
            'email': self.test_email,
            'password': self.test_password,
        }, follow=False)
        
        # Should redirect to dashboard, rejecting external URL
        self.assertRedirects(response, self.dashboard_url)

    def test_user_logout(self):
        user = User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        self.client.force_login(user)
        
        response = self.client.get(self.logout_url, follow=True)
        self.assertRedirects(response, self.landing_url)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_dashboard_requires_authentication(self):
        response = self.client.get(self.dashboard_url)
        # Should redirect to login with next parameter
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_dashboard_accessible_when_authenticated(self):
        user = User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        self.client.force_login(user)
        
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, self.test_name)
        self.assertIn("Start Revision", response.content.decode())
        self.assertIn("Recall Performance", response.content.decode())
        self.assertContains(response, "Two Sum")

    def test_authenticated_user_redirected_from_landing(self):
        user = User.objects.create_user(email=self.test_email, password=self.test_password, name=self.test_name)
        self.client.force_login(user)

        response = self.client.get(self.landing_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.dashboard_url)

    def test_landing_page_never_cache_headers(self):
        response = self.client.get(self.landing_url)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)

