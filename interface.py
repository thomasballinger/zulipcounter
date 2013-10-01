import os
from functools import wraps

from flask import Flask, render_template, redirect, request, Response
app = Flask(__name__)

from zulipcounter import ZulipUsersCounter, HaveWrittenZulipMessage, HavePushedCommitToZulip, HavePostedBroadcast

HS_EXTERNAL_IP = os.environ['HS_EXTERNAL_IP']
NOT_VERY_SECRET_PASSWORD = os.environ['NOT_VERY_SECRET_PASSWORD']

users = ['Tom Ballinger']

counter = ZulipUsersCounter(filename='data.json', usernames=users)
counter.add_attribute(HaveWrittenZulipMessage())
counter.add_attribute(HavePushedCommitToZulip())
counter.add_attribute(HavePostedBroadcast())
counter.start_in_thread()

def require_HS_ip(func):
    @wraps(func)
    def newfunc(*args, **kwargs):
        if (request.remote_addr == HS_EXTERNAL_IP
            or request.remote_addr[:7] == '192.168'
            or request.remote_addr == '127.0.0.1'):
            return func(*args, **kwargs)
        else:
            print request.remote_addr, '!=', HS_EXTERNAL_IP
            auth = request.authorization
            if auth and auth.password.replace(' ', '').lower() == NOT_VERY_SECRET_PASSWORD.lower():
                return func(*args, **kwargs)
            else:
                if auth:
                    print 'bad auth:', auth.username, auth.password
                return Response(
                'Sorry, this app just for people physically located at 455 Broadway.', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'})
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

@app.route('/update/<att>')
@require_HS_ip
def update(att):
    counter.update(att)
    return redirect('/')

if __name__ == '__main__':
    app.run(port=8222, host='0.0.0.0')
