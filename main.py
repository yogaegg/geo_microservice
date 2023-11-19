from fastapi import FastAPI, Response, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*']
)

base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gds&term=GPL96[ACCN]+AND+gse[ETYP]+AND+cel[suppFile]&retmax=5000&usehistory=y"

thread_pool = ThreadPoolExecutor(max_workers=10)

def save_to_cache():

    return

async def get_token(database:str, term:str):
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url+f"esearch.fcgi?db={database}&term={term}&usehistory=y")
        # print(base_url+f"esearch.fcgi?db={database}&term={term}&usehistory=y")
        # base_url+f"?db={database}&term={term}+AND+[Filter]&retmax=5000&usehistory=y"

        return response.text

async def get_content(database:str,query_key:str, web_env:str):
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url+f"efetch.fcgi?db={database}&query_key={query_key}&WebEnv={web_env}&retmax=20")
        return response.text

@app.get("/search/{database}&{term}")
async def getDetails(background_tasks:BackgroundTasks,database:str, term:str):
    query_response = await get_token(database, term)
    # print(query_response)
    res_tree = ET.fromstring(query_response)
    query_key = res_tree.find("QueryKey").text
    web_env = res_tree.find("WebEnv").text
    print(query_key,web_env)
    content_response = await get_content(database,query_key,web_env)
    # print(content_response)
    # background_tasks.add_task(thread_pool.submit,save_to_cache)
    return content_response
        # Response(content=response, media_type="application/xml")





@app.on_event("shutdown")
def shutdown_event():
    thread_pool.shutdown(wait=False)

