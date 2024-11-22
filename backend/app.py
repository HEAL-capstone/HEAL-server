from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # CORS 지원 추가

# MySQL 데이터베이스 연결 설정
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://heal_user:heal_password@db:3306/heal_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
        name = data['name']
        gender = data['gender']
        birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d')

        new_user = User(name=name, gender=gender, birth_date=birth_date)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({'message': '회원가입이 완료되었습니다!', 'user_id': new_user.user_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 관심분야 추가 API
@app.route('/add_interest', methods=['POST'])
def add_interest():
    try:
        data = request.json
        user_id = data['user_id']
        interests = data['interests']  # 관심분야 ID 리스트

        # 입력 데이터 검증
        if not user_id or not interests:
            return jsonify({'error': 'user_id와 interests는 필수 입력값입니다.'}), 400
        if not isinstance(interests, list) or len(interests) == 0:
            return jsonify({'error': 'interests는 비어있을 수 없습니다.'}), 400

        # 유효한 user_id인지 확인
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': f'user_id {user_id}가 존재하지 않습니다.'}), 404

        # 관심 분야 ID가 유효한지 확인
        for interest_id in interests:
            interest = Interest.query.get(interest_id)
            if not interest:
                return jsonify({'error': f'interests_id {interest_id}가 존재하지 않습니다.'}), 404

            # 관심분야 추가
            user_interest = UserInterest(user_id=user_id, interests_id=interest_id)
            db.session.add(user_interest)

        db.session.commit()
        return jsonify({'message': '관심분야가 추가되었습니다!'}), 201
        
    except Exception as e:
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 초기 테이블 생성
    app.run(host='0.0.0.0', port=5000)