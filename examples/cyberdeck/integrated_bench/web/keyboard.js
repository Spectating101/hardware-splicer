/* Independent LOWER glass: touch keys only, no terminal read access. */
(() => {
 'use strict';
 const token=new URLSearchParams(location.search).get('token')||'';
 const status=document.getElementById('status');
 const counter=document.getElementById('touch-count');
 const keypad=document.getElementById('keypad');
 let layer='letters',ctrl=false,shift=false,count=0;
 const LETTERS=[
   'qwertyui'.split(''), 'opasdfgh'.split(''), 'jklzxcvb'.split(''),
   ['n','m',',','.','/',';',':',"'"],
   ['ESC','TAB','CTRL','SHIFT','LEFT','DOWN','UP','RIGHT'],
   ['TMUX','CTRL-C','CTRL-D','BACKSPACE','SPACE','ENTER'],
 ];
 const SYMBOLS=[
   '12345678'.split(''),['9','0','!','@','#','$','%','^'],
   ['&','*','(',')','[',']','{','}'],
   ['`','~','+','-','_','=','\\','|'],
   ['<','>','?',':',';','"','ESC','TAB'],
   ['CTRL','SHIFT','LEFT','DOWN','UP','RIGHT','BACKSPACE','ENTER'],
   ['TMUX','CTRL-C','CTRL-D','SPACE'],
 ];
 const enc={
   ESC:'\x1b',TAB:'\t',ENTER:'\r',BACKSPACE:'\x7f',SPACE:' ',
   UP:'\x1b[A',DOWN:'\x1b[B',LEFT:'\x1b[D',RIGHT:'\x1b[C',
   TMUX:'\x02','CTRL-C':'\x03','CTRL-D':'\x04',
 };
 const special=new Set([...Object.keys(enc),'CTRL','SHIFT']);
 const ws=new WebSocket('ws://'+location.host+'/keyboard/ws?token='+encodeURIComponent(token));
 ws.onmessage=(event)=>{
   const msg=JSON.parse(event.data);
   if(msg.type==='status'){
      const ok=msg.value==='connected';
      status.textContent=ok?'READY':msg.value.toUpperCase();
      document.body.classList.toggle('online',ok);
      document.body.dataset.connected=ok?'yes':'no';
   }
   if(msg.type==='error') status.textContent=msg.value;
 };
 ws.onclose=()=>{status.textContent='DISCONNECTED';document.body.dataset.connected='no';};
 function send(value){
    if(ws.readyState!==WebSocket.OPEN)return false;
    ws.send(JSON.stringify({type:'input',data:value}));
    count++;counter.textContent=count+' keystrokes';return true;
 }
 function press(key){
    if(key==='CTRL'){ctrl=!ctrl;render();return;}
    if(key==='SHIFT'){shift=!shift;render();return;}
    let ch=Object.hasOwn(enc,key)?enc[key]:key;
    if(!Object.hasOwn(enc,key)){
        if(shift)ch=ch.toUpperCase();
        if(ctrl&&/^[a-z]$/i.test(ch))ch=String.fromCharCode(ch.toUpperCase().charCodeAt(0)-64);
    }
    send(ch);shift=false;ctrl=false;render();
 }
 function render(){
    keypad.replaceChildren();
    const rows=layer==='letters'?LETTERS:SYMBOLS;
    for(const keys of rows){
       const row=document.createElement('div');row.className='keyrow';
       for(const key of keys){
          const btn=document.createElement('button');btn.type='button';btn.className='key';
          btn.dataset.key=key;btn.textContent=key==='SPACE'?'SPACE':key;
          if(special.has(key))btn.classList.add('special');
          if((key==='CTRL'&&ctrl)||(key==='SHIFT'&&shift))btn.classList.add('active');
          btn.addEventListener('pointerdown',e=>e.preventDefault());
          btn.addEventListener('click',()=>press(key));row.appendChild(btn);
       }
       keypad.appendChild(row);
    }
    document.body.dataset.keyboardLayer=layer;
 }
 for(const choice of ['letters','symbols']){
    document.getElementById(choice).addEventListener('click',()=>{
        layer=choice;ctrl=false;shift=false;render();
        document.getElementById('letters').classList.toggle('active',layer==='letters');
        document.getElementById('symbols').classList.toggle('active',layer==='symbols');
    });
 }
 render();
 window.hsLower={count:()=>count,layer:()=>layer,send,socket:ws};
})();
