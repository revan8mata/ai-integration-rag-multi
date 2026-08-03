import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
import models
from sqlalchemy import select
@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_register_rejects_bad_password(client):
    response = client.post("/auth/register", json={
        "username": "testuser1",
        "password": "abc"
    })
    assert response.status_code == 422


def test_register_accepts_valid_credentials(client, db_session):
    response = client.post("/auth/register", json={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response.status_code == 201
    assert response.json()["notif"] == "testuser2 is now a user"

    # cleanup
    user = db_session.query(models.User).filter(models.User.username == "testuser2").first()
    db_session.delete(user)
    db_session.commit()


def test_talk_requires_authentication(client):
    response = client.post("/talk", json={"content": "hello"})
    assert response.status_code == 401

def test_continue_talk_requires_auth (client):
    response = client.post("/conversations/1/messages", json={"content": "how big is america?"})
    assert response.status_code == 401

def test_continue_talk_requires_auth (client):
    response = client.post("/conversations/1/messages", json={"content": "how big is america?"}
                           ,headers={"Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo0LCJleHAiOjE3ODU2ODA1NTh9.SsR5XpYA6_bEYgOGV7pVKibOO60KtGjaCAzVAUMoQJI"})
    assert response.status_code == 201


def test_talk_token(client, db_session):
    response1 = client.post("/auth/register", json={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response1.status_code == 201
    assert response1.json()["notif"] == "testuser2 is now a user"

    response2 = client.post("/auth/login", json={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response2.status_code == 200

    token = response2.json()["access_token"]

    response3 = client.post("/talk", json={"content": "hello"}
                            ,headers={"Authorization":f"Bearer {token}"} )

    if not response3.status_code == 201:
        raise AssertionError

    # message = db.execute(select(models.Message).where(models.Message.username == "testuser2")).scalar_one_or_none()

    user = db_session.execute(select(models.User).where(models.User.username == "testuser2")).scalar_one_or_none()
    db_session.delete(user)
    db_session.commit()


