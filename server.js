import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const app = express();
app.use(express.json());
const PORT = process.env.PORT || 3000;

const conversations = [
  [{text:"昨日",reading:"きのう",meaning:"yesterday"},{text:"、"},{text:"帰り道",reading:"かえりみち",meaning:"way home"},{text:"で"},{text:"猫",reading:"ねこ",meaning:"cat"},{text:"を"},{text:"見かけた",reading:"みかけた",meaning:"happened to see"},{text:"んだけど、"},{text:"めっちゃ",reading:"めっちゃ",meaning:"really / super"},{text:"堂々としてた",reading:"どうどうとしてた",meaning:"looked very confident"},{text:"。"}],
  [{text:"ところで",reading:"ところで",meaning:"by the way"},{text:"、"},{text:"最近",reading:"さいきん",meaning:"recently"},{text:"何か",reading:"なにか",meaning:"anything"},{text:"面白い",reading:"おもしろい",meaning:"interesting"},{text:"ことあった？"}]
];
const escapeHtml = s => String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function readerHtml(sentences) {
 const parts = sentences.map(line=>'<p>'+line.map(t=>t.meaning ? '<button class="word" data-reading="'+escapeHtml(t.reading)+'" data-meaning="'+escapeHtml(t.meaning)+'">'+escapeHtml(t.text)+'</button>' : escapeHtml(t.text)).join('')+'</p>').join('');
 return `<!doctype html><html lang="ja"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
 :root{color-scheme:light dark}body{font-family:system-ui,"Noto Sans JP",sans-serif;margin:0;padding:24px;background:#f8f5ef;color:#282522}
 .reader{max-width:640px;margin:auto}.word{border:0;border-bottom:1px dotted #b89a72;background:transparent;color:inherit;font:inherit;padding:2px;cursor:pointer}
 p{font-size:22px;line-height:2.2}.detail{position:sticky;bottom:12px;padding:16px;background:#fff;border:1px solid #e4d9ca;border-radius:16px;box-shadow:0 4px 24px #0001;min-height:55px}
 small{color:#766c60}h2{font-size:18px;font-weight:500}button:focus-visible{outline:2px solid #99734c}
 </style><div class="reader"><small>KOTOBA · Japanese immersion</small><h2>今日の会話</h2>${parts}<div class="detail" id="detail">Tap a Japanese expression to see its reading and meaning.</div></div>
 <script>document.querySelectorAll('.word').forEach(b=>b.addEventListener('click',()=>{document.querySelector('#detail').textContent=b.textContent+' · '+b.dataset.reading+' · '+b.dataset.meaning;}));</script></html>`;
}
function makeServer(){
 const server=new McpServer({name:"kotoba",version:"0.1.0"});
 server.registerResource("Japanese reading interface","ui://kotoba/reader.html",{},async()=>({contents:[{uri:"ui://kotoba/reader.html",mimeType:"text/html",text:readerHtml(conversations),_meta:{"openai/widgetDescription":"Tap Japanese words to reveal readings and English meanings."}}]}));
 server.registerTool("open_kotoba",{description:"Open a natural Japanese reading panel with tappable words and English glosses.",inputSchema:{topic:z.string().optional()},_meta:{"openai/outputTemplate":"ui://kotoba/reader.html","openai/toolInvocation/invoking":"Opening Kotoba","openai/toolInvocation/invoked":"Kotoba is ready"}},async({topic})=>({content:[{type:"text",text:"Kotoba reading panel ready. The panel currently contains a fixed sample; topic selection and AI-generated text are planned for the next iteration."}],structuredContent:{topic:topic||"daily life"}}));
 return server;
}
app.get("/",(_req,res)=>res.type("html").send(readerHtml(conversations)));
app.get("/health",(_req,res)=>res.json({ok:true,app:"kotoba"}));
app.post("/mcp",async(req,res)=>{const server=makeServer();const transport=new StreamableHTTPServerTransport({sessionIdGenerator:undefined});res.on("close",()=>{transport.close();server.close()});await server.connect(transport);await transport.handleRequest(req,res,req.body)});
app.get("/mcp",(_req,res)=>res.status(405).send("Method Not Allowed"));
app.delete("/mcp",(_req,res)=>res.status(405).send("Method Not Allowed"));
app.listen(PORT,"0.0.0.0",()=>console.log("Kotoba listening on "+PORT));
