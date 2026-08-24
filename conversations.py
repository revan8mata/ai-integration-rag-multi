from google.genai._interactions.types import Webhook
from pygments.lexer import default
from starlette.responses import StreamingResponse
from llm import generate_stream
import models
import oauth2
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, Body, HTTPException, status, Response , APIRouter
from database import get_db
from sqlalchemy import select
import schemas
from fastapi import BackgroundTasks
from google import genai
from config import settings
from retrieval import get_relevant_chunks
from rate_limit import check_rate_limit, r, check_token_limit,record_token_usage
from sqlalchemy.sql import func
from datetime import date
import httpx
import asyncio
ROUTER = APIRouter(tags=['conversations'])

client = genai.Client(api_key=settings.api_key)

async def streameresponse(history, conversation_id,  current_user_id ,
                          background_tasks ,   db  ,  payload: dict = None  ,   event_type: str = None   ,  provider="gemini"):

    full_text = ""
    last_metadata = None
    try:

        async for chunk , metadata in generate_stream(history, provider):
            full_text += chunk
            last_metadata = metadata
            yield chunk

    except Exception as e:
        db.rollback()
        r.decr(f"rate_limit:{current_user_id}:chat")
        yield f"error: {str(e)}"
        return
    if last_metadata is not None:
        record_token_usage(current_user_id,last_metadata ,2000)
    assistant_message = models.Message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_text,
            provider=provider
        )

    db.add(assistant_message)
    db.commit()
    if event_type:
        background_tasks.add_task(fire_webhook, event_type=event_type, payload=payload, db = db, user_id = current_user_id)



@ROUTER.post("/talk" ) #stat code 200 = streaming
async def talk(prompt : schemas.Prompt,
               background_tasks:BackgroundTasks,
               db: Session = Depends(get_db), current_user : int = Depends(oauth2.get_current_user),provider: str = "gemini"):
    conversation = models.Conversation(
        user_id=current_user.id,
        title=prompt.content[:40]
    )

    db.add(conversation)
    db.flush()
    message = models.Message(
        conversation_id=conversation.id,
        role="user",
        content=prompt.content
    )
    db.add(message)
    db.flush()
    event_type = "new_conversation"
    payload = {"conversation_id": conversation.id , "title" :prompt.content[:40]  }

    check_rate_limit(current_user.id, "chat", 10, 60)

    retrieval = await get_relevant_chunks(prompt.content,current_user.id, db)

    history = [{
        "role": "user",
        "parts": [{"text": f"""Use ONLY this context to answer questions.you are talking to a everyday user so 
         modify your way of communicating. If the answer is not in the context, say you don't know.

Context:
{retrieval}

User question:
{prompt.content}
"""}]
    }]


    return StreamingResponse(
    streameresponse(history=history,
    conversation_id=message.conversation_id,
    current_user_id=current_user.id,
    db=db,
    provider=provider,
    background_tasks=background_tasks,
    event_type=event_type,
    payload=payload),
    media_type="text/event-stream"
)
# 1. db set up
# 2. rate limit check
# 3. retrival
# 4. prompt and context formated
# 5. RETURN ( streaming and streameresponse() )
# 6. llm call and error handle --> llm provider chosen - formatbased on provider
# meta data abstraction - yeald response and meta data
# 7. db messege commit.
# 8. webhook
#

#start conversations  event_type: str,   payload: dict,


@ROUTER.post("/conversations/{conversation_id}/messages",response_model=schemas.gemini)
async def conversation (conversation_id : int,
                        prompt: schemas.Prompt,
                        background_tasks:BackgroundTasks,
                        db: Session = Depends(get_db),
                        current_user : int = Depends(oauth2.get_current_user) , provider="gemini"):
    query = (db.execute(select(models.Conversation)
                      .where(models.Conversation.id == conversation_id,
                             models.Conversation.user_id == current_user.id))).scalar_one_or_none() #find out the conversation that blongs to the user
    if not query:
        raise HTTPException(status_code=404, detail="conversation not found or not aaccessable by you")
    query2 = db.execute(select(models.Message)
                        .where(models.Message.conversation_id == conversation_id)
                        .order_by(models.Message.created_at)).scalars().all()        #we can order based on id aswell

    history = []

    for message in query2:
        history.append({
            "role": "model" if message.role == "assistant" else "user",
            "parts": [
                {"text": message.content}
            ]
        })
    history.append({
        "role": "user",
        "parts": [
            {"text": prompt.content}
        ]
    })

    retrieval = await get_relevant_chunks(prompt.content,current_user.id, db)
    history.insert(0, {
        "role": "user",
        "parts": [{"text": f"""Use ONLY this context to answer questions. If not in context, say you don't know.

    Context:{retrieval}"""}]
    })

    check_rate_limit(current_user.id, "chat", 10, 60)

    message1 = models.Message(
        conversation_id=conversation_id,
        role="user",
        content=prompt.content
    )
    db.add(message1)
    db.flush()

    return StreamingResponse(
        streameresponse(history=history,
                        conversation_id=message.conversation_id,
                        current_user_id=current_user.id,
                        db=db ,
                        background_tasks=background_tasks,
                        provider=provider),
        media_type="text/event-stream")
    # keep going with already existing conversations



@ROUTER.delete('/conversations/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(id : int , background_tasks:BackgroundTasks,
                       db: Session = Depends(get_db),
                       current_user:models.User = Depends(oauth2.get_current_user)):
    conv_id = id


    dlt_conversation = db.execute(select(models.Conversation).where(models.Conversation.id == id,
                                          models.Conversation.user_id == current_user.id)).scalar_one_or_none()
    if not dlt_conversation:
        raise HTTPException(status_code =status.HTTP_404_NOT_FOUND,detail="conversation not found")
    title_conversation = dlt_conversation.title
    db.delete(dlt_conversation)
    db.commit()
    background_tasks.add_task(fire_webhook,
                              event_type="document_uploaded",
                              payload={"conversation_id": conv_id,
                              "conversation_title": title_conversation,
                                                                                     }
                              , db=db, user_id=current_user.id)

    #delete conversations

@ROUTER.patch('/conversations/{id}', status_code=status.HTTP_200_OK)
async def update_conversation(id : int ,title : str,db: Session = Depends(get_db),current_user: int = Depends(oauth2.get_current_user)):
    conversation = db.execute(select(models.Conversation).where(models.Conversation.id == id,
                                                                models.Conversation.user_id == current_user.id)).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="conversation not found")
    conversation.title = title
    # patched_name = models.Conversation( title = title)
    db.commit()
    db.refresh(conversation)
    return conversation
    #update the conversation title


@ROUTER.get("/conversations", response_model=list[schemas.ConversationOut])
async def get_conversations(db: Session = Depends(get_db),current_user : int = Depends(oauth2.get_current_user)):
    conversations = db.execute(select(models.Conversation)
                               .where(models.Conversation.user_id== current_user.id)
                               .order_by(models.Conversation.created_at)).scalars().all()

    return conversations
# conversations list sidebar

@ROUTER.get('/stats')
async def get_stats(db: Session = Depends(get_db), current_user: int = Depends(oauth2.get_current_user)):
    user = db.execute(select(models.User).where(models.User.id == current_user.id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="user not found")
    if not user.is_admin:
        raise HTTPException (status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin only")

    total_conversations = db.execute(select(func.count(models.Conversation.id))).scalar()
    total_messages = db.execute(select(func.count(models.Message.id))).scalar()
    total_documents = db.execute(select(func.count(models.Document.id))).scalar()

    today = date.today()
    active_users_today = db.execute(
        select(func.count(func.distinct(models.Message.conversation_id)))
        .where(func.date(models.Message.created_at) == today)
    ).scalar()

    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_documents": total_documents,
        "active_users_today": active_users_today
    }


async def deliver_webhook(webhook, payload):
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook.url, json=payload, timeout=5.0)
            return  # success, stop retrying
        except Exception as e:
            print(f"webhook failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s backoff

async def fire_webhook(event_type: str, payload: dict, user_id: int, db: Session):
    webhooks = db.execute(
        select(models.Webhooks)
        .where(models.Webhooks.user_id == user_id,
               models.Webhooks.event_type == event_type)
    ).scalars().all()

    tasks = [deliver_webhook(webhook, payload) for webhook in webhooks]
    await asyncio.gather(*tasks)


    # await asyncio.gather(
    #     some_async_function(),
    #     another_async_function(),
    #     yet_another_async_function()
    # )

@ROUTER.post('/webhook', status_code=status.HTTP_201_CREATED)
async def hook(create: schemas.WebhookCreate,db: Session = Depends(get_db),current_user: int = Depends(oauth2.get_current_user)):
    query = db.execute(select(models.Webhooks)
                       .where(models.Webhooks.user_id == current_user.id ,
                              models.Webhooks.event_type == create.event_type)).scalar_one_or_none()
    if query:
        raise HTTPException(status_code=400,detail="webhook already exists")
    webhook = models.Webhooks(
        url=create.url,
        event_type=create.event_type,
        user_id=current_user.id
    )
    db.add(webhook)
    db.commit()
    return {"new_webhook": "webhook created"}

# webhook signup

