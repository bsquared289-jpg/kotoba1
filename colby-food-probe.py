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

TOOLS=[{'name':'get_colby_menu','description':'Fetch live Colby College dining menu with detailed raw Nutrislice fields, including stations, dietary tags, allergens and nutrition if present.','inputSchema':{'type':'object','properties':{'hall':{'type':'string','enum':list(HALLS)},'meal':{'type':'string','enum':sorted(MEALS)},'date':{'type':'string','description':'YYYY-MM-DD'}},'required':['hall','meal','date']}},{'name':'get_colby_locations','description':'List available Colby dining locations.','inputSchema':{'type':'object','properties':{}}}]
def mcp_result(req):
 method=req.get('method');ident=req.get('id')
 if method=='notifications/initialized':return None
 if method=='initialize':return {'jsonrpc':'2.0','id':ident,'result':{'protocolVersion':'2025-03-26','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'colby-dining','version':'0.1.0'}}}
 if method=='ping':return {'jsonrpc':'2.0','id':ident,'result':{}}
 if method=='tools/list':return {'jsonrpc':'2.0','id':ident,'result':{'tools':TOOLS}}
 if method=='tools/call':
  p=req.get('params') or {};a=p.get('arguments') or {}
  try:
   if p.get('name')=='get_colby_locations':data={'locations':HALLS,'meals':sorted(MEALS)}
   elif p.get('name')=='get_colby_menu':data=fetch(a.get('hall',''),a.get('meal',''),a.get('date',''))
   else:raise ValueError('Unknown tool')
   result={'content':[{'type':'text','text':json.dumps(data)}]}
  except Exception as e:result={'isError':True,'content':[{'type':'text','text':str(e)}]}
  return {'jsonrpc':'2.0','id':ident,'result':result}
 return {'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}}

class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  if urlparse(self.path).path!='/mcp':return self.reply(404,{'error':'Not found'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n>200000:raise ValueError('Request too large')
   request=json.loads(self.rfile.read(n));result=mcp_result(request)
   if result is None:self.send_response(202);self.end_headers();return
   self.reply(200,result)
  except Exception as e:self.reply(400,{'error':str(e)})

 def reply(self,status,obj):
  body=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/health':return self.reply(200,{'ok':True})
  if p.path=='/api/menu':
   q=parse_qs(p.query);hall=q.get('hall',['roberts-dining-hall'])[0];meal=q.get('meal',['dinner'])[0];date=q.get('date',['2026-10-12'])[0]
   try:return self.reply(200,fetch(hall,meal,date))
   except Exception as e:return self.reply(502,{'error':str(e)})
  if p.path=='/' or p.path=='/index.html':
   with open('colby-bites.html','rb') as file: body=file.read()
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
  return self.reply(404,{'error':'Not found'})
if __name__=='__main__':
 import threading
 def startup_check():
  try:
   result=fetch('roberts-dining-hall','dinner','2026-10-12')
   print('COLBY_API_TEST_SUCCESS',json.dumps({'url':result['source_url'],'keys':result['keys'],'day_count':len(result['days']),'first_day':str(result['days'][:1])[:1200]}),flush=True)
  except Exception as e:print('COLBY_API_TEST_FAILURE',repr(e),flush=True)
 threading.Thread(target=startup_check,daemon=True).start()
 ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','10000'))),Handler).serve_forever()
