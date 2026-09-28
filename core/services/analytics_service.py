"""
Analytics and streak calculation service for ReCode.
Provides robust calculation of:
- Total problems added / solved
- Total revisions completed
- Active streak (consecutive days of active recall revision)
- Longest / maximum streak recorded
- Total distinct revision days
- Recall performance distribution (Forgot, Hard, Good, Easy)
- Rocket streak milestone targets and track progress percentage
"""

import calendar
import datetime
from zoneinfo import ZoneInfo
from django.db import models
from django.utils import timezone
from core.models import UserProblem, ReviewHistory, Pattern

IST = ZoneInfo("Asia/Kolkata")


def calculate_user_streak(user):
    """
    Calculates consecutive active revision days from ReviewHistory in IST.
    - An active streak is alive if the user revised today OR yesterday.
    - If neither, active streak is 0.
    - Longest streak is the maximum sequence of consecutive calendar days ever recorded.
    """
    if not user or not user.is_authenticated:
        return {
            'active_streak': 0,
            'max_streak': 0,
            'total_revision_days': 0,
            'reviewed_today': False,
        }

    # Extract distinct calendar dates in IST for this user's reviews
    reviews_qs = (
        ReviewHistory.objects.filter(user_problem__user=user)
        .values_list('reviewed_at', flat=True)
    )
    review_dates = set()
    for dt in reviews_qs:
        if dt:
            ist_d = dt.astimezone(IST).date() if timezone.is_aware(dt) else dt.date()
            review_dates.add(ist_d)

    total_revision_days = len(review_dates)

    if not review_dates:
        return {
            'active_streak': 0,
            'max_streak': 0,
            'total_revision_days': 0,
            'reviewed_today': False,
        }

    today = datetime.datetime.now(IST).date()
    yesterday = today - datetime.timedelta(days=1)
    reviewed_today = today in review_dates

    # 1. Active Streak calculation
    active_streak = 0
    if reviewed_today:
        check_date = today
        while check_date in review_dates:
            active_streak += 1
            check_date -= datetime.timedelta(days=1)
    elif yesterday in review_dates:
        # User has not revised yet today, but streak remains intact from yesterday
        check_date = yesterday
        while check_date in review_dates:
            active_streak += 1
            check_date -= datetime.timedelta(days=1)
    else:
        active_streak = 0

    # 2. Max (Longest) Streak calculation
    sorted_dates = sorted(review_dates)
    max_streak = 1
    current_run = 1

    for i in range(1, len(sorted_dates)):
        prev_d = sorted_dates[i - 1]
        curr_d = sorted_dates[i]
        diff = (curr_d - prev_d).days
        if diff == 1:
            current_run += 1
            if current_run > max_streak:
                max_streak = current_run
        elif diff > 1:
            current_run = 1

    max_streak = max(max_streak, active_streak)

    return {
        'active_streak': active_streak,
        'max_streak': max_streak,
        'total_revision_days': total_revision_days,
        'reviewed_today': reviewed_today,
    }


def get_rocket_streak_milestones(active_streak):
    """
    Computes fixed-distance rocket streak track percentage across 15 days.
    - Streak 0: Not started (rocket_pct = 0, has_flame = False, is_max = False)
    - Streak 1..14: Rocket ignites and scales visibly across track from 8% to ~92%
    - Streak >= 15: Rocket anchors at 100% of inner track and flies in place with continuous flame
    """
    max_days = 15
    if active_streak <= 0:
        rocket_pct = 0
        has_flame = False
        is_max = False
    elif active_streak >= max_days:
        rocket_pct = 100
        has_flame = True
        is_max = True
    else:
        # Scale smoothly across days 1 to 14
        ratio = (active_streak - 1) / (max_days - 1)
        rocket_pct = round(8 + (ratio * 84))
        has_flame = True
        is_max = False

    return {
        'max_days': max_days,
        'rocket_pct': rocket_pct,
        'has_flame': has_flame,
        'is_max': is_max,
    }


def get_dashboard_analytics(user):
    """
    Compiles complete dashboard metrics, recall breakdown, and rocket streak state.
    """
    if not user or not user.is_authenticated:
        # Default mock / preview state for unauthenticated preview
        return _get_preview_analytics()

    user_problems = UserProblem.objects.filter(user=user)
    reviews = ReviewHistory.objects.filter(user_problem__user=user)

    total_problems = user_problems.count()
    total_revs = reviews.count()

    # Recall ratings:
    # 1: Again / Forgot (0% weight)
    # 2: Hard (50% weight)
    # 3: Good (75% weight)
    # 4: Easy (100% weight)
    again_cnt = reviews.filter(rating=1).count()
    hard_cnt = reviews.filter(rating=2).count()
    good_cnt = reviews.filter(rating=3).count()
    easy_cnt = reviews.filter(rating=4).count()

    if total_revs > 0:
        # Memory retention based on all states: Easy (100%), Good (75%), Hard (50%), Forgot (0%)
        weighted_score = (easy_cnt * 100) + (good_cnt * 75) + (hard_cnt * 50) + (again_cnt * 0)
        recall_success_pct = round(weighted_score / total_revs)

        counts = [
            ('Easy', easy_cnt, round((easy_cnt / total_revs) * 100)),
            ('Good', good_cnt, round((good_cnt / total_revs) * 100)),
            ('Hard', hard_cnt, round((hard_cnt / total_revs) * 100)),
            ('Forgot', again_cnt, round((again_cnt / total_revs) * 100)),
        ]
        counts.sort(key=lambda x: -x[1])
        dominant_state, dominant_count, dominant_pct = counts[0]

        high_impact_pct = round(((easy_cnt + good_cnt) / total_revs) * 100)
        low_impact_pct = round(((hard_cnt + again_cnt) / total_revs) * 100)

        if recall_success_pct >= 85:
            recall_grade = 'Optimal'
            recall_grade_badge = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
        elif recall_success_pct >= 70:
            recall_grade = 'Strong'
            recall_grade_badge = 'bg-lime-500/20 text-lime-400 border-lime-500/30'
        elif recall_success_pct >= 50:
            recall_grade = 'Moderate'
            recall_grade_badge = 'bg-amber-500/20 text-amber-400 border-amber-500/30'
        else:
            recall_grade = 'Needs Focus'
            recall_grade_badge = 'bg-rose-500/20 text-rose-400 border-rose-500/30'

        gauge_dashoffset = round(276.46 * (1 - (recall_success_pct / 100)), 1)

        recall_stats = {
            'easy_count': easy_cnt,
            'easy_pct': round((easy_cnt / total_revs) * 100),
            'good_count': good_cnt,
            'good_pct': round((good_cnt / total_revs) * 100),
            'hard_count': hard_cnt,
            'hard_pct': round((hard_cnt / total_revs) * 100),
            'again_count': again_cnt,
            'again_pct': round((again_cnt / total_revs) * 100),
            'dominant_state': dominant_state,
            'dominant_pct': dominant_pct,
            'high_impact_pct': high_impact_pct,
            'low_impact_pct': low_impact_pct,
            'recall_grade': recall_grade,
            'recall_grade_badge': recall_grade_badge,
            'gauge_dashoffset': gauge_dashoffset,
        }
    else:
        recall_success_pct = 0
        recall_stats = {
            'easy_count': 0, 'easy_pct': 0,
            'good_count': 0, 'good_pct': 0,
            'hard_count': 0, 'hard_pct': 0,
            'again_count': 0, 'again_pct': 0,
            'dominant_state': 'None',
            'dominant_pct': 0,
            'high_impact_pct': 0,
            'low_impact_pct': 0,
            'recall_grade': 'No Data',
            'recall_grade_badge': 'bg-slate-500/20 text-slate-400 border-slate-500/30',
            'gauge_dashoffset': 276.46,
        }

    # Streak calculations
    streak_data = calculate_user_streak(user)
    rocket_data = get_rocket_streak_milestones(streak_data['active_streak'])

    stats = {
        'total_problems': total_problems,
        'total_revs_done': total_revs,
        'total_reviews': total_revs,
        'recall_success_pct': recall_success_pct,
        'active_streak': streak_data['active_streak'],
        'max_streak': streak_data['max_streak'],
        'total_revision_days': streak_data['total_revision_days'],
        'reviewed_today': streak_data['reviewed_today'],
        'rocket': rocket_data,
    }

    return stats, recall_stats


def get_most_forgotten_problems(user, limit=5):
    """
    Returns top N problems most frequently rated 'Forgot' (rating=1) by this user.
    Each item contains problem number, title, difficulty, canonical_url, and forgot_count.
    Does not expose pattern to preserve active recall cues.
    """
    if not user or not user.is_authenticated:
        return []

    annotated_qs = (
        UserProblem.objects.filter(user=user)
        .annotate(
            forgot_count=models.Count('review_logs', filter=models.Q(review_logs__rating=1)),
            last_forgot_at=models.Max('review_logs__reviewed_at', filter=models.Q(review_logs__rating=1)),
            total_revs=models.Count('review_logs'),
        )
        .filter(forgot_count__gt=0)
        .select_related('problem')
        .order_by('-forgot_count', '-last_forgot_at')[:limit]
    )

    results = []
    for up in annotated_qs:
        results.append({
            'id': up.id,
            'title': up.title,
            'number': (up.problem.problem_number if up.problem else None) or up.id,
            'difficulty': up.effective_difficulty,
            'canonical_url': up.canonical_url or '#',
            'forgot_count': up.forgot_count,
            'total_revs': up.total_revs,
        })
    return results


def get_forgotten_stats(user):
    """
    Returns aggregate forgotten rating metrics for this user.
    """
    if not user or not user.is_authenticated:
        return {
            'total_forgot_ratings': 0,
            'distinct_forgot_problems': 0,
        }
    total_forgot_ratings = ReviewHistory.objects.filter(user_problem__user=user, rating=1).count()
    distinct_forgot_problems = UserProblem.objects.filter(user=user, review_logs__rating=1).distinct().count()
    return {
        'total_forgot_ratings': total_forgot_ratings,
        'distinct_forgot_problems': distinct_forgot_problems,
    }


def get_revision_heatmap_data(user, months=12):
    """
    Builds a 52-week (last 12 months) GitHub-style contribution heatmap for the user.
    Columns represent weeks (Mon-Sun), rows represent 7 days of the week.
    Returns:
    - weeks: list of 52 weeks, each containing 7 day objects
    - month_labels: list of {name, week_col} positioned above starting weeks without duplicate labels
    - total_reviews_year: total revisions within the 52-week window
    - active_days_year: distinct days with revisions in the 52-week window
    - max_day_reviews: highest revision count on a single day
    """
    today = datetime.datetime.now(IST).date()
    # Align to Monday 51 weeks before this week's Monday (total 52 weeks)
    start_monday = today - datetime.timedelta(days=today.weekday(), weeks=51)

    date_counts = {}
    if user and user.is_authenticated:
        reviews_qs = (
            ReviewHistory.objects.filter(user_problem__user=user)
            .values_list('reviewed_at', flat=True)
        )
        for dt in reviews_qs:
            if dt:
                ist_d = dt.astimezone(IST).date() if timezone.is_aware(dt) else dt.date()
                if start_monday <= ist_d <= today:
                    date_counts[ist_d] = date_counts.get(ist_d, 0) + 1

    total_reviews_year = sum(date_counts.values())
    active_days_year = len([c for c in date_counts.values() if c > 0])
    max_day_reviews = max(date_counts.values()) if date_counts else 0

    # Max streak: maximum consecutive days with >= 1 revision in the 52-week period
    max_streak = 0
    curr_streak = 0
    curr_d = start_monday
    while curr_d <= today:
        if date_counts.get(curr_d, 0) > 0:
            curr_streak += 1
            if curr_streak > max_streak:
                max_streak = curr_streak
        else:
            curr_streak = 0
        curr_d += datetime.timedelta(days=1)

    # 12 chronological months ending in current month for LeetCode month blocks
    month_pairs = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_pairs.append((y, m))

    months_data = []
    month_names = []
    for y, m in month_pairs:
        _, num_days = calendar.monthrange(y, m)
        month_name = datetime.date(y, m, 1).strftime('%b')
        month_names.append(month_name)
        first_day_date = datetime.date(y, m, 1)
        # Sunday=0, Monday=1, ..., Saturday=6
        first_day_dow = (first_day_date.weekday() + 1) % 7

        month_columns = []
        current_col = []

        # Empty slots before day 1
        for _ in range(first_day_dow):
            current_col.append(None)

        for day_num in range(1, num_days + 1):
            d = datetime.date(y, m, day_num)
            is_future = d > today
            cnt = date_counts.get(d, 0) if not is_future else 0

            if is_future or cnt == 0:
                level = 0
            elif cnt == 1:
                level = 1
            elif cnt <= 3:
                level = 2
            elif cnt <= 6:
                level = 3
            else:
                level = 4

            current_col.append({
                'day': day_num,
                'date': d.strftime('%Y-%m-%d'),
                'formatted_date': d.strftime('%b %d, %Y'),
                'count': cnt,
                'level': level,
                'is_future': is_future,
            })

            if len(current_col) == 7:
                # Dynamically include column only if it has past or current days
                if any(slot and not slot['is_future'] for slot in current_col):
                    month_columns.append(current_col)
                current_col = []

        if current_col:
            while len(current_col) < 7:
                current_col.append(None)
            if any(slot and not slot['is_future'] for slot in current_col):
                month_columns.append(current_col)

        if month_columns:
            months_data.append({
                'name': month_name,
                'year': y,
                'month': m,
                'columns': month_columns,
            })

    # Backward compatible month_labels for tests
    month_labels = []
    for idx, name in enumerate(month_names):
        col = 2.5 + (idx * 4.5)
        pct = round((col / 52.0) * 100, 3)
        month_labels.append({
            'name': name,
            'col': col,
            'pct': pct,
            'week_col': round(col),
            'is_first': (idx == 0),
            'is_last': (idx == 11),
        })

    weeks = []
    for w_idx in range(52):
        week_monday = start_monday + datetime.timedelta(weeks=w_idx)
        week_days = []

        for d_idx in range(7):
            d = week_monday + datetime.timedelta(days=d_idx)
            is_future = d > today
            count = date_counts.get(d, 0) if not is_future else 0

            # Level 0 to 4 calculation
            if is_future:
                level = 0
            elif count == 0:
                level = 0
            elif count == 1:
                level = 1
            elif count <= 3:
                level = 2
            elif count <= 6:
                level = 3
            else:
                level = 4

            week_days.append({
                'date': d.strftime('%Y-%m-%d'),
                'formatted_date': d.strftime('%b %d, %Y'),
                'count': count,
                'level': level,
                'is_future': is_future,
                'day_name': d.strftime('%a'),
            })

        weeks.append({
            'week_idx': w_idx,
            'days': week_days,
        })

    return {
        'weeks': weeks,
        'month_labels': month_labels,
        'months_data': months_data,
        'total_reviews_year': total_reviews_year,
        'active_days_year': active_days_year,
        'max_day_reviews': max_day_reviews,
        'max_streak': max_streak,
    }


def _get_preview_analytics():
    """Fallback analytics for demo/preview purposes."""
    rocket_data = get_rocket_streak_milestones(5)
    stats = {
        'total_problems': 42,
        'total_revs_done': 83,
        'total_reviews': 83,
        'recall_success_pct': 75,
        'active_streak': 5,
        'max_streak': 12,
        'total_revision_days': 19,
        'reviewed_today': True,
        'rocket': rocket_data,
    }
    recall_stats = {
        'easy_count': 19, 'easy_pct': 23,
        'good_count': 43, 'good_pct': 52,
        'hard_count': 14, 'hard_pct': 17,
        'again_count': 7, 'again_pct': 8,
        'dominant_state': 'Good',
        'dominant_pct': 52,
        'high_impact_pct': 75,
        'low_impact_pct': 25,
        'recall_grade': 'Strong',
        'recall_grade_badge': 'bg-lime-500/20 text-lime-400 border-lime-500/30',
        'gauge_dashoffset': 62.8,
    }
    return stats, recall_stats
