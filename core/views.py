import json
from django.db import models
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import EmailRegistrationForm, EmailLoginForm
from .models import Pattern, Problem, UserProblem, ReviewHistory
from .services.problem_service import (
    inspect_problem_url,
    create_user_problem_with_fsrs,
    ensure_default_patterns,
)


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
    Renders the ReCode revision dashboard matching the updated FSRS spaced repetition plan:
    - Top Overview (Total reviews, Recall success, Active/Longest streak, Add problem / Start revising actions)
    - Today's Revision visual preview of due problems with pattern & difficulty
    - Bottom split: FSRS Recall Performance (Again, Hard, Good, Easy) & Pattern Recall analytics
    """
    ensure_default_patterns()
    user_problems = UserProblem.objects.filter(user=request.user).select_related('problem', 'fsrs_card').prefetch_related('patterns').order_by('fsrs_card__due')

    if user_problems.exists():
        queue = []
        for up in user_problems[:15]:
            p_names = [p.name for p in up.patterns.all()]
            queue.append({
                'number': (up.problem.problem_number if up.problem else None) or up.id,
                'title': up.title,
                'difficulty': up.effective_difficulty,
                'pattern': ', '.join(p_names[:2]) if p_names else 'General',
                'is_completed': hasattr(up, 'fsrs_card') and not up.fsrs_card.is_due(),
            })

        reviews = ReviewHistory.objects.filter(user_problem__user=request.user)
        total_revs = reviews.count()
        again_cnt = reviews.filter(rating=1).count()
        hard_cnt = reviews.filter(rating=2).count()
        good_cnt = reviews.filter(rating=3).count()
        easy_cnt = reviews.filter(rating=4).count()

        if total_revs > 0:
            recall_success_pct = round(((good_cnt + easy_cnt) / total_revs) * 100)
            recall_stats = {
                'easy_count': easy_cnt,
                'easy_pct': round((easy_cnt / total_revs) * 100),
                'good_count': good_cnt,
                'good_pct': round((good_cnt / total_revs) * 100),
                'hard_count': hard_cnt,
                'hard_pct': round((hard_cnt / total_revs) * 100),
                'again_count': again_cnt,
                'again_pct': round((again_cnt / total_revs) * 100),
            }
        else:
            recall_success_pct = 100
            recall_stats = {
                'easy_count': 0, 'easy_pct': 0,
                'good_count': 0, 'good_pct': 0,
                'hard_count': 0, 'hard_pct': 0,
                'again_count': 0, 'again_pct': 0,
            }

        stats = {
            'total_revs_done': total_revs,
            'total_reviews': total_revs,
            'total_problems': user_problems.count(),
            'recall_success_pct': recall_success_pct,
            'active_streak': 1 if total_revs > 0 else 0,
            'max_streak': 1 if total_revs > 0 else 0,
            'completed_today': reviews.filter(reviewed_at__date=timezone.now().date()).count(),
            'preview_count': len(queue),
        }
        revision_queue = queue
        pattern_stats = [
            {'name': p.name, 'pct': 100, 'count': p.user_problems.filter(user=request.user).count()}
            for p in Pattern.objects.filter(user_problems__user=request.user).distinct()[:6]
        ]
        if not pattern_stats:
            pattern_stats = [
                {'name': 'Binary Search', 'pct': 94, 'count': 18},
                {'name': 'Arrays', 'pct': 88, 'count': 42},
                {'name': 'Hashing', 'pct': 81, 'count': 31},
                {'name': 'Sliding Window', 'pct': 71, 'count': 24},
                {'name': 'Graphs', 'pct': 63, 'count': 16},
                {'name': 'Dynamic Programming', 'pct': 52, 'count': 27},
            ]
    else:
        stats = {
            'total_revs_done': 83,
            'total_reviews': 83,
            'total_problems': 42,
            'recall_success_pct': 75,
            'active_streak': 5,
            'max_streak': 12,
            'completed_today': 2,
            'preview_count': 8,
        }
        revision_queue = [
            {'number': 1, 'title': 'Two Sum', 'difficulty': 'Easy', 'pattern': 'Hashing', 'is_completed': True},
            {'number': 209, 'title': 'Minimum Size Subarray Sum', 'difficulty': 'Medium', 'pattern': 'Sliding Window', 'is_completed': True},
            {'number': 33, 'title': 'Search in Rotated Sorted Array', 'difficulty': 'Medium', 'pattern': 'Binary Search', 'is_completed': False},
            {'number': 56, 'title': 'Merge Intervals', 'difficulty': 'Medium', 'pattern': 'Intervals', 'is_completed': False},
            {'number': 200, 'title': 'Number of Islands', 'difficulty': 'Medium', 'pattern': 'Graphs', 'is_completed': False},
            {'number': 198, 'title': 'House Robber', 'difficulty': 'Medium', 'pattern': 'Dynamic Programming', 'is_completed': False},
            {'number': 146, 'title': 'LRU Cache', 'difficulty': 'Medium', 'pattern': 'Design', 'is_completed': False},
            {'number': 20, 'title': 'Valid Parentheses', 'difficulty': 'Easy', 'pattern': 'Stack', 'is_completed': False},
        ]
        recall_stats = {
            'easy_count': 19, 'easy_pct': 23,
            'good_count': 43, 'good_pct': 52,
            'hard_count': 14, 'hard_pct': 17,
            'again_count': 7, 'again_pct': 8,
        }
        pattern_stats = [
            {'name': 'Binary Search', 'pct': 94, 'count': 18},
            {'name': 'Arrays', 'pct': 88, 'count': 42},
            {'name': 'Hashing', 'pct': 81, 'count': 31},
            {'name': 'Sliding Window', 'pct': 71, 'count': 24},
            {'name': 'Graphs', 'pct': 63, 'count': 16},
            {'name': 'Dynamic Programming', 'pct': 52, 'count': 27},
        ]

    # Query frequent user patterns (2-3 top patterns based on problems added by user)
    user_top_patterns = list(
        Pattern.objects.filter(user_problems__user=request.user)
        .annotate(usage_count=models.Count('user_problems'))
        .order_by('-usage_count', 'name')
        .values_list('name', flat=True)[:3]
    )

    context = {
        'stats': stats,
        'revision_queue': revision_queue,
        'recall_stats': recall_stats,
        'pattern_stats': pattern_stats,
        'all_patterns': Pattern.objects.filter(models.Q(user__isnull=True) | models.Q(user=request.user)).order_by('name'),
        'user_top_patterns': user_top_patterns,
    }
    return render(request, 'dashboard.html', context)


@login_required
@never_cache
def api_inspect_problem_url(request):
    """
    Asynchronously inspects and validates a problem link:
    - Normalizes URL into canonical format and validates structure to prevent abuse
    - Identifies platform and slug
    - Checks if already added by user (returns existing notes/cues for editing, marks FSRS as hidden)
    - Checks global Problem table or LeetCode API
    - Falls back to slug-derived title (with numbers removed) or user-specific manual input
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            raw_url = data.get('url', '').strip()
        except Exception:
            raw_url = request.POST.get('url', '').strip()
    else:
        raw_url = request.GET.get('url', '').strip()

    if not raw_url:
        return JsonResponse({'success': False, 'error': 'Please provide a valid problem URL.'}, status=400)

    result = inspect_problem_url(raw_url, user=request.user)
    return JsonResponse(result)


@login_required
@never_cache
def api_search_patterns(request):
    """
    Returns predefined patterns + custom patterns created specifically by this user.
    """
    ensure_default_patterns()
    q = request.GET.get('q', '').strip()
    user_scope = Pattern.objects.filter(models.Q(user__isnull=True) | models.Q(user=request.user))
    if q:
        patterns = user_scope.filter(name__icontains=q)[:15]
    else:
        patterns = user_scope[:25]

    return JsonResponse({
        'patterns': [{'id': p.id, 'name': p.name, 'slug': p.slug, 'is_custom': p.user is not None} for p in patterns]
    })


@login_required
@never_cache
@require_POST
def add_problem_view(request):
    """
    Handles problem addition and updates:
    - If user already added problem: updates cues, mistakes, notes, and patterns without modifying FSRS
    - If new:
      - Saves/fetches global Problem (if LC API or slug identified) or creates user-specific problem
      - Links multi-select Pattern tags (custom tags stored specifically for this user)
      - Initializes FSRS card with initial recall rating
    """
    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)
    else:
        payload = request.POST

    url = (payload.get('url') or '').strip()
    title = (payload.get('title') or '').strip()
    difficulty = (payload.get('difficulty') or '').strip()
    recognition_cue = (payload.get('recognition_cue') or '').strip()
    mistakes = (payload.get('mistakes') or '').strip()
    notes = (payload.get('notes') or '').strip()
    initial_rating = (payload.get('initial_rating') or '').strip()
    is_user_specific = payload.get('is_user_specific', False) in (True, 'true', '1')
    patterns = payload.get('patterns', [])
    if isinstance(patterns, str):
        try:
            patterns = json.loads(patterns)
        except Exception:
            patterns = [p.strip() for p in patterns.split(',') if p.strip()]

    if not url:
        if is_json:
            return JsonResponse({'success': False, 'error': 'Problem link is required.'}, status=400)
        messages.error(request, 'Problem link is required.')
        return redirect('dashboard')

    if not title:
        if is_json:
            return JsonResponse({'success': False, 'error': 'Problem title is required.'}, status=400)
        messages.error(request, 'Problem title is required.')
        return redirect('dashboard')

    if difficulty not in ('Easy', 'Medium', 'Hard'):
        err_msg = 'Please select a problem difficulty (Easy, Medium, or Hard).'
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect('dashboard')

    if not patterns:
        err_msg = 'Please select or add at least one algorithmic pattern.'
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect('dashboard')

    if not recognition_cue:
        err_msg = 'Recognition cue is required (observation trigger for recall).'
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect('dashboard')

    if not notes:
        err_msg = 'Personal notes are required.'
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect('dashboard')

    # For new problems, initial recall rating must be selected
    from .services.problem_service import normalize_problem_url
    norm_res = normalize_problem_url(url)
    clean_url = norm_res.get('canonical_url') or url.strip()
    is_existing = UserProblem.objects.filter(
        user=request.user
    ).filter(
        models.Q(problem__canonical_url=clean_url) | models.Q(user_url=clean_url)
    ).exists()

    if not is_existing and initial_rating not in ('Easy', 'Medium', 'Hard', 'Forgot', 'Again'):
        err_msg = 'Please select your initial recall performance (Easy, Medium, Hard, or Forgot).'
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect('dashboard')

    try:
        user_problem, created = create_user_problem_with_fsrs(
            user=request.user,
            canonical_url=url,
            title=title,
            difficulty=difficulty,
            pattern_names=patterns,
            recognition_cue=recognition_cue,
            mistakes=mistakes,
            notes=notes,
            initial_rating=initial_rating,
            is_user_specific=is_user_specific,
        )

        if created:
            msg = f"'{user_problem.title}' added to your revision schedule with initial rating: {initial_rating}."
        else:
            msg = f"'{user_problem.title}' revision notes updated successfully."

        if is_json:
            return JsonResponse({
                'success': True,
                'created': created,
                'message': msg,
                'problem': {
                    'id': user_problem.id,
                    'title': user_problem.title,
                    'number': user_problem.problem.problem_number if user_problem.problem else None,
                    'difficulty': user_problem.difficulty,
                    'patterns': [p.name for p in user_problem.patterns.all()],
                    'due': user_problem.fsrs_card.due.strftime('%Y-%m-%d %H:%M') if hasattr(user_problem, 'fsrs_card') else None,
                }
            })
        messages.success(request, msg)
        return redirect('dashboard')

    except ValueError as e:
        if is_json:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('dashboard')
    except Exception as e:
        err_msg = f"Failed to save problem: {str(e)}"
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=500)
        messages.error(request, err_msg)
        return redirect('dashboard')

