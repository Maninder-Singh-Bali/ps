'use strict';
let setup=false;
fetch('/api/access/session').then(r=>r.json()).then(s=>{
 if(s.authenticated){location.replace('/');return}
 setup=!s.configured;
 if(setup){document.querySelector('#intro').textContent=s.setup_allowed?'Create your private Studio sign-in. Use at least 12 characters.':'Set up sign-in on the Windows desktop first.';document.querySelector('#submit').textContent='Create sign-in';document.querySelector('#submit').disabled=!s.setup_allowed;document.querySelector('#password').autocomplete='new-password';document.querySelector('#password').minLength=12}
}).catch(()=>document.querySelector('#status').textContent='Desktop unavailable. Check its network and awake state.');
document.querySelector('form').addEventListener('submit',async e=>{
 e.preventDefault();const b=document.querySelector('#submit');b.disabled=true;
 try{const r=await fetch('/api/access/'+(setup?'setup':'login'),{method:'POST',headers:{'Content-Type':'application/json','X-Pixeloid-Client':'1'},body:JSON.stringify({user:document.querySelector('#user').value,password:document.querySelector('#password').value})});const d=await r.json();if(!r.ok)throw Error(d.error);document.querySelector('#password').value='';location.replace('/')}
 catch(err){document.querySelector('#status').textContent=err.message;b.disabled=false}
});
