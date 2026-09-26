from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import EmailRegistrationForm, EmailLoginForm


def landing(request):
    """Render the public landing page."""
    return render(request, 'landing.html')


def register_view(request):
    """Handle new user registration using email."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = EmailRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='core.backends.EmailBackend')
            messages.success(request, f"Account created for {user.email}.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below to continue.")
    else:
        form = EmailRegistrationForm()
        
    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    """Handle user login using email."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = EmailLoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='core.backends.EmailBackend')
            messages.success(request, f"Signed in as {user.email}.")
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password. Please try again.")
    else:
        form = EmailLoginForm(request=request)
        
    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    """Log the user out and redirect to landing page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('landing')


@login_required
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
