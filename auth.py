
import schemas
import utilities
import models
import oauth2
from database import get_db

from fastapi import Depends, HTTPException, status, APIRouter, Response
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session


ROUTER = APIRouter(tags=['login'])

@ROUTER.post("/auth/login", status_code=status.HTTP_200_OK)
async def login(user_credentials : OAuth2PasswordRequestForm = Depends() , db: Session = Depends(get_db)):
    logger = db.query(models.User).filter(models.User.username == user_credentials.username).first()

    if not logger:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Incorrect username or password")

    if not utilities.verify(user_credentials.password, logger.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Incorrect username or password")

    create_access_token = oauth2.create_token(data = {"user_id": logger.id, "is_admin": logger.is_admin})
    return {"access_token": create_access_token, "token_type": "bearer"}




