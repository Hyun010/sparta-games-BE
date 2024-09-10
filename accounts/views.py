from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

import rest_framework
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from dj_rest_auth import views
from dj_rest_auth.registration.views import SocialLoginView
from dj_rest_auth.serializers import JWTSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib import messages
from django.contrib.auth import get_user_model, login
import re
import requests
from rest_framework import status
from spartagames import config


class AlertException(Exception):
    pass


class TokenException(Exception):
    pass


from games.models import GameCategory

# ---------- API---------- #
class SignUpAPIView(APIView):
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9+-_.]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    PASSWORD_PATTERN = re.compile(r'^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[a-zA-Z]).{8,32}$')

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        password_check = request.data.get("password_check")
        nickname = request.data.get("nickname")
        game_category = request.data.getlist("game_category")
        user_tech = request.data.get("user_tech")
        is_maker = request.data.get("is_maker")
        
        # email 유효성 검사
        if not self.EMAIL_PATTERN.match(email):
            return Response({"error_message":"올바른 email을 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)
        elif get_user_model().objects.filter(email=email).exists():
            return Response({"error_message":"이미 존재하는 email입니다.."}, status=status.HTTP_400_BAD_REQUEST)
        
        # password 유효성 검사
        if not self.PASSWORD_PATTERN.match(password):
            return Response({"error_message":"올바른 password.password_check를 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)
        elif not password == password_check:
            return Response({"error_message":"암호를 확인해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        # nickname 유효성 검사
        if len(nickname) > 30:
            return Response({"error_message":"닉네임은 30자 이하만 가능합니다."}, status=status.HTTP_400_BAD_REQUEST)
        elif len(nickname) == 0:
            return Response({"error_message":"닉네임을 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)
        elif get_user_model().objects.filter(nickname=nickname).exists():
            return Response({"error_message":"이미 존재하는 username입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # DB에 유저 등록
        user = get_user_model().objects.create_user(
            email = email,
            password = password,
            nickname = nickname,
            user_tech = user_tech,
            is_maker = is_maker,
        )

        # 카테고리 가져오기
        game_categories = GameCategory.objects.filter(name__in=game_category)
        user.game_category.set(game_categories)  # ManyToManyField 값 설정
        
        return Response({
            "message":"회원가입 성공",
            "data":{
                "email":user.email,
                "nickname":user.nickname,
                "game_category": game_category,
                "user_tech": user_tech,
                "is_maker": is_maker,
            },
        }, status=status.HTTP_201_CREATED)


@api_view(('GET',))
@renderer_classes((JSONRenderer,))
def google_login_callback(request):
    # Authorization code를 token으로 전환
    try:
        authorization_code = request.META.get('HTTP_AUTHORIZATION')
        url = "https://oauth2.googleapis.com/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "code": authorization_code,
            "client_id": config.GOOGLE_AUTH["client_id"],
            "client_secret": config.GOOGLE_AUTH["client_secret"],
            "redirect_uri": config.GOOGLE_AUTH["redirect_uri"],
            "grant_type": "authorization_code"
        }
        tokens_request = requests.post(url, headers=headers, data=data)
        tokens_json = tokens_request.json()
    except Exception as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # token 유효성 확인 및 로그인 진행, 유저 정보 전달
    try:
        id_token = tokens_json["id_token"]
        profile_request = requests.get(f'https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={id_token}')
        profile_json = profile_request.json()

        username = profile_json.get('name', None)
        email = profile_json.get('email', None)
        
        return social_signinup(email=email, username=username, provider="구글")
    except AlertException as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_406_NOT_ACCEPTABLE)
    except TokenException as e:
        print(e)
        # 개발 단계에서 확인
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

@api_view(('GET',))
@renderer_classes((JSONRenderer,))
def naver_login_callback(request):
    try:
        authorization_code = request.META.get('HTTP_AUTHORIZATION')
        url = "https://nid.naver.com/oauth2.0/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": config.NAVER_AUTH["client_id"],
            "client_secret": config.NAVER_AUTH["client_secret"],
            "code": authorization_code,
            "state": config.NAVER_AUTH["state"],
        }
        tokens_request = requests.get(url, params=data)
        tokens_json = tokens_request.json()
    except Exception as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        access_token = tokens_json["access_token"]
        url = "https://openapi.naver.com/v1/nid/me"
        headers = {
            "Authorization": "Bearer " + access_token,
        }
        profile_request = requests.get(url, headers=headers)
        profile_json = profile_request.json().get("response", None)

        username = profile_json.get('name', None)
        email = profile_json.get('email', None)
        
        return social_signinup(email=email, username=username, provider="네이버")
    except AlertException as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_406_NOT_ACCEPTABLE)
    except TokenException as e:
        print(e)
        # 개발 단계에서 확인
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(('GET',))
@renderer_classes((JSONRenderer,))
def kakao_login_callback(request):
    # Authorization code를 token으로 전환
    try:
        authorization_code = request.META.get('HTTP_AUTHORIZATION')
        url = "https://kauth.kakao.com/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        data = {
            "code": authorization_code,
            "client_id": config.KAKAO_AUTH["client_id"],
            "redirect_uri": config.KAKAO_AUTH["redirect_uri"],
            "grant_type": "authorization_code"
        }
        tokens_request = requests.post(url, headers=headers, data=data)
        tokens_json = tokens_request.json()
    except Exception as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # token 유효성 확인 및 로그인 진행, 유저 정보 전달
    try:
        access_token = tokens_json["access_token"]
        url = "https://kapi.kakao.com/v2/user/me"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Authorization": "Bearer " + access_token,
        }
        profile_request = requests.get(url, headers=headers)
        profile_json = profile_request.json()
        
        account = profile_json.get('kakao_account', None)
        username = account["profile"]["nickname"]
        email = account["email"]
        
        return social_signinup(email=email, username=username, provider="카카오")
    except AlertException as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_406_NOT_ACCEPTABLE)
    except TokenException as e:
        print(e)
        # 개발 단계에서 확인
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(('GET',))
@renderer_classes((JSONRenderer,))
def discord_login_callback(request):
    # Authorization code를 token으로 전환
    try:
        authorization_code = request.META.get('HTTP_AUTHORIZATION')
        url = "https://discord.com/api/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "code": authorization_code,
            "client_id": config.DISCORD_AUTH["client_id"],
            "client_secret": config.DISCORD_AUTH["client_secret"],
            "redirect_uri": config.DISCORD_AUTH["redirect_uri"],
            "grant_type": "authorization_code",
            "scope": 'identify, email',
        }
        tokens_request = requests.post(url, headers=headers, data=data)
        tokens_json = tokens_request.json()
    except Exception as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # token 유효성 확인 및 로그인 진행, 유저 정보 전달
    try:
        access_token = tokens_json["access_token"]
        url = "https://discordapp.com/api/users/@me"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Authorization": "Bearer " + access_token,
        }
        profile_request = requests.get(url, headers=headers)
        profile_json = profile_request.json()
        
        username = profile_json.get('username', None)
        email = profile_json.get('email', None)
        
        return social_signinup(email=email, username=username, provider="디스코드")
    except AlertException as e:
        print(e)
        messages.error(request, e)
        # 유저에게 알림
        return Response({'message': str(e)}, status=status.HTTP_406_NOT_ACCEPTABLE)
    except TokenException as e:
        print(e)
        # 개발 단계에서 확인
        return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# 회원가입 또는 로그인을 처리하는 함수
def social_signinup(email, username, provider=''):
    try:
        user = get_user_model().objects.get(email=email)
    except get_user_model().DoesNotExist:
        user = None
    if user is None:
        return Response({"message": "회원가입 페이지로 이동", "username": username, "email": email})

    token = RefreshToken.for_user(user)
    data = {
        'user': user,
        'access': str(token.access_token),
        'refresh': str(token),
    }
    serializer = JWTSerializer(data)
    return Response({'message': f'{provider} 로그인 성공', **serializer.data}, status=status.HTTP_200_OK)


# ---------- Web---------- #
def login_page(request):
    return render(request, 'accounts/login.html')


def signup_page(request):
    return render(request, 'accounts/signup.html')
