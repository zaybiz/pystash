# -*- coding: utf-8 -*-
import sys
import os
import shlex

import json

import argparse
from subprocess import Popen, PIPE
from clint.textui import colored
from clint import piped_in

from stash.common import StashedItem, ShelveStorage, NotListException, output
from stash.web import API, AlreadyLoggedIn
import getpass

import requests

# todo: create groups or subcommands
# todo: index should be positive int
# todo: colored
# todo: multiple objects in delete
# todo: convert to list (append flag)
# todo: convert to single value
# todo: create home dir
# todo: keys
# todo: not found error
# todo: numbered list
# todo: show index
# todo: prepend
# todo: user sticky bit in rights
# todo: add login and token to database

DB = 'stash.db'
VERSION = 0.2
# todo; don't disable stash after first search
# todo: create storage adapter and find fastest storage
# todo: fix accept with enter instead yes/no

"""
def output(message, color='white', text_only=False):
    if text_only:
        return str(getattr(colored, color)(message))
    else:
        sys.stdout.write(str(getattr(colored, color)(message)))
"""

def catch_errors(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (IndexError, KeyError):
            output("Item doesn't exists \n", 'red')
        except NotListException:
            output("Item isn't a list \n", 'red')
        except Exception, e:
            output('%s\n' % e.message, 'red')

    return wrapper


class Stash(object):
    COMMANDS = ('all', 'help', 'delete', 'sync', 'set', 'get', 'login', 'logout')
    SYNONYMS = {'remove': 'delete', 'rm': 'delete', 'del': 'delete'}

    command = None
    key = None
    value = None
    index = None
    is_list = False
    numbered = False
    overwrite = False

    def __init__(self, args):
        #self.check_installation()
        self.args = args
        self.db = ShelveStorage()
        self.os = self.detect_os()
        self.load_config()
        if self.REMOTE:
            self.api = API()

    def check_installation(self):
        netrc_path = os.path.join(os.path.expanduser('~'), '.netrc')
        if not os.path.exists(netrc_path):
            open(netrc_path, 'w').close()

        home = os.path.join(os.path.expanduser('~'), '.stash')
        if not os.path.exists(home):
            os.mkdir(home)

    def load_config(self):
        self.LOCAL = 0
        self.REMOTE = 1
        home = os.path.join(os.path.expanduser('~'), '.stash')
        config = home + '/.stash'
        if os.path.exists(config):
            config = eval("\n".join(open(config, "r").readlines()))
            for key in config:
                self.key = config[key]

    @staticmethod
    def detect_os():
        if sys.platform.startswith('win'):
            return 'windows'
        elif sys.platform.startswith('darwin'):
            return 'mac'
        elif sys.platform.startswith('linux'):
            return 'linux'
        return

    def validate_args(self):
        # todo: finish
        """Validate args values and pairs"""

        if self.args.println and self.args.copy:
            raise Exception('Unavailable argument set')
        if self.index is not None and self.index < 0:
            raise Exception('Index should be positive')

    def detect_command(self):
        # todo: code review
        command_mapping = {
            'get': self.get_item_or_index,
            'set': self.add_or_update,
            'delete': self.delete_item_or_index,
            'sync': self.sync,
            'login': self.login,
            'logout': self.logout,
            'all': self.all,
            'help': self.help
        }

        piped_data = piped_in()

        if self.args.name is not None:
            command = None
            if self.args.name.lower() in self.COMMANDS:
                command = self.args.name.lower()
            elif self.args.name.lower() in self.SYNONYMS:
                command = self.SYNONYMS[self.args.name.lower()]
            else:
                self.key = self.args.name

            if len(self.args.value) > 0:
                value = self.args.value
            elif piped_data:
                value = piped_data.strip('\n')
            else:
                value = None

            if value is not None:

                if command is not None:
                    # we need to parse value
                    if len(value) > 1:
                        self.key = str(value[0])
                        self.value = value[1:] if self.is_list else ' '.join(value[1:])
                    else:
                        self.key = ''.join(value)

                else:
                    # detect value
                    self.value = value if self.is_list else ' '.join(value)
                    command = 'set'
            else:
                command = 'get'if command is None else command
        else:
            command = 'help'
        command_mapping[command]()
        output("\n")

    #@catch_errors
    def open_stash(self):
        self.validate_args()
        self.process_args()
        self.detect_command()

    def process_args(self):
        #self.is_list = self.args.list
        self.overwrite = self.args.overwrite
        #self.index = self.args.index

    def all(self):
        result = ''
        for k, v in self.db.get_all().iteritems():
            result += '%s:\n' % k if v.is_list else '%s: ' % k
            if self.numbered:
                v.numbered = True
            result += str(v)
            result += '\n'
        output(result) if len(result) > 0 else output('Your stash is empty\n')


    # the API doesn't have to be there when the use logs in
    def login(self):
        output('Login: ')
        sys.stdin = open('/dev/tty')
        login = raw_input().lower()
        password = getpass.getpass(output('Enter password: ', 'white', text_only=True))
        api = API()
        try:
            if api.login(login, password):
                output('You have been logged in!\n', 'green')
            else:
                output('Something went wrong...\n', 'red')
        except AlreadyLoggedIn:
            output('You are already logged in\n', 'white')

    def logout(self):
        api = API()
        if api.logout():
            output('Logged out of Stash\n', 'red')
        else:
            output('Something went wrong...\n', 'red')

    def sync(self):
        api = API()
        #some_data = api.sync(self.db.get_database_data())
        local_data = self.db.get_database_data()
        # todo: remove! it's temporary stuff
        print "Data from db", local_data
        #print self.db.get_database_data()
        #r = requests.post("http://127.0.0.1/sync", data=self.db.get_database_data())
        r = requests.post("http://localhost:5000/sync", data=json.dumps(local_data))
        synced_data = r.json()
        print 'synced data: '
        print synced_data
        #self.db.set_database_data(synced_data)
        print 'Synced!!!'

    def get_item_or_index(self):

        item = None
        if self.LOCAL:
            item = self.db.get(self.key, self.index)
            if self.numbered:
                item.numbered = True
            if not self.args.copy:
                output(str(item))
            if not self.args.println:
                self.__copy_to_clipboard(str(item))
                if self.args.copy:
                    output('Value has been copied to clipboard \n')

        elif self.REMOTE:
            key = self.key
            data = self.api.get(key)
            if data.has_key('result'):
                if (data['result'] == None):
                    output('Nothing here.', 'yellow')
                else:
                    output(data['result'])
            else:
                output('Nothing here.', 'yellow')

    def __copy_to_clipboard(self, value):
        val = Popen(('echo', value.strip('\n')), stdout=PIPE)
        Popen(self.__generate_copy_command(), stdin=val.stdout)

    def delete_item_or_index(self):

        if self.LOCAL:
            if self.db.exist(self.key, self.index):
                if self.query_yes_no("Are you sure?", default="no") == "yes":
                    self.db.delete(self.key, self.index)
                    output('Item has been deleted \n')
                else:
                    # todo: create message mapping
                    output('Aborted\n', 'yellow')
            else:
                output('Item doesn\'t exists\n', 'red')

        if self.REMOTE:
            # todo: on delete check if key exists
            key = self.key
            response = self.api.delete(key)
            output('%s has been deleted' % key)

    def add_or_update(self):
        """
        Possible args:
          -o
          -l
          -i
          -n
          -s
        """
        if self.LOCAL:
            if self.db.exist(self.key, None):
                val = self.db.get(self.key)
                if not self.db.exist(self.key, self.index) and val.is_list and \
                        self.index != len(val.get_value()):
                    raise IndexError
                else:

                    if self.args.overwrite or self.query_yes_no("Are you sure that you want update?") == 'yes':
                        item = self.db.update(self.key, self.get_value(), self.index, self.args.overwrite)
                        output('Item has been updated\n')
                        if self.args.println:
                            output(str(item))
                    else:
                        output('Aborted \n', 'red')
            else:
                item = self.db.add(self.key, self.get_value())
                output('Item has been created\n', 'green')
                if self.args.println:
                    output(str(item))

        if self.REMOTE:

            key = self.key
            value = self.get_value()

            data = self.api.set(key, value)
            if data.has_key('error'):
                return colored.yellow(data['error'])

            if ('result' in data) and (data['result'] == 'exists'):
                # todo: colorize
                sys.stdin = open('/dev/tty')
                res = raw_input('Key already exist. (O)verwrite/(A)ppend/E(X)it: ')
                #while res.lower() != 'y' and res.lower() != 'n':
                #TODO
                if res.lower() == 'y':
                    self.api.set(key, value, True, False)
                if res.lower() == 'o':
                    self.api.set(key, value, True, False)
                if res.lower() == 'a':
                    self.api.set(key, value, False, True)
                else:
                    outout('Aborted', 'red')
            output('Saved', 'green')

    @staticmethod
    def help():
        output('Here will be help from list\n')

    def get_value(self):
        """
        Format value
        """
        if self.value is None:
            raise Exception("Value doesn't set")
        if self.is_list:
            value = self.value if isinstance(self.value, list) else [self.value]
        else:
            value = ' '.join(self.value) if isinstance(self.value, list) else self.value
        return value

    def __generate_copy_command(self):
        """
        Return copy command for current os
        """
        if self.os == 'mac':
            return 'pbcopy'
        return shlex.split('xclip -selection clipboard')

    def __generate_open_command(self):
        """
        Return open command for current os
        """
        if self.os == 'mac':
            return 'open'
        return 'xdg-open'

    def run(self):
        value = self.db.get(self.key, self.index)
        # todo: open list or text with text editor
        output('Opening...\n')
        Popen([self.__generate_open_command(), '%s' % str(value)], stdout=PIPE, stderr=PIPE)

    @staticmethod
    def query_yes_no(question, default="yes"):

        """
        From http://code.activestate.com/recipes/577058/

        Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

        The "answer" return value is one of "yes" or "no".
        """
        valid = {"yes": "yes", "y": "yes", "ye": "yes", "no": "no", "n": "no"}

        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while 1:
            output(question + prompt, 'yellow')
            sys.stdin = open('/dev/tty')
            choice = raw_input().lower()
            if default is not None and choice == '':
                return default
            elif choice in valid.keys():
                return valid[choice]
            else:
                output("Please respond with 'yes' or 'no' (or 'y' or 'n').\n", 'yellow')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name', nargs='?')
    parser.add_argument('value', nargs='*')

    parser.add_argument('-c', '--copy', action='store_true',
                        help="Copy item, but don\'t output it to terminal. Opposite to -p")

    parser.add_argument('-p', '--println', action='store_true', help='Print item after action')
    #parser.add_argument('-i', '--index', nargs='?', type=int, help="Set index (used for lists)")
    #parser.add_argument('-l', '--list', action='store_true', help="Create list")
    #parser.add_argument('-a', '--all', action='store_true', help="Create list")
    #parser.add_argument('-n', '--numbered', action='store_true', help="Set list type to numbered")
    parser.add_argument('-o', '--overwrite', action='store_true', help="Overwrite value if exists")
    parser.add_argument('-r', '--run', action='store_true', help="Run with associated program")
    #parser.add_argument('-m', '--marked', action='store_true',
    #                    help="On list creation means list should be marked. On list update - marks all items as done. On element update or create - marks it's completed")

    #parser.add_argument('--push')
    #parser.add_argument('--pull')
    #parser.add_argument('--login')
    #parser.add_argument('--about', nargs='?')
    #parser.add_argument('--email', nargs='?')
    arg = parser.parse_args()
    Stash(arg).open_stash()

