"""Root-owned optional Wi-Fi recovery; never reboot or cycle a healthy LAN."""
import json
from pathlib import Path
import subprocess
import time
from companion_network import NetworkMonitor


def decide(state, net, now):
    state=dict(state)
    if net.get('latency') is not None or net.get('lan'):
        state.update(since=None,attempts=0)
        return state,None
    if state.get('since') is None:state['since']=now
    if now-state['since']<120 or now-state.get('last',-1000)<300:return state,None
    recent=[stamp for stamp in state.get('resets',[]) if 0<=now-stamp<3600]
    action='reconnect'
    if state.get('attempts',0)>=1:
        if len(recent)>=2:return state,None
        action='usb-reset';recent.append(now)
    state.update(last=now,attempts=state.get('attempts',0)+1,resets=recent)
    return state,action


def command(*args):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=40)
    return result.returncode,result.stdout.strip()


def reset_usb(config):
    device=Path(config['usb_path']).resolve()
    if not str(device).startswith('/sys/devices/') or device.joinpath('idVendor').read_text().strip()!=config['vendor'] or device.joinpath('idProduct').read_text().strip()!=config['product']:
        raise ValueError('Wi-Fi USB identity changed; reset refused')
    try:
        device.joinpath('authorized').write_text('0')
        time.sleep(2)
    finally:device.joinpath('authorized').write_text('1')
    time.sleep(8)


def run():
    config=json.loads(Path('/etc/nexus-network.json').read_text())
    root=Path('/var/lib/nexus-network');root.mkdir(exist_ok=True)
    path=root/'recovery.json';boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    try:state=json.loads(path.read_text())
    except (OSError,ValueError):state={}
    if state.get('boot')!=boot:state={'boot':boot}
    code,radio=command('nmcli','radio','wifi')
    if code or radio!='enabled':return
    monitor=NetworkMonitor();monitor.probe();net=monitor.snapshot()
    # Never touch a different default-route interface such as working Ethernet.
    if net.get('interface') not in (None,config['interface']):return
    state,action=decide(state,net,time.monotonic())
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(state));temporary.replace(path)
    print(json.dumps({'check':'wifi','label':net['label'],'lan':net.get('lan'),'action':action}),flush=True)
    if not action:return
    if action=='usb-reset':reset_usb(config)
    else:command('nmcli','--wait','10','device','disconnect',config['interface'])
    code,_=command('nmcli','--wait','30','connection','up','uuid',config['uuid'],'ifname',config['interface'])
    print('Wi-Fi recovery completed' if code==0 else 'Wi-Fi recovery failed; cooldown applies',flush=True)


if __name__=='__main__':run()
