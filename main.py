from fastapi import FastAPI, Response, Request, BackgroundTasks
import httpx
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()
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

@app.get("/search/{database}&{term}")
async def root(background_tasks:BackgroundTasks,database:str, term:str):
    response = await get_token(database, term)
    print(response)
    res_tree = ET.fromstring(response)
    print(res_tree.find("QueryKey").text)
    print(res_tree.find("WebEnv").text)


    # for child in response:
    #     print(child)

    # background_tasks.add_task(thread_pool.submit,save_to_cache)
    return response
        # Response(content=response, media_type="application/xml")


@app.get("/hello/{name}")
async def search(name: str):
    return {"message": f"Hello {name}"}


@app.on_event("shutdown")
def shutdown_event():
    thread_pool.shutdown(wait=False)

