Passe-Partout
Nathaniel Fairfield [than@timbrel.org]
=============

There are lots of games out there, but you can’t share stuff between them. It would be really cool to be able to use the same toon, with the same characteristics, capabilities, and property, in multiple virtual worlds.

In addition to some pretty graphics and a painless way to transition from one domain to another, there is the more fundamental issue of exactly how your toon, and its possessions, are transferred from one domain to another. Normally, a virtual world is controlled by a single company, which has a central strategy for ensuring that the game is balanced and fun. One problem with transporting stuff between worlds is that a poorly (or maliciously) run domain could grant its visitors ridiculous powers or items.

Passe Partout is a mechanism for transporting stuff between worlds. Its key ideas are:
* Local inventory: inventory is maintained by the user
 * items can be transferred directly between users
 * but items can’t be duplicated!
* Immigration: servers can decide whether to allow each item to be imported, based both on
 * which server originally issued the item (do you trust those guys?)
 * and based on its description (is a 10 foot long sword realistic?)

A related idea is a standardized protocol for describing items, so that they can be screened in immigration, and implemented in the context of a particular virtual world.

The key mechanisms underlying Passe-Partour are crytographic signatures to verify the originating server of an item, and the usage of the bitcoin block chain to make items transferrable but not copyable.

Further details are provided below, after quick start instructions.

============
TODO
============
* Run on the real bitcoin network (just tested on testnets so far)
* Create an example server.

============
QUICK START
============
Install bitcoin, sync to the block chain (may take a long time).  Alternatively, set up a test net.
Install pyme
Install hkp
Install Crypto

Create a server key:
 python
 >>> import pp_keys
 >>> my_server_key = pp_keys.GenerateServerKey('MyServerName')
 >>> my_exported_key = pp_keys.ExportPubKey(my_server_key)
 >>> pp_keys.UploadKey(my_exported_key)


============
DETAILS
============

TRANSFERRABLE BUT NOT COPYABLE ITEMS

How are digital items handled?  In the simplest case, server1 gives an item to player1 by entering it into server1's internal record of player1's inventory.

If player1 wants to transfer an item to player2, server1 is the clearing-house: after verifying the transaction with both players it clears the item from player1's inventory, and adds it to player2's inventory.

These items are valid only for this server. To support exchanging items with other servers, server1 can issue a signed item that can be imported into other servers:
 itemA:{server1_sig(item_desc, player1_pub_key])}. 
This item is not (necessarily) stored by server1: it is stored by player1. The
item has been signed so that when player1 declares itemA, any server can verify:               
 1) itemA is owned by player1, who presents proof that they own the private key.               
 2) itemA is untampered and was signed by a trusted peer server.                               
Which is sufficient to determine whether to allow player1 to import itemA.

However, player1 may want to trade the item to player2 while connected to a different server (or no server at all). Since the connection to the internal inventories of the servers has been broken, there is no way to verify that player1 doesn't simply keep a copy of the itemA, and continue to present it for import: so there is no uniqueness-preserving method for transferring the item to player2.
                                                                                               
To allow uniqueness-preserving distributed transactions, we can use the bitcoin block chain as a common ledger.

An exported item is paired with a special bitcoin transaction that is transferred to player1:  
 txE{single output: (fixed_value, player1_bitcoin_address)},
 itemE:{server_sig(item_desc, txE)}.
Note that itemE no longer has the player_id embedded in it: this information is now encoded in txE.  However itemE *does* include the originating bitcoin transaction txE.                     

To declare an item that has been exported, player1 must present both itemE and a transaction txE to the server. They must verify that they own the private key that backs txE. This is done by signing a message from the server (which includes the server's name and signature, to prevent man-in-the-middle attacts) with the private key that backs player1's bitcoin address. The server will have a list of the public keys of peer servers, and will be able to verify
 1) The output of txE is owned by player1 (verifies they own the private key),
 2) itemE is untampered and was signed by a trusted peer server.
This is sufficient to demonstrate that player1 owns itemE, and that they got it from server1. ServerN can then decide whether to allow the item to be imported.

If the user wishes to transfer the item to another user, they create a bitcoin transaction:    
 txN:{in: txE, single output: player2_bitcoin_address}

Note that a chain of these transactions may have multiple inputs (to inject funds for fees, for example), but only *one* output.  This chain of single outputs means that the progenitor transaction (txE) that is part of the signed payload of itemE can only have a single heir.           

When player2 declares itemE, the destination server will have to verify the transaction chain all the way back to the progenitor tx (txE) -- although this chain should be fairly short for most items.                                                                                       


WEBS OF TRUST

People who run servers can establish webs of trust using the standard public key signature methods used by gnupg.