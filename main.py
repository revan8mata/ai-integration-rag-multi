
from fastapi import  FastAPI,status,Depends, HTTPException
from google import genai
from sqlalchemy.orm import Session
import documents
import messages
import auth
import schemas
import users
import models
import conversations
import oauth2
import os
import config
from config import settings
from fastapi.middleware.cors import CORSMiddleware
from database import get_db
from fastapi.staticfiles import StaticFiles
app = FastAPI()

origins = ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.ROUTER)
app.include_router(users.ROUTER)
app.include_router(conversations.ROUTER)
app.include_router(messages.ROUTER)
app.include_router(documents.ROUTER)



app.mount("/", StaticFiles(directory="static", html=True), name="static")

client = genai.Client(api_key=settings.api_key)


