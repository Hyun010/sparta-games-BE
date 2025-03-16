# [sparta-games.net](https://www.sparta-games.net)(배포 주소)
🕹️ SpartaGames – 게임 관리 및 추천 시스템

## 페이지 이용 안내
Unity 2D를 사용하여 게임을 제작하고 이를 업로드 및 관리할 수 있는 사이트

- 누구나 게임을 플레이할 수 있습니다.
- 게임을 업로드할 땐, 로그인이 필요합니다.
- 리뷰를 남기며 게임 발전에 기여합니다.
- 회원탈퇴는 문의를 남겨주세요.

## 개요
 
### 주요 기능
- Unity의 WebGL 빌드 파일을 사이트에 업로드하고 이를 플레이할 수 있는 서비스를 제공
- 유저가 플레이하고 싶은 게임을 추천해줄 수 있는 대화형 추천 서비스 기능 제공

### 컨셉 및 목표
- 주니어 게임 개발자의 공간 제공
- 유저로부터 피드백
- 한글화된 사이트를 서비스
- 협업 기능을 제공, 주니어 개발자들의 커뮤니티 형성에 도움

## 개발 기간
- 2024-05-08 ~ 진행중


## ERD
![ERD (1)](https://github.com/creative-darkstar/sparta-games/assets/75594057/a8d7f6a7-9782-4cc0-af33-1c81b92129c6)

<br>

## Service Architecture(수정 필요->프론트 분리)

![339234770-3fa8fb1e-d104-4807-9d76-fb7cbb810840](https://github.com/creative-darkstar/sparta-games/assets/75594057/a6696e14-4c07-491d-b8dd-a191bea3ea49)

<br>

## API 명세


## 역할 분담

- **박성현(나)**: PM(서기), 기능(Games, Qnas 위주) 구현, 사용자 맞춤 태그 추천 서비스, Celery를 통한 비동기 시스템 구축

- 정해진: 전체 일정 조정, 기능(Users, Accounts 위주) 구현, AWS 구조 구축

- 전관: 유효성 검증 등 기능 정밀화, 기능(Games, Qnas 위주) 구현, 사용자 맞춤 태그 추천 서비스

## 사용하는 기술
- Python
- Python Django
- Python Django Rest Framework
- AWS
  - EC2
  - RDS(PostgreSQL)
  - S3
  - Route53
  - ACM
- gunicorn
- Nginx
- Celery + Redis
- JWT (SimpleJWT)


## 설치 필요 패키지
- requirements.txt에 명시
- `pip install -r requirements.txt` 로 설치
