#!/usr/bin/env python3
"""Run inside a disposable root container with old/new installer mounts.

Exercises actual package lifecycle scripts and frozen privileged maintenance,
including two users, PyInstaller pairs, custom history paths and closed apps.
"""
import os
from pathlib import Path
import pwd
import signal
import shutil
import sqlite3
import subprocess
import sys
import time

from timetrace.package_restart import discover_instances, read_process

kind=sys.argv[1]
old_dir=Path('/old-packages')
new_dir=Path('/new-packages')
patterns={'deb':'*.deb','rpm':'*.rpm','arch':'*.pkg.tar.zst'}

def install(path):
    commands={'deb':['dpkg','-i'], 'rpm':['rpm','-Uvh','--replacepkgs'],
              'arch':['pacman','-U','--noconfirm']}
    subprocess.run([*commands[kind],str(path)],check=True)

def instances():
    processes=[process for entry in Path('/proc').iterdir() if entry.name.isdecimal()
               if (process:=read_process(int(entry.name))) is not None]
    return discover_instances(processes)

def wait_for(predicate, explanation, timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=predicate()
        if result: return result
        time.sleep(.1)
    raise AssertionError(explanation)

def user_options(name, environment):
    account=pwd.getpwnam(name)
    return dict(env=environment, user=account.pw_uid, group=account.pw_gid,
                extra_groups=os.getgrouplist(name,account.pw_gid))

old=next(old_dir.glob(patterns[kind]))
new=next(new_dir.glob(patterns[kind]))
install(old)
assert not instances(), 'fresh install launched an app'
accounts=[]
launchers=[]
try:
    for number in (1,2):
        name=f'timetrace_test{number}'
        subprocess.run(['useradd','-m',name],check=True)
        account=pwd.getpwnam(name)
        runtime=Path(f'/run/user/{account.pw_uid}')
        runtime.mkdir(parents=True,exist_ok=True)
        runtime.chmod(0o700); os.chown(runtime,account.pw_uid,account.pw_gid)
        home=Path(account.pw_dir)/'custom-home'
        home.mkdir(); os.chown(home,account.pw_uid,account.pw_gid)
        env={'HOME':str(home),'XDG_RUNTIME_DIR':str(runtime),'QT_QPA_PLATFORM':'offscreen',
             'XDG_CURRENT_DESKTOP':'','XDG_SESSION_TYPE':'','PATH':'/usr/bin:/bin'}
        address=subprocess.check_output([shutil.which('dbus-daemon'),'--session','--fork','--print-address'],
            **user_options(name,env),text=True).strip()
        env['DBUS_SESSION_BUS_ADDRESS']=address
        if number==2:
            env['XDG_DATA_HOME']=str(home/'data with spaces')
        database=Path(env.get('XDG_DATA_HOME',str(home/'.local/share')))/'timetrace/data.db'
        launchers.append(subprocess.Popen(['/usr/bin/timetrace','--minimized'], **user_options(name,env),
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        def old_instance():
            found=[p for p in instances() if p.uid==account.pw_uid]
            return found[0] if len(found)==1 and database.is_file() else None
        process=wait_for(old_instance,'old app failed to start')
        accounts.append((account,env,database,process))
    time.sleep(1.5)  # allow old app's first database checkpoint
    install(new)
    assert subprocess.check_output(['/usr/bin/timetrace','--version'],text=True).strip()=='timetrace 0.1.8'
    for account,env,database,old_process in accounts:
        def replacement():
            found=[p for p in instances() if p.uid==account.pw_uid]
            if len(found)!=1 or found[0].pid==old_process.pid: return None
            if ' (deleted)' in os.readlink(f'/proc/{found[0].pid}/exe'): return None
            return found[0]
        process=wait_for(replacement,'new app did not replace the old app')
        assert process.uid != 0
        assert process.environment['HOME']==env['HOME']
        assert process.environment['DBUS_SESSION_BUS_ADDRESS']==env['DBUS_SESSION_BUS_ADDRESS']
        assert '--minimized' in process.args
        def history_saved():
            try:
                with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as connection:
                    rows=connection.execute('select id,end_ts from presence_intervals order by id').fetchall()
                return len(rows)>=2 and rows[0][1] is not None and rows[-1][1] is None
            except sqlite3.Error:
                return False
        assert wait_for(history_saved,'history not preserved or old interval left open')
        print(f'PASS {kind}: UID {account.pw_uid}, PID {old_process.pid}->{process.pid}, history preserved',flush=True)
    for process in instances():
        os.kill(process.pid,signal.SIGTERM)
    wait_for(lambda:not instances(),'apps did not exit')
    install(new)
    assert not instances(), 'upgrade launched a previously closed app'
    remove={'deb':['dpkg','-r','timetrace'],'rpm':['rpm','-e','timetrace'],
            'arch':['pacman','-R','--noconfirm','timetrace-git']}
    subprocess.run(remove[kind],check=True)
    install(new)
    assert not instances(), 'fresh 0.1.8 install launched an app'
    print(f'PASS {kind}: reinstall while closed and fresh install stay closed',flush=True)
finally:
    for process in instances():
        try: os.kill(process.pid,signal.SIGTERM)
        except ProcessLookupError: pass
    for launcher in launchers:
        try: launcher.wait(timeout=5)
        except subprocess.TimeoutExpired: pass
