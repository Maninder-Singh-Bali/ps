"""Private-LAN authentication. Secrets never enter the project database."""
import hashlib, hmac, ipaddress, json, secrets, threading, time
from http.cookies import SimpleCookie
from pathlib import Path

COOKIE='pixeloid_session'

class Access:
    def __init__(self, directory, port, lan_ip=None, subnet=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.file=self.directory/'credentials.json';self.lock=threading.RLock()
        self.sessions={};self.failures={};self.port=port;self.lan_ip=lan_ip
        self.network=ipaddress.ip_network(subnet) if subnet else None
        if lan_ip and (not ipaddress.ip_address(lan_ip).is_private or not self.network or ipaddress.ip_address(lan_ip) not in self.network):
            raise ValueError('LAN mode requires a private address and its explicit local subnet.')
    @property
    def configured(self):return self.file.is_file()
    def origin(self,headers,peer):
        address=ipaddress.ip_address(peer)
        if not address.is_loopback and (not self.network or address not in self.network):raise PermissionError('Only the configured local subnet can access Studio.')
        hosts={f'127.0.0.1:{self.port}',f'localhost:{self.port}'}
        if self.lan_ip:hosts.add(f'{self.lan_ip}:{self.port}')
        host=headers.get('Host')
        if host not in hosts:raise PermissionError('Use the configured Studio address.')
        if headers.get('Origin') and headers['Origin']!='http://'+host:raise PermissionError('Same-origin request required.')
        if headers.get('Sec-Fetch-Site')=='cross-site':raise PermissionError('Cross-site request refused.')
    def setup(self,user,password,peer):
        if not ipaddress.ip_address(peer).is_loopback:raise PermissionError('Create the first sign-in on the Windows desktop at localhost.')
        if not isinstance(user,str) or not 1<=len(user.strip())<=80:raise ValueError('Enter a sign-in name.')
        if not isinstance(password,str) or not 12<=len(password)<=256:raise ValueError('Use a password of 12–256 characters.')
        with self.lock:
            if self.configured:raise PermissionError('Sign-in is already configured.')
            salt=secrets.token_hex(24)
            record={'user':user.strip(),'salt':salt,'iterations':600000,'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()}
            with self.file.open('x',encoding='utf-8') as f:json.dump(record,f)
    def login(self,user,password,peer):
        with self.lock:
            stamp=time.time();attempts=[t for t in self.failures.get(peer,[]) if stamp-t<600]
            if len(attempts)>=8:raise PermissionError('Too many sign-in attempts. Wait ten minutes.')
            if len(self.failures)>1024:self.failures.clear()
            self.failures[peer]=attempts+[stamp]
            if not self.configured:raise PermissionError('Set up sign-in on the Windows desktop first.')
            row=json.loads(self.file.read_text(encoding='utf-8'))
            if not isinstance(password,str) or len(password)>256:raise PermissionError('Incorrect sign-in.')
            digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row['salt']),row['iterations']).hex()
            if not hmac.compare_digest(str(user),row['user']) or not hmac.compare_digest(digest,row['hash']):raise PermissionError('Incorrect sign-in.')
            self.failures.pop(peer,None);token=secrets.token_urlsafe(32)
            self.sessions={k:v for k,v in self.sessions.items() if stamp-v['last']<43200 and stamp-v['created']<86400}
            if len(self.sessions)>=64:self.sessions.pop(next(iter(self.sessions)))
            self.sessions[hashlib.sha256(token.encode()).hexdigest()]={'created':stamp,'last':stamp,'csrf':secrets.token_urlsafe(32)}
            return token
    def session(self,headers):
        try:c=SimpleCookie();c.load(headers.get('Cookie',''));token=c[COOKIE].value
        except (KeyError,ValueError):return None
        with self.lock:
            row=self.sessions.get(hashlib.sha256(token.encode()).hexdigest());stamp=time.time()
            if not row or stamp-row['last']>43200 or stamp-row['created']>86400:return None
            row['last']=stamp;return row
    def check(self,headers,write=False):
        row=self.session(headers)
        if not row:return False
        if write and not hmac.compare_digest(headers.get('X-Pixeloid-CSRF',''),row['csrf']):raise PermissionError('Session check failed. Reload Studio and try again.')
        return True
    def logout(self,headers):
        try:c=SimpleCookie();c.load(headers.get('Cookie',''));key=hashlib.sha256(c[COOKIE].value.encode()).hexdigest()
        except (KeyError,ValueError):return
        with self.lock:self.sessions.pop(key,None)

def interrupted(store):
    """Preserve outputs and submission IDs; restart never repeats expensive work."""
    changed=False
    with store.lock:
        for job in store.db['jobs'].values():
            if job.get('remote_job_id'):continue
            if job['status'] in ('queued','waiting','running'):
                job.update(status='interrupted',stage='Interrupted by dashboard restart',error='Inputs and outputs retained. Use Recover to reconcile the previous activity before resuming.',finished=time.time(),progress=None)
                changed=True
        if changed:store.save()
