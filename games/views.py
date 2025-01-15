import re

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny  # 로그인 인증토큰
from rest_framework import status
from rest_framework.decorators import permission_classes

from games.pagination import CategoryGamesPagination, ReviewPagination

from .models import (
    Chip,
    Game,
    Like,
    View,
    Review,
    Screenshot,
    GameCategory,
    ReviewsLike,
    PlayLog,
    TotalPlayTime,
)
from accounts.models import BotCnt
from .serializers import (
    GameListSerializer,
    GameDetailSerializer,
    ReviewSerializer,
    ScreenshotSerializer,
    CategorySerailizer,
)

from django.conf import settings
from openai import OpenAI
from django.utils import timezone
from spartagames.pagination import ReviewCustomPagination
import random
from urllib.parse import urlencode
from .utils import assign_chip_based_on_difficulty

class GameListAPIView(APIView):
    """
    포스트일 때 로그인 인증을 위한 함수
    """

    def get_permissions(self):  # 로그인 인증토큰
        permissions = super().get_permissions()

        if self.request.method.lower() == 'post':  # 포스트할때만 로그인
            permissions.append(IsAuthenticated())

        return permissions

    """
    게임 목록 조회
    """

    def get(self, request):
        order = request.query_params.get('order')
        new_game_chip = Chip.objects.filter(name="New Game").first()
        limit = int(request.query_params.get('limit', 4))
        categories = list(GameCategory.objects.all().values_list('name',flat=True))
        if not categories:
            return Response({"message": "카테고리가 존재하지 않는다. 카테고리 생성이 필요하다"}, status=status.HTTP_404_NOT_FOUND)
        if len(categories) < 3:
            return Response({"message": "카테고리가 2개 이하입니다. 카테고리가 최소 3개 필요합니다."}, status=status.HTTP_404_NOT_FOUND)
        selected_categories = random.sample(categories, 3)
        
        rand1 = Game.objects.filter(is_visible=True, register_state=1,category__name=selected_categories[0])[:limit]
        rand2 = Game.objects.filter(is_visible=True, register_state=1,category__name=selected_categories[1])[:limit]
        rand3 = Game.objects.filter(is_visible=True, register_state=1,category__name=selected_categories[2])[:limit]
        favorites = Game.objects.filter(chip__name="Daily Top",is_visible=True, register_state=1)[:limit]
        if new_game_chip:
            recent_games = Game.objects.filter(chip=new_game_chip, is_visible=True, register_state=1)[:limit]
        else:
            recent_games = Game.objects.none()  # new_game 칩이 없으면 빈 QuerySet

        # 2024-12-30 FE 요청으로 games/api/list 에서 게임팩 삭제, users/api/<int:user_pk>/gamepacks/ 로 이관
        # # 유저 존재 시 my_game_pack 추가
        # my_game_pack = None
        # if request.user.is_authenticated:
        #     # 1. 즐겨찾기한 게임
        #     liked_games = Game.objects.filter(likes__user=request.user, is_visible=True, register_state=1).order_by('-created_at')[:4]
        #     # 2. 최근 플레이한 게임
        #     recently_played_games = Game.objects.filter(is_visible=True, register_state=1,totalplaytime__user=request.user).order_by('-totalplaytime__latest_at').distinct()
            
        #     # 좋아요한 게임과 최근 플레이한 게임을 조합하여 최대 4개의 게임으로 구성
        #     liked_games_count = liked_games.count()
        #     if liked_games_count < 4:
        #         additional_recent_games = recently_played_games[:4 - liked_games_count]
        #         combined_games = list(liked_games) + list(additional_recent_games)
        #     else:
        #         combined_games = liked_games  # 좋아요한 게임만으로 4개가 이미 채워짐

        #     # my_game_pack 설정
        #     if combined_games:
        #         my_game_pack = GameListSerializer(combined_games, many=True, context={'user': request.user}).data
        #     else:
        #         my_game_pack = [{"message": "게임이 없습니다."}]
        # else:
        #     my_game_pack = [{"message": "사용자가 인증되지 않았습니다."}]

        # 추가 옵션 정렬
        """ if order == 'new':
            rows = rows.order_by('-created_at')
        elif order == 'view':
            rows = rows.order_by('-view_cnt')
        elif order == 'star':
            rows = rows.order_by('-star')
        else:
            rows = rows.order_by('-created_at') """

        # 시리얼라이저 및 데이터 확인
        serializer = GameListSerializer(rand1, many=True, context={'user': request.user})
        serializer2 = GameListSerializer(rand2, many=True, context={'user': request.user})
        serializer3 = GameListSerializer(rand3, many=True, context={'user': request.user})
        favorite_serializer = GameListSerializer(favorites, many=True, context={'user': request.user}).data if favorites.exists() else []
        recent_serializer = GameListSerializer(recent_games, many=True, context={'user': request.user}).data if recent_games.exists() else []

        # 응답 데이터 구성
        data = {
            "rand1": {
                "category_name": selected_categories[0],
                "game_list": serializer.data if rand1.exists() else []
            },
            "rand2": {
                "category_name": selected_categories[1],
                "game_list": serializer2.data if rand2.exists() else []
            },
            "rand3": {
                "category_name": selected_categories[2],
                "game_list": serializer3.data if rand3.exists() else []
            },
            "trending_games": favorite_serializer,
            "recent": recent_serializer,
        }
        # 2024-12-30 FE 요청으로 games/api/list 에서 게임팩 삭제, users/api/<int:user_pk>/gamepacks/ 로 이관
        # if request.user.is_authenticated:
        #     data["my_game_pack"] = my_game_pack
        return Response(data, status=status.HTTP_200_OK)


    """
    게임 등록
    """

    def post(self, request):
        # 필수 항목 확인
        required_fields = ["title", "category", "content", "gamefile"]
        missing_fields = [field for field in required_fields if not request.data.get(field)]

        # 누락된 필수 항목이 있을 경우 에러 메시지 반환
        if missing_fields:
            return Response(
                {"error": f"필수 항목이 누락되었습니다: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        category_data = request.data.get('category')
        invalid_categories = []
        valid_categories = []

        if category_data:
            for item in category_data.split(','):
                try:
                    category = GameCategory.objects.get(name=item)
                    valid_categories.append(category)  # 유효한 카테고리만 추가
                except GameCategory.DoesNotExist:
                    invalid_categories.append(item)

        # 잘못된 카테고리가 있는 경우 오류 메시지 반환
        if invalid_categories:
            return Response(
                {"message": f"다음 카테고리는 존재하지 않습니다: {', '.join(invalid_categories)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Game model에 우선 저장
        game = Game.objects.create(
            title=request.data.get('title'),
            thumbnail=request.FILES.get('thumbnail'),
            youtube_url=request.data.get('youtube_url'),
            maker=request.user,
            content=request.data.get('content'),
            gamefile=request.FILES.get('gamefile'),
            base_control=request.data.get('base_control'),
            release_note=request.data.get('release_note'),
            star=0,
            review_cnt=0,
        )

        for category in valid_categories:
            game.category.add(category)

        new_game_chip, created = Chip.objects.get_or_create(name="New Game")
        game.chip.add(new_game_chip)

        # 기본 'NORMAL' 칩 추가
        normal_chip, _ = Chip.objects.get_or_create(name="NORMAL")
        game.chip.add(normal_chip)

        # 이후 Screenshot model에 저장
        screenshots = list()
        for item in request.FILES.getlist("screenshots"):
            screenshot = Screenshot.objects.create(
                src=item,
                game=game
            )
            screenshots.append(screenshot.src.url)

        # 게임 등록 로그에 데이터 추가
        game.logs_game.create(
            recoder = request.user,
            maker = request.user,
            game = game,
            content = "검수요청",
        )
        
        return Response({"message": "게임업로드 성공했습니다"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])  # 인증이 필요할 경우 IsAuthenticated로 변경 가능
def game_list_search(request):
    keyword = request.query_params.get('keyword')

    # 기본 필터 조건
    query = Q(is_visible=True, register_state=1)

    # 키워드 조건 추가
    if keyword:
        query &= Q(
            Q(category__name__icontains=keyword) |
            Q(title__icontains=keyword) |
            Q(maker__nickname__icontains=keyword)
        )

    # 게임 목록 필터링
    games = Game.objects.filter(query).distinct().order_by('-created_at')

    # 즐겨찾기 분리
    favorite_games = []
    if request.user.is_authenticated:
        favorite_games = games.filter(likes__user=request.user)
        favorite_cnt=len(favorite_games)
        if favorite_games:
            games = games.exclude(pk__in=favorite_games.values_list('pk', flat=True))
    all_games = list(favorite_games) + list(games)
    if all_games==[]:
        return Response({"message": "게임이 없습니다."}, status=404)
    # 페이지네이션 처리
    paginator = ReviewCustomPagination()
    paginated_games = paginator.paginate_queryset(all_games, request)

    # 직렬화
    game_serializer = GameListSerializer(paginated_games, many=True, context={'user': request.user})

    # 응답 데이터 구성
    response_data = paginator.get_paginated_response(game_serializer.data).data

    # 1페이지일 경우 즐겨찾기 게임 추가
    if request.user.is_authenticated:
        if paginator.page.number == 1 and favorite_games.exists():
            all_games=response_data["results"]["all_games"]
            list_of_games=[]
            for i in range(favorite_cnt):
                list_of_games.append(all_games.pop(i))
                all_games.insert(0,{})
            response_data["results"]["favorite_games"]=list_of_games

    return Response(response_data)

@api_view(['GET'])
@permission_classes([AllowAny])
def category_games_list(request):
    """
    특정 카테고리에 속하는 게임 목록을 페이지네이션하여 반환하는 API.
    URL: /api/list/categories/?category=<category_name>&page=<page_number>&limit=<page_size>
    """
    category_name = request.query_params.get('category', None)
    
    if not category_name:
        return Response(
            {"error": "category 파라미터가 필요합니다."},
            status=400
        )
    
    # 카테고리 존재 여부 확인
    category = get_object_or_404(GameCategory, name=category_name)
    
    # 해당 카테고리에 속하는 게임 필터링
    games = Game.objects.filter(
        category=category,
        is_visible=True,
        register_state=1
    ).order_by('-created_at')  # 최신순 정렬

    if not games.exists():
        return Response(
            {"message": f"카테고리 '{category_name}'에 맞는 게임이 없습니다."},
            status=404  # Not Found
        )
    
    # 페이지네이션 적용
    paginator = CategoryGamesPagination()
    paginated_games = paginator.paginate_queryset(games, request)
    serializer = GameListSerializer(paginated_games, many=True, context={'user': request.user})
    
    return paginator.get_paginated_response(serializer.data)


class GameDetailAPIView(APIView):
    """
    포스트일 때 로그인 인증을 위한 함수
    """

    def get_permissions(self):  # 로그인 인증토큰
        permissions = super().get_permissions()

        if self.request.method.lower() == ('put' or 'delete'):  # 포스트할때만 로그인
            permissions.append(IsAuthenticated())

        return permissions

    def get_object(self, game_pk):
        return get_object_or_404(Game, pk=game_pk, is_visible=True)

    """
    게임 상세 조회
    """

    def get(self, request, game_pk):
        game = self.get_object(game_pk)

        serializer = GameDetailSerializer(game, context={'user': request.user})
        # data에 serializer.data를 assignment
        # serializer.data의 리턴값인 ReturnDict는 불변객체이다
        data = serializer.data

        screenshots = Screenshot.objects.filter(game_id=game_pk)
        screenshot_serializer = ScreenshotSerializer(screenshots, many=True)

        categories = game.category.all()
        category_serializer = CategorySerailizer(categories, many=True)

        data["screenshot"] = screenshot_serializer.data
        data['category'] = category_serializer.data

        return Response(data, status=status.HTTP_200_OK)

    """
    게임 수정
    """

    def put(self, request, game_pk):
        game = self.get_object(game_pk)

        # 작성한 유저이거나 관리자일 경우 동작함
        if game.maker == request.user or request.user.is_staff == True:
            if request.FILES.get("gamefile"):  # 게임파일을 교체할 경우 검수페이지로 이동
                game.register_state = 0
                game.gamefile = request.FILES.get("gamefile")
            game.title = request.data.get("title", game.title)
            game.thumbnail = request.FILES.get("thumbnail", '')
            game.youtube_url = request.data.get(
                "youtube_url", game.youtube_url)
            game.content = request.data.get("content", game.content)
            game.base_control = request.data.get(
                'base_control', game.base_control),
            game.release_note = request.data.get(
                'release_note', game.release_note),
            game.save()

            category_data = request.data.get('category')
            if category_data is not None:  # 태그가 바뀔 경우 기존 태그를 초기화, 신규 태그로 교체
                game.category.clear()
                categories = [GameCategory.objects.get_or_create(name=item.strip())[
                    0] for item in category_data.split(',') if item.strip()]
                game.category.set(categories)

            # 기존 데이터 삭제
            pre_screenshots_data = Screenshot.objects.filter(game=game)
            pre_screenshots_data.delete()

            # 받아온 스크린샷으로 교체
            if request.data.get('screenshots'):
                for item in request.FILES.getlist("screenshots"):
                    game.screenshots.create(src=item)
            
            # 게임 파일 수정인 경우 게임 등록 로그에 데이터 추가
            if game.register_state == 0:
                game.logs_game.create(
                    recoder = request.user,
                    maker = request.user,
                    game = game,
                    content = "수정 후 검수요청",
                )
            # 그 외의 항목이 수정됐을 경우 게임 등록 로그에 데이터 추가
            # 추후 작업 예정
            # else:
            #     game.logs_game.create(
            #         recoder = request.user,
            #         maker = request.user,
            #         game = game,
            #         content = "수정",
            #     )
            
            return Response({"messege": "수정이 완료됐습니다"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "작성자가 아닙니다"}, status=status.HTTP_400_BAD_REQUEST)

    """
    게임 삭제
    """

    def delete(self, request, game_pk):
        game = self.get_object(game_pk)

        # 작성한 유저이거나 관리자일 경우 동작함
        if game.maker == request.user or request.user.is_staff == True:
            game.is_visible = False
            game.save()
            
            # 게임 삭제 시 게임 등록 로그에 데이터 추가
            game.logs_game.create(
                recoder = request.user,
                maker = request.user,
                game = game,
                content = "삭제",
            )
            return Response({"message": "삭제를 완료했습니다"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "작성자가 아닙니다"}, status=status.HTTP_400_BAD_REQUEST)


class GameLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, game_pk):
        game = get_object_or_404(Game, pk=game_pk)
        like_instance = Like.objects.filter(user=request.user, game=game).first()
        if like_instance:
            # 수정
            like_instance.delete()
            return Response({'message': "즐겨찾기 취소"}, status=status.HTTP_200_OK)
        else:
            # 생성
            Like.objects.create(user=request.user, game=game)
            return Response({'message': "즐겨찾기"}, status=status.HTTP_200_OK)


# class GameStarAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, game_pk):
#         star_list = [1,2,3,4,5]
#         star = int(request.data['star'])
#         if star not in star_list:
#             star = 5
#         game = get_object_or_404(Game, pk=game_pk)
#         if game.stars.filter(user=request.user).exists():
#             # 수정
#             game.stars.filter(user=request.user).update(
#                 star=star)
#         else:
#             # 생성
#             Star.objects.create(
#                 star=star,
#                 user=request.user,
#                 game=game,
#             )
#         star_values=[item['star'] for item in game.stars.values()]
#         average_star = round(sum(star_values) / len(star_values),1)
#         return Response({"res":"ok","avg_star":average_star}, status=status.HTTP_200_OK)


class ReviewAPIView(APIView):
    def get_permissions(self):  # 로그인 인증토큰
        permissions = super().get_permissions()

        if self.request.method.lower() == 'post':  # 포스트할때만 로그인
            permissions.append(IsAuthenticated())

        return permissions

    def get(self, request, game_pk):
        order = request.query_params.get('order', 'new')  # 기본값 'new'

        # 모든 리뷰 가져오기
        reviews = Review.objects.filter(game=game_pk, is_visible=True)

        # 로그인 상태에서 내 리뷰 추출
        my_review = None
        if request.user.is_authenticated:
            my_review = reviews.filter(author=request.user).first()
            if my_review:
                reviews = reviews.exclude(pk=my_review.pk)  # 내 리뷰 제외

        # 정렬 조건 적용
        if order == 'likes':
            reviews = reviews.annotate(
                like_count=Count('reviews', filter=Q(reviews__is_like=1))
            ).order_by('-like_count', '-created_at')
        elif order == 'dislikes':
            reviews = reviews.annotate(
                dislike_count=Count('reviews', filter=Q(reviews__is_like=2))
            ).order_by('-dislike_count', '-created_at')
        else:
            reviews = reviews.order_by('-created_at')  # 최신순

        # `my_review`를 포함한 쿼리셋 생성
        if my_review:
            all_reviews = [my_review] + list(reviews)
        else:
            all_reviews = list(reviews)

        # 페이지네이션 처리
        paginator = ReviewPagination()
        paginated_reviews = paginator.paginate_queryset(all_reviews, request, self)

        if paginated_reviews is None:
            return Response({"message": "리뷰가 없습니다."}, status=404)

        # 직렬화
        serializer = ReviewSerializer(paginated_reviews, many=True, context={'user': request.user})

        # 페이징 결과 직렬화
        response_data=paginator.get_paginated_response(serializer.data).data
        # 1페이지일 때만 `my_review` 추가
        # 1페이지일 경우 my_review를 처리
        if paginator.page.number == 1 and my_review:
            all_reviews = response_data["results"]["all_reviews"]
            response_data["results"]["my_review"] = all_reviews.pop(0)
            all_reviews.insert(0,{})

        return Response(response_data) 

    def post(self, request, game_pk):
        game = get_object_or_404(Game, pk=game_pk)  # game 객체를 올바르게 설정

        # 이미 리뷰를 작성한 사용자인 경우 등록 거부
        if game.reviews.filter(author__pk=request.user.pk, is_visible=True).exists():
            return Response({"message": "이미 리뷰를 등록한 사용자입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 별점 계산
        game.star = game.star + \
            ((request.data.get('star')-game.star)/(game.review_cnt+1))
        game.review_cnt = game.review_cnt+1
        game.save()

        serializer = ReviewSerializer(
            data=request.data, context={'user': request.user})
        if serializer.is_valid(raise_exception=True):
            serializer.save(author=request.user, game=game)  # 데이터베이스에 저장
            assign_chip_based_on_difficulty(game)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewDetailAPIView(APIView):
    def get_permissions(self):  # 로그인 인증토큰
        permissions = super().get_permissions()

        if self.request.method.lower() == ('put' or 'delete'):  # 포스트할때만 로그인
            permissions.append(IsAuthenticated())

        return permissions

    def get(self, request, review_id):
        try:
        # 리뷰가 존재하고, is_visible이 True인 경우만 가져옴
            review = Review.objects.get(pk=review_id, is_visible=True)
        except Review.DoesNotExist:
            # 리뷰가 존재하지 않으면 404 응답과 함께 메시지 반환
            return Response({"message": "상세 평가 기록이 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReviewSerializer(review, context={'user': request.user})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, review_id):
        try:
            # 리뷰가 존재하고, is_visible이 True인 경우에만 가져옴
            review = get_object_or_404(Review, pk=review_id, is_visible=True)
        except Http404:
            # 리뷰가 없을 경우 사용자에게 메시지와 함께 404 응답 반환
            return Response({"message": "리뷰가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        # 작성한 유저이거나 관리자일 경우 동작함
        if request.user == review.author or request.user.is_staff == True:
            game_pk = request.data.get('game_pk')
            game = get_object_or_404(Game, pk=game_pk)  # game 객체를 올바르게 설정
            game.star = game.star + \
                ((request.data.get('star')-request.data.get('pre_star'))/(game.review_cnt))
            game.save()
            serializer = ReviewSerializer(
                review, data=request.data, partial=True, context={'user': request.user})
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                assign_chip_based_on_difficulty(review.game)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "작성자가 아닙니다"}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, review_id):
        try:
            # 리뷰가 존재하고, is_visible이 True인 경우에만 가져옴
            review = get_object_or_404(Review, pk=review_id, is_visible=True)
        except Http404:
            # 리뷰가 없을 경우 사용자에게 메시지와 함께 404 응답 반환
            return Response({"message": "리뷰가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        # 작성한 유저이거나 관리자일 경우 동작함
        if request.user == review.author or request.user.is_staff == True:
            game_pk = request.data.get('game_pk')
            game = get_object_or_404(Game, pk=game_pk)  # game 객체를 올바르게 설정
            if game.review_cnt > 1:
                game.star = game.star + \
                    ((game.star-review.star)/(game.review_cnt-1))
            else:
                game.star = 0
            game.review_cnt = game.review_cnt-1
            game.save()
            review.is_visible = False
            review.save()
            assign_chip_based_on_difficulty(review.game)
            return Response({"message": "삭제를 완료했습니다"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "작성자가 아닙니다"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def toggle_review_like(request, review_id):
    """
    리뷰에 좋아요/싫어요 동작
    """
    user = request.user
    try:
        # 리뷰가 존재하고, is_visible이 True인 경우에만 가져옴
        review = get_object_or_404(Review, pk=review_id, is_visible=True)
    except Http404:
        # 리뷰가 없을 경우 사용자에게 메시지와 함께 404 응답 반환
        return Response({"message": "리뷰가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)
    # ReviewsLike 객체를 가져오거나 새로 생성
    # get_or_create 리턴: review_like - ReviewsLike 객체(행), _ - 행 생성 여부
    review_like, _ = ReviewsLike.objects.get_or_create(
        user=user, review=review)

    # 요청에서 받은 'action'에 따라 상태 변경
    action = request.data.get('action', None)
    if action == 'like':
        if review_like.is_like != 1:  # 현재 상태가 'like'가 아니면 'like'로 변경
            review_like.is_like = 1
        else:
            # 이미 'like' 상태일 경우 'no state'로 전환
            review_like.is_like = 0
    elif action == 'dislike':
        if review_like.is_like != 2:  # 현재 상태가 'dislike'가 아니면 'dislike'로 변경
            review_like.is_like = 2
        else:
            # 이미 'dislike' 상태일 경우 'no state'로 전환
            review_like.is_like = 0

    review_like.save()  # 변경 사항 저장
    return Response({"message": f"리뷰(id: {review_id})에 {review_like.is_like} 동작을 수행했습니다."}, status=status.HTTP_200_OK)


class CategoryAPIView(APIView):
    def get_permissions(self):  # 로그인 인증토큰
        permissions = super().get_permissions()

        if self.request.method.lower() == ('post' or 'delete'):  # 포스트할때만 로그인
            permissions.append(IsAuthenticated())

        return permissions
    
    def get(self, request):
        categories = GameCategory.objects.all()
        serializer = CategorySerailizer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.is_staff is False:
            return Response({"error": "권한이 없습니다"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CategorySerailizer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            category=request.data.get("name")
            return Response({"message": f"태그({category})를 추가했습니다"}, status=status.HTTP_200_OK)

    def delete(self, request):
        if request.user.is_staff is False:
            return Response({"error": "권한이 없습니다"}, status=status.HTTP_400_BAD_REQUEST)
        category = get_object_or_404(GameCategory, pk=request.data['pk'])
        category.delete()
        return Response({"message": "삭제를 완료했습니다"}, status=status.HTTP_200_OK)


class GamePlaytimeAPIView(APIView):
    def get(self, request, game_pk):
        # 로그인 여부 확인
        if request.user.is_authenticated is False:
            return Response({"error": "로그인이 필요합니다."}, status=status.HTTP_401_UNAUTHORIZED)
        if Game.objects.filter(pk=game_pk, is_visible=True).exists():
            playtime = PlayLog.objects.create(
                user=request.user,
                game=get_object_or_404(Game, pk=game_pk, is_visible=True),
                start_at=timezone.now()  # 현재 시간으로 start_time
            )
            playtime_pk = playtime.pk
            return Response({"message": "게임 플레이 시작시간 기록을 성공했습니다.", "playtime_pk":playtime_pk}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "게임이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, game_pk):
        # 로그인 여부 확인
        if request.user.is_authenticated is False:
            return Response({"error": "로그인이 필요합니다."}, status=status.HTTP_401_UNAUTHORIZED)
        if Game.objects.filter(pk=game_pk, is_visible=True).exists():
            game=get_object_or_404(Game, pk=game_pk, is_visible=True)
            playlog = get_object_or_404(PlayLog, pk=request.data.get("playtime_pk"))
            totalplaytime,_ = TotalPlayTime.objects.get_or_create(user=request.user, game=game)

            playlog.end_at = timezone.now()  # 현재 시간으로 end_time
            totalplaytime.latest_at = timezone.now()

            totaltime = (playlog.end_at - playlog.start_at).total_seconds()
            playlog.playtime = totaltime  # playtime_seconds로 playtime_seconds 계산
            totalplaytime.totaltime = totalplaytime.totaltime + totaltime

            playlog.save()
            totalplaytime.save()
            return Response({"message": "게임 플레이 종료시간 기록을 성공했습니다.", 
                            "start_time":playlog.start_at,
                            "end_time":playlog.end_at,
                            "playtime": playlog.playtime,
                            "totalplaytime":totalplaytime.totaltime}
                            , status=status.HTTP_200_OK)
        else:
            return Response({"error": "게임이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)


CLIENT = OpenAI(api_key=settings.OPEN_API_KEY)
MAX_USES_PER_DAY = 10  # 하루 당 질문 10개로 제한기준

# chatbot API

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ChatbotAPIView(request):
    user = request.user
    today = timezone.now().date()

    usage, created = BotCnt.objects.get_or_create(user=user, date=today)

    if usage.count >= MAX_USES_PER_DAY:
        return Response({"error": "Daily usage limit reached"}, status=status.HTTP_400_BAD_REQUEST)

    usage.count += 1
    usage.save()

    input_data = request.data.get('input_data')
    categorylist = list(GameCategory.objects.values_list('name', flat=True))

    # GPT API와 통신을 통해 답장을 받아온다.(아래 형식을 따라야함)(추가 옵션은 문서를 참고)
    instructions = f"""
    내가 제한한 카테고리 목록 : {categorylist} 여기서만 이야기를 해줘, 이외에는 말하지마
    받은 내용을 요약해서 내가 제한한 목록에서 제일 관련 있는 항목 한 개를 골라줘
    결과 형식은 다른 말은 없이 꾸미지도 말고 딱! '카테고리:'라는 형식으로만 작성해줘
    결과에 특수문자, 이모티콘 붙이지마
    """
    completion = CLIENT.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": f"받은 내용: {input_data}"},
        ],
    )

    # 응답받은 데이터 처리
    gpt_response = completion.choices[0].message.content
    about_category = gpt_response.split('태그:')[1]
    about_category = re.sub(
        '[-=+,#/\?:^.@*\"※~ㆍ!』‘|\(\)\[\]`\'…》\”\“\’·]', '', about_category)
    about_category = about_category.strip()
    uncategorylist = ['없음', '']
    if about_category in uncategorylist:
        about_category = '없음'
    return Response({"category": about_category}, status=status.HTTP_200_OK)


# ---------- Web ---------- #


# # 게임 등록 Api 테스트용 페이지 렌더링
# def game_detail_view(request, game_pk):
#     return render(request, "games/game_detail.html", {'game_pk': game_pk})


# # 테스트용 base.html 렌더링
# def test_base_view(request):
#     return render(request, "base.html")


# # 테스트용 메인 페이지 렌더링
# def main_view(request):
#     return render(request, "games/main.html")


# # 테스트용 검색 페이지 렌더링
# def search_view(request):
#     # 쿼리스트링을 그대로 가져다가 '게임 목록 api' 호출
#     return render(request, "games/search.html")


# # 게임 검수용 페이지 뷰
# def admin_list(request):
#     rows = Game.objects.filter(is_visible=True, register_state=0)
#     return render(request, "games/admin_list.html", context={"rows": rows})


# def admin_category(request):
#     categories = GameCategory.objects.all()
#     return render(request, "games/admin_tags.html", context={"categories": categories})


# def game_create_view(request):
#     return render(request, "games/game_create.html")


# def game_update_view(request, game_pk):
#     return render(request, "games/game_update.html", {'game_pk': game_pk})


# def chatbot_view(request):
#     return render(request, "games/chatbot.html")
