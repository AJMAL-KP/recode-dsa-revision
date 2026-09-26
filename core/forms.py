from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class EmailRegistrationForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'alex@example.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Choose a secure password',
        })
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Confirm your password',
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        if password:
            validate_password(password)

        return cleaned_data

    def save(self):
        email = self.cleaned_data['email']
        password = self.cleaned_data['password']
        user = User.objects.create_user(username=email, email=email, password=password)
        return user


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'alex@example.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Enter your password',
        })
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email', '').strip().lower()
        password = cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Invalid email or password. Please try again.")
        return cleaned_data

    def get_user(self):
        return self.user_cache
