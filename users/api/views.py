from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import UserSerializer, RegisterSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        import secrets
        from django.core.cache import cache
        from django.core.mail import send_mail
        from django.conf import settings
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        otp = secrets.token_hex(4).upper()
        
        if not otp:
            return Response({"detail": "Failed to generate OTP. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        cache.set(f"activation_otp_{user.email}", otp, timeout=300)
        
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags

        html_message = render_to_string("users/email/activation_email.html", {"user": user, "otp": otp})
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject="Activate your Upemba account",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_message,
        )
        
        return Response({
            "detail": "Account created. Please check your email for the activation code.",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


from rest_framework.views import APIView

class ActivateUserView(APIView):
    permission_classes = (AllowAny,)
    
    def post(self, request, *args, **kwargs):
        from django.core.cache import cache
        email = request.data.get("email")
        code = request.data.get("code")
        
        if not email or not code:
            return Response({"detail": "Email and code are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        cached_otp = cache.get(f"activation_otp_{email}")
        
        if not cached_otp or cached_otp.strip().upper() != str(code).strip().upper():
            return Response({"detail": "Invalid or expired activation code."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
            
        user.is_active = True
        user.save()
        cache.delete(f"activation_otp_{email}")
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "detail": "Account activated successfully.",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user, context={"request": request}).data
        }, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    permission_classes = (AllowAny,)
    
    def post(self, request, *args, **kwargs):
        from django.core.cache import cache
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        import secrets
        
        email = request.data.get("email")
        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Silent fail for security/enumeration
            return Response({"detail": "If the email is registered, a new OTP has been sent."}, status=status.HTTP_200_OK)
            
        if user.is_active:
            return Response({"detail": "Account is already active."}, status=status.HTTP_400_BAD_REQUEST)
            
        otp = secrets.token_hex(4).upper()
        
        if not otp:
            return Response({"detail": "Failed to generate OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        cache.set(f"activation_otp_{user.email}", otp, timeout=300)
        
        html_message = render_to_string("users/email/activation_email.html", {"user": user, "otp": otp})
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject="Activate your Upemba account (Resend)",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_message,
        )
        
        return Response({
            "detail": "A new activation code has been sent to your email."
        }, status=status.HTTP_200_OK)


class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = "username"

    def get_queryset(self, *args, **kwargs):
        assert isinstance(self.request.user.id, int)
        return self.queryset.filter(id=self.request.user.id)

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        if request.method == "PATCH":
            serializer = UserSerializer(request.user, data=request.data, partial=True, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response(status=status.HTTP_200_OK, data=serializer.data)
            return Response(status=status.HTTP_400_BAD_REQUEST, data=serializer.errors)

        serializer = UserSerializer(request.user, context={"request": request})
        return Response(status=status.HTTP_200_OK, data=serializer.data)
  
    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password1")
        
        if not old_password or not new_password:
            return Response({"detail": "Both old and new passwords are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.check_password(old_password):
            return Response({"detail": "Wrong current password."}, status=status.HTTP_400_BAD_REQUEST)
            
        user.set_password(new_password)
        user.save()
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
