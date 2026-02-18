## INSTALL DJANGO AS SERVICE
1. Dowbload nssm from https://nssm.cc/download
2. Run nssm.exe install DjangoSSLService

#INSTALL SERVICE (RUN AS ADMIN)
Application path: C:\Path\To\Python\python.exe
Startup directory: C:\Path\To\Your\DjangoProject
Arguments: manage.py runsslserver 0.0.0.0:3333 --certificate certs/cert.pem --key certs/key.pem

#REMOVE SERVCE (RUN AS ADMIN)
nssm remove DjangoSSLService confirm

