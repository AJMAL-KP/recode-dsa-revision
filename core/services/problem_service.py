import re
import urllib.parse
import requests
from django.utils.text import slugify
from django.utils import timezone
from django.db import models
from fsrs import Scheduler, Card, Rating
from core.models import Problem, UserProblem, Pattern, FSRSCard, ReviewHistory

# Pre-seeded DSA Algorithmic Patterns
DEFAULT_PATTERNS = [
    "Two Pointers",
    "Sliding Window",
    "Fast & Slow Pointers",
    "Merge Intervals",
    "Cyclic Sort",
    "In-place Reversal of a LinkedList",
    "Tree Breadth First Search",
    "Tree Depth First Search",
    "Two Heaps",
    "Subsets",
    "Modified Binary Search",
    "Bitwise XOR",
    "Top 'K' Elements",
    "K-way Merge",
    "0/1 Knapsack",
    "Topological Sort",
    "Prefix Sum",
    "Monotonic Stack",
    "Union Find",
    "Dynamic Programming",
    "Trie",
    "Backtracking",
    "Greedy",
    "Binary Search Tree",
    "Graphs",
    "Hashing",
    "Stack",
    "Queue",
    "Heap / Priority Queue",
    "Linked List",
    "String Parsing",
    "Recursion",
    "Intervals",
    "Matrix",
    "Design",
    "Math & Geometry",
]


def ensure_default_patterns():
    """Populates default algorithmic patterns if none exist as global patterns."""
    for name in DEFAULT_PATTERNS:
        p_slug = slugify(name)
        if not Pattern.objects.filter(slug=p_slug, user__isnull=True).exists():
            Pattern.objects.create(name=name, slug=p_slug, user=None)


def title_from_slug(slug: str) -> str:
    """
    Converts a URL slug into a human-readable title with all numbers/digits removed.
    e.g. '123-two-sum' -> 'Two Sum', 'two-sum-2' -> 'Two Sum', 'problem-45-merge-intervals' -> 'Merge Intervals'.
    """
    if not slug:
        return ""
    # Replace dashes and underscores with spaces
    cleaned = re.sub(r'[-_]+', ' ', slug).strip()
    # Remove all numbers/digits to clean up leading or trailing problem numbers
    cleaned = re.sub(r'\d+', '', cleaned).strip()
    # Title-case each word
    words = [word.capitalize() for word in cleaned.split() if word]
    return ' '.join(words)


def normalize_problem_url(raw_url: str) -> dict:
    """
    Validates and normalizes a problem link into its canonical form,
    extracting platform and slug.
    Rejects malformed text to prevent abuse.
    """
    if not raw_url or not isinstance(raw_url, str):
        return {'canonical_url': '', 'platform': 'other', 'slug': '', 'error': 'Please enter a problem URL.'}

    url = raw_url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return {'canonical_url': '', 'platform': 'other', 'slug': '', 'error': 'Invalid URL format.'}

    domain = (parsed.netloc or '').lower()
    if domain.startswith('www.'):
        domain = domain[4:]

    # Strict domain/hostname validation to prevent abuse with arbitrary text
    host = domain.split(':')[0]
    if not host or '.' not in host or not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$', host):
        return {'canonical_url': '', 'platform': 'other', 'slug': '', 'error': 'Please provide a valid web URL with a recognized domain.'}

    path = parsed.path.rstrip('/')

    # 1. LeetCode detection
    if 'leetcode.com' in domain or 'leetcode.cn' in domain:
        platform = 'leetcode'
        match = re.search(r'/problems/([^/?#]+)', path, re.IGNORECASE)
        if match:
            slug = match.group(1).lower().strip()
            canonical_url = f"https://leetcode.com/problems/{slug}/"
            return {
                'canonical_url': canonical_url,
                'platform': platform,
                'slug': slug,
                'error': None
            }
        else:
            return {
                'canonical_url': '',
                'platform': 'leetcode',
                'slug': '',
                'error': 'Invalid LeetCode problem URL. Please provide a link in the format https://leetcode.com/problems/<problem-slug>/'
            }

    # 2. HackerRank detection
    if 'hackerrank.com' in domain:
        platform = 'hackerrank'
        match = re.search(r'/challenges/([^/?#]+)', path, re.IGNORECASE)
        slug = match.group(1).lower().strip() if match else ''
        canonical_url = f"https://www.hackerrank.com/challenges/{slug}/" if slug else f"https://www.hackerrank.com{path}/"
        return {
            'canonical_url': canonical_url,
            'platform': platform,
            'slug': slug,
            'error': None
        }

    # 3. Codeforces detection
    if 'codeforces.com' in domain:
        platform = 'codeforces'
        match = re.search(r'/(?:problemset/problem|contest/\d+/problem)/([^/?#]+)/?([^/?#]*)', path, re.IGNORECASE)
        if match:
            slug = f"{match.group(1)}-{match.group(2)}".strip('-').lower()
        else:
            segments = [s for s in path.split('/') if s]
            slug = segments[-1].lower() if segments else ''
        canonical_url = f"https://codeforces.com{path}"
        return {
            'canonical_url': canonical_url,
            'platform': platform,
            'slug': slug,
            'error': None
        }

    # 4. GeeksforGeeks detection
    if 'geeksforgeeks.org' in domain:
        platform = 'geeksforgeeks'
        match = re.search(r'/problems/([^/?#]+)', path, re.IGNORECASE)
        slug = match.group(1).lower().strip() if match else ''
        if not slug:
            segments = [s for s in path.split('/') if s]
            slug = segments[-1].lower() if segments else ''
        canonical_url = f"https://www.geeksforgeeks.org/problems/{slug}/" if slug else f"https://www.geeksforgeeks.org{path}/"
        return {
            'canonical_url': canonical_url,
            'platform': platform,
            'slug': slug,
            'error': None
        }

    # 5. Generic / Other platform
    platform_name = domain.split('.')[0] if domain else 'other'
    segments = [s for s in path.split('/') if s and s not in ('problem', 'problems', 'task', 'challenges', 'index.html')]
    slug = segments[-1].lower() if segments else ''
    canonical_url = f"https://{domain}{path}" if path else f"https://{domain}/"

    return {
        'canonical_url': canonical_url,
        'platform': platform_name,
        'slug': slug,
        'error': None
    }


def fetch_leetcode_metadata(slug: str) -> dict | None:
    """
    Queries LeetCode's public GraphQL endpoint for problem details.
    """
    if not slug:
        return None

    graphql_query = """
    query getQuestionDetail($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            questionFrontendId
            title
            difficulty
            isPaidOnly
        }
    }
    """

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Referer': 'https://leetcode.com',
    }

    try:
        response = requests.post(
            'https://leetcode.com/graphql',
            json={'query': graphql_query, 'variables': {'titleSlug': slug}},
            headers=headers,
            timeout=4.0
        )
        if response.status_code == 200:
            data = response.json()
            question = data.get('data', {}).get('question')
            if question and question.get('title'):
                frontend_id = question.get('questionFrontendId', '')
                prob_num = int(frontend_id) if frontend_id and frontend_id.isdigit() else None
                diff = question.get('difficulty', 'Medium')
                if diff not in ('Easy', 'Medium', 'Hard'):
                    diff = 'Medium'
                return {
                    'title': question.get('title', '').strip(),
                    'difficulty': diff,
                    'problem_number': prob_num,
                }
    except Exception:
        return None

    return None


def inspect_problem_url(url: str, user=None) -> dict:
    """
    Validates and inspects a problem link:
    - Normalizes URL and identifies platform & slug.
    - If user has already added the problem before:
        returns existing notes, cues, mistakes, patterns. Title and difficulty
        are locked (read-only) unless it was originally a user-specific problem.
        Indicates that FSRS should not be shown or applied.
    - If not already added:
        - Checks Global Problem database first.
        - If LeetCode: queries LeetCode GraphQL API. If found, both title and difficulty
          are read-only and problem is stored in global table.
        - If slug is identified (or if LC API failed but slug exists):
          title is read-only (with numbers removed), difficulty requires user input
          (with unselected default placeholder), and problem is stored in global table.
        - If neither LC API nor slug could identify the problem:
          stored as a user-specific problem with user input for title and difficulty.
    """
    normalized = normalize_problem_url(url)
    if normalized.get('error'):
        return {
            'success': False,
            'error': normalized['error'],
        }

    canonical_url = normalized['canonical_url']
    platform = normalized['platform']
    slug = normalized['slug']

    # 1. Check if the user already added this problem
    if user and user.is_authenticated:
        url_clean = canonical_url.rstrip('/')
        url_variants = list({
            url_clean,
            url_clean + '/',
            url_clean.replace('https://', 'http://'),
            url_clean.replace('https://', 'http://') + '/',
        })
        existing_up = UserProblem.objects.filter(
            user=user
        ).filter(
            models.Q(problem__canonical_url__in=url_variants) | models.Q(user_url__in=url_variants)
        ).select_related('problem').prefetch_related('patterns').first()

        if existing_up:
            is_user_spec = existing_up.is_user_specific
            return {
                'success': True,
                'canonical_url': canonical_url,
                'platform': existing_up.problem.platform if existing_up.problem else 'other',
                'slug': (existing_up.problem.slug if existing_up.problem else '') or slug,
                'title': existing_up.title,
                'difficulty': existing_up.difficulty,
                'problem_number': existing_up.problem.problem_number if existing_up.problem else None,
                'already_added': True,
                'user_problem_id': existing_up.id,
                'is_user_specific': is_user_spec,
                'is_locked': not is_user_spec,
                'is_title_locked': not is_user_spec,
                'is_diff_locked': not is_user_spec,
                'recognition_cue': existing_up.recognition_cue,
                'mistakes': existing_up.mistakes,
                'notes': existing_up.notes,
                'patterns': [p.name for p in existing_up.patterns.all()],
                'notice': 'You have already added this problem! You can edit your patterns, recognition cues, mistakes, and notes below.',
            }

    # 2. Check Global Problem Table first
    global_problem = Problem.objects.filter(canonical_url=canonical_url).first()
    if global_problem:
        return {
            'success': True,
            'canonical_url': canonical_url,
            'platform': global_problem.platform,
            'slug': global_problem.slug or slug,
            'title': global_problem.title,
            'difficulty': global_problem.difficulty,
            'problem_number': global_problem.problem_number,
            'is_locked': True,
            'is_title_locked': True,
            'is_diff_locked': True,
            'is_user_specific': False,
            'source': 'database',
            'already_added': False,
        }

    # 3. Case: LeetCode platform
    if platform == 'leetcode':
        api_data = fetch_leetcode_metadata(slug) if slug else None
        if api_data:
            return {
                'success': True,
                'canonical_url': canonical_url,
                'platform': 'leetcode',
                'slug': slug,
                'title': api_data['title'],
                'difficulty': api_data['difficulty'],
                'problem_number': api_data['problem_number'],
                'is_locked': True,
                'is_title_locked': True,
                'is_diff_locked': True,
                'is_user_specific': False,
                'source': 'leetcode_api',
                'already_added': False,
            }
        else:
            return {
                'success': False,
                'error': 'Invalid LeetCode problem URL. Problem could not be found on LeetCode.',
            }

    # 4. Case: Non-LeetCode platform
    slug_title = title_from_slug(slug) if slug else ""
    if slug_title:
        # Slug identified: title read-only from slug, difficulty user input, stored in global table
        return {
            'success': True,
            'canonical_url': canonical_url,
            'platform': platform,
            'slug': slug,
            'title': slug_title,
            'difficulty': '',
            'problem_number': None,
            'is_locked': False,
            'is_title_locked': True,
            'is_diff_locked': False,
            'is_user_specific': False,
            'source': 'slug',
            'already_added': False,
        }

    # 5. Case: Slug not recognizable -> user-specific problem
    return {
        'success': True,
        'canonical_url': canonical_url,
        'platform': platform,
        'slug': '',
        'title': '',
        'difficulty': '',
        'problem_number': None,
        'is_locked': False,
        'is_title_locked': False,
        'is_diff_locked': False,
        'is_user_specific': True,
        'source': 'manual',
        'already_added': False,
        'notice': 'Platform/slug not recognized. Enter title and difficulty; will be stored as your user-specific problem.',
    }


def create_user_problem_with_fsrs(
    user,
    canonical_url: str,
    title: str,
    difficulty: str,
    platform: str = 'leetcode',
    slug: str = '',
    problem_number: int | None = None,
    pattern_names: list[str] | None = None,
    recognition_cue: str = '',
    mistakes: str = '',
    notes: str = '',
    initial_rating: str = 'Good',
    is_user_specific: bool = False,
) -> tuple[UserProblem, bool]:
    """
    Creates or updates a problem for the user:
    - If the user already added this problem:
      Updates patterns, recognition_cue, mistakes, and notes (and user_title/difficulty if user-specific).
      DOES NOT touch FSRS card or ReviewHistory.
    - If new:
      - If global (LC API or slug identified): populates global Problem, then UserProblem.
      - If user-specific: stores directly in UserProblem without global Problem.
      - Attaches patterns (custom tags stored specifically for this user).
      - Initializes FSRS card with initial recall rating.
    """
    ensure_default_patterns()

    normalized = normalize_problem_url(canonical_url)
    clean_url = normalized.get('canonical_url') or canonical_url.strip()
    detected_platform = normalized.get('platform') or platform or 'other'
    clean_slug = normalized.get('slug') or slug or slugify(title)

    # Check if already added
    url_clean = clean_url.rstrip('/')
    url_variants = list({
        url_clean,
        url_clean + '/',
        url_clean.replace('https://', 'http://'),
        url_clean.replace('https://', 'http://') + '/',
    })
    existing_up = UserProblem.objects.filter(
        user=user
    ).filter(
        models.Q(problem__canonical_url__in=url_variants) | models.Q(user_url__in=url_variants)
    ).select_related('problem').first()

    if existing_up:
        # Existing problem update flow: update cue, mistakes, notes, patterns
        existing_up.recognition_cue = recognition_cue.strip()
        existing_up.mistakes = mistakes.strip()
        existing_up.notes = notes.strip()

        # If it was a user-specific problem, allow updating title and difficulty
        if existing_up.is_user_specific:
            if title.strip():
                existing_up.user_title = title.strip()
            if difficulty in ('Easy', 'Medium', 'Hard'):
                existing_up.user_difficulty = difficulty

        existing_up.save()

        # Update patterns
        if pattern_names is not None:
            existing_up.patterns.clear()
            for p_name in pattern_names:
                p_clean = p_name.strip()
                if p_clean:
                    p_slug = slugify(p_clean)
                    p_obj = Pattern.objects.filter(slug=p_slug, user__isnull=True).first()
                    if not p_obj:
                        p_obj, _ = Pattern.objects.get_or_create(
                            slug=p_slug,
                            user=user,
                            defaults={'name': p_clean}
                        )
                    existing_up.patterns.add(p_obj)

        return existing_up, False

    # New problem addition flow
    is_lc = (detected_platform == 'leetcode')
    if is_lc:
        # LeetCode problems MUST exist in DB or successfully fetch from LeetCode API
        global_problem = Problem.objects.filter(canonical_url=clean_url).first()
        if not global_problem:
            api_data = fetch_leetcode_metadata(clean_slug) if clean_slug else None
            if api_data:
                title = api_data['title']
                difficulty = api_data['difficulty']
                problem_number = api_data['problem_number']
            elif not title:
                raise ValueError("Invalid LeetCode problem URL. Problem could not be found on LeetCode.")

    # Determine if it should be stored user-specific or global
    slug_identified = bool(title_from_slug(clean_slug))

    # If explicitly flagged as user_specific or neither LC nor slug identified:
    if is_user_specific or (not is_lc and not slug_identified):
        user_problem = UserProblem.objects.create(
            user=user,
            problem=None,
            user_url=clean_url,
            user_title=title.strip(),
            user_difficulty=difficulty if difficulty in ('Easy', 'Medium', 'Hard') else 'Medium',
            recognition_cue=recognition_cue.strip(),
            mistakes=mistakes.strip(),
            notes=notes.strip(),
        )
    else:
        # Global Problem storage
        global_problem, _ = Problem.objects.get_or_create(
            canonical_url=clean_url,
            defaults={
                'title': title.strip(),
                'platform': detected_platform,
                'slug': clean_slug,
                'problem_number': problem_number,
                'difficulty': difficulty if difficulty in ('Easy', 'Medium', 'Hard') else 'Medium',
            }
        )

        if not global_problem.title and title:
            global_problem.title = title.strip()
            global_problem.save(update_fields=['title'])
        if global_problem.difficulty in ('Unknown', '') and difficulty in ('Easy', 'Medium', 'Hard'):
            global_problem.difficulty = difficulty
            global_problem.save(update_fields=['difficulty'])

        user_problem = UserProblem.objects.create(
            user=user,
            problem=global_problem,
            recognition_cue=recognition_cue.strip(),
            mistakes=mistakes.strip(),
            notes=notes.strip(),
        )

    # Attach patterns (user-scoped custom tags)
    if pattern_names:
        for p_name in pattern_names:
            p_clean = p_name.strip()
            if p_clean:
                p_slug = slugify(p_clean)
                p_obj = Pattern.objects.filter(slug=p_slug, user__isnull=True).first()
                if not p_obj:
                    p_obj, _ = Pattern.objects.get_or_create(
                        slug=p_slug,
                        user=user,
                        defaults={'name': p_clean}
                    )
                user_problem.patterns.add(p_obj)

    # Initialize FSRS card with initial recall rating
    rating_map = {
        'Again': Rating.Again,
        'Forgot': Rating.Again,
        'Hard': Rating.Hard,
        'Medium': Rating.Good,
        'Good': Rating.Good,
        'Easy': Rating.Easy,
    }

    fsrs_rating = rating_map.get(initial_rating, Rating.Good)

    scheduler = Scheduler()
    initial_card = Card()
    reviewed_card, review_log = scheduler.review_card(initial_card, fsrs_rating)

    state_val = int(reviewed_card.state)
    last_review_dt = reviewed_card.last_review or timezone.now()
    scheduled_days_val = max(0, (reviewed_card.due - last_review_dt).days)

    # Persist FSRSCard
    FSRSCard.objects.update_or_create(
        user_problem=user_problem,
        defaults={
            'due': reviewed_card.due,
            'stability': reviewed_card.stability or 0.0,
            'difficulty': reviewed_card.difficulty or 0.0,
            'elapsed_days': 0,
            'scheduled_days': scheduled_days_val,
            'step': reviewed_card.step,
            'state': state_val,
            'last_review': last_review_dt,
        }
    )

    # Log initial review in ReviewHistory
    ReviewHistory.objects.create(
        user_problem=user_problem,
        rating=int(fsrs_rating),
        reviewed_at=last_review_dt,
        scheduled_days=scheduled_days_val,
        elapsed_days=0,
        state=state_val,
    )

    return user_problem, True
