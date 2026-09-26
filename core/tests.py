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
        
    def test_landing_page_accessible(self):
        response = self.client.get(self.landing_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ReCode")

    def test_user_registration_success(self):
        response = self.client.post(self.register_url, {
            'email': self.test_email,
            'password': self.test_password,
            'confirm_password': self.test_password,
        }, follow=True)
        
        self.assertTrue(User.objects.filter(email=self.test_email).exists())
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_registration_password_mismatch(self):
        response = self.client.post(self.register_url, {
            'email': self.test_email,
            'password': self.test_password,
            'confirm_password': "DifferentPassword123!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email=self.test_email).exists())
        self.assertFormError(response.context['form'], 'confirm_password', "Passwords do not match.")

    def test_registration_duplicate_email(self):
        User.objects.create_user(username=self.test_email, email=self.test_email, password=self.test_password)
        response = self.client.post(self.register_url, {
            'email': self.test_email,
            'password': self.test_password,
            'confirm_password': self.test_password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', "An account with this email already exists.")

    def test_user_login_success(self):
        User.objects.create_user(username=self.test_email, email=self.test_email, password=self.test_password)
        
        # Test case-insensitivity in email login
        response = self.client.post(self.login_url, {
            'email': "ALEX@Example.com",
            'password': self.test_password,
        }, follow=True)
        
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_user_login_invalid_password(self):
        User.objects.create_user(username=self.test_email, email=self.test_email, password=self.test_password)
        
        response = self.client.post(self.login_url, {
            'email': self.test_email,
            'password': "WrongPassword!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], None, "Invalid email or password. Please try again.")

    def test_user_logout(self):
        user = User.objects.create_user(username=self.test_email, email=self.test_email, password=self.test_password)
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
        user = User.objects.create_user(username=self.test_email, email=self.test_email, password=self.test_password)
        self.client.force_login(user)
        
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertIn("Start Revision", response.content.decode())
        self.assertIn("Recall Performance", response.content.decode())
        self.assertContains(response, "Two Sum")
