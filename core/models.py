from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


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
