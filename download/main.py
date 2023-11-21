from fastapi import FastAPI
from ftplib import FTP
import pika, json


app = FastAPI()
url = "ftp://ftp.ncbi.nlm.nih.gov"
# file_name = "/geo/series/GSE223nnn/GSE223251/soft"

def donwloadFTP(url:str):
    ftp = FTP('ftp.ncbi.nlm.nih.gov')

    # Anonymous login
    ftp.login()

    # Navigate to the desired directory
    ftp.cwd('/geo/datasets/GDS1nnn/GDS1001/soft/')

    # List files in the directory
    files = ftp.nlst()
    print("Files in the directory:")
    for file in files:
        print(file)

    # Download a specific file
    with open('GDS1001.soft.gz', 'wb') as f:
        ftp.retrbinary('example.txt', f.write)

    # Close the FTP connection
    ftp.quit()

@app.get("/download/")
async def root():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='events')

    def callback(ch, method, properties, body):
        event_data = json.loads(body)
        # Process the event data here
        print(f"Received event: {event_data}")

    channel.basic_consume(queue='events', on_message_callback=callback, auto_ack=True)
    print("Waiting for events. To exit, press CTRL+C")
    channel.start_consuming()



    return {"message": "Hello World"}


@app.post("/receive-event")
async def receive_event(event_data: dict):
    # Process the received event data here
    print(f"Received event: {event_data}")

    # You can perform any desired actions with the event data
    print(event_data)
    return {"message": "Event received and processed successfully"}


