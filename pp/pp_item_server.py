import pp_keys
import pp_lineage
from pp_item import Item

import cPickle
import logging
import os
import time
from jsonrpc import ServiceProxy

USER_ACCOUNT_FILENAME = 'user_account.pickle'
#BLOCK_DIRECTORY = '/home/than/windows-than/bitcoin_testnet/testnet-box/1/testnet3'
BLOCK_DIRECTORY = '/home/' + os.environ['USER'] + '/.bitcoin'

class ItemServer():
  """ An issuer of items, among other things...
  It also maintains the heavy data structures and interfaces."""

  def __init__(self,
               key_name,
               btc_proxy = 'http://test:123@localhost:19001',
               lineage_filename = 'lineage.pickle'):
    if pp_keys.ExportPubKey(key_name) == '':
      raise Exception('Unknown key name ' + key_name)
    self.key_name = key_name
    self.btc = ServiceProxy(btc_proxy)
    self.btc.getinfo()  # Will raise an exception if we aren't connected
    # Load user accounts
    try:
      self.user_account = cPickle.load(file(USER_ACCOUNT_FILENAME))
    except:
      logging.info('Starting with empty user accounts')
      self.user_account= {}
    # Load lineage
    try:
      self.lineage = cPickle.load(file(lineage_filename))
    except:
      logging.info('Starting with empty lineage')
      self.lineage = pp_lineage.Lineage()
    logging.info('Loading block chain from' + BLOCK_DIRECTORY)
    self.lineage.UpdateDir(BLOCK_DIRECTORY)
    # Save the updated lineage (only at __init__).
    logging.info('Saving updated lineage...')
    cPickle.dump(self.lineage, file(lineage_filename, 'w'), -1)

  def CreateAccount(self, password):
    """ Clients create a new account by making a payment to an address. """
    new_address = self.btc.getnewaddress()
    self.user_account[new_address] = password
    # Save the user accounts to disk.
    cPickle.dump(self.user_account, file('user_account.pickle', 'w'), -1)
    return new_address

  def VerifyAccount(self, btc_address, password, proof_sig):
    """ Clients log in by verifying their payment to a btc_address. """
    # TODO: add a day-stamp to the text?
    if not btc_address in self.user_account:
      logging.warning('Unknown btc_address %s' % btc_address)
      return False
    if self.user_account[btc_address] != password:
      logging.warning('Password does not match for account %s' % btc_address)
      return False
    MIN_ACCOUNT_AMOUNT = 0.001
    account_amount = self.btc.getreceivedbyaddress(btc_address, 1)
    if account_amount < MIN_ACCOUNT_AMOUNT:
      logging.warning('Address %s not sufficiently funded %f < %f' % 
                      (btc_address, account_amount, MIN_ACCOUNT_AMOUNT))
      return False
    # TODO: actually verify that they can prove they made the (first?) payment.
    #return self.btc.verifymessage(btc_address, proof_sig, self.key_name)
    return True
  
  def Create(self, item_name, content):
    item = Item(item_name, content, self.key_name)
    return item

  def GrantToKey(self, item, key_name):
    """ Give an item to a particular owner: non-transferrable. """
    if item.creator_key_name != self.key_name:
      logging.warning('This server is not the creator of the item %s' % item)
      return None
    if item.owner_key_name != '':
      logging.warning('This item has already been granted')
      return None
    item.owner_key_name = key_name
    # Sign the item to make it official.
    item.signature = pp_keys.Sign(item.signed_content(), self.key_name)
    return item

  def GrantToAddress(self, item, address, btc_value=0.01):
    """ Give an item to a bitcoin address: transferrable. """
    if item.creator_key_name != self.key_name:
      logging.warning('This server is not the creator of the item %s' % item)
      return None
    if item.origin_tx_id != '':
      logging.warning('This item has already been granted')
      return None
    item.origin_tx_id = self.btc.sendtoaddress(address, btc_value) 
    item.last_tx_id = item.origin_tx_id
    # Sign the item to make it official.
    item.signature = pp_keys.Sign(item.signed_content(), self.key_name)
    return item

  def Transfer(self, item, address, min_btc_confirmations=6, btc_fee=0.0005):
    if item.last_tx_id == '':
      print 'This item is not transferrable (no last tx id)'
      return False
    # NOTE: we assume the btc server knows of this this transaction because the
    # user is the owner of the item.
    last_tx = self.btc.gettransaction(item.last_tx_id)
    value = float(last_tx['amount'])
    confirmations = last_tx['confirmations']
    if confirmations < min_btc_confirmations:
      print 'Not enough confirmations of last_tx:',
      print confirmations, '<', min_btc_confirmations
      return False
    # For the initial grant TX, vout will be 1, otherwise 0.
    vout = 0
    if (item.origin_tx_id == item.last_tx_id): vout = 1
    raw_tx = self.btc.createrawtransaction(
        [{"txid":item.last_tx_id, "vout":vout}], {address:value - btc_fee})
    signed = self.btc.signrawtransaction(raw_tx)
    if signed['complete']:
      item.last_tx_id = self.btc.sendrawtransaction(signed['hex'])
      return True
    return False

  def Verify(self, item, proof_sig):
    """ Verify the integrity and ownership of the item:
    1) The serialized item is properly signed,
    2) and that the claimed owner also controls the heir bitcoin. """
    # TODO: Check that the last tx has sufficient confirmations.
    # TODO: Support non-transferrable items. 
    if item.origin_tx_id == '' or item.last_tx_id == '' or item.signature == '':
      print 'This item has not been granted'
      return False
    if not pp_keys.FindAndImportVerifiedKey(item.creator_key_name):
      print 'Could not find item creator key', item.creator_key_name
      return False
    if not pp_keys.Verify(item.signed_content(), item.signature):
      print 'Could not verify item signature'
      return False
    self.lineage.UpdateAll()
    if not self.lineage.VerifyLineage(item.last_tx_id, item.origin_tx_id):
      print 'Could not verify item lineage'
      return False
    last_address = self.lineage.GetOutputAddress(item.last_tx_id)
    if not last_address:
      print 'Could not find last tx output address'
      return False
    last_address_verified = self.btc.verifymessage(
        last_address, proof_sig, self.key_name)
    if not last_address_verified:
      print 'Could not verify ownership of last tx output address'
      return False
    return True

  def GenerateProofSig(self, item, target):
    """ Prove that this server owns the output of last_tx_id. """
    self.lineage.UpdateAll()
    last_address = self.lineage.GetOutputAddress(item.last_tx_id)
    if not last_address:
      print 'Could not find last tx output address'
      return ''
    proof_sig = self.btc.signmessage(last_address, target)
    return proof_sig


###############################################################################

if __name__ == '__main__':

  if 1:  # Setup
    server1_name = 'Passe-Partout Shen'
    item_server1 = ItemServer(server1_name)
    server2_name = 'Passe-Partout Ando'
    item_server2 = ItemServer(server2_name,
        btc_proxy = 'http://test:123@localhost:19011'
        )

  if 0:  # Item tests
    if 0:  # Creating item
      hat = item_server1.Create('hat', 'a fluffy hat')
    
    if 0:  # Granting item
      btc_address2 = item_server2.btc.getnewaddress()
      # This should fail
      print 'Trying to grant from 2 (should fail)'
      item_server2.GrantToAddress(hat, btc_address2)
      # This should work
      print 'Trying to grant from 1 (should pass)'
      item_server1.GrantToAddress(hat, btc_address2)
  
    if 0:  # Let the bitcoin server generate for a while.
      print 'Starting generation'
      item_server1.btc.setgenerate(True)
      print 'Sleeping for 20 seconds'
      time.sleep(20)
      item_server1.btc.setgenerate(False)
  
    if 0:  # Proof sigs and verification
      print 'Verifying'
      # This should fail because server1 doesn't own hat.
      try:
        print 'Trying to generate proof sig from 1 (should fail)'
        proof_sig = item_server1.GenerateProofSig(hat, server1_name)
        print 'Should never see this! Proof sig:', proof_sig
      except:
        print 'Couldnt generate proof sig from server 1 (correct!)'
      # These should work
      print 'Trying to generate proof sig from 2'
      proof_sig = item_server2.GenerateProofSig(hat, server1_name)
      print 'Sig for 1'
      print 'Proof sig:', proof_sig
      print 'Verify 1:', item_server1.Verify(hat, proof_sig)
      print 'Verify 2:', item_server2.Verify(hat, proof_sig)
      proof_sig = item_server2.GenerateProofSig(hat, server2_name)
      print 'Sig for 2'
      print 'Proof sig:', proof_sig
      print 'Verify 1:', item_server1.Verify(hat, proof_sig)
      print 'Verify 2:', item_server2.Verify(hat, proof_sig)
  
    if 0:  # Transferring item
      print 'Transferring to server 1'
      btc_address1 = item_server1.btc.getnewaddress()
      item_server2.Transfer(hat, btc_address1)
  
    if 0:  # Let the bitcoin server generate for a while.
      print 'Starting generation'
      item_server1.btc.setgenerate(True)
      print 'Sleeping for 20 seconds'
      time.sleep(20)
      item_server1.btc.setgenerate(False)
  
    if 0:  # Proof sigs and verification
      print 'Verifying'
      # This should fail because server1 doesn't own hat.
      try:
        print 'Trying to generate proof sig from 2 (should fail)'
        proof_sig = item_server2.GenerateProofSig(hat, server1_name)
        print 'Should never see this! Proof sig:', proof_sig
      except:
        print 'Couldnt generate proof sig from server 2 (correct!)'
      # These should work
      print 'Trying to generate proof sig from 1'
      proof_sig = item_server1.GenerateProofSig(hat, server1_name)
      print 'Sig for 1'
      print 'Proof sig:', proof_sig
      print 'Verify 1:', item_server1.Verify(hat, proof_sig)
      print 'Verify 2:', item_server2.Verify(hat, proof_sig)
      proof_sig = item_server1.GenerateProofSig(hat, server2_name)
      print 'Sig for 2'
      print 'Proof sig:', proof_sig
      print 'Verify 1:', item_server1.Verify(hat, proof_sig)
      print 'Verify 2:', item_server2.Verify(hat, proof_sig)

  if 1:  # Account tests 
    btc_address = item_server1.CreateAccount('kittens')
    print 'Trying to VerifyAccount, should be false:',
    print item_server1.VerifyAccount(btc_address, 'kittens', '')

    print 'Funding the account'
    item_server2.btc.sendtoaddress(btc_address, 0.1)

    if 1:  # Let the bitcoin server generate for a while.
      print 'Starting generation'
      item_server1.btc.setgenerate(True)
      print 'Sleeping for 20 seconds'
      time.sleep(20)
      item_server1.btc.setgenerate(False)

    print 'Trying to VerifyAccount, should be true:',
    print item_server1.VerifyAccount(btc_address, 'kittens', '')
