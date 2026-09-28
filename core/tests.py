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
        
        # Empty dashboard verification
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, self.test_name)
        self.assertIn("Start Revising", response.content.decode())
        self.assertIn("Most Forgotten", response.content.decode())
        self.assertIn("Revision Heatmap", response.content.decode())
        self.assertContains(response, "No Solved Problems Yet")

        # Dashboard with problem verification
        from core.services.problem_service import create_user_problem_with_fsrs
        create_user_problem_with_fsrs(
            user=user,
            canonical_url="https://leetcode.com/problems/two-sum/",
            title="Two Sum",
            difficulty="Easy",
            pattern_names=["Hashing"],
            recognition_cue="Lookup complement in O(1)",
            mistakes="None",
            notes="Use hash map for complement",
            initial_rating="Good",
        )
        response_with_prob = self.client.get(self.dashboard_url)
        self.assertContains(response_with_prob, "Two Sum")

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


class AddProblemWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="developer@example.com",
            password="StrongPassword123!",
            name="Dev Tester"
        )
        self.client.force_login(self.user)
        self.inspect_url = reverse('api_inspect_problem_url')
        self.search_patterns_url = reverse('api_search_patterns')
        self.add_problem_url = reverse('add_problem')

    def test_normalize_problem_url_and_abuse_prevention(self):
        from core.services.problem_service import normalize_problem_url

        # LeetCode with query params and subpath
        res1 = normalize_problem_url("https://leetcode.com/problems/two-sum/description/?envType=daily-question")
        self.assertEqual(res1['canonical_url'], "https://leetcode.com/problems/two-sum/")
        self.assertEqual(res1['platform'], "leetcode")
        self.assertEqual(res1['slug'], "two-sum")
        self.assertIsNone(res1['error'])

        # HackerRank
        res2 = normalize_problem_url("https://www.hackerrank.com/challenges/simple-array-sum/problem")
        self.assertEqual(res2['canonical_url'], "https://www.hackerrank.com/challenges/simple-array-sum/")
        self.assertEqual(res2['platform'], "hackerrank")
        self.assertEqual(res2['slug'], "simple-array-sum")

        # Abuse prevention: invalid random text without domain
        res_abuse = normalize_problem_url("not_a_valid_url")
        self.assertIsNotNone(res_abuse['error'])

        res_abuse2 = normalize_problem_url("hello world")
        self.assertIsNotNone(res_abuse2['error'])

    def test_title_from_slug_removes_numbers(self):
        from core.services.problem_service import title_from_slug

        # Test numbers removed from slug
        self.assertEqual(title_from_slug("123-two-sum"), "Two Sum")
        self.assertEqual(title_from_slug("two-sum-2"), "Two Sum")
        self.assertEqual(title_from_slug("45-merge-intervals"), "Merge Intervals")
        self.assertEqual(title_from_slug("valid-parentheses"), "Valid Parentheses")

    def test_inspect_problem_url_database_hit(self):
        from core.models import Problem

        Problem.objects.create(
            canonical_url="https://leetcode.com/problems/3sum/",
            platform="leetcode",
            title="3Sum",
            slug="3sum",
            problem_number=15,
            difficulty="Medium",
        )

        response = self.client.post(
            self.inspect_url,
            data={'url': 'https://leetcode.com/problems/3sum/description/'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'database')
        self.assertEqual(data['title'], '3Sum')
        self.assertEqual(data['difficulty'], 'Medium')
        self.assertEqual(data['problem_number'], 15)
        self.assertTrue(data['is_locked'])
        self.assertFalse(data['already_added'])

    def test_inspect_problem_url_non_leetcode_slug(self):
        response = self.client.post(
            self.inspect_url,
            data={'url': 'https://www.hackerrank.com/challenges/simple-array-sum/'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'slug')
        self.assertEqual(data['title'], 'Simple Array Sum')
        self.assertTrue(data['is_title_locked'])
        self.assertFalse(data['is_diff_locked'])
        self.assertEqual(data['difficulty'], '')

    def test_custom_user_patterns_isolated_per_user(self):
        from core.models import Pattern
        from django.contrib.auth import get_user_model
        User = get_user_model()
        other_user = User.objects.create_user(email="other@example.com", password="Password123#")

        # Global pattern (user=None)
        Pattern.objects.create(name="Binary Search", slug="binary-search", user=None)
        # Custom pattern for self.user
        Pattern.objects.create(name="Ajmal Custom Pattern", slug="ajmal-custom-pattern", user=self.user)
        # Custom pattern for other_user
        Pattern.objects.create(name="Other Secret Tag", slug="other-secret-tag", user=other_user)

        # Self user searches: should see global + own custom, but NOT other_user's custom
        response = self.client.get(f"{self.search_patterns_url}")
        self.assertEqual(response.status_code, 200)
        names = [p['name'] for p in response.json()['patterns']]
        self.assertIn("Binary Search", names)
        self.assertIn("Ajmal Custom Pattern", names)
        self.assertNotIn("Other Secret Tag", names)

    def test_add_problem_endpoint_with_fsrs_and_patterns(self):
        from core.models import Problem, UserProblem, FSRSCard, ReviewHistory, Pattern

        payload = {
            'url': 'https://leetcode.com/problems/valid-parentheses/',
            'title': 'Valid Parentheses',
            'difficulty': 'Easy',
            'patterns': ['Stack', 'String Parsing'],
            'recognition_cue': 'Matching open and closed brackets in LIFO order.',
            'mistakes': 'Empty stack handling when closing bracket arrives first.',
            'notes': 'Use dictionary mapping closing to opening bracket.',
            'initial_rating': 'Medium',
        }

        response = self.client.post(
            self.add_problem_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['created'])

        # 1. Global Problem created
        problem = Problem.objects.filter(canonical_url='https://leetcode.com/problems/valid-parentheses/').first()
        self.assertIsNotNone(problem)
        self.assertEqual(problem.title, 'Valid Parentheses')
        self.assertEqual(problem.difficulty, 'Easy')

        # 2. UserProblem created
        user_prob = UserProblem.objects.filter(user=self.user, problem=problem).first()
        self.assertIsNotNone(user_prob)
        self.assertEqual(user_prob.difficulty, 'Easy')
        self.assertEqual(user_prob.recognition_cue, payload['recognition_cue'])

        # 3. Patterns linked
        patterns = list(user_prob.patterns.values_list('name', flat=True))
        self.assertIn('Stack', patterns)
        self.assertIn('String Parsing', patterns)

        # 4. FSRS Card created
        self.assertTrue(hasattr(user_prob, 'fsrs_card'))
        card = user_prob.fsrs_card
        self.assertIsNotNone(card.due)
        self.assertGreater(card.stability, 0.0)

        # 5. Review History logged
        history = ReviewHistory.objects.filter(user_problem=user_prob).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.rating, 3)

    def test_already_added_problem_editing_does_not_modify_fsrs(self):
        from core.models import Problem, UserProblem, FSRSCard, ReviewHistory

        # First add
        payload = {
            'url': 'https://leetcode.com/problems/climbing-stairs/',
            'title': 'Climbing Stairs',
            'difficulty': 'Easy',
            'patterns': ['Dynamic Programming'],
            'recognition_cue': 'Fibonacci sequence pattern',
            'mistakes': 'Base cases off by one',
            'notes': 'Keep 2 variables for O(1) space',
            'initial_rating': 'Easy',
        }
        res1 = self.client.post(self.add_problem_url, data=payload, content_type='application/json')
        self.assertEqual(res1.status_code, 200)
        up = UserProblem.objects.get(user=self.user, problem__canonical_url='https://leetcode.com/problems/climbing-stairs/')
        original_due = up.fsrs_card.due
        original_rev_count = ReviewHistory.objects.filter(user_problem=up).count()
        self.assertEqual(original_rev_count, 1)

        # Inspect URL again: should flag already_added=True
        insp_res = self.client.post(self.inspect_url, data={'url': 'https://leetcode.com/problems/climbing-stairs/'}, content_type='application/json')
        insp_data = insp_res.json()
        self.assertTrue(insp_data['already_added'])
        self.assertEqual(insp_data['recognition_cue'], 'Fibonacci sequence pattern')

        # Re-submit with edited notes and cue
        edit_payload = {
            'url': 'https://leetcode.com/problems/climbing-stairs/',
            'title': 'Climbing Stairs',
            'difficulty': 'Easy',
            'patterns': ['Dynamic Programming', 'Recursion'],
            'recognition_cue': 'Updated cue for climbing stairs',
            'mistakes': 'Updated mistakes',
            'notes': 'Updated notes',
            'initial_rating': 'Forgot',  # Should NOT be applied!
        }
        res2 = self.client.post(self.add_problem_url, data=edit_payload, content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.json()['created'])

        up.refresh_from_db()
        self.assertEqual(up.recognition_cue, 'Updated cue for climbing stairs')
        self.assertIn('Recursion', list(up.patterns.values_list('name', flat=True)))
        # Verify FSRS was NOT re-evaluated or altered
        self.assertEqual(up.fsrs_card.due, original_due)
        # Verify no new ReviewHistory was created
        self.assertEqual(ReviewHistory.objects.filter(user_problem=up).count(), original_rev_count)

    def test_user_specific_problem_creation(self):
        from core.models import Problem, UserProblem

        # An obscure custom URL with no recognizable slug or LC platform
        payload = {
            'url': 'https://custom-contest.org/task?id=9999',
            'title': 'Custom Algorithmic Puzzle',
            'difficulty': 'Hard',
            'is_user_specific': True,
            'patterns': ['Math & Geometry'],
            'recognition_cue': 'Custom observation',
            'mistakes': 'Math overflow',
            'notes': 'Use 64-bit int',
            'initial_rating': 'Hard',
        }
        res = self.client.post(self.add_problem_url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)

        # Verify it was NOT saved to global Problem table
        self.assertFalse(Problem.objects.filter(canonical_url__icontains='custom-contest.org').exists())

        # Verify it was saved to UserProblem as user-specific
        user_prob = UserProblem.objects.filter(user=self.user, user_url__icontains='custom-contest.org').first()
        self.assertIsNotNone(user_prob)
        self.assertTrue(user_prob.is_user_specific)
        self.assertEqual(user_prob.title, 'Custom Algorithmic Puzzle')
        self.assertEqual(user_prob.difficulty, 'Hard')
        self.assertTrue(hasattr(user_prob, 'fsrs_card'))

    def test_inspect_invalid_leetcode_url_fails_gracefully(self):
        # Invalid / non-existent problem slug on LeetCode
        response = self.client.post(
            self.inspect_url,
            data={'url': 'https://leetcode.com/problems/this-slug-definitely-does-not-exist-xyz999/'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn("Invalid LeetCode problem URL", data['error'])

    def test_required_fields_validation_in_add_problem(self):
        base_payload = {
            'url': 'https://leetcode.com/problems/invert-binary-tree/',
            'title': 'Invert Binary Tree',
            'difficulty': 'Easy',
            'patterns': ['Tree', 'Recursion'],
            'recognition_cue': 'Swap left and right children recursively.',
            'notes': 'Simple DFS traversal.',
            'initial_rating': 'Easy',
        }

        # 1. Missing patterns
        p1 = dict(base_payload)
        p1['patterns'] = []
        r1 = self.client.post(self.add_problem_url, data=p1, content_type='application/json')
        self.assertEqual(r1.status_code, 400)
        self.assertIn("algorithmic pattern", r1.json()['error'])

        # 2. Missing recognition_cue
        p2 = dict(base_payload)
        p2['recognition_cue'] = ''
        r2 = self.client.post(self.add_problem_url, data=p2, content_type='application/json')
        self.assertEqual(r2.status_code, 400)
        self.assertIn("Recognition cue is required", r2.json()['error'])

        # 3. Missing notes
        p3 = dict(base_payload)
        p3['notes'] = ''
        r3 = self.client.post(self.add_problem_url, data=p3, content_type='application/json')
        self.assertEqual(r3.status_code, 400)
        self.assertIn("Personal notes are required", r3.json()['error'])

        # 4. Missing initial_rating for new problem
        p4 = dict(base_payload)
        p4['initial_rating'] = ''
        r4 = self.client.post(self.add_problem_url, data=p4, content_type='application/json')
        self.assertEqual(r4.status_code, 400)
        self.assertIn("initial recall performance", r4.json()['error'])


class FSRSIssuesVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="fsrs_tester@example.com",
            password="Password123!",
            name="FSRS Tester"
        )
        self.client.force_login(self.user)
        self.dashboard_url = reverse('dashboard')
        self.add_problem_url = reverse('add_problem')

    def test_issue1_fsrs_state_choices_and_default(self):
        from core.models import FSRSCard
        
        # Verify 0 = 'New' is not in STATE_CHOICES
        state_values = [val for val, _ in FSRSCard.STATE_CHOICES]
        self.assertNotIn(0, state_values)
        self.assertEqual(state_values, [1, 2, 3])
        
        # Verify choices map to Learning, Review, Relearning
        choices_dict = dict(FSRSCard.STATE_CHOICES)
        self.assertEqual(choices_dict[1], 'Learning')
        self.assertEqual(choices_dict[2], 'Review')
        self.assertEqual(choices_dict[3], 'Relearning')
        
        # Verify model default is 1 (Learning)
        state_field = FSRSCard._meta.get_field('state')
        self.assertEqual(state_field.default, 1)

    def test_issue2_dashboard_view_user_specific_problem_does_not_crash(self):
        from core.models import UserProblem, FSRSCard
        from django.utils import timezone
        import datetime
        
        # Create user-specific problem where problem is None
        user_prob = UserProblem.objects.create(
            user=self.user,
            problem=None,
            user_url='https://custom-oj.org/problem/42',
            user_title='My Custom Interval Scheduling Problem',
            user_difficulty='Hard',
            recognition_cue='Sort by end time',
            mistakes='Sorting by start time fails with long intervals',
            notes='Greedy activity selection pattern',
        )
        FSRSCard.objects.create(
            user_problem=user_prob,
            due=timezone.now() + datetime.timedelta(days=1),
            stability=2.5,
            difficulty=5.0,
            state=1,
            step=1,
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Custom Interval Scheduling Problem')

    def test_issue3_fsrs_step_persistence_and_reconstruction(self):
        from core.models import UserProblem, FSRSCard
        from fsrs import Scheduler, Card, Rating, State

        # Create user problem
        up = UserProblem.objects.create(
            user=self.user,
            user_url='https://custom.com/step-test',
            user_title='Step Test Problem',
        )
        
        # Review with Good -> Py-FSRS v6 gives state=Learning (1), step=1
        scheduler = Scheduler()
        card = Card()
        reviewed, log = scheduler.review_card(card, Rating.Good)
        self.assertEqual(reviewed.state, State.Learning)
        self.assertEqual(reviewed.step, 1)
        
        # Persist to Django FSRSCard
        fsrs_card = FSRSCard.objects.create(
            user_problem=up,
            due=reviewed.due,
            stability=reviewed.stability,
            difficulty=reviewed.difficulty,
            state=int(reviewed.state),
            step=reviewed.step,
            last_review=reviewed.last_review,
        )
        self.assertEqual(fsrs_card.step, 1)
        
        # Reconstruct fsrs.Card from Django FSRSCard
        reconstructed = fsrs_card.to_fsrs_card()
        self.assertEqual(reconstructed.state, State.Learning)
        self.assertEqual(reconstructed.step, 1)
        self.assertEqual(reconstructed.stability, reviewed.stability)
        self.assertEqual(reconstructed.difficulty, reviewed.difficulty)
        
        # Reviewing reconstructed card with Good should advance to Review (state=2)
        advanced, _ = scheduler.review_card(reconstructed, Rating.Good)
        self.assertEqual(advanced.state, State.Review)
        self.assertIsNone(advanced.step)
        
        # Update model from the advanced card
        fsrs_card.update_from_fsrs_card(advanced)
        fsrs_card.refresh_from_db()
        self.assertEqual(fsrs_card.state, 2)
        self.assertIsNone(fsrs_card.step)

    def test_issue4_no_reps_or_lapses_on_fsrs_card_and_review_history_analytics(self):
        from core.models import FSRSCard, ReviewHistory, UserProblem
        from django.core.exceptions import FieldDoesNotExist
        
        # reps and lapses must not be model fields on FSRSCard
        with self.assertRaises(FieldDoesNotExist):
            FSRSCard._meta.get_field('reps')
        with self.assertRaises(FieldDoesNotExist):
            FSRSCard._meta.get_field('lapses')
            
        # Review count analytics come from ReviewHistory
        up = UserProblem.objects.create(
            user=self.user,
            user_url='https://custom.com/rev-test',
            user_title='Review Count Test',
        )
        ReviewHistory.objects.create(user_problem=up, rating=1)
        ReviewHistory.objects.create(user_problem=up, rating=3)
        ReviewHistory.objects.create(user_problem=up, rating=4)
        
        review_count = ReviewHistory.objects.filter(user_problem=up).count()
        self.assertEqual(review_count, 3)


class ForgottenProblemsAndHeatmapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="learner@recode.dev", password="Password123!", name="Dev Learner")
        self.client = Client()
        self.client.force_login(self.user)

    def test_most_forgotten_problems_ranking(self):
        from core.models import UserProblem, ReviewHistory, Pattern
        from core.services.analytics_service import get_most_forgotten_problems, get_forgotten_stats

        p_pattern = Pattern.objects.create(name="Binary Search", slug="binary-search", user=self.user)

        # Problem 1: 3 forgot ratings
        up1 = UserProblem.objects.create(user=self.user, user_title="Search in Rotated Sorted Array", user_url="https://leetcode.com/problems/search-in-rotated-sorted-array/")
        up1.patterns.add(p_pattern)
        for _ in range(3):
            ReviewHistory.objects.create(user_problem=up1, rating=1)

        # Problem 2: 1 forgot rating
        up2 = UserProblem.objects.create(user=self.user, user_title="Binary Search Basic", user_url="https://leetcode.com/problems/binary-search/")
        up2.patterns.add(p_pattern)
        ReviewHistory.objects.create(user_problem=up2, rating=1)

        # Problem 3: 0 forgot ratings (all Good/Easy)
        up3 = UserProblem.objects.create(user=self.user, user_title="Easy Two Sum", user_url="https://leetcode.com/problems/two-sum/")
        ReviewHistory.objects.create(user_problem=up3, rating=3)

        forgotten = get_most_forgotten_problems(self.user, limit=5)
        self.assertEqual(len(forgotten), 2)
        self.assertEqual(forgotten[0]['title'], "Search in Rotated Sorted Array")
        self.assertEqual(forgotten[0]['forgot_count'], 3)
        self.assertEqual(forgotten[1]['title'], "Binary Search Basic")
        self.assertEqual(forgotten[1]['forgot_count'], 1)

        stats = get_forgotten_stats(self.user)
        self.assertEqual(stats['total_forgot_ratings'], 4)
        self.assertEqual(stats['distinct_forgot_problems'], 2)

    def test_revision_heatmap_structure(self):
        from core.models import UserProblem, ReviewHistory
        from core.services.analytics_service import get_revision_heatmap_data
        from django.utils import timezone

        up = UserProblem.objects.create(user=self.user, user_title="Heatmap Test", user_url="https://leetcode.com/problems/heatmap/")
        # Add reviews today
        ReviewHistory.objects.create(user_problem=up, rating=3, reviewed_at=timezone.now())
        ReviewHistory.objects.create(user_problem=up, rating=4, reviewed_at=timezone.now())

        heatmap = get_revision_heatmap_data(self.user, months=12)
        self.assertEqual(len(heatmap['weeks']), 52)
        for week in heatmap['weeks']:
            self.assertEqual(len(week['days']), 7)

        self.assertGreaterEqual(heatmap['total_reviews_year'], 2)
        self.assertGreaterEqual(heatmap['active_days_year'], 1)
        self.assertGreaterEqual(heatmap['max_day_reviews'], 2)
        self.assertTrue(len(heatmap['month_labels']) >= 10)

    def test_dashboard_renders_forgotten_and_heatmap(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('most_forgotten', response.context)
        self.assertIn('heatmap_data', response.context)
        self.assertIn("Revision Heatmap", response.content.decode())
        self.assertIn("Most Forgotten", response.content.decode())


