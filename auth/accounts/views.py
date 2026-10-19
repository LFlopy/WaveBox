import json

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST

User = get_user_model()


@require_POST
def register(request):
    try:
        data = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Expected JSON object"},
            status=400,
        )

    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")

    if not all(isinstance(value, str) for value in (username, email, password)):
        return JsonResponse({"error": "Invalid field types"}, status=400)

    username = username.strip()
    email = email.strip()

    if not username or not email or not password:
        return JsonResponse({"error": "All field are required"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": "User already exists"}, status=409)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error": "This email is already taken"}, status=400)

    try:
        validate_password(password)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
    )

    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
        status=201,
    )
