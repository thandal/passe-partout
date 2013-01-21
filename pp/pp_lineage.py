import pp_parse

import BCDataStream
import Crypto.Hash.SHA256 as SHA256

import cPickle
import os
import sys
  
GENESIS_HEX = '0' * 64

def Switcheroo(data):
  """ Don't know why, but bitcoin rpc tx ids are bass-ackwards and swapped. """
  # Reverse data
  rev = ''
  for d in reversed(data):
    rev += d
  # Swap pairs
  out = ''
  for i in range(0, len(data), 2):
    out += rev[i+1]
    out += rev[i]
  return out

def BHash(data):
  # Double SHA256
  return Switcheroo(
      SHA256.new(SHA256.new(data).digest()).digest().encode('hex'))

class Lineage:
  def __init__(self, payment_address = None, smart_skip = True): 
    self.parent = {}
    self.address = {}
    self.inputs = {}
    self.smart_skip = smart_skip
  
  def Update(self, filename):
    """ Update map of transaction ancestry.
        heir tx hash -> progenitor tx hash """
    ds = BCDataStream.BCDataStream()
    ds.map_file(open(filename, 'rb'), 0)
    blk_count = 0
    ds_size = len(ds.input)
    # We know that Passe-Partout activity didn't start before blk0003.dat.
    if self.smart_skip:
      if filename.endswith('blk0001.dat') or filename.endswith('blk0002.dat'):
        self.inputs[filename] = ds_size
        print 'Skipping', filename, 'to', ds_size
        return
    ds.read_cursor = self.inputs.setdefault(filename, 0)
    print 'Scanning', filename, 'from', ds.read_cursor
    while ds.read_cursor < ds_size:
      sys.stdout.write('\r block %d (%d percent)' %
                       (blk_count, 100.0 * ds.read_cursor / ds_size))
      d = pp_parse.parse_Block(ds)
      blk_count += 1
      for tx in d['transactions']:
        first_prevout_hash = Switcheroo(
            tx['txIn'][0]['prevout_hash'].encode('hex'))
        # Short circuit for genesis blocks
        if first_prevout_hash == GENESIS_HEX:
          continue
        if len(tx['txIn']) > 2 or len(tx['txOut']) > 2:
          continue
        tx_hash = BHash(tx['tx'])
        for txOut in tx['txOut']:
          if txOut.has_key('address'):
            self.parent[tx_hash] = first_prevout_hash
            self.address[tx_hash] = txOut['address']
    self.inputs[filename] = ds.read_cursor
    print ' Read to', ds.read_cursor
    return ds.read_cursor

  def UpdateAll(self):
    for filename in self.inputs:
      self.Update(filename)

  def UpdateDir(self, dirname):
    files = os.listdir(dirname)
    i = 1
    while True:
      blk_filename = 'blk%04d.dat' % i
      if blk_filename in files:
        self.Update(os.path.join(dirname, blk_filename))
      else:
        break
      i += 1
  
  def VerifyLineage(self, heir, progenitor):
    while heir in self.parent:
      if (heir == progenitor): return True
      heir = self.parent[heir]
    return True

  def GetOutputAddress(self, tx_id):
    if not tx_id in self.address: return None
    return self.address[tx_id]

if __name__ == '__main__':
  lineage_filename = 'lineage.pickle'
  if 1:
    try:
      lineage = cPickle.load(file(lineage_filename))
    except:
      lineage = Lineage()
    block_files = [
      #'/home/than/.bitcoin/blk0001.dat',
      #'/home/than/.bitcoin/blk0002.dat',
      '/home/than/windows-than/bitcoin_testnet/testnet-box/1/testnet3/blk0001.dat',
      ]
    for block_file in block_files:
      lineage.Update(block_file)
    #cPickle.dump(lineage, file(lineage_filename, 'w'), -1)

  if 1:
    #lineage = cPickle.load(file(lineage_filename))
    heir = 'fffc6cfeb414873ac5c5a44201e4cdc9e243a6bfa900a87542b65f2a09b9099f'
    prog = 'bbc2d22dbcfd30c0e9e1e1055f2601ab0d52a4e0c3154cfeb595c15992ddec10'
    print 'Verifying that'
    print heir
    print 'is the heir of '
    print prog
    print lineage.VerifyLineage(heir, prog)
