# A minimal version of the ItemServer that uses the BlockChain.info JSON api
# https://blockchain.info/api/json_rpc_api

from jsonrpc import ServiceProxy

class ItemClient():

  def __init__(self, wallet, password, second_password):
    self.second_password = second_password
    self.btc = ServiceProxy(
       'https://%s:%s@blockchain.info:443' % (wallet, password))

  def GetNewAddress(self):
    self.btc.walletpassphrase(self.second_password, 50)
    return self.btc.getnewaddress()

  def SignMessage(self, address, message):
    self.btc.walletpassphrase(self.second_password, 50)
    sig = self.btc.signmessage(address, message)
    return sig

  def GenerateProofSig(self, item, target):
    """ Prove that this server owns the output of last_tx_id. """
    tx = self.btc.gettransaction(item.last_tx_id)
    last_address = None
    for det in tx['details']:
      if det['category'] == 'receive':
        last_address = det['address']
    if not last_address: return None
    self.btc.walletpassphrase(self.second_password, 50)
    proof_sig = self.btc.signmessage(last_address, target)
    return proof_sig
