from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import EmailRegistrationForm, EmailLoginForm


@never_cache
def landing(request):
    """Render the public landing page with signin/signup tabs."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    tab = request.GET.get('tab', 'signin')

    # Retrieve preserved form inputs from session (if previous submission had validation errors)
    auth_data = request.session.pop('auth_form_data', None)
    initial_login = {}
    initial_register = {}
    auth_errors = {}

    if auth_data:
        auth_errors = auth_data.get('errors', {})
        if auth_data.get('type') == 'signin':
            initial_login = {'email': auth_data.get('email', '')}
        elif auth_data.get('type') == 'signup':
            initial_register = {
                'name': auth_data.get('name', ''),
                'email': auth_data.get('email', ''),
            }

    login_form = EmailLoginForm(request=request, initial=initial_login)
    register_form = EmailRegistrationForm(initial=initial_register)

    return render(request, 'landing.html', {
        'active_tab': tab,
        'login_form': login_form,
        'register_form': register_form,
        'saved_email': initial_login.get('email') or initial_register.get('email', ''),
        'saved_name': initial_register.get('name', ''),
        'auth_errors': auth_errors,
    })


@never_cache
def register_view(request):
    """Handle new user registration using email and optional display name."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = EmailRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='core.backends.EmailBackend')
            greeting_name = user.name or user.email
            messages.success(request, f"Welcome to ReCode, {greeting_name}!")
            return redirect('dashboard')
        else:
            first_err = None
            if form.non_field_errors():
                first_err = form.non_field_errors()[0]
            else:
                for field in ['name', 'email', 'password', 'confirm_password']:
                    if field in form.errors and form.errors[field]:
                        first_err = form.errors[field][0]
                        break
            messages.error(request, first_err or "Please correct the errors below to continue.")
            # Keep user inputs (name, email) in session so they don't have to retype.
            # Passwords are NEVER preserved for security and privacy.
            field_errors = {field: str(errs[0]) for field, errs in form.errors.items()}
            request.session['auth_form_data'] = {
                'type': 'signup',
                'name': request.POST.get('name', '').strip(),
                'email': request.POST.get('email', '').strip(),
                'errors': field_errors,
            }
            return redirect(f"{reverse('landing')}?tab=signup")
    return redirect(f"{reverse('landing')}?tab=signup")


@never_cache
def login_view(request):
    """Handle user login using email and password with open-redirect protection."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = EmailLoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='core.backends.EmailBackend')
            messages.success(request, f"Welcome back, {user.get_short_name()}!")
            
            # Secure redirect validation
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect('dashboard')
        else:
            first_err = "Invalid email or password. Please try again."
            if form.non_field_errors():
                first_err = form.non_field_errors()[0]
            elif form.errors.get('email'):
                first_err = form.errors['email'][0]
            elif form.errors.get('password'):
                first_err = form.errors['password'][0]
            messages.error(request, first_err)
            # Keep email input in session so user doesn't have to retype.
            # Password is NEVER preserved.
            request.session['auth_form_data'] = {
                'type': 'signin',
                'email': request.POST.get('email', '').strip(),
                'errors': {'email': first_err},
            }
            return redirect(f"{reverse('landing')}?tab=signin")
    return redirect(f"{reverse('landing')}?tab=signin")


@never_cache
def logout_view(request):
    """Log the user out and redirect to landing page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('landing')


@login_required
@never_cache
def dashboard_view(request):
    """
    Renders the ReCode revision dashboard matching the minimalist layout:
    - Top Overview (Total revs, Recall success, Active/Max streak, Add problem / Start rev actions)
    - Single unified Start Revision queue section with daily quota selector and strikethrough for revised problems
    - Bottom split: Recall Performance & Pattern Recall analytics
    """
    context = {
        'stats': {
            'total_revs_done': 83,
            'total_revs_target': 200,
            'recall_success_pct': 76,
            'active_streak': 5,
            'max_streak': 12,
            'daily_quota': 10,
            'completed_today': 2,
            'total_today': 8,
            'pending_today': 6,
        },
        'revision_queue': [
            {
                'number': 1,
                'title': 'Two Sum',
                'difficulty': 'Easy',
                'level': 2,
                'is_completed': True,
            },
            {
                'number': 209,
                'title': 'Minimum Size Subarray Sum',
                'difficulty': 'Medium',
                'level': 1,
                'is_completed': True,
            },
            {
                'number': 33,
                'title': 'Search in Rotated Sorted Array',
                'difficulty': 'Medium',
                'level': 3,
                'is_completed': False,
            },
            {
                'number': 56,
                'title': 'Merge Intervals',
                'difficulty': 'Medium',
                'level': 2,
                'is_completed': False,
            },
            {
                'number': 200,
                'title': 'Number of Islands',
                'difficulty': 'Medium',
                'level': 1,
                'is_completed': False,
            },
            {
                'number': 198,
                'title': 'House Robber',
                'difficulty': 'Medium',
                'level': 0,
                'is_completed': False,
            },
            {
                'number': 20,
                'title': 'Valid Parentheses',
                'difficulty': 'Easy',
                'level': 4,
                'is_completed': False,
            },
            {
                'number': 15,
                'title': '3Sum',
                'difficulty': 'Medium',
                'level': 2,
                'is_completed': False,
            },
        ],
        'recall_stats': {
            'independent_count': 63,
            'independent_pct': 76,
            'hint_count': 14,
            'hint_pct': 17,
            'forgot_count': 6,
            'forgot_pct': 7,
        },
        'pattern_stats': [
            {'name': 'Binary Search', 'pct': 92, 'count': 15},
            {'name': 'Arrays & Hashing', 'pct': 84, 'count': 28},
            {'name': 'Two Pointers', 'pct': 80, 'count': 18},
            {'name': 'Graphs & Trees', 'pct': 58, 'count': 10},
            {'name': 'Dynamic Programming', 'pct': 48, 'count': 12},
        ],
    }
    return render(request, 'dashboard.html', context)
