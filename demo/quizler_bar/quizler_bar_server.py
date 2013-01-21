#!/bin/python

# NOTE: running a server is considerably complex.

# GETTING STARTED
# 1. Install dependencies:
#  sudo apt-get install python-pyme python-crypto python-openssl
#  sudo pip install python-hkp
# 2. Create your gpg keys (specified as your server_key below).
#  gpg --gen-key
#  [follow the prompts]
# 3. Create your ssl certs
#   openssl genrsa -out key.pem 1024
#   openssl req -new -key key.pem -out request.pem
#   openssl x509 -req -days 30 -in request.pem -signkey key.pem -out cert.pem
# 4. Set up your config file ~/.pp_game_server.cfg
#   [quizler_bar]
#   server_key = Passe-Partout Shen
#   btc_rpc_url = http://rpcusername:35lk2j34lksdijt@localhost:8332

import ConfigParser
import cPickle
import os
import random
import sys
import time
import xmlrpclib
import SimpleXMLRPCServer

sys.path.append('../../pp')
from pp_item_server import ItemServer
import SecureXMLRPCServer

QUIZLER_INTERVAL = 10
QUESTIONS = {'How many buns make five?' : 'four',
             'How many quarts in a gallon?' : 'four',
             'Twice two?' : 'four',
             'What do you yell before hitting a golf ball?' : 'fore',
             'Opposite of aft?' : 'fore',
             }

class XmlRpcServer():
  def __init__(self, server_key, btc_proxy):
    self.item_server = ItemServer(server_key, btc_proxy)
    self.user_addresses = {}  # {user_address: user_name}
    self.user_names = {}  # {user_name: user_address}
    self.privileged = {}  # {user_address}
    self.descriptions = {}  # {user_address}
    self.messages = {}  # {user_address: message_list}
    self.tables = {}  # {table_name: {dict_of_user_names}}
    self.items = {}  # {user_address: [list_of_items,]}

  def _dispatch(self, method, params):
    try:
      # We are forcing the 'export_' prefix on methods that are
      # callable through XML-RPC to prevent potential security
      # problems.
      func = getattr(self, 'export_' + method)
    except AttributeError:
      raise Exception('method "%s" is not supported' % method)
    else:
      return func(*params)

  def CheckLoginAddress(self, key):
    if key not in self.user_addresses:
      print 'Unknown address:', key
      return False
    return True

  def export_AddTable(self, key, table_name):
    if key not in self.privileged:
      print 'Not privileged:', key
      return False
    self.tables.setdefault(table_name, {})
    return True

  def export_Authenticate(self, user_name, address, proof_sig):
    # TODO: cull stale user names
    last_address_verified = self.item_server.btc.verifymessage(
        address, proof_sig, self.item_server.key_name)
    if not last_address_verified:
      print 'Couldn\'t verify address'
      return ''
    if address in self.user_addresses:
      print 'Was already logged in with address', address
      self.user_names.pop(self.user_addresses[address])
      self.user_addresses.pop(address)
    while user_name in self.user_names:
      print 'User name already taken:', user_name
      user_name += '~'
    self.user_names[user_name] = address
    self.user_addresses[address] = user_name
    self.descriptions[address] = 'a non-descript type'
    print 'Authenticated:', user_name, address
    return user_name

  def export_Declare(self, key, binary_item, proof_sig):
    if not self.CheckLoginAddress(key): return False
    item = cPickle.loads(binary_item.data)
    if not item:
      print 'Couldn\'t parse serialized item' 
      return False
    if self.item_server.Verify(item, proof_sig):
      self.descriptions[key] = 'carrying ' + item.name
      self.privileged[key] = time.time()
      return True
    return False

  def export_Disconnect(self, key):
    user_name = ''
    if key in self.user_addresses:
      user_name = self.user_addresses[key]
      self.user_names.pop(user_name)
      self.user_addresses.pop(key)
    if key in self.descriptions: self.descriptions.pop(key)
    if key in self.messages: self.messages.pop(key)
    for table in self.tables:
      if user_name in self.tables[table]: self.tables[table].pop(user_name)
    return True
  
  def export_SendMessage(self, key, dest, message):
    if not self.CheckLoginAddress(key): return False
    user_name = self.user_addresses[key]
    if dest == user_name:
      print 'Can\'t tell yourself:', dest
      return False
    # Quizler answer
    if dest == 'quizler':
      # The last part of a quizler answer is a bitcoin address.
      tokens = message.split(' ')
      if tokens[0] == self.quizler_answer:
        if not self.item_server.btc.validateaddress(tokens[1]):
          print 'Invalid btc address in quizler answer'
          return False
        # They have the right answer
        item = self.item_server.Create('copper_mug',
            'name: "copper mug"\ntype: "mug"\nmaterial: "copper"')
        self.item_server.GrantToAddress(item, tokens[1])
        self.items.setdefault(key, []).append(item)
      return True
    # Deliver to a specific user (at any table)
    if dest in self.user_names:
      self.messages.setdefault(self.user_names[dest], []).append(
          user_name + ' tells you: ' + message)
      return True
    # Deliver to everybody at your table
    if dest == '*':  
      # Figure out your table
      found_table = ''
      for table in self.tables:
        if user_name in self.tables[table]:
          found_table = table
      if not found_table:
        print 'Not at a table'
        return False
      for name in self.tables[found_table]:
        if name == user_name: continue
        self.messages.setdefault(self.user_names[name], []).append(
            user_name + ' says: ' + message)
      return True
    return False
  
  def export_GetServerName(self):
    return self.item_server.key_name
  
  def export_GetMessages(self, key):
    if not self.CheckLoginAddress(key): return []
    if key not in self.messages:
      print 'No messages for:', key
      return []
    m = self.messages[key]
    self.messages[key] = []
    return m
  
  def export_GetTables(self, key):
    if not self.CheckLoginAddress(key): return []
    return self.tables

  def export_GetItems(self, key):
    # Have to return a list of strings.
    serialized_items = map(cPickle.dumps, self.items.setdefault(key, []))
    # Clear out reported items.
    self.items[key] = []
    return serialized_items

  def export_ExamineUser(self, key, user_name):
    if not self.CheckLoginAddress(key): return ''
    if user_name not in self.user_names:
      print 'Unknown user name:', user_name
      return ''
    return self.descriptions[self.user_names[user_name]]

  def export_JoinTable(self, key, table_name):
    if not self.CheckLoginAddress(key): return False
    user_name = self.user_addresses[key]
    if table_name not in self.tables:
      print 'Unknown table:', table_name
      return False
    # TODO table permissions
    for table in self.tables:
      if user_name in self.tables[table]:
        self.tables[table].pop(user_name)
        break
    self.tables[table_name][user_name] = time.time()
    return True

  def RunQuizler(self):
    index = random.randint(0, len(QUESTIONS) - 1)
    question = QUESTIONS.keys()[index]
    self.quizler_answer = QUESTIONS.values()[index]
    for name in self.tables['quizler']:
      self.messages.setdefault(self.user_names[name], []).append(
          'The quizler asks: ' + question)
    

if __name__ == '__main__':
  PP_CONFIG_PATH = '~/.pp_game_server.cfg'
  config_filename = os.path.expanduser(PP_CONFIG_PATH)
  config = ConfigParser.SafeConfigParser()
  config.read(config_filename)

  xml_rpc_server = XmlRpcServer(config.get('quizler_bar', 'server_key'),
                                config.get('quizler_bar', 'btc_rpc_url'))

  xml_rpc_server.tables.setdefault('bar', {})
  xml_rpc_server.tables.setdefault('quizler', {})

  if 0:  # insecure
    server = SimpleXMLRPCServer.SimpleXMLRPCServer(("localhost", 8000))
  if 1:  # secure
    server = SecureXMLRPCServer.SecureXMLRPCServer(("localhost", 8000))
  server.register_instance(xml_rpc_server)

  sa = server.socket.getsockname()
  print "Serving on", sa[0], "port", sa[1]

  quizler_time = time.time()
  while True:
    if time.time() - quizler_time > QUIZLER_INTERVAL:
      quizler_time = time.time()
      xml_rpc_server.RunQuizler()
    server.handle_request()
    time.sleep(0.01)
