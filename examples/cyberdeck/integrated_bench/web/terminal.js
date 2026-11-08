/* This pane is OUTPUT ONLY; it cannot type to the SSH PTY. */
(() => {
 'use strict';
 const token=new URLSearchParams(location.search).get('token')||'';
 const status=document.getElementById('status');
 const size=document.getElementById('dimensions');
 const terminal=new Terminal({
   allowTransparency:false,fontFamily:'ui-monospace,monospace',
   fontSize:23,lineHeight:1.2,scrollback:1500,cursorBlink:true,
   theme:{background:'#0a1118',foreground:'#cfeee0',cursor:'#a5dec6',
     green:'#91e7b3',red:'#fa8d93',yellow:'#edcb83',blue:'#a0cbff'},
 });
 const fit=new FitAddon.FitAddon();terminal.loadAddon(fit);
 terminal.open(document.getElementById('terminal'));
 const ws=new WebSocket('ws://'+location.host+'/terminal/ws?token='+encodeURIComponent(token));
 ws.binaryType='arraybuffer';
 let outputBytes=0;
 function resize(){
    fit.fit();size.textContent=terminal.cols+'×'+terminal.rows;
    if(ws.readyState===WebSocket.OPEN){
       ws.send(JSON.stringify({type:'resize',cols:terminal.cols,rows:terminal.rows}));
    }
 }
 ws.onopen=resize;
 ws.onmessage=(event)=>{
    if(typeof event.data==='string'){
      let state;
      try{state=JSON.parse(event.data);}catch{return;}
      if(state.type==='status'&&state.value==='connected'){
         status.textContent='SSH CONNECTED';document.body.classList.add('online');
         document.body.dataset.connected='yes';
         resize();
      }
    }else{
      const data=new Uint8Array(event.data);
      outputBytes+=data.byteLength;terminal.write(data);
    }
 };
 ws.onclose=()=>{
    status.textContent='DISCONNECTED';document.body.classList.remove('online');
    document.body.dataset.connected='no';
 };
 new ResizeObserver(resize).observe(document.getElementById('terminal'));
 // No terminal.onData() handler: sending commands from the upper panel is forbidden.
 window.hsUpper={
   outputBytes:()=>outputBytes,
   cells:()=>({cols:terminal.cols,rows:terminal.rows}),
   text:()=>Array.from({length:terminal.rows},(_,i)=>
      terminal.buffer.active.getLine(i)?.translateToString(true)||'').join('\n'),
   socket:ws,
 };
})();
