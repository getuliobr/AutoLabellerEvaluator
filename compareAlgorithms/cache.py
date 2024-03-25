from collections import defaultdict

class Cache:
  def __init__(self) -> None:
    self.cache = defaultdict(lambda: defaultdict(lambda: None))
    
  def clear(self):
    self.cache.clear()
    
  def set(self, a, b, val):
    self.cache[a][b] = val
    
  def get(self, a, b):
    return self.cache[a][b]