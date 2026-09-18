FROM python:3.10

COPY Bot.py .
COPY Config.py .
COPY Cred.py .
COPY Process.py .
COPY DB.py .
COPY Logger.py .
COPY requirements.txt .

RUN pip3 install -r requirements.txt
CMD python3 Bot.py