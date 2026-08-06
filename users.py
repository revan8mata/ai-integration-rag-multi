from sqlalchemy import select

import utilities
import schemas
import models
import oauth2
from fastapi import Cookie, FastAPI, Depends, Body, HTTPException, status, Response , APIRouter
from logging import exception
from sqlalchemy.orm import Session
from database import get_db

ROUTER = APIRouter(tags=['login'])

#
@ROUTER.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    reg: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    register = db.execute(
        select(models.User)
        .where(models.User.username == reg.username)
    ).first()

    if register:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    hashed = utilities.hash(reg.password)

    new_user = models.User(
        username=reg.username,
        hashed_password=hashed
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "notif": f"{new_user.username} is now a user"
    }
# Steps:
# 1. Validate input
# 2. Check duplicate username
# 3. Hash password
# 4. Create User model
# 5. Save DB
# 6. Return response

@ROUTER.delete("/auth/user_delete/self", status_code=status.HTTP_204_NO_CONTENT)
async def user_delete( db: Session = Depends(get_db), current_user : int = Depends(oauth2.get_current_user)):
    user_delete= (db.execute(
        select(models.User)
        .where(models.User.id == current_user.id))).scalar_one_or_none()
    if not user_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    db.delete(user_delete)
    db.commit()
#user self deletion


@ROUTER.delete("/auth/user_delete/admin/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def user_delete(id: int , db: Session = Depends(get_db), current_user : int = Depends(oauth2.get_current_user)):
    user_delete= (db.execute(
        select(models.User)
        .where(models.User.id == id ))).scalar_one_or_none()
    if not user_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    admin = (db.execute(
        select(models.User)
        .where(models.User.id == current_user.id))).scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="admin not found ")
    if not admin.is_admin:
        raise HTTPException(status_code=403, detail="only admins can remove users! go and never return!")

    db.delete(user_delete)
    db.commit()

    # admin delete