import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const app = express();
app.use(express.json({limit:"1mb"}));
const PORT = process.env.PORT || 3000;
const sample = [
 {text:"最近",reading:"さいきん",meaning:"lately"},
 {text:"、"}, {text:"何か",reading:"なにか",meaning:"anything"},
 {text:"面白い",reading:"おもしろい",meaning:"interesting"},
 {text:"ことあった？",reading:"ことあった",meaning:"has anything happened?"}
];
const esc = s => String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const template = `<!doctype html><html lang="ja"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{color-scheme:light dark}*{box-sizing:border-box}body{margin:0;padding:8px 4px;font-family:system-ui,-apple-system,"Noto Sans JP",sans-serif;background:transparent;color:var(--app-text,#222)}.wrap{max-width:100%;margin:auto}.passage{font-size:17px;line-height:2.1;overflow-wrap:anywhere;white-space:pre-wrap}.token{border:0;border-radius:4px;background:transparent;color:inherit;font:inherit;line-height:inherit;padding:0 1px;cursor:pointer}.token:active,.token:focus-visible{background:rgba(120,120,120,.13);outline:none}.gloss{margin-top:12px;padding:11px 13px;border:1px solid rgba(128,128,128,.25);border-radius:12px;font-size:14px;display:none}.gloss strong{font-weight:600}.muted{opacity:.65;font-size:12px}.hint{font-size:12px;opacity:.6;margin-top:8px}.gloss.show{display:block}@media(prefers-color-scheme:dark){body{color:#e9e9e9}}
</style></head><body><div class="wrap"><div id="passage" class="passage" aria-label="Japanese conversation"></div><div class="gloss" id="gloss" aria-live="polite"></div><div class="hint" id="hint">Tap any expression for its meaning</div></div><script>
const fallback=${JSON.stringify(sample)};
const root=document.getElementById('passage'),gloss=document.getElementById('gloss');
function render(data){const tokens=Array.isArray(data?.tokens)&&data.tokens.length?data.tokens:fallback;root.replaceChildren();for(const t of tokens){const s=String(t.text??'');if(!s)continue;const b=document.createElement('button');b.type='button';b.className='token';b.textContent=s;b.addEventListener('click',()=>{gloss.classList.add('show');gloss.replaceChildren();const title=document.createElement('strong');title.textContent=s;gloss.append(title);const reading=document.createElement('div');reading.className='muted';reading.textContent=t.reading||'Reading not provided';gloss.append(reading);const meaning=document.createElement('div');meaning.textContent=t.meaning||'No gloss supplied';gloss.append(meaning);});root.append(b);}document.getElementById('hint').textContent='Tap an expression for its meaning';}
render(window.openai?.toolOutput);
window.addEventListener('openai:set_globals',e=>{if(e.detail?.globals?.toolOutput)render(e.detail.globals.toolOutput)});
</script></body></html>`;
function makeServer(){
 const server=new McpServer({name:"kotoba",version:"0.2.0"});
 server.registerResource("Kotoba reader","ui://kotoba/reader.html",{},async()=>({contents:[{uri:"ui://kotoba/reader.html",mimeType:"text/html",text:template,_meta:{"openai/widgetDescription":"Minimal Japanese reader with clickable expressions."}}]}));
 server.registerTool("open_kotoba",{
 description:"Display a natural Japanese reply as an interactive reader. IMPORTANT: Generate the Japanese reply yourself based on the user's conversation, then segment the ENTIRE reply into ordered tokens. Supply a Japanese reading and concise English meaning for EVERY token including particles and inflections (punctuation can be combined with neighboring tokens). Do not repeat the Japanese reply outside the widget. Use conversational, adult Japanese, not textbook lessons.",
 inputSchema:{tokens:z.array(z.object({text:z.string(),reading:z.string().optional(),meaning:z.string().optional()})).min(1).max(150).optional().describe("Optional complete Japanese response, segmented into tappable expressions, in reading order."),topic:z.string().optional()},
 _meta:{"openai/outputTemplate":"ui://kotoba/reader.html","openai/toolInvocation/invoking":"Writing in Japanese","openai/toolInvocation/invoked":"Kotoba"},
 },async({tokens,topic})=>({content:[{type:"text",text:"Kotoba reader opened. If no tokens were supplied, a sample is shown."}],structuredContent:{tokens:tokens?.length?tokens:sample,topic:topic||""}}));
 return server;
}
app.get("/",(_req,res)=>res.type("html").send(template));
app.get("/health",(_req,res)=>res.json({ok:true,app:"kotoba",version:"0.2.0"}));
app.post("/mcp",async(req,res)=>{const server=makeServer();const transport=new StreamableHTTPServerTransport({sessionIdGenerator:undefined});res.on("close",()=>{transport.close();server.close()});try{await server.connect(transport);await transport.handleRequest(req,res,req.body)}catch(e){console.error(e);if(!res.headersSent)res.status(500).json({error:"MCP request failed"})}});
app.get("/mcp",(_req,res)=>res.status(405).send("Method Not Allowed"));
app.delete("/mcp",(_req,res)=>res.status(405).send("Method Not Allowed"));
app.listen(PORT,"0.0.0.0",()=>console.log("Kotoba listening on "+PORT));
