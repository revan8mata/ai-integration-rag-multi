import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
import models
from sqlalchemy import select
from sqlalchemy import text
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

def test_talk_requires_authentication(client):
    response = client.post("/talk", json={"content": "hello"})
    assert response.status_code == 401

def test_continue_talk_requires_auth (client):
    response = client.post("/conversations/1/messages", json={"content": "how big is america?"})
    assert response.status_code == 401



def test_talk_token(client, db_session):
    response1 = client.post("/auth/register", json={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response1.status_code == 201
    assert response1.json()["notif"] == "testuser2 is now a user"

    response2 = client.post("/auth/login", data={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response2.status_code == 200

    token = response2.json()["access_token"]

    response3 = client.post("/talk", json={"content": "hello"}
                            ,headers={"Authorization":f"Bearer {token}"} )

    print(response3.status_code)
    print(response3.text)

    assert response3.status_code == 200

    user = (db_session.execute(select(models.User).where(models.User.username == "testuser2"))).scalar_one_or_none()


    try:
        db_session.delete(user)
        db_session.commit()

    except Exception as e:
        db_session.rollback()
        print(e)
        raise


def test_provider_blocks (client, db_session):
    response1 = client.post("/auth/register", json={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response1.status_code == 201
    assert response1.json()["notif"] == "testuser2 is now a user"

    response2 = client.post("/auth/login", data={
        "username": "testuser2",
        "password": "rferfgA#1"
    })
    assert response2.status_code == 200

    token = response2.json()["access_token"]

    response3 = client.post("/talk", json={"content": "hello","provider": "blizzard"}
                            ,headers={"Authorization":f"Bearer {token}"} )

    print(response3.status_code)
    print(response3.text)

    assert "error" in response3.text

    extract_id = db_session.execute(select(models.User).where(models.User.username == "testuser2")).scalar_one_or_none()
    extracted_id = extract_id.id
    print(extracted_id)

    conversatin_exist_check= db_session.execute(select(models.Conversation).where(models.Conversation.user_id == extracted_id)).scalar_one_or_none()

    assert conversatin_exist_check is None

    try:
        db_session.delete(extract_id)
        db_session.commit()

    except Exception as e:
        db_session.rollback()
        print(e)
        raise





