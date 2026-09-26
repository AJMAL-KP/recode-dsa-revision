from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailBackend(ModelBackend):
    """Authenticate using email address instead of username."""
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        email = kwargs.get('email', username)
        if not email:
            return None
        try:
            user = UserModel.objects.filter(email__iexact=email).first()
            if not user:
                # Also try matching username in case someone used username
                user = UserModel.objects.filter(username__iexact=email).first()
            if user and user.check_password(password):
                return user
        except Exception:
            return None
        return None
