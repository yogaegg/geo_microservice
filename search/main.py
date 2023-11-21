from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import xml.etree.ElementTree as ET
import json, pika, uuid, httpx

SECRET_KEY = "aeca11aa5d871bcf438559e72025d96b33e7410c8a380bf0a931c0faca78d370"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username:str or None = None

class User(BaseModel):
    username:str
    email:str or None = None
    disabled: bool or None = None
class Project(BaseModel):
    id: str
    data: list

class UserInDB(User):
    hashed_password: str


client = MongoClient("mongodb://localhost:27017/")
db = client["project_database"]
collection = db["project_collection"]

base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")
oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

thread_pool = ThreadPoolExecutor(max_workers=10)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*']
)

def save_to_database(project:Project):
    db["project"].insert_one(project.dict())


async def get_token(database: str, term: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url + f"esearch.fcgi?db={database}&term={term}&usehistory=y")

        return response.text


async def get_content(database: str, query_key: str, web_env: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            base_url + f"efetch.fcgi?db={database}&query_key={query_key}&WebEnv={web_env}&retmax=5000")
        return response.text


def parse_data(raw):
    raw_data = raw.split('\n\n')
    data = []
    for d in raw_data:
        entries = d.split('\n')
        dictionary = {}
        if not entries[0]: entries.pop(0)
        first_space = entries[0].find(' ')
        dictionary["Title"] = entries[0][first_space + 1:]
        # dictionary["Summary"] = entries[1]
        for i in range(1, len(entries)):
            entry = entries[i].replace('\t', ' ').split(':')
            if len(entry) == 2 and i!=1:
                dictionary[entry[0]] = entry[1].strip()
            elif len(entry) == 1 or i==1:
                dictionary["Summary"] = entry[0]
            elif entry[0] == "FTP download":
                dictionary["FTP download"] = entries[i].replace('\t', ' ').split(' ')[-1]
            else:
                dictionary["Accession"] = entry[1].replace('\t', ' ').split(' ')[1]
                dictionary["ID"] = entry[-1]

        data.append(dictionary)
    id = uuid.uuid1()
    return {"id":str(id),"data":data}


def verity_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password,hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(username:str):
    user = db["user"].find_one({"username": username})
    if user is not None:
        user_data = user
        return UserInDB(**user_data)
    else:
        raise HTTPException(status_code=404, detail="User not found")

def authenticate_user(username:str, password:str):
    user = get_user(username)
    if not user:
        return False
    if not verity_password(password,user.hashed_password):
        return False
    return user

def create_access_token(data:dict, expires_delta: timedelta or None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow()+expires_delta
    else:
        expire = datetime.utcnow()+timedelta(minutes=15)

    to_encode.update({"exp":expire})
    encoded_jwt = jwt.encode(to_encode,SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token:str = Depends(oauth_2_scheme)):
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Could not validate credentials",
                                         headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username:str = payload.get("sub")
        if username is None:
            raise credential_exception
        token_data = TokenData(username=username)

    except JWTError:
        raise credential_exception

    user = get_user(username=token_data.username)
    if user is None:
        raise credential_exception
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400,detail="Inactive user")

    return current_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm=Depends()):
    user = authenticate_user(form_data.username,form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token= create_access_token(data={"sub":user.username},expires_delta=access_token_expires)
    return {"access_token":access_token, "token_type":"bearer"}


@app.get("/search/{database}&{term}")
async def search(background_tasks: BackgroundTasks, database: str, term: str,current_user: User = Depends(get_current_active_user)):
    query_response = await get_token(database, term)
    res_tree = ET.fromstring(query_response)
    query_key = res_tree.find("QueryKey").text
    web_env = res_tree.find("WebEnv").text
    print(query_key, web_env)
    content_response = await get_content(database, query_key, web_env)
    data = parse_data(content_response)

    project_instance = Project(**data)
    background_tasks.add_task(save_to_database,project_instance)

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', 5672))
    channel = connection.channel()
    channel.queue_declare(queue='events')

    channel.basic_publish(exchange='', routing_key='events', body=data.encode('utf-8'))

    connection.close()
    return data


@app.get("/filter/{web_env}&{filter}")
async def filter(background_tasks: BackgroundTasks, web_env: str, filter: str,current_user: User = Depends(get_current_active_user)):
    item = db["project"].find_one({"id": web_env})

    if item is not None:
        data = item['data']
        key,constraints = filter[:-1].split('[')
        print(key,constraints)
        result = [d for d in data if constraints in d[key].lower()]
        return result

    else:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/download/all/{web_env}")
async def downloadAll(background_tasks: BackgroundTasks, web_env: str,current_user: User = Depends(get_current_active_user)):
    items = db["project"].find_one({"id": web_env})
    if items is not None:
        data = items['data']

        return [{"Accession": d["Accession"],"FTP download":d["FTP download"]} for d in data]

    else:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/download/{web_env}&{accession}")
async def download(background_tasks: BackgroundTasks, web_env: str,accession:str,current_user: User = Depends(get_current_active_user)):
    items = db["project"].find_one({"id": web_env})

    if items is not None:
        data = items['data']

        for d in data:
            if d["Accession"] == accession:
                return {"Accession": accession,"FTP download":d["FTP download"]}
        return {}

    else:
        raise HTTPException(status_code=404, detail="Item not found")
@app.on_event("shutdown")
def shutdown_event():
    thread_pool.shutdown(wait=False)
