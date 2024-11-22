-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS heal_db;

-- user 테이블 생성
CREATE TABLE user (
    user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(20) NOT NULL,
    gender ENUM('male', 'female') NOT NULL,
    birth_date DATE NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- interests 테이블 생성
CREATE TABLE interests (
    interests_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(255) NOT NULL
);

-- user_interests 중간 테이블 생성
CREATE TABLE user_interests (
    user_interest_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    interests_id BIGINT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (interests_id) REFERENCES interests(interests_id)
);