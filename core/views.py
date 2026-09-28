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

    queue = []
    for up in user_problems[:25]:
        p_names = [p.name for p in up.patterns.all()]
        queue.append({
            'number': (up.problem.problem_number if up.problem else None) or up.id,
            'title': up.title,
            'difficulty': up.effective_difficulty,
            'pattern': ', '.join(p_names[:2]) if p_names else 'General',
            'pattern_names': p_names,
            'pattern_names_csv': ','.join(p_names),
            'is_completed': hasattr(up, 'fsrs_card') and not up.fsrs_card.is_due(),
        })

    from .services.analytics_service import (
        get_dashboard_analytics,
        get_most_forgotten_problems,
        get_forgotten_stats,
        get_revision_heatmap_data,
    )
    stats, recall_stats = get_dashboard_analytics(request.user)
    stats['preview_count'] = len(queue)
    stats['completed_today'] = ReviewHistory.objects.filter(
        user_problem__user=request.user,
        reviewed_at__date=timezone.localdate()
    ).count()

    most_forgotten = get_most_forgotten_problems(request.user, limit=5)
    forgotten_stats = get_forgotten_stats(request.user)
    heatmap_data = get_revision_heatmap_data(request.user, months=12)

    revision_queue = queue

    # Pattern recall analytics for user using weighted retention across all 4 FSRS states
    user_patterns = Pattern.objects.filter(user_problems__user=request.user).distinct()
    all_pattern_stats = []
    for p in user_patterns:
        p_revs = ReviewHistory.objects.filter(user_problem__user=request.user, user_problem__patterns=p)
        tot = p_revs.count()
        if tot > 0:
            easy_cnt = p_revs.filter(rating=4).count()
            good_cnt = p_revs.filter(rating=3).count()
            hard_cnt = p_revs.filter(rating=2).count()
            again_cnt = p_revs.filter(rating=1).count()
            pct = round(((easy_cnt * 100) + (good_cnt * 75) + (hard_cnt * 50) + (again_cnt * 0)) / tot)
        else:
            pct = 100
        prob_count = p.user_problems.filter(user=request.user).count()
        all_pattern_stats.append({
            'name': p.name,
            'pct': pct,
            'count': prob_count,
            'revs_count': tot,
        })

    if not all_pattern_stats:
        top_patterns = [
            {'name': 'Binary Search', 'pct': 92, 'count': 4, 'revs_count': 12},
            {'name': 'Two Pointers', 'pct': 88, 'count': 6, 'revs_count': 18},
            {'name': 'Sliding Window', 'pct': 82, 'count': 5, 'revs_count': 14},
            {'name': 'Hashing', 'pct': 78, 'count': 8, 'revs_count': 20},
            {'name': 'Trees', 'pct': 74, 'count': 7, 'revs_count': 16},
        ]
        weak_patterns = [
            {'name': 'Dynamic Programming', 'pct': 48, 'count': 7, 'revs_count': 15},
            {'name': 'Graphs', 'pct': 56, 'count': 4, 'revs_count': 9},
            {'name': 'Trie', 'pct': 62, 'count': 3, 'revs_count': 6},
            {'name': 'Backtracking', 'pct': 68, 'count': 5, 'revs_count': 11},
            {'name': 'Bit Manipulation', 'pct': 70, 'count': 3, 'revs_count': 5},
        ]
        total_patterns_count = 0
        avg_pattern_retention = 85
        weak_patterns_count = 0
    else:
        top_patterns = sorted(all_pattern_stats, key=lambda x: (-x['pct'], -x['count']))[:5]
        weak_patterns = sorted(all_pattern_stats, key=lambda x: (x['pct'], -x['count']))[:5]
        total_patterns_count = len(all_pattern_stats)
        avg_pattern_retention = round(sum(p['pct'] for p in all_pattern_stats) / total_patterns_count)
        weak_patterns_count = sum(1 for p in all_pattern_stats if p['pct'] < 70)

    # Query frequent user patterns (2-3 top patterns based on problems added by user)
    user_top_patterns = list(
        Pattern.objects.filter(user_problems__user=request.user)
        .annotate(usage_count=models.Count('user_problems'))
        .order_by('-usage_count', 'name')
        .values_list('name', flat=True)[:3]
    )

    user_frequency_patterns = list(
        Pattern.objects.annotate(
            user_usage_count=models.Count(
                'user_problems',
                filter=models.Q(user_problems__user=request.user)
            )
        )
        .filter(models.Q(user__isnull=True) | models.Q(user=request.user))
        .order_by('-user_usage_count', 'name')
    )

    context = {
        'stats': stats,
        'revision_queue': revision_queue,
        'recall_stats': recall_stats,
        'pattern_stats': top_patterns,
        'top_patterns': top_patterns,
        'weak_patterns': weak_patterns,
        'total_patterns_count': total_patterns_count,
        'avg_pattern_retention': avg_pattern_retention,
        'weak_patterns_count': weak_patterns_count,
        'all_patterns': user_frequency_patterns,
        'user_top_patterns': user_top_patterns,
        'most_forgotten': most_forgotten,
        'forgotten_stats': forgotten_stats,
        'heatmap_data': heatmap_data,
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

    if not is_existing and initial_rating not in ('Easy', 'Good', 'Hard', 'Forgot', 'Again', 'Medium'):
        err_msg = 'Please select your initial recall performance (Forgot, Hard, Good, or Easy).'
        if is_json:
            return JsonResponse({'success': False, 'error': err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect('dashboard')

    if initial_rating == 'Medium':
        initial_rating = 'Good'

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

