from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class EmailRegistrationForm(forms.Form):
    """
    Form for registering a new user using their email address.
    A display name is collected strictly for visual/greeting purposes.
    """
    name = forms.CharField(
        label="Full Name",
        max_length=150,
        required=True,
        error_messages={
            'required': 'Please enter your name.',
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Alex Morgan',
            'autocomplete': 'name',
        })
    )
    email = forms.EmailField(
        label="Email Address",
        max_length=255,
        widget=forms.EmailInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'alex@example.com',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        label="Password",
        min_length=8,
        error_messages={
            'required': 'Password is required.',
            'min_length': 'Password must be at least 8 characters long.',
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Choose a secure password (min 8 chars)',
            'autocomplete': 'new-password',
        })
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        min_length=8,
        error_messages={
            'required': 'Please confirm your password.',
            'min_length': 'Password must be at least 8 characters long.',
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
        })
    )

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Please enter your name.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("Email address is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        email = cleaned_data.get('email')
        name = cleaned_data.get('name')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        if password:
            # Build mock user instance so UserAttributeSimilarityValidator can compare against email and name
            temp_user = User(email=email or '', name=name or '')
            try:
                validate_password(password, user=temp_user)
            except ValidationError as error:
                self.add_error('password', error)

        return cleaned_data

    def save(self):
        name = self.cleaned_data.get('name', '')
        email = self.cleaned_data['email']
        password = self.cleaned_data['password']
        user = User.objects.create_user(email=email, password=password, name=name)
        return user


class EmailLoginForm(forms.Form):
    """Form for authenticating an existing user using email address and password."""
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'alex@example.com',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
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
                # Check if account exists but is deactivated
                existing_user = User.objects.filter(email__iexact=email).first()
                if existing_user and not existing_user.is_active:
                    raise forms.ValidationError("This account has been deactivated. Please contact support.")
                raise forms.ValidationError("Invalid email or password. Please try again.")
        return cleaned_data

    def get_user(self):
        return self.user_cache
