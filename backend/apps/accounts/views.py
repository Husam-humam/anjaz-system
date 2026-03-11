"""
طبقة العرض (Views) لتطبيق الحسابات — نقاط نهاية المصادقة وإدارة المستخدمين.
"""
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.organization.permissions import IsStatisticsAdmin

from .serializers import (
    LoginSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .services import UserService

User = get_user_model()


class LoginView(APIView):
    """
    تسجيل الدخول — POST /api/auth/login/
    يتحقق من بيانات الاعتماد ويُرجع توكنات JWT مع معلومات المستخدم.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response(
                {
                    'error': True,
                    'message': 'اسم المستخدم أو كلمة المرور غير صحيحة.',
                    'code': 'AUTHENTICATION_ERROR',
                    'details': {},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    'error': True,
                    'message': 'هذا الحساب معطّل. يرجى التواصل مع مدير النظام.',
                    'code': 'AUTHENTICATION_ERROR',
                    'details': {},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # إنشاء توكنات JWT
        refresh = RefreshToken.for_user(user)
        user_data = UserProfileSerializer(user).data

        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': user_data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    تسجيل الخروج — POST /api/auth/logout/
    يضع رمز التحديث في القائمة السوداء.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {
                    'error': True,
                    'message': 'رمز التحديث مطلوب.',
                    'code': 'VALIDATION_ERROR',
                    'details': {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {
                    'error': True,
                    'message': 'رمز التحديث غير صالح أو منتهي الصلاحية.',
                    'code': 'VALIDATION_ERROR',
                    'details': {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'message': 'تم تسجيل الخروج بنجاح.'},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    الملف الشخصي — GET /api/auth/me/
    يُرجع معلومات المستخدم الحالي.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """
    إدارة المستخدمين — CRUD كامل لمدير قسم الإحصاء فقط.
    GET    /api/users/              — قائمة المستخدمين
    POST   /api/users/              — إنشاء مستخدم
    GET    /api/users/{id}/         — تفاصيل مستخدم
    PATCH  /api/users/{id}/         — تحديث مستخدم
    DELETE /api/users/{id}/         — حذف مستخدم
    POST   /api/users/{id}/reset_password/ — إعادة تعيين كلمة المرور
    """
    permission_classes = [permissions.IsAuthenticated, IsStatisticsAdmin]
    queryset = User.objects.select_related('unit').order_by('-created_at')
    search_fields = ['username', 'full_name']
    filterset_fields = ['role', 'is_active']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # تصفية حسب الوحدة التنظيمية
        unit_id = self.request.query_params.get('unit_id')
        if unit_id:
            queryset = queryset.filter(unit_id=unit_id)
        return queryset

    def perform_create(self, serializer):
        """إنشاء مستخدم جديد باستخدام طبقة الخدمات"""
        data = serializer.validated_data.copy()
        try:
            user = UserService.create_user(data, created_by=self.request.user)
        except DjangoValidationError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(e.message_dict)
        # تحديث instance في السيريالايزر لإرجاع البيانات الصحيحة
        serializer.instance = user

    def perform_update(self, serializer):
        """تحديث بيانات مستخدم باستخدام طبقة الخدمات"""
        data = serializer.validated_data.copy()
        try:
            user = UserService.update_user(serializer.instance, data)
        except DjangoValidationError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(e.message_dict)
        serializer.instance = user

    @action(detail=True, methods=['post'], url_path='reset_password')
    def reset_password(self, request, pk=None):
        """إعادة تعيين كلمة مرور مستخدم"""
        user = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['new_password']
        UserService.reset_password(user, new_password)

        return Response(
            {'message': 'تم إعادة تعيين كلمة المرور بنجاح.'},
            status=status.HTTP_200_OK,
        )
