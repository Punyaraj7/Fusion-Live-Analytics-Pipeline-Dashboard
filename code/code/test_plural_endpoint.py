from auth import get_token
from config import BASE_URL
import requests

wid=905
token=get_token()
url=f"{BASE_URL}/workspaces/{wid}/modules"
print('GET',url)
resp=requests.get(url, headers={'Authorization':f'Bearer {token}'}, timeout=30)
print('status',resp.status_code)
print(resp.text[:800])
