from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import jwt
from functools import wraps
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
import logging
from logstash_formatter import LogstashFormatterV1
import logstash 


app = Flask(__name__)
CORS(app, supports_credentials=True, origins=['http://localhost:3000'])  # CORS 지원 추가

# 시크릿 키 설정 (실제 환경에서는 안전하게 관리되어야 합니다)
app.config['SECRET_KEY'] = 'your_secret_key'

# 토큰 만료 시간 설정
app.config['TOKEN_EXPIRATION'] = timedelta(hours=1)

# MySQL 데이터베이스 연결 설정
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://heal_user:heal_password@db:3306/heal_db?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)


# Flask JSON 인코더 커스터마이징
class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ensure_ascii = False  # JSON 응답에서 한글 깨짐 방지

app.json_encoder = CustomJSONEncoder

# 로깅 설정
logger = logging.getLogger('flask_app')
logger.setLevel(logging.INFO)

# Logstash 핸들러 수정된 포맷터 클래스 정의
class FixedLogstashFormatterV1(LogstashFormatterV1):
    def format(self, record):
        message = super().format(record)
        if isinstance(message, str):  # bytes를 str로 변환
            return message.encode('utf-8')
        return message

# Logstash Formatter 핸들러 추가(stdout 출력용)
stream_handler = logging.StreamHandler()  # 로그를 스트림(표준 출력)으로 출력
stream_handler.setFormatter(LogstashFormatterV1())  # LogstashFormatterV1 사용
stream_handler.setLevel(logging.INFO)  # 로그 레벨 설정
logger.addHandler(stream_handler)

# Logstash 핸들러 추가
# logstash_host = app.config.get('LOGSTASH_HOST', 'logstash')
# logstash_port = int(app.config.get('LOGSTASH_PORT', 5044))

logstash_host = 'logstash'  # 또는 Logstash 서버의 IP 주소
logstash_port = 5044

try:
    logstash_handler = logstash.TCPLogstashHandler(logstash_host, logstash_port, version=1)
    logstash_handler.setFormatter(FixedLogstashFormatterV1())
    logstash_handler.setLevel(logging.INFO)  # 로그 레벨 설정

    # 중복 방지를 위해 기존 핸들러 제거
    logger.handlers = [h for h in logger.handlers if not isinstance(h, logstash.TCPLogstashHandler)]
    logger.addHandler(logstash_handler)

    # Logstash 핸들러 초기화 확인 로그
    logger.info("Flask app started with Logstash handler")
    logger.debug(f"Logstash handler initialized with host={logstash_host}, port={logstash_port}")

except Exception as e:
    logger.error(f"Failed to initialize Logstash handler: {e}")

# Werkzeug Logger 수정
flask_logger = logging.getLogger('werkzeug')
flask_logger.handlers = [h for h in flask_logger.handlers if not isinstance(h, logstash.TCPLogstashHandler)]
flask_logger.addHandler(stream_handler)  # stdout만 기록
flask_logger.setLevel(logging.INFO)

# # Flask의 기본 로거에도 Logstash 핸들러 추가
# flask_logger = logging.getLogger('werkzeug')
# flask_logger.addHandler(logstash_handler)
# flask_logger.setLevel(logging.INFO)


# logstash_handler = logstash.TCPLogstashHandler(logstash_host, logstash_port, version=1)
# logstash_handler.setFormatter(LogstashFormatterV1())
# logger.addHandler(logstash_handler)


# # Logstash 핸들러 추가
# logstash_host = app.config.get('LOGSTASH_HOST', 'logstash')
# logstash_port = int(app.config.get('LOGSTASH_PORT', 5044))
# logger.addHandler(logstash.TCPLogstashHandler(logstash_host, logstash_port, version=1))



# # JSON 형식으로 로그를 포맷하기 위한 핸들러 설정
# class JsonFormatter(logging.Formatter):
#     def format(self, record):
#         log_record = {
#             'message': record.getMessage(),
#             'level': record.levelname,
#             'timestamp': self.formatTime(record, self.datefmt),
#             'name': record.name,
#             'pathname': record.pathname,
#             'lineno': record.lineno,
#             'funcName': record.funcName,
#         }
#         return json.dumps(log_record)

# json_formatter = JsonFormatter()
# for handler in logger.handlers:
#     handler.setFormatter(json_formatter)


# 데이터베이스 모델 정의
class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # 추가: 유저네임 필드
    password = db.Column(db.String(255), nullable=False)  # 추가: 비밀번호 해싱된 값 저장
    name = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.Enum('male', 'female'), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    modified_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Interest(db.Model):
    __tablename__ = 'interests'
    interests_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    category = db.Column(db.String(255), nullable=False)

class UserInterest(db.Model):
    __tablename__ = 'user_interests'
    user_interest_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.user_id'), nullable=False)
    interests_id = db.Column(db.BigInteger, db.ForeignKey('interests.interests_id'), nullable=False)

# 인증 데코레이터
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 쿠키에서 토큰 가져오기
        token = request.cookies.get('token')

        # # 헤더에서 토큰 가져오기
        # if 'Authorization' in request.headers:
        #     token = request.headers['Authorization'].split(" ")[1]  # "Bearer <token>"

        if not token:
            logger.warning('토큰이 제공되지 않았습니다.')
            return jsonify({'error': '토큰이 제공되지 않았습니다.'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                logger.warning('사용자를 찾을 수 없습니다.', extra={'user_id': data.get('user_id')})
                return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 401
            g.user = current_user  # 글로벌 컨텍스트에 사용자 저장
        except jwt.ExpiredSignatureError:
            logger.warning('토큰이 만료되었습니다.', extra={'user_id': data.get('user_id') if 'data' in locals() else 'unknown'})
            return jsonify({'error': '토큰이 만료되었습니다.'}), 401
        except Exception as e:
            logger.error(f'유효하지 않은 토큰입니다: {e}')
            return jsonify({'error': '유효하지 않은 토큰입니다.'}), 401

        return f(*args, **kwargs)
    return decorated


# @app.route('/test-log', methods=['GET'])
# def test_log():
#     record = logging.LogRecord(
#         name="test_log",
#         level=logging.INFO,
#         pathname=__file__,
#         lineno=0,
#         msg="Direct log to Logstash",
#         args=None,
#         exc_info=None,
#     )
#     logstash_handler.emit(record)  # Logstash 핸들러 직접 호출
#     return jsonify({"message": "Test log sent"}), 200

@app.route('/test-log', methods=['GET'])
def test_log():
    logger.info("This is a test log message from Flask")
    return jsonify({"message": "Test log sent"}), 200

# 회원가입 API
@app.route('/users', methods=['POST'])
def register_user():
    try :
        data = request.json

         # 사용자 정보
        username = data['username']
        password = data['password']
        name = data['name']
        gender = data['gender']
        birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d')

        # 사용자명 중복 확인
        if User.query.filter_by(username=username).first():
            logger.warning('회원가입 실패: 이미 존재하는 사용자명.', extra={'username': username})
            return jsonify({'error': '이미 존재하는 사용자명입니다.'}), 400
        
        # 비밀번호 해싱
        hashed_password = bcrypt.generate_password_hash(password)
        
        # 사용자 추가
        new_user = User(
            username=username,
            password=hashed_password.decode('utf-8'),
            name=name,
            gender=gender,
            birth_date=birth_date
        )
        db.session.add(new_user)
        db.session.flush()  # flush()로 user_id를 미리 가져옴
        user_id = new_user.user_id

        # 관심분야 리스트
        interests = data.get('interests', [])  # 없으면 빈 리스트

        # 관심분야 추가
        for interest_id in interests:
            interest = Interest.query.get(interest_id)
            if not interest:
                logger.warning('관심분야 추가 실패: 유효하지 않은 interest_id.', extra={'interest_id': interest_id})
                return jsonify({'error': f'interests_id {interest_id}가 존재하지 않습니다.'}), 404

            user_interest = UserInterest(user_id=new_user.user_id, interests_id=interest_id)
            db.session.add(user_interest)

        db.session.commit()

        logger.info('회원가입 성공', extra={'user_id': user_id, 'username': username})
        return jsonify({'message': '회원가입이 완료되었습니다!', 'user_id': new_user.user_id})
    except Exception as e:
        db.session.rollback()
        logger.error(f'회원가입 중 오류 발생: {e}', extra={'username': data.get('username') if 'data' in locals() else 'unknown'})
        return jsonify({'error': str(e)}), 500


# 로그인 API
@app.route('/auth/login', methods=['POST'])
def login_user():
    try:
        data = request.json
        username = data['username']
        password = data['password']

        # 간단한 인증 로직 추가 (비밀번호 해싱 필요 시 Hash 적용)
        user = User.query.filter_by(username=username).first()
        if user is None:
            logger.warning('로그인 실패: 존재하지 않는 사용자.', extra={'username': username})
            return jsonify({'error': '존재하지 않는 사용자입니다.'}), 404

       # 비밀번호 확인
        if not bcrypt.check_password_hash(user.password, password):
            logger.warning('로그인 실패: 비밀번호 불일치.', extra={'username': username})
            return jsonify({'error': '비밀번호가 올바르지 않습니다.'}), 401

        # JWT 토큰 생성
        token = jwt.encode({
            'user_id': user.user_id,
            'exp': datetime.utcnow() + app.config['TOKEN_EXPIRATION']
        }, app.config['SECRET_KEY'], algorithm="HS256")


        # 응답 생성
        response = jsonify({'message': '로그인 성공'})
        # 쿠키에 토큰 저장
        response.set_cookie(
            'token',  # 쿠키 이름
            token,    # 쿠키 값
            httponly=False,
            secure=False,  # HTTPS 환경에서는 True로 설정
            samesite='Lax',  # CSRF 방지를 위해 설정
            max_age=app.config['TOKEN_EXPIRATION'].total_seconds()
        )
        logger.info('로그인 성공', extra={'username': username, 'user_id': user.user_id})
        return response, 200
        # return jsonify({'message': '로그인 성공', 'token': token}), 200
    except Exception as e:
        logger.error(f'로그인 중 오류 발생: {e}', extra={'username': username if 'username' in locals() else 'unknown'})
        return jsonify({'error': str(e)}), 500

# 로그아웃 API (클라이언트 측에서 토큰을 삭제하면 되므로 서버에서는 특별한 처리가 필요하지 않을 수 있음)
@app.route('/auth/logout', methods=['DELETE'])
@token_required
def logout_user():
    try:
        # 응답 생성
        response = jsonify({'message': '로그아웃 되었습니다.'})
        # 쿠키 삭제 (만료 시간 과거로 설정)
        response.set_cookie('token', '', expires=0)
        return response, 200
        # # 서버 측에서 특별한 처리를 하지 않음
        # return jsonify({'message': '로그아웃 되었습니다.'}), 200
    except Exception as e:
        logger.error(f'로그아웃 중 오류 발생: {e}', extra={'user_id': g.user.user_id if 'g.user' in locals() else 'unknown'})
        return jsonify({'error': str(e)}), 500




# 현재 사용자 정보 조회 API
@app.route('/users/me', methods=['GET'])
@token_required
def get_current_user():
    try:
        user = g.user
        user_data = {
            'user_id': user.user_id,
            'username': user.username,
            'name': user.name,
            'gender': user.gender,
            'birth_date': user.birth_date.strftime('%Y-%m-%d'),
            'created_date': user.created_date.strftime('%Y-%m-%d %H:%M:%S'),
            'modified_date': user.modified_date.strftime('%Y-%m-%d %H:%M:%S')
        }
        logger.info('현재 사용자 정보 조회', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify(user_data), 200
    except Exception as e:
        logger.error(f'현재 사용자 정보 조회 중 오류 발생: {e}', extra={'user_id': g.user.user_id if 'g.user' in locals() else 'unknown'})
        return jsonify({'error': str(e)}), 500


# 현재 사용자 정보 수정 API
@app.route('/users/me', methods=['PUT'])
@token_required
def update_current_user():
    try:
        data = request.json
        user = g.user

        # 업데이트 가능한 필드
        user.name = data.get('name', user.name)
        user.gender = data.get('gender', user.gender)
        birth_date = data.get('birth_date')
        if birth_date:
            user.birth_date = datetime.strptime(birth_date, '%Y-%m-%d')

        db.session.commit()

        logger.info('현재 사용자 정보 수정', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'message': '사용자 정보가 업데이트되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'현재 사용자 정보 수정 중 오류 발생: {e}', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'error': str(e)}), 500



# 비밀번호 변경 API
@app.route('/users/me/password', methods=['PUT'])
@token_required
def change_password():
    try:
        data = request.json
        user = g.user

        current_password = data['current_password']
        new_password = data['new_password']

        # 현재 비밀번호 확인
        if not bcrypt.check_password_hash(user.password, current_password):
            logger.warning('비밀번호 변경 실패: 현재 비밀번호 불일치.', extra={'user_id': user.user_id, 'username': user.username})
            return jsonify({'error': '현재 비밀번호가 올바르지 않습니다.'}), 401

        # 새로운 비밀번호 해싱 및 저장
        hashed_password = bcrypt.generate_password_hash(new_password)
        user.password = hashed_password

        db.session.commit()

        logger.info('비밀번호 변경 성공', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'message': '비밀번호가 변경되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'비밀번호 변경 중 오류 발생: {e}', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'error': str(e)}), 500



# 관심분야 목록 조회 API
@app.route('/interests', methods=['GET'])
def get_all_interests():
    try:
        interests = Interest.query.all()
        interests_list = [{'interests_id': i.interests_id, 'category': i.category} for i in interests]
        logger.info('관심분야 목록 조회')
        return jsonify({'interests': interests_list}), 200
    except Exception as e:
        logger.error(f'관심분야 목록 조회 중 오류 발생: {e}')
        return jsonify({'error': str(e)}), 500


# 현재 사용자의 관심분야 조회 API
@app.route('/users/me/interests', methods=['GET'])
@token_required
def get_user_interests():
    try:
        user = g.user
        user_interests = UserInterest.query.filter_by(user_id=user.user_id).all()

        interests_list = []
        for user_interest in user_interests:
            interest = Interest.query.get(user_interest.interests_id)
            if interest:
                interests_list.append({
                    'interests_id': interest.interests_id,
                    'category': interest.category
                })

        logger.info('현재 사용자 관심분야 조회', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'user_id': user.user_id, 'interests': interests_list}), 200
    except Exception as e:
        logger.error(f'현재 사용자 관심분야 조회 중 오류 발생: {e}', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'error': str(e)}), 500


# 관심분야 추가 API
@app.route('/users/me/interests', methods=['POST'])
@token_required
def add_user_interests():
    try:
        data = request.json
        user = g.user
        new_interests = data.get('interests', [])  # 새 관심분야 ID 리스트

        # 입력 데이터 검증
        if not new_interests:
            logger.warning('관심분야 추가 실패: interests가 비어있습니다.', extra={'user_id': user.user_id, 'username': user.username})
            return jsonify({'error': 'interests는 비어있을 수 없습니다.'}), 400
        if not isinstance(new_interests, list):
            logger.warning('관심분야 추가 실패: interests가 리스트가 아닙니다.', extra={'user_id': user.user_id, 'username': user.username})
            return jsonify({'error': 'interests는 리스트여야 합니다.'}), 400

        # 기존 관심분야 삭제
        UserInterest.query.filter_by(user_id=user.user_id).delete()

        # 관심 분야 ID가 유효한지 확인 후 추가
        for interest_id in new_interests:
            interest = Interest.query.get(interest_id)
            if not interest:
                logger.warning('관심분야 추가 실패: 유효하지 않은 interest_id.', extra={'interest_id': interest_id, 'user_id': user.user_id, 'username': user.username})
                return jsonify({'error': f'interests_id {interest_id}가 존재하지 않습니다.'}), 404

            # 관심분야 추가
            user_interest = UserInterest(user_id=user.user_id, interests_id=interest_id)
            db.session.add(user_interest)

        db.session.commit()
        logger.info('관심분야 추가 성공', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'message': '관심분야가 업데이트되었습니다!'}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f'관심분야 추가 중 오류 발생: {e}', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'error': str(e)}), 500


# 관심분야 삭제 API
@app.route('/users/me/interests/<int:interest_id>', methods=['DELETE'])
@token_required
def delete_user_interest(interest_id):
    try:
        user = g.user

        user_interest = UserInterest.query.filter_by(user_id=user.user_id, interests_id=interest_id).first()
        if not user_interest:
            logger.warning('관심분야 삭제 실패: 해당 관심분야가 존재하지 않습니다.', extra={'interest_id': interest_id, 'user_id': user.user_id, 'username': user.username})
            return jsonify({'error': '해당 관심분야가 존재하지 않습니다.'}), 404

        db.session.delete(user_interest)
        db.session.commit()
        logger.info('관심분야 삭제 성공', extra={'interest_id': interest_id, 'user_id': user.user_id, 'username': user.username})
        return jsonify({'message': '관심분야가 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'관심분야 삭제 중 오류 발생: {e}', extra={'interest_id': interest_id, 'user_id': user.user_id, 'username': user.username})
        return jsonify({'error': str(e)}), 500

# 회원 탈퇴 API
@app.route('/users/me', methods=['DELETE'])
@token_required
def delete_current_user():
    try:
        user = g.user

        # 연관 데이터 삭제 (예: user_interests)
        UserInterest.query.filter_by(user_id=user.user_id).delete()

        # 사용자 계정 삭제
        db.session.delete(user)
        db.session.commit()

        # 응답 생성 및 쿠키 삭제
        response = jsonify({'message': '회원 탈퇴가 완료되었습니다.'})
        response.set_cookie('token', '', expires=0)  # 토큰 쿠키 제거

        logger.info('회원 탈퇴 성공', extra={'user_id': user.user_id, 'username': user.username})
        return response, 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'회원 탈퇴 중 오류 발생: {e}', extra={'user_id': user.user_id, 'username': user.username})
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    with app.app_context():
         # MySQL 세션에 utf8mb4 설정 적용
        db.session.execute(text("SET NAMES 'utf8mb4'"))
        db.session.execute(text("SET character_set_connection = 'utf8mb4'"))
        db.session.execute(text("SET character_set_results = 'utf8mb4'"))
        db.session.execute(text("SET character_set_client = 'utf8mb4'"))
        db.session.commit()

        # MySQL 문자셋 설정 확인
        print("MySQL 세션의 문자셋 설정:")
        result = db.session.execute(text("SHOW VARIABLES LIKE 'character_set%'")).fetchall()
        for row in result:
            print(row)

        
        db.create_all()  # 초기 테이블 생성

        # 로깅 설정 디버깅 추가
        print("Configured log handlers for flask_app logger:")
        for handler in logger.handlers:
            print(f"Handler: {handler}, Level: {handler.level}")

        print("\nWerkzeug log handlers:")
        werkzeug_logger = logging.getLogger('werkzeug')
        for handler in werkzeug_logger.handlers:
            print(f"Handler: {handler}, Level: {handler.level}")

        # # Logstash 핸들러 직접 호출 테스트
        # print("\nTesting direct Logstash handler:")
        # try:
        #     record = logging.LogRecord(
        #         name="test_log",
        #         level=logging.INFO,
        #         pathname=__file__,
        #         lineno=0,
        #         msg="Direct log to Logstash during startup",
        #         args=None,
        #         exc_info=None,
        #     )
        #     logstash_handler.emit(record)
        #     print("Logstash handler test succeeded.")
        # except Exception as e:
        #     print(f"Logstash handler test failed: {e}")

    app.run(host='0.0.0.0', port=8000)