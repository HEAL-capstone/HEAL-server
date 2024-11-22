from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

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
    data = request.json
    name = data['name']
    gender = data['gender']
    birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d')

    new_user = User(name=name, gender=gender, birth_date=birth_date)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': '회원가입이 완료되었습니다!', 'user_id': new_user.user_id})

# 관심분야 추가 API
@app.route('/add_interest', methods=['POST'])
def add_interest():
    data = request.json
    user_id = data['user_id']
    interests = data['interests']  # 관심분야 ID 리스트

    for interest_id in interests:
        user_interest = UserInterest(user_id=user_id, interests_id=interest_id)
        db.session.add(user_interest)

    db.session.commit()
    return jsonify({'message': '관심분야가 추가되었습니다!'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 초기 테이블 생성
    app.run(host='0.0.0.0', port=5000)