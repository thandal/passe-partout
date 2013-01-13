# The following parse_* methods are from bitcoin-abe

import base58

def parse_TxIn(vds):
  d = {}
  d['prevout_hash'] = vds.read_bytes(32)
  d['prevout_n'] = vds.read_uint32()
  d['scriptSig'] = vds.read_bytes(vds.read_compact_size())
  d['sequence'] = vds.read_uint32()
  return d

def parse_TxOut(vds):
  d = {}
  d['value'] = vds.read_int64()
  raw = vds.read_bytes(vds.read_compact_size())
  d['scriptPubKey'] = raw
  if len(raw) == 25 and raw[0] == '\x76' and raw[1] == '\xa9' and raw[2] == '\x14':
    d['address'] = base58.hash_160_to_bc_address(raw[3:-2])
  return d

def parse_Transaction(vds):
  d = {}
  start = vds.read_cursor
  d['version'] = vds.read_int32()
  n_vin = vds.read_compact_size()
  d['txIn'] = []
  for i in xrange(n_vin):
    d['txIn'].append(parse_TxIn(vds))
  n_vout = vds.read_compact_size()
  d['txOut'] = []
  for i in xrange(n_vout):
    d['txOut'].append(parse_TxOut(vds))
  d['lockTime'] = vds.read_uint32()
  d['tx'] = vds.input[start:vds.read_cursor]
  return d

def parse_BlockHeader(vds):
  d = {}
  blk_magic = vds.read_bytes(4)
  #if blk_magic != '\xf9\xbe\xb4\xd9':
#  if blk_magic != '\xbf\xfa\xda\xb5':
#    raise Exception('Bad magic' + str(blk_magic))
#    return d
  blk_length = vds.read_int32()

  header_start = vds.read_cursor
  d['version'] = vds.read_int32()
  d['hashPrev'] = vds.read_bytes(32)
  d['hashMerkleRoot'] = vds.read_bytes(32)
  d['nTime'] = vds.read_uint32()
  d['nBits'] = vds.read_uint32()
  d['nNonce'] = vds.read_uint32()
  header_end = vds.read_cursor
  d['__header__'] = vds.input[header_start:header_end]
  return d

def parse_Block(vds):
  d = parse_BlockHeader(vds)
  d['transactions'] = []
  nTransactions = vds.read_compact_size()
  for i in xrange(nTransactions):
    d['transactions'].append(parse_Transaction(vds))
  return d

