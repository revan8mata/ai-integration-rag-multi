import schemas
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
EXPIRE_MINUTES = settings.access_token_expire_minutes


def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str,credential_exception):
    try:

        payload = jwt.decode(token,
                             SECRET_KEY,
                             algorithms=[ALGORITHM])
        id: str = payload.get("user_id")
        if id is None:
            raise credential_exception
        Token_Data = schemas.   TokenData(id=int(id))

    except JWTError:
        raise credential_exception
    return Token_Data

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                          detail="Could not validate credentials",
                                          headers={"WWW-Authenticate": "Bearer"})
    return verify_access_token(token, credentials_exception)
