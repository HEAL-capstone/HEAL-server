-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS heal_db;

-- user 테이블 생성
CREATE TABLE IF NOT EXISTS user (
    user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(20) NOT NULL,
    gender ENUM('male', 'female') NOT NULL,
    birth_date DATE NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- interests 테이블 생성
CREATE TABLE IF NOT EXISTS interests (
    interests_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(255) NOT NULL
);

INSERT INTO interests (category) VALUES
('간 건강'),
('피로 개선'),
('눈 건강'),
('관절/뼈 건강'),
('면역력 강화'),
('소화 건강'),
('수면 개선'),
('스트레스 관리'),
('피부 건강'),
('혈액순환');

-- user_interests 중간 테이블 생성
CREATE TABLE IF NOT EXISTS user_interests (
    user_interest_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    interests_id BIGINT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (interests_id) REFERENCES interests(interests_id)
);

-- supplements 테이블 생성
CREATE TABLE IF NOT EXISTS supplements (
    supplements_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    supplement_name VARCHAR(50) NOT NULL,
    supplement_description TEXT
);

-- supplement_interests 중간 테이블 생성
CREATE TABLE IF NOT EXISTS supplement_interests (
    supplement_interest_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    supplements_id BIGINT NOT NULL,
    interests_id BIGINT NOT NULL,
    UNIQUE (supplements_id, interests_id),  -- 중복 방지
    FOREIGN KEY (supplements_id) REFERENCES supplements(supplements_id) ON DELETE CASCADE,
    FOREIGN KEY (interests_id) REFERENCES interests(interests_id) ON DELETE CASCADE
);

