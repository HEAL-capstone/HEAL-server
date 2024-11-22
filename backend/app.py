from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_cors import CORS
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)  # CORS 지원 추가

# MySQL 데이터베이스 연결 설정
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://heal_user:heal_password@db:3306/heal_db?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask JSON 인코더 커스터마이징
class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ensure_ascii = False  # JSON 응답에서 한글 깨짐 방지

app.json_encoder = CustomJSONEncoder

# 데이터베이스 모델 정의
class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
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

# 회원가입 API
@app.route('/register', methods=['POST'])
def register_user():
    try :
        data = request.json

         # 사용자 정보
        name = data['name']
        gender = data['gender']
        birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d')

        # 관심분야 리스트
        interests = data.get('interests', [])  # 없으면 빈 리스트

        # 사용자 추가
        new_user = User(name=name, gender=gender, birth_date=birth_date)
        db.session.add(new_user)
        db.session.flush()  # flush()로 user_id를 미리 가져옴
        user_id = new_user.user_id

        # 관심분야 추가
        for interest_id in interests:
            interest = Interest.query.get(interest_id)
            if not interest:
                return jsonify({'error': f'interests_id {interest_id}가 존재하지 않습니다.'}), 404

            user_interest = UserInterest(user_id=new_user.user_id, interests_id=interest_id)
            db.session.add(user_interest)

        db.session.commit()
        # # 사용자 추가
        # new_user = User(name=name, gender=gender, birth_date=birth_date)
        # db.session.add(new_user)
        # db.session.commit()

        return jsonify({'message': '회원가입이 완료되었습니다!', 'user_id': new_user.user_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 관심분야 추가 API
@app.route('/update_interest', methods=['POST'])
def update_interest():
    try:
        data = request.json
        user_id = data['user_id']
        new_interests = data.get('interests', [])  # 새 관심분야 ID 리스트

        # 입력 데이터 검증
        if not user_id or not new_interests:
            return jsonify({'error': 'user_id와 interests는 필수 입력값입니다.'}), 400
        if not isinstance(new_interests, list) or len(new_interests) == 0:
            return jsonify({'error': 'interests는 비어있을 수 없습니다.'}), 400

        # 유효한 user_id인지 확인
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': f'user_id {user_id}가 존재하지 않습니다.'}), 404


        # 기존 관심분야 삭제
        UserInterest.query.filter_by(user_id=user_id).delete()

        # 관심 분야 ID가 유효한지 확인 후 추가
        for interest_id in new_interests:
            interest = Interest.query.get(interest_id)
            if not interest:
                return jsonify({'error': f'interests_id {interest_id}가 존재하지 않습니다.'}), 404

            # 관심분야 추가
            user_interest = UserInterest(user_id=user_id, interests_id=interest_id)
            db.session.add(user_interest)

        db.session.commit()
        return jsonify({'message': '관심분야가 추가되었습니다!'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 로그인 API
@app.route('/login', methods=['POST'])
def login_user():
    try:
        data = request.json
        username = data['username']
        password = data['password']

        # 간단한 인증 로직 추가 (비밀번호 해싱 필요 시 Hash 적용)
        user = User.query.filter_by(name=username).first()
        if user is None:
            return jsonify({'error': '존재하지 않는 사용자입니다.'}), 404

        # 비밀번호 비교 로직 (현재는 단순 비교)
        if password != 'testpassword':  # 실제로는 해시 비교가 필요
            return jsonify({'error': '비밀번호가 올바르지 않습니다.'}), 401

        return jsonify({'message': '로그인 성공', 'user_id': user.user_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 관심분야 조회 API
@app.route('/user_interests/<int:user_id>', methods=['GET'])
def get_user_interests(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': f'user_id {user_id}가 존재하지 않습니다.'}), 404

        user_interests = UserInterest.query.filter_by(user_id=user_id).all()
        if not user_interests:
            return jsonify({'message': '관심 분야가 없습니다.', 'user_id': user_id, 'interests': []}), 200

        interests_list = []
        for user_interest in user_interests:
            interest = Interest.query.get(user_interest.interests_id)
            if interest:
                interests_list.append({
                    'interests_id': interest.interests_id,
                    'category': interest.category
                })

        # 디버깅: 직렬화 전 데이터 출력
        print({'user_id': user_id, 'interests': interests_list})

        return jsonify({'user_id': user_id, 'interests': interests_list}), 200

    except Exception as e:
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
    app.run(host='0.0.0.0', port=5000)