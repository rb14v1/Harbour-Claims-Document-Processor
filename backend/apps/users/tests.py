from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="Password123!")

    def test_create_user_defaults_to_adjuster_role(self):
        user = User.objects.create_user(email="joe@example.com", password="Password123!")
        self.assertEqual(user.role, User.Role.ADJUSTER)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("Password123!"))

    def test_create_superuser_is_admin_role(self):
        user = User.objects.create_superuser(email="root@example.com", password="Password123!")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_no_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertFalse(hasattr(User, "username"))

    def test_str_is_email(self):
        user = User.objects.create_user(email="joe@example.com", password="Password123!")
        self.assertEqual(str(user), "joe@example.com")


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_and_login_flow(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "newuser@example.com",
                "password": "Password123!",
                "first_name": "New",
                "last_name": "User",
                "role": "adjuster",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": "newuser@example.com", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)
        self.assertEqual(login_response.data["user"]["email"], "newuser@example.com")

    def test_refresh_token(self):
        User.objects.create_user(email="refresh@example.com", password="Password123!")
        login_response = self.client.post(
            "/api/auth/login/",
            {"email": "refresh@example.com", "password": "Password123!"},
            format="json",
        )
        refresh_response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

    def test_login_wrong_password_fails(self):
        User.objects.create_user(email="wrongpass@example.com", password="Password123!")
        response = self.client.post(
            "/api/auth/login/",
            {"email": "wrongpass@example.com", "password": "nope"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_me_endpoint_requires_auth(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
