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
        self.users = {user:{} for user in usernames} if usernames else {}
        self.users_lock = threading.RLock()
        self.attributes = []
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump(self.users, f)
        with open(self.filename, 'r') as f:
            self.counted_users = set(json.load(f))

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

    def get_complete(self, att):
        with self.users_lock:
            return [user for user in self.users if self.users[user].get(att, False)]

    def check_off(self, user, att):
        assert att in self.att_names
        with self.users_lock:
            if not self.users[user][att]:
                self.users[user][att] = True
                msg = att.on_check_off(user, self.get_complete(att), self.users)
                if msg:
                    BOT_CLIENT.send_message(msg)
                with open(self.filename, 'w') as f:
                    json.dump(self.users, f)

    def uncheck(self, user, att):
        assert att in self.att_names
        with self.users_lock:
            self.users[user][att] = False
            with open(self.filename, 'w') as f:
                json.dump(self.users, f)

    def add(self, user):
        with self.users_lock:
            if user in self.users:
                print 'user already on list!'
            else:
                self.users[user] = {}

    def remove(self, user):
        with self.users_lock:
            if user in self.users:
                del self.users[user]
            else:
                print 'users not on list!'

    def get_user(self, event):
        with self.users_lock:
            if event['type'] == 'message':
                user = event['message']['sender_full_name']
                if user in self.users:
                    return user
                else:
                    print 'user %s not found in users list' % user
            return False

    def callback(self, event):
        with self.users_lock:
            user = self.get_user(event)
            if user:
                for att in self.attributes:
                    if att.message_filter(event):
                        self.check_off(user, att)

    def start(self):
        CLIENT.call_on_each_event(self.callback)

    def start_in_thread(self):
        t = threading.Thread(target=self.start)
        t.daemon = True
        t.start()

class HavePushedCommitsToZulip(Attribute):
    def __init__(self):
        self.name = "commit"
        def filterfunc(event):
            return event['type'] == 'message' and event['message']['type'] == 'stream' and event['message']['display_recipient'] == 'test-bot2' and 'pushed' in event['message']['content'] and 'to branch' in event['message']['content']
        self.message_filter = filterfunc
        def update_msg(username, done, users):
            return {
                "type": "stream",
                "to": "test-bot2",
                "subject": "Commit Participation Progress",
                "content": "%d out of %d Hacker Schooler%s published pushing of commits on Zulip!" % (len(done), len(users), ' has' if len(self.counted_users) == 1 else 's have')
            }
        self.on_check_off = update_msg
        self.on_uncheck = None

class HaveWrittenZulipMessage(Attribute):
    def __init__(self):
        self.name = 'zulip'
        def filterfunc(event):
            return event['type'] == 'message' and ('`' in event['message']['content'] or '~~~' in event['message']['content'] or '    ' in event['message']['content'])
        self.message_filter = filterfunc
        def update_msg(username, done, users):
            return {
                "type": "stream",
                "to": "test-bot2",
                "subject": "Zulip Participation Progress",
                "content": "%d out of %d Hacker Schooler%s sent messages containing code on Zulip!" % (len(done), len(users), ' has' if len(self.counted_users) == 1 else 's have')
            }
        self.on_check_off = update_msg
        self.on_uncheck = None

if __name__ == '__main__':
    counter = ZulipUsersCounter(filename='data.json')
    counter.add_attribute(HavePushedCommitsToZulip())
    counter.add_attribute(HaveWrittenZulipMessage())
    counter.start()
