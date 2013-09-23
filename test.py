#!/usr/bin/env python

import zulip
import os

CLIENT = zulip.Client(email=os.environ['ZULIP_EMAIL'],
                      api_key=os.environ['ZULIP_API_KEY'])
BOTCLIENT = zulip.Client(email=os.environ['ZULIP_COMMIT_BOT_EMAIL'],
                         api_key=os.environ['ZULIP_COMMIT_BOT_API_KEY'])

class ZulipUsersCounter(object):
    """Counts unique users that have taken some action on Zulip"""
    counters = []
    zulip_callback_set = False

    @classmethod
    def call_each_callback(cls, event): #so works as an instance method and a function
        print event
        for counter in ZulipUsersCounter.counters: # not cls so subclasses use same list
            counter.callback(event)

    @classmethod
    def start(cls):
        CLIENT.call_on_each_event(ZulipUsersCounter.call_each_callback)

    def __init__(self, filterfunc, new_user_msg, users=None, intro_message=None):
        """msg_new_user is sent when a unique user from the users list passes the filterfunc"""
        ZulipUsersCounter.counters.append(self) # not cls so subclasses use same list
        self.counted_users = set()
        self.users = users
        self.filterfunc = filterfunc
        self.new_user_msg = new_user_msg
        self.sender = BOTCLIENT
        if intro_message:
            self.sender.send_message(intro_message)

    def callback(self, event):
        if self.filterfunc(event):
            if event['type'] == 'message':
                user = event['message']['sender_full_name']
                if self.users is None or user in self.users:
                    self.count(user)

    def count(self, user):
        if user not in self.counted_users:
            self.counted_users.add(user)
            if self.new_user_msg.func_code.co_argcount == 1:
                self.sender.send_message(self.new_user_msg(user))
            else:
                self.sender.send_message(self.new_user_msg())

class CommitUsersCounter(ZulipUsersCounter):
    def __init__(self):
        def filterfunc(event):
            return event['type'] == 'message' and event['message']['type'] == 'stream' and event['message']['display_recipient'] == 'test-bot2' and 'pushed' in event['message']['content'] and 'to branch' in event['message']['content']
        def new_user_msg():
            return {
                "type": "stream",
                "to": "test-bot2",
                "subject": "Commit Participation Progress",
                "content": "%d Hacker Schooler%s published pushing of commits on Zulip!" % (len(self.counted_users), ' has' if len(self.counted_users) == 1 else 's have')
            }
        intro_message = {
                "type": "stream",
                "to": "test-bot2",
                "subject": "Commit Participation Progress",
                "content": "Let's keep track of how many Hacker Schoolers from this batch have published the pushing of a commit on Zulip!"
            }
        super(CommitUsersCounter, self).__init__(filterfunc, new_user_msg, users=None, intro_message=intro_message)

class UsedZulipUsersCounter(ZulipUsersCounter):
    def __init__(self):
        def filterfunc(event):
            return event['type'] == 'message' and ('`' in event['message']['content'] or '~~~' in event['message']['content'] or '    ' in event['message']['content'])
        def new_user_msg():
            return {
                "type": "stream",
                "to": "test-bot2",
                "subject": "Zulip Participation Progress",
                "content": "%d Hacker Schooler%s sent messages containing code on Zulip!" % (len(self.counted_users), ' has' if len(self.counted_users) == 1 else 's have')
            }
        intro_message = {
                "type": "stream",
                "to": "test-bot2",
                "subject": "Zulip Participation Progress",
                "content": "Let's keep track of how many Hacker Schoolers from this batch have sent messages on Zulip containing correctly formatted code! (see 'message formatting' under the gear icon menu for help)"
            }
        super(UsedZulipUsersCounter, self).__init__(filterfunc, new_user_msg, users=None, intro_message=intro_message)

a = UsedZulipUsersCounter()
b = CommitUsersCounter()
a.start()
