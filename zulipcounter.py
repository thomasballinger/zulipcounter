#!/usr/bin/env python

import zulip
import os
import json
import threading

#TODO use a database instead

CLIENT = zulip.Client(email=os.environ['ZULIP_EMAIL'],
                      api_key=os.environ['ZULIP_API_KEY'])
BOT_CLIENT = zulip.Client(email=os.environ['ZULIP_COMMIT_BOT_EMAIL'],
                         api_key=os.environ['ZULIP_COMMIT_BOT_API_KEY'])

class Attribute(object):
    def __init__(self, name, message_filter=lambda *args:False, on_checkoff=lambda *args:None, on_uncheck=lambda *args:None):
        """


        on_checkoff, on_complete and on_uncheck with be passed arguments:
            on_checkoff(username, done, total) -> message to broadcast
            on_uncheck(username, done, total) -> message to send
        """
        self.name = name
        self.message_filter = message_filter
        self.on_checkoff = on_checkoff
        self.on_uncheck = on_uncheck

class ZulipUsersCounter(object):
    """Counts unique users that have taken various action on Zulip

    For each attribute added allows filters and messages to be send on Zulip event
    """

    def __init__(self, filename, usernames=None):
        """msg_new_user is sent when a unique user from the users list passes the filterfunc"""
        self.filename = filename
        self.users = dict([(user,{}) for user in usernames]) if usernames else {}
        self.users_lock = threading.RLock()
        self.attributes = []
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump(self.users, f)
        with open(self.filename, 'r') as f:
            self.users = json.load(f)

    def add_attribute(self, attribute):
        self.attributes.append(attribute)

    @property
    def att_names(self):
        with self.users_lock:
            return [att.name for att in self.attributes]

    @property
    def user_names(self):
        with self.users_lock:
            return self.users.keys()

    @property
    def all(self):
        return self.user_names

    def has_done(self, user, att):
        return self.users[user].get(att.name, False)

    def __getattr__(self, attr):
        try:
            if attr[:4].lower() == 'not_':
                att, = [att for att in self.attributes if att.name.lower() == attr[4:].lower()]
                return self.get_incomplete(att)
            else:
                att, = [att for att in self.attributes if att.name.lower() == attr.lower()]
                return self.get_complete(att)
        except ValueError:
            raise AttributeError(repr(self)+' doesn\'t have attribute '+att)

    def get_complete(self, att):
        if not att in self.attributes:
            att, = [a for a in self.attributes if a.name == att]
        assert att in self.attributes
        with self.users_lock:
            return [user for user in self.users if self.users[user].get(att.name, False)]

    def get_incomplete(self, att):
        if not att in self.attributes:
            att, = [a for a in self.attributes if a.name == att]
        assert att in self.attributes
        with self.users_lock:
            return [user for user in self.users if not self.users[user].get(att.name, False)]

    def check_off(self, username, att, run_callback=True):
        if not att in self.attributes:
            att, = [a for a in self.attributes if a.name == att]
        assert att in self.attributes
        with self.users_lock:
            if not self.users[username].get(att.name, False):
                self.users[username][att.name] = True
                msg = att.on_checkoff(username, self.get_complete(att), self.users)
                print 'got this message from', att, 'and user', username
                if msg and run_callback:
                    BOT_CLIENT.send_message(msg)
                with open(self.filename, 'w') as f:
                    json.dump(self.users, f)

    def update(self, att):
        if not att in self.attributes:
            att, = [a for a in self.attributes if a.name == att]
        assert att in self.attributes
        msg = att.on_checkoff("someone", self.get_complete(att), self.users)
        if msg:
            BOT_CLIENT.send_message(msg)

    def uncheck(self, user, att):
        if not att in self.attributes:
            att, = [a for a in self.attributes if a.name == att]
        assert att in self.attributes
        with self.users_lock:
            self.users[user][att.name] = False
            with open(self.filename, 'w') as f:
                json.dump(self.users, f)

    def add(self, user):
        with self.users_lock:
            if user in self.users:
                print 'user already on list!'
            else:
                self.users[user] = {}
                with open(self.filename, 'w') as f:
                    json.dump(self.users, f)

    def remove(self, user):
        with self.users_lock:
            if user in self.users:
                del self.users[user]
                with open(self.filename, 'w') as f:
                    json.dump(self.users, f)
            else:
                print 'users not on list!'

    def get_user(self, event):
        with self.users_lock:
            if event['type'] == 'message':
                user = event['message']['sender_full_name']
                if user == 'Broadcasts':
                    text = event['message']['content']
                    try:
                        i = text.rindex('-')
                        name = text[i+2:]+" (F'13)"
                        print 'broadcasts: trying', name
                        user = name
                    except ValueError:
                        print 'user %s not found in users list' % user
                        return False
                if user in self.users:
                    return user
                else:
                    print 'user %s not found in users list' % user
            return False

    def callback(self, event):
        with self.users_lock:
            user = self.get_user(event)
            if user:
                print 'got user:', user, 'from event', event
                for att in self.attributes:
                    if att.message_filter(event):
                        print 'message filter for', att, 'succeeded'
                        self.check_off(user, att)
                    else:
                        print 'did not pass for', att

    def start(self):
        CLIENT.call_on_each_event(self.callback)

    def start_in_thread(self):
        t = threading.Thread(target=self.start)
        t.daemon = True
        t.start()


class HavePushedCommitToZulip(Attribute):
    def __init__(self):
        self.name = "commit"
        self.display_name = "pushed a commit to Github after setting up a Zulip service hook on Github"
        def filterfunc(event):
            return event['type'] == 'message' and event['message']['type'] == 'stream' and event['message']['display_recipient'] == 'commits' and 'pushed' in event['message']['content'] and 'to branch' in event['message']['content']
        self.message_filter = filterfunc
        def update_msg(username, done, users):
            return {
                "type": "stream",
                "to": "participation",
                "subject": "Commit Participation Progress",
                "content": "%d out of %d Hacker Schooler%s published pushing of commits on Zulip!" % (len(done), len(users), ' has' if len(done) == 1 else 's have')
            }
        self.on_checkoff = update_msg
        self.on_uncheck = None

class HaveWrittenCodeInZulip(Attribute):
    def __init__(self):
        self.name = 'zulipcode'
        self.display_name = 'written a Zulip message containing formatted code'
        def filterfunc(event):
            return event['type'] == 'message' and ('`' in event['message']['content'] or '~~~' in event['message']['content'] or '    ' in event['message']['content'])
        self.message_filter = filterfunc
        def update_msg(username, done, users):
            return {
                "type": "stream",
                "to": "participation",
                "subject": "Zulip Participation Progress",
                "content": "%d out of %d Hacker Schooler%s sent messages containing code on Zulip!" % (len(done), len(users), ' has' if len(done) == 1 else 's have')
            }
        self.on_checkoff = update_msg
        self.on_uncheck = None

class HaveWrittenZulipMessage(Attribute):
    def __init__(self):
        self.name = 'zulip'
        self.display_name = 'written a Zulip message'
        def filterfunc(event):
            return event['type'] == 'message'
        self.message_filter = filterfunc
        def update_msg(username, done, users):
            return {
                "type": "stream",
                "to": "participation",
                "subject": "Zulip Participation Progress",
                "content": "%d out of %d Hacker Schooler%s sent messages on Zulip!" % (len(done), len(users), ' has' if len(done) == 1 else 's have')
            }
        self.on_checkoff = update_msg
        self.on_uncheck = None

class HavePostedBroadcast(Attribute):
    def __init__(self):
        self.name = 'broadcast'
        self.display_name = 'posted a broadcast from the Hacker School site'
        def filterfunc(event):
            return event['type'] == 'message' and event['message']['display_recipient'] == 'Broadcasts'
        self.message_filter = filterfunc
        def update_msg(username, done, users):
            return {
                "type": "stream",
                "to": "participation",
                "subject": "participation",
                "content": "%d out of %d Hacker Schooler%s posted broadcasts!" % (len(done), len(users), ' has' if len(done) == 1 else 's have')
            }
        self.on_checkoff = update_msg
        self.on_uncheck = None

if __name__ == '__main__':
    counter = ZulipUsersCounter(filename='data.json')
    counter.add_attribute(HavePushedCommitToZulip())
    counter.add_attribute(HaveWrittenZulipMessage())
    counter.start()
