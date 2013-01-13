class Item():
  """ An item is a signed entity. """
  def __init__(self, name, content, creator_key_name):
    self.name = name
    # The content, or data payload, of the item.
    self.content = content
    # The crypto key name of the server that created this item.
    self.creator_key_name = creator_key_name
    # For non-transferrable items, the owner_key_name is specified rather than
    # the origin_tx_id.
    self.owner_key_name = ''
    # For transferrable items, the origin_tx_id is the original grant
    # transaction id, and the last_tx_id is the most recent transaction (in
    # which the item may have been transferred to another person).
    self.origin_tx_id = ''
    self.last_tx_id = ''

  def __str__(self):
    return self.name

  def signature(self):
    return self.signature

  def name(self):
    return self.name

  def signed_content(self):
    if self.name == '': raise Exception('Name is not set')
    if self.content == '': raise Exception('Content is not set')
    if self.creator_key_name == '':
      raise Exception('Creator key name is not set')
    if self.origin_tx_id != '' and self.owner_key_name != '':
      raise Exception('Only one of origin_tx_id OR owner_key_name may be set')
    if self.origin_tx_id != '':
      return str(self.name + self.content + self.creator_key_name + self.origin_tx_id)
    if self.owner_key_name != '':
      return str(self.name + self.content + self.creator_key_name + self.owner_key_name)
    raise Exception('One of origin_tx_id OR owner_key_name must be set')
    return None
      
class Attribute(Item):
  """ Quantity attributes such as having 10 gallons: non-transferable. """
  def __init__(self, name, points, creator_key_name):
    content = str(points)
    Item.__init__(self, name, content, creator_key_name)
    self.available = points
    self.total = points
 
  def Initialize(self):
    """ Parse content to sent quantity fields. """
    points = float(self.content)
    self.available = points
    self.total = points
