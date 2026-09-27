from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from fsrs import Card, State


class UserManager(BaseUserManager):
    """Custom manager for User model where email is the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Production-grade Custom User Model:
    - Primary authentication: email + password
    - name: used strictly for visual / greeting display purposes
    """
    email = models.EmailField(
        verbose_name="Email Address",
        unique=True,
        db_index=True,
        max_length=255,
    )
    name = models.CharField(
        verbose_name="Full Name",
        max_length=150,
        blank=True,
        help_text="Display name for visual greeting across dashboard and emails.",
    )
    is_active = models.BooleanField(
        verbose_name="Active",
        default=True,
        help_text="Designates whether this user account should be treated as active.",
    )
    is_staff = models.BooleanField(
        verbose_name="Staff status",
        default=False,
        help_text="Designates whether the user can log into the admin site.",
    )
    date_joined = models.DateTimeField(
        verbose_name="Date joined",
        default=timezone.now,
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.name.strip() or self.email

    def get_short_name(self):
        if self.name:
            return self.name.strip().split()[0]
        return self.email.split('@')[0]


class Pattern(models.Model):
    """
    Algorithmic pattern tag (e.g. Hashing, Two Pointers, Dynamic Programming).
    Supports pre-seeded global patterns (user=None) and custom user-created patterns.
    Custom user-created patterns are only stored and displayed for that user.
    """
    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=120, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_patterns',
        help_text="Null for predefined global patterns; set for custom user-created patterns.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pattern"
        verbose_name_plural = "Patterns"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['slug'],
                condition=models.Q(user__isnull=True),
                name='unique_global_pattern_slug'
            ),
            models.UniqueConstraint(
                fields=['user', 'slug'],
                condition=models.Q(user__isnull=False),
                name='unique_user_pattern_slug'
            ),
        ]

    def __str__(self):
        return f"{self.name} (Custom: {self.user.email})" if self.user else self.name


class Problem(models.Model):
    """
    Global Problem database table.
    The normalized URL is the canonical identifier and unique field.
    """
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
        ('Unknown', 'Unknown'),
    ]

    canonical_url = models.URLField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text="Normalized canonical URL identifying the problem uniquely.",
    )
    platform = models.CharField(
        max_length=50,
        default='leetcode',
        db_index=True,
        help_text="Platform identifier (e.g., leetcode, hackerrank, codeforces, other).",
    )
    title = models.CharField(max_length=255, db_index=True)
    slug = models.CharField(max_length=255, blank=True, db_index=True)
    problem_number = models.IntegerField(null=True, blank=True, db_index=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Medium')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Global Problem"
        verbose_name_plural = "Global Problems"
        ordering = ['problem_number', 'title']

    def __str__(self):
        if self.problem_number:
            return f"#{self.problem_number} {self.title} ({self.difficulty})"
        return f"{self.title} ({self.difficulty})"


class UserProblem(models.Model):
    """
    User-specific problem instance storing active recall notes, recognition cues,
    mistakes, and multi-select patterns.
    
    If the problem is identified via LeetCode GraphQL API or a recognizable URL slug,
    `problem` references the global Problem row.
    If the URL cannot be identified by LC API or slug, it is stored as a user-specific problem:
    `problem` is None, and `user_url`, `user_title`, `user_difficulty` are populated.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_problems')
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_instances',
        help_text="Null if user-specific problem (not identified by LC API or slug)."
    )
    user_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text="Canonical URL for user-specific problems when not in global Problem table."
    )
    user_title = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="User-entered title when problem is user-specific."
    )
    user_difficulty = models.CharField(
        max_length=20,
        choices=Problem.DIFFICULTY_CHOICES[:3],
        blank=True,
        default='Medium',
        help_text="User-entered difficulty when problem is user-specific."
    )
    patterns = models.ManyToManyField(Pattern, related_name='user_problems', blank=True)
    recognition_cue = models.TextField(
        max_length=250,
        blank=True,
        help_text="Observation trigger: how to recognize this problem or algorithmic approach.",
    )
    mistakes = models.TextField(
        max_length=300,
        blank=True,
        help_text="Edge case traps or mistakes made during problem solving.",
    )
    notes = models.TextField(
        max_length=600,
        blank=True,
        help_text="Personal implementation notes, key invariants, and takeaways.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Problem"
        verbose_name_plural = "User Problems"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'problem'],
                condition=models.Q(problem__isnull=False),
                name='unique_user_global_problem'
            ),
            models.UniqueConstraint(
                fields=['user', 'user_url'],
                condition=models.Q(problem__isnull=True),
                name='unique_user_specific_url'
            ),
        ]

    @property
    def title(self):
        return self.problem.title if self.problem else self.user_title

    @property
    def difficulty(self):
        return self.problem.difficulty if self.problem else self.user_difficulty

    @property
    def effective_difficulty(self):
        return self.difficulty

    @property
    def canonical_url(self):
        return self.problem.canonical_url if self.problem else self.user_url

    @property
    def is_user_specific(self):
        return self.problem is None

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class FSRSCard(models.Model):
    """
    Persistent FSRS state associated with a user's problem.
    Scheduler updates these fields on every active recall review.
    Matches Py-FSRS v6 State and Card attributes.
    """
    STATE_CHOICES = [
        (1, 'Learning'),
        (2, 'Review'),
        (3, 'Relearning'),
    ]

    user_problem = models.OneToOneField(
        UserProblem,
        on_delete=models.CASCADE,
        related_name='fsrs_card',
    )
    due = models.DateTimeField(db_index=True)
    stability = models.FloatField(default=0.0)
    difficulty = models.FloatField(default=0.0)
    elapsed_days = models.IntegerField(default=0)
    scheduled_days = models.IntegerField(default=0)
    step = models.IntegerField(null=True, blank=True, default=0)
    state = models.IntegerField(choices=STATE_CHOICES, default=1)
    last_review = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FSRS Card"
        verbose_name_plural = "FSRS Cards"
        ordering = ['due']

    def __str__(self):
        return f"FSRS[{self.user_problem.title}] Due: {self.due.strftime('%Y-%m-%d %H:%M')}"

    def is_due(self):
        return timezone.now() >= self.due

    def to_fsrs_card(self) -> Card:
        """
        Reconstruct a Py-FSRS v6 Card object from this database model instance.
        Restores state, step, stability, difficulty, due, and last_review.
        """
        return Card(
            card_id=self.id,
            state=State(self.state),
            step=self.step,
            stability=self.stability if self.stability and self.stability > 0 else None,
            difficulty=self.difficulty if self.difficulty and self.difficulty > 0 else None,
            due=self.due,
            last_review=self.last_review,
        )

    def update_from_fsrs_card(self, card: Card, save: bool = True):
        """
        Update this model instance from a Py-FSRS v6 Card object.
        Saves the current step, state, stability, difficulty, due, and last_review.
        """
        self.due = card.due
        self.stability = card.stability or 0.0
        self.difficulty = card.difficulty or 0.0
        self.step = card.step
        self.state = int(card.state)
        self.last_review = card.last_review
        if card.last_review and card.due:
            self.scheduled_days = max(0, (card.due - card.last_review).days)
        if save:
            self.save()


class ReviewHistory(models.Model):
    """
    Complete chronological record of all active recall reviews for analytics and FSRS progression.
    """
    RATING_CHOICES = [
        (1, 'Again'),
        (2, 'Hard'),
        (3, 'Good'),
        (4, 'Easy'),
    ]

    user_problem = models.ForeignKey(
        UserProblem,
        on_delete=models.CASCADE,
        related_name='review_logs',
    )
    rating = models.IntegerField(choices=RATING_CHOICES)
    reviewed_at = models.DateTimeField(default=timezone.now, db_index=True)
    scheduled_days = models.IntegerField(default=0)
    elapsed_days = models.IntegerField(default=0)
    state = models.IntegerField(default=1)

    class Meta:
        verbose_name = "Review History"
        verbose_name_plural = "Review Histories"
        ordering = ['-reviewed_at']

    def __str__(self):
        return f"{self.user_problem.title} - Rating {self.get_rating_display()} on {self.reviewed_at.strftime('%Y-%m-%d')}"

