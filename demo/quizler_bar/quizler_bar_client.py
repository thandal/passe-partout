#!/bin/python

# GETTING STARTED:
# 1. Create a wallet on blockchain.info.
# 2. Go to Account Settings and set a second password.
# 3. Generate an address (or copy the one on the wallet main page)
# 4. Assemble the information in your ~/.pp_game.cfg file:
#   [game]
#   server_url = https://localhost:8000/
#   user_name = sam
#   user_btc_address = $ADDRESS
#   [blockchain]
#   wallet = $WALLET
#   password = $PASSWORD
#   second_password = $SECOND_PASSWORD

import ConfigParser
import cPickle
import os
import sys
import select
import xmlrpclib

sys.path.append('../../pp')
from pp_item import Item
from pp_item_client_blockchain import ItemClient

VERSION = '0.1'
PP_CONFIG_PATH = '~/.pp_game.cfg'

def SmartInput(message):
  """ Utility function for reading from stdin. """
  sys.stdout.write(message)
  sys.stdout.flush()
  ready = select.select([sys.stdin], [], [], 1.0)
  if sys.stdin in ready[0]:
    return sys.stdin.readline().strip()
  else:
    return ''

# Load config
config_filename = os.path.expanduser(PP_CONFIG_PATH)
config = ConfigParser.SafeConfigParser()
config.read(config_filename)
server = xmlrpclib.ServerProxy(config.get('game', 'server_url'))
user_name = config.get('game', 'user_name')
user_btc_address = config.get('game', 'user_btc_address')
key = user_btc_address

# Login
server_name = server.GetServerName()
item_client = ItemClient(config.get('blockchain', 'wallet'),
                         config.get('blockchain', 'password'),
                         config.get('blockchain', 'second_password'))
login_proof_sig = item_client.SignMessage(user_btc_address, server_name)
# May not be able to get desired user name
user_name = server.Authenticate(user_name, user_btc_address, login_proof_sig)
if not user_name:
  print 'Can\'t authenticate'
  sys.exit()

print 'You are in the public house %s' % server_name
print 'Enter h for help'

tables = {}
while 1:
  print user_name, '> ',
  while 1:
    r = SmartInput('')
    if r: break
    messages = server.GetMessages(key)
    for message in messages:
      print message
      print user_name, '> ',
    serialized_items = server.GetItems(key)
    for serialized_item in serialized_items:
      item = cPickle.loads(serialized_item)
      print 'RECEIVED ITEM "%s"' % item.name
      filename = item.name + '.item'
      while os.path.isfile(filename):
        filename += '.new'
      cPickle.dump(item, file(filename, 'w'), 0)
      print 'Saved as "%s"' % filename
  s = r.split(' ')  
  if s[0] == 'h' or s[0] == 'help':
    print 'Help'
    print 'a, add       Add a table (must have a mug!)'
    print 'd, declare   Declare an item'
    print 'e, examine   Examine a person'
    print 'h, help      This help'
    print 'j, join      Join a table'
    print 'l, look      Look at a table'
    print 'q, quit      Quit'
    print 's, say       Say something'
    print 't, tell      Tell someone something' 
    print 'v, version   Print client version'
  elif s[0] == 'a' or s[0] == 'add':
    if len(s) != 2:
      print 'Bad command, usage "add some_table_name"'
      continue
    if not server.AddTable(key, s[1]):
      print 'Couldn\'t add table', s[1]
  elif s[0] == 'd' or s[0] == 'declare':
    if len(s) != 2:
      print 'Bad command, usage "declare some_item_file"'
      continue
    if not os.path.isfile(s[1]):
      print 'Can\'t find file "%s"' % s[1]
      continue
    serialized_item = file(s[1]).read()
    item = cPickle.loads(serialized_item)
    if not item:
      print 'Couldn\'t parse serialized item from "%s"' % s[1]
      continue
    proof_sig = item_client.GenerateProofSig(item, server_name)
    if not proof_sig:
      print 'Couldn\'t sign item (has it been confirmed yet?)'
      continue
    # Have to wrap the serialized string or xml may barf.
    binary_item = xmlrpclib.Binary(serialized_item)
    if server.Declare(key, binary_item, proof_sig):
      print 'Declared item "%s"' % item.name
    else:
      print 'Failed to declare item "%s"' % item.name
  elif s[0] == 'e' or s[0] == 'examine':
    if len(s) != 2:
      print 'Bad command, usage "examine some_user"'
      continue
    user_description = server.ExamineUser(key, s[1])
    if user_description:
      print '%s is %s' % (s[1], user_description)
    else:
      print 'Nobody named %s here...' % s[1]
  elif s[0] == 'j' or s[0] == 'join':
    tables = server.GetTables(key)
    if len(s) != 2:
      print 'Bad command'
      continue
    if s[1] in tables:
      if server.JoinTable(key, s[1]):
        print 'You join table %s' % s[1]
      else:
        print 'You are not allowed to join table %s' % s[1]
    else:
      print 'Unknown table %s' % s[1]
  elif s[0] == 'l' or s[0] == 'look':
    tables = server.GetTables(key)
    if len(s) == 1:
      print 'You are in a public house'
      print 'You see the following tables:'
      for table in tables:
        print '  %s with %d people' % (table, len(tables[table]))
    if len(s) == 2: 
      if s[1] in tables:
        print 'Table %s has the following people' % s[1]
        for user in tables[s[1]]:
          print ' ', user
      else:
        print 'No table named %s' % s[1]
  elif s[0] == 'q' or s[0] == 'quit':
    print 'Quitting...'
    server.Disconnect(key)
    break
  elif s[0] == 's' or s[0] == 'say':
    if len(s) < 2:
      print 'Bad command'
      continue
    if server.SendMessage(key, '*', ' '.join(s[1:])):
      print 'You say "%s"' % ' '.join(s[1:])
    else:
      print 'You can\'t talk here'
  elif s[0] == 't' or s[0] == 'tell':
    if len(s) < 3:
      print 'Bad command'
      continue
    message = ' '.join(s[2:])
    # We append a unique address to quizler answers, since they may result
    # in a new item that needs an address.
    if s[1] == 'quizler':
      message += ' ' + item_client.GetNewAddress()
    server.SendMessage(key, s[1], message)
    print 'You tell %s "%s"' % (s[1], message)
  elif s[0] == 'v' or s[0] == 'version':
    print 'Version:', VERSION
  else:
    print 'Unknown command "%s"' % r
