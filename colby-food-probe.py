import os,json,datetime,urllib.request
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
HALLS={'roberts-dining-hall':'Roberts','dana-dining-hall':'Dana','foss-dining-hall':'Foss'}
MEALS={'breakfast','lunch','dinner'}
def fetch(hall,meal,date):
 if hall not in HALLS or meal not in MEALS: raise ValueError('Invalid hall or meal')
 dt=datetime.date.fromisoformat(date);y,m,d=dt.year,dt.month,dt.day
 urls=[f'https://colby.api.nutrislice.com/menu/api/weeks/school/{hall}/menu-type/{meal}/{y}/{m}/{d}/?format=json',f'https://colby.nutrislice.com/menu/api/weeks/school/{hall}/menu-type/{meal}/{y}/{m}/{d}/?format=json']
 errors=[]
 for url in urls:
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=12) as res: data=json.load(res)
   return {'source_url':url,'keys':list(data.keys()),'days':data.get('days',[])}
  except Exception as e: errors.append(type(e).__name__+': '+str(e)[:150])
 raise RuntimeError('; '.join(errors))
class Handler(BaseHTTPRequestHandler):
 def reply(self,status,obj):
  body=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/health':return self.reply(200,{'ok':True})
  if p.path=='/api/menu':
   q=parse_qs(p.query);hall=q.get('hall',['roberts-dining-hall'])[0];meal=q.get('meal',['dinner'])[0];date=q.get('date',['2026-10-12'])[0]
   try:return self.reply(200,fetch(hall,meal,date))
   except Exception as e:return self.reply(502,{'error':str(e)})
  return self.reply(200,{'service':'Colby Food live menu probe','usage':'/api/menu?hall=roberts-dining-hall&meal=dinner&date=2026-10-12'})
if __name__=='__main__':
 import threading
 def startup_check():
  try:
   result=fetch('roberts-dining-hall','dinner','2026-10-12')
   print('COLBY_API_TEST_SUCCESS',json.dumps({'url':result['source_url'],'keys':result['keys'],'day_count':len(result['days']),'first_day':str(result['days'][:1])[:1200]}),flush=True)
  except Exception as e:print('COLBY_API_TEST_FAILURE',repr(e),flush=True)
 threading.Thread(target=startup_check,daemon=True).start()
 ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','10000'))),Handler).serve_forever()
