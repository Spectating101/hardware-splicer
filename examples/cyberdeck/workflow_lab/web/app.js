/* HS touchscreen keyboard over an ACTUAL sandboxed OpenSSH PTY.
 * Rendering/parsing uses upstream xterm.js; this is not custom VT emulation.
 * Never attach this UI to user credentials or expose it beyond loopback.
 */
(() => {
  'use strict';
  const terminalArea = document.getElementById('terminal');
  const keysRoot = document.getElementById('keys');
  const status = document.getElementById('status');
  const dimensions = document.getElementById('dimensions');
  const latency = document.getElementById('latency');
  const probe = document.getElementById('probe');
  const reconnect = document.getElementById('reconnect');
  const term = new Terminal({
    allowTransparency:false,
    fontFamily:'ui-monospace, SFMono-Regular, Consolas, monospace',
    fontSize:18, lineHeight:1.18, letterSpacing:0,
    scrollback:1200, cursorBlink:true,
    cursorStyle:'bar', theme:{
      background:'#0a1118',foreground:'#c9e8dd',cursor:'#d7f9e8',
      selectionBackground:'#52726366',
      black:'#101a20', red:'#fa8582', green:'#8ae1bb', yellow:'#ffd38f',
      blue:'#8bb6ef',magenta:'#c7a5ef',cyan:'#80e7e3',white:'#e8efed',
    },
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(terminalArea);
  let ws;
  let shift=false;
  let ctrl=false;
  let pendingProbe=null;
  let probeBuffer='';
  let touchInputCount=0;
  let completedProbes=0;
  const qp=new URLSearchParams(window.location.search);
  const token=qp.get('token')||'';
  const wsScheme=window.location.protocol==='https:'?'wss:':'ws:';

  function send(value){
    if(!ws||ws.readyState!==WebSocket.OPEN)return false;
    ws.send(JSON.stringify({type:'input',data:value}));
    return true;
  }
  function resize(){
    fit.fit();
    dimensions.textContent=term.cols+' × '+term.rows+' cells';
    if(ws&&ws.readyState===WebSocket.OPEN){
      ws.send(JSON.stringify({type:'resize',cols:term.cols,rows:term.rows}));
    }
  }
  function setMode(mode){
    shift=mode==='shift'?!shift:shift;
    ctrl=mode==='ctrl'?!ctrl:ctrl;
    document.querySelectorAll('[data-mode]').forEach(el=>{
      el.classList.toggle('active',el.dataset.mode==='shift'?shift:ctrl);
      el.setAttribute('aria-pressed',el.classList.contains('active')?'true':'false');
    });
    document.querySelectorAll('[data-letter]').forEach(el=>{
      el.textContent=shift?el.dataset.letter.toUpperCase():el.dataset.letter;
    });
  }
  function press(key){
    if(key==='SHIFT'||key==='CTRL'){setMode(key.toLowerCase());return;}
    const special={
      'ESC':'\x1b','TAB':'\t','ENTER':'\r','BACKSPACE':'\x7f','SPACE':' ',
      'UP':'\x1b[A','DOWN':'\x1b[B','RIGHT':'\x1b[C','LEFT':'\x1b[D',
      'TMUX':'\x02','CTRL-C':'\x03','CTRL-D':'\x04',
    };
    let output=special[key]||key;
    if(!(key in special)){
      if(shift){output=output.toUpperCase();}
      if(ctrl&&output.length===1&&/[a-zA-Z]/.test(output)){
        output=String.fromCharCode(output.toUpperCase().charCodeAt(0)-64);
      }
    }
    if(send(output)){touchInputCount++;}
    shift=false;
    ctrl=false;
    setMode('reset');
    term.focus();
  }
  const KEY_ROWS=[
    [['ESC','Esc'],['~','~'],['!','!'],['@','@'],['#','#'],['$','$'],['%','%'],
      ['^','^'],['&','&'],['*','*'],['(','('],[')',')'],['BACKSPACE','⌫']],
    [['TAB','Tab'],...Array.from('qwertyuiop').map(k=>[k,k]),['[','['],[']',']'],['\\','\\']],
    [['CTRL','Ctrl'],...Array.from('asdfghjkl').map(k=>[k,k]),[';', ';'],["'", "'"],['ENTER','Enter']],
    [['SHIFT','Shift'],...Array.from('zxcvbnm').map(k=>[k,k]),[',',','],['.','.'],['/','/'],['UP','↑']],
    [['TMUX','Ctrl+B'],['CTRL-C','Ctrl+C'],['CTRL-D','Ctrl+D'],['LEFT','←'],
      ['DOWN','↓'],['RIGHT','→'],['SPACE','Space'],['-','-'],['=','='],['ENTER','↵']],
  ];
  const specialKeys=new Set(['ESC','TAB','CTRL','SHIFT','ENTER','BACKSPACE',
    'UP','DOWN','LEFT','RIGHT','TMUX','CTRL-C','CTRL-D','SPACE']);
  for(const list of KEY_ROWS){
    const row=document.createElement('div');row.className='keyrow';
    for(const [key,label] of list){
      const button=document.createElement('button');
      button.type='button';button.className='key';
      if(specialKeys.has(key))button.classList.add('special');
      if(['SPACE'].includes(key))button.classList.add('space');
      if(['ENTER','CTRL','SHIFT','TMUX','TAB'].includes(key))button.classList.add('wide');
      button.textContent=label;
      button.dataset.key=key;
      if(key.length===1&&/[a-z]/.test(key)){button.dataset.letter=key;}
      if(key==='CTRL'||key==='SHIFT'){
        button.dataset.mode=key.toLowerCase();
        button.setAttribute('aria-pressed','false');
      }
      button.addEventListener('pointerdown',e=>e.preventDefault());
      button.addEventListener('click',()=>press(key));
      row.appendChild(button);
    }
    keysRoot.appendChild(row);
  }
  term.onData(send);
  ws=new WebSocket(wsScheme+'//'+location.host+'/ws?token='+encodeURIComponent(token));
  ws.binaryType='arraybuffer';
  ws.onopen=()=>{
    status.innerHTML='<span class="pulse"></span>SSH CONNECTING';
    resize();
  };
  ws.onmessage=(event)=>{
    if(typeof event.data==='string'){
      let msg;
      try{msg=JSON.parse(event.data);}catch{return;}
      if(msg.type==='status'){
        status.innerHTML='<span class="pulse"></span>REAL SSH / SANDBOX';
        status.classList.add('online');
        document.body.dataset.connected='yes';
        resize();
      }
      if(msg.type==='error'){status.title=msg.value;}
      return;
    }
    const bytes=new Uint8Array(event.data);
    term.write(bytes);
    if(pendingProbe){
      const out=new TextDecoder().decode(bytes);
      probeBuffer=(probeBuffer+out).slice(-512);
      if(probeBuffer.includes(pendingProbe.token)){
        const delta=performance.now()-pendingProbe.start;
        const text=delta.toFixed(1)+' ms SSH echo';
        latency.textContent=text;
        latency.dataset.lastRttMs=delta.toFixed(3);
        completedProbes++;
        latency.dataset.completedProbes=String(completedProbes);
        pendingProbe=null;probeBuffer='';
      }
    }
  };
  ws.onclose=()=>{
    status.innerHTML='<span class="pulse"></span>DISCONNECTED';
    status.classList.remove('online');
    document.body.dataset.connected='no';
  };
  ws.onerror=()=>{status.title='WebSocket error';};
  // Security: probe token must NOT appear literally in the local echoed
  // command, otherwise measuring terminal echo would produce a false RTT.
  reconnect.addEventListener('click',()=>window.location.reload());
  probe.addEventListener('click',()=>{
    if(!ws||ws.readyState!==WebSocket.OPEN)return;
    const token='HSP_'+Math.random().toString(36).slice(2,10).toUpperCase();
    const octal=Array.from(token).map(ch=>'\\'+ch.charCodeAt(0).toString(8).padStart(3,'0')).join('');
    pendingProbe={token,start:performance.now()};
    probeBuffer='';
    send("printf '"+octal+"\\n'\r");
  });
  window.addEventListener('resize',resize);
  new ResizeObserver(resize).observe(terminalArea);
  window.hsBench={
    send,press,term,ready:()=>Boolean(ws&&ws.readyState===WebSocket.OPEN),
    getTouches:()=>touchInputCount,
    getLastRtt:()=>latency.dataset.lastRttMs||null,
    getProbeCount:()=>completedProbes,
    getScreenText:()=>Array.from({length:term.rows},(_,i)=>{
      return term.buffer.active.getLine(i)?.translateToString(true)||'';
    }).join('\n'),
  };
  requestAnimationFrame(resize);
})();
