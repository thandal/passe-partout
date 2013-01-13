import pyme
from pyme import core, callbacks
from pyme.constants.sig import mode

from hkp import KeyServer
try: _serv
except:
  _serv = KeyServer('http://pool.sks-keyservers.net')

def Sign(content, key_name):
  c = core.Context()
  #c.set_armor(1)
  #c.set_progress_cb(callbacks.progress_stdout, None)
  con = core.Data(content)
  sig = core.Data()
  c.signers_clear()
  for sigkey in c.op_keylist_all(key_name, 1):
    if sigkey.can_sign:
      c.signers_add(sigkey)
  if not c.signers_enum(0):
    raise ('No signing keys found for key name:', key_name)
  c.op_sign(con, sig, pyme.constants.SIG_MODE_DETACH)
  sig.seek(0,0)
  return sig.read()

def Verify(content, signature):
  c = core.Context()
  con = core.Data(content)
  sig = core.Data(signature)
  c.op_verify(sig, con, None)
  result = c.op_verify_result()
  for sign in result.signatures:
    # TODO verify that sign.fpr matches the item's creator_key_name.  For now,
    # we are somewhat protected by the assumption that the server has rejected
    # any bad keys.

    #print "signature"
    #print "  summary:    ", sign.summary
    #print "  status:     ", sign.status
    #print "  timestamp:  ", sign.timestamp
    #print "  fingerprint:", sign.fpr
    #print "  uid:        ", c.get_key(sign.fpr, 0).uids[0].uid
    if not sign.summary & pyme.constants.SIGSUM_VALID: return False
  return True

def GenerateServerKey(key_name):
  c = core.Context()
  c.set_armor(1)
  params = """<GnupgKeyParms format="internal">
  Key-Type: RSA
  Key-Length: 2048
  Name-Real: """ + key_name + """
  Name-Comment: Server Key
  Expire-Date: 0
  </GnupgKeyParms>
  """
  c.op_genkey(params, None, None)
  print 'Generated server key with fingerprint', c.op_genkey_result().fpr
  key_fingerprint = c.op_genkey_result().fpr
  return key_fingerprint

def ExportPubKey(key_name):
  c = core.Context()
  c.set_armor(1)
  exported_key = core.Data()
  c.op_export(key_name, 0, exported_key)
  exported_key.seek(0,0)
  return exported_key.read()

def UploadKey(key):
  _serv.add(key)

def FindAndImportKey(key_name):
  c = core.Context()
  keys = list(c.op_keylist_all(key_name, 0))
  if len(keys) > 0:
    #print 'Already have key for:', key_name
    return True
  keys = _serv.search(key_name)
  if len(keys) != 1:
    return False
  k = keys[0]
  key = core.Data(k.key)
  c.op_import(key)
  return True

def VerifyKey(key_name):
  # Check that the name maps to a unique key.
  c = core.Context()
  c.set_keylist_mode(pyme.constants.KEYLIST_MODE_LOCAL |
                     pyme.constants.KEYLIST_MODE_SIGS)
  keys = list(c.op_keylist_all(key_name, 0))
  if len(keys) != 1:
    return False
  key = keys[0]
  # Check that the key that was signed by the Passe-Partout Root Key.
  for uid in key.uids:
    for sig in uid.signatures:
      if sig.uid == 'Passe-Partout (Root Key)':
        return True
  return False

def FindAndImportVerifiedKey(key_name):
  if FindAndImportKey(key_name) and VerifyKey(key_name):
    return True
  return False

def ImportRootKey():
  ROOT_PUB_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----
  Version: GnuPG v1.4.11 (GNU/Linux)

  mQENBFCET3sBCADHatPTOYrNkmDNheWno76LbULSH70IP3ONnGM1hjTElDpLmdE6
  ZRfHuqqNGbkF1nC909J+GHEEKWWvAb6NWMihH/2nltih1Viqhd3Reb043r4Qdm6I
  LEw91AZIYtJRIzeciMyFPGDYEUd9xKVqzMrE4LZhv0bw466p9VfG6GFMLQjk+E83
  yFW3ZpZIodSsunnbBkS8dNH+XeOgyWAeSkTVCBoW+mkAo93aakhmjdKzcluck3pV
  8fygYCCDElU2OLRzzvLJMZKEaT2os8MhckNqi/IJvjn0hyw8mLxSh49wjRgphign
  fJzHAcxfOPyQEnicf6Ja39uZdI88z3SYYKvfABEBAAG0GFBhc3NlLVBhcnRvdXQg
  KFJvb3QgS2V5KYkBOAQTAQIAIgUCUIRPewIbAwYLCQgHAwIGFQgCCQoLBBYCAwEC
  HgECF4AACgkQ1A1Vy9ciXwZwQgf/bh2yFcPsawrRXaPmHWm2nIizgCrf2UQU+/Tm
  q+p5zOJrkyz4KLF1Qfiv8z+T+w/m7htWL8W/VL7XMb9+TizSAiEbnvZXGitf36OG
  Vz+MVedCTBASU0S1s9LJ+g/8X2SVMUxyp6q59O2dGkkEH0XsMznuEGKi4qyVQ8mp
  LN0wjWhUNctgApVccSfkaEYi3EabJV7TJ4WlFTcIesSfhfnN+Uv7sZqJ+CDfgd2n
  fS9TcQxeXlP4b3MW5si9SQpnLmjqfZOVWLCgK4j0S+RRXkhOcspfNr5SOWAFlKyV
  rK50gHEwIAdyU0AxWXmktk4+vapjcWFFH67zSr6Yt/XPRv11d7kBDQRQhE97AQgA
  9IX4tW82axfBO4i+BgIlN3b5jn7p/b2Jmlcgnnj5n/sbx44LRMBdTGuXLdb8PpHN
  o/Ihyq190FO9LEhzMntFvm0gOQsY/ddQtqC/1hDLydVmBR+TXKAJvBQd8/b6PFhX
  G/I32/POXQ58YsdV3lI1QdQB8RP4RNPveScXokcBi9oIKQurLtSDw5w6doAT3KYt
  Vryk0wQbmfXSaHNLpSZTiyV+iA9ak5vBFAdbBCU1I7ucAZf7LkmftVB9ap0SXWTY
  2YdomE06Su92ti8szNy90lz4OoqvuxzmrxmWW7AsMY32yMCgcium3/eaNoRQd6j0
  jjs9U/9Y98ikrjk0ZumwswARAQABiQEfBBgBAgAJBQJQhE97AhsMAAoJENQNVcvX
  Il8GQyMH/Rnnv3xRxamNLwFJpxmy4IPyM5aZksapruM9PzxKIA4mdAqMqRPusIMW
  94e17I8Fgg03xDIcybZzX9RbmQ2z7gI+SeUONd6w+3//eizfetlepIaJaqQgLeg6
  7RM76TPCdViXU47KArgiVWfk7uzEmcbZaIpfXzjVS3R2JEte0tArnMf+cRtV+sph
  i7PlKLi69ShBdbIAqZvZDN/OcOlqB1ISbroRDabELYlcr1O4FwjRw0hEmOVYP4KS
  D45ksT+Yqtx9fuis/KNo+Vw879+f/iuqbm/xKDcZQo4aVpdnkbqb5r2YjbdxOf8L
  sp2FpZROkaS0Q7gAsUdOoMECloJRQT4=
  =WxAX
  -----END PGP PUBLIC KEY BLOCK-----"""
  key_data = core.Data(ROOT_PUB_KEY)
  c = core.Context()
  c.op_import(key_data)

if __name__ == '__main__':
  ImportRootKey()
  if 0:
    key_name = 'Passe-Partout Shen'
    content = 'Monkeyshine'
    signature = Sign(content, key_name)
    print 'Verified content:', Verify(content, signature)
  if 1:
    key_name = 'Passe-Partout Shen'
    print 'Verified key', key_name, VerifyKey(key_name)
    key_name = 'Passe-Partout Ando'
    print 'Verified key', key_name, VerifyKey(key_name)
