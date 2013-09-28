import os
from functools import wraps

from flask import Flask, render_template, redirect, request
app = Flask(__name__)
app.debug = True

from zulipcounter import ZulipUsersCounter, HaveWrittenZulipMessage, HavePushedCommitToZulip, HavePostedBroadcast

users = ['Tom Ballinger',
       "Jay Weisskopf (S'13)"]

counter = ZulipUsersCounter(filename='data.json', usernames=users)
counter.add_attribute(HaveWrittenZulipMessage())
counter.add_attribute(HavePushedCommitToZulip())
counter.add_attribute(HavePostedBroadcast())
counter.start_in_thread()

HS_EXTERNAL_IP = os.environ['HS_EXTERNAL_IP']

def require_HS_ip(func):
    @wraps(func)
    def newfunc(*args, **kwargs):
        if (request.remote_addr == HS_EXTERNAL_IP
            or request.remote_addr[:7] == '192.168'
            or request.remote_addr == '127.0.0.1'):
            return func(*args, **kwargs)
        else:
            print request.remote_addr, '!=', HS_EXTERNAL_IP
            return '<html>Sorry, this app just for people physically located at 455 Broadway.</html>'
    return newfunc

def get_username_by_hash(num):
    username, = [name for name in counter.user_names if hash(name) == int(num)]
    return username

@app.route('/')
@require_HS_ip
def main():
    return render_template('users.html', counter=counter, hash=hash)

@app.route('/check-off/<att>/<num>')
@require_HS_ip
def check_off(att, num):
    name = get_username_by_hash(num)
    counter.check_off(name, att, run_callback=False)
    return redirect('/')

@app.route('/uncheck/<att>/<num>')
@require_HS_ip
def uncheck(att, num):
    name = get_username_by_hash(num)
    counter.uncheck(name, att)
    return redirect('/')

@app.route('/remove/<num>')
@require_HS_ip
def remove(num):
    name = get_username_by_hash(num)
    counter.remove(name)
    return redirect('/')

@app.route('/add', methods=["POST"])
@require_HS_ip
def add():
    counter.add(request.form['name'])
    return redirect('/')

@app.route('/update/<att>')
@require_HS_ip
def update(att):
    counter.update(att)
    return redirect('/')

if __name__ == '__main__':
    app.run()
