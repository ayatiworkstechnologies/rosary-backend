For next time live

ssh -i "C:\Users\admin\.ssh\cloud2_devteam_ed25519" -o IdentitiesOnly=yes devteam@89.167.92.220

cd /var/www/rosary-backend

git pull --ff-only origin main

source venv/bin/activate

sudo -n pm2 restart 13

sudo -n pm2 status

pip install -r requirements.txt
sudo -n pm2 restart 13


