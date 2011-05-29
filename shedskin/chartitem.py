
class ChartItem(object):
	__slots__ = ("label", "vec", "_hash")
	def __init__(self, label, vec):
		self.label = label
		self.vec = vec
		self._hash = hash((self.label, self.vec))
	def __hash__(self):
		return self._hash
	def __cmp__(self, other):
		if self.label == other.label and self.vec == other.vec: return 0
		elif self.label < other.label or (self.label == other.label
									and self.vec < other.vec): return -1
		return 1
	def __eq__(self, other):
		if other is None: return False
		return self.label == other.label and self.vec == other.vec
	def __lt__(self, other):
		if other is None: return False
		return self.label < other.label or (self.label == other.label
									and self.vec < other.vec)
	def __gt__(self, other):
		if other is None: return False
		return self.label > other.label or (self.label == other.label
									and self.vec > other.vec)
	def __getitem__(self, n):
		if n == 0: return self.label
		elif n == 1: return self.vec
	def __repr__(self):
		#would need sentence length to properly pad with trailing zeroes
		return "%s[%s]" % (self.label, bin(self.vec)[2:][::-1])

def main():
	item = ChartItem(0, 0)
	assert ChartItem(0, 0) < ChartItem(1, 0)
	assert ChartItem(1, 0) > ChartItem(0, 0)
	assert ChartItem(1, 0) >= ChartItem(0, 0)
	assert ChartItem(0, 0) == ChartItem(0, 0)
	print hash(item), repr(item),
	print item[0], item[1], item.__cmp__(ChartItem(1, 0))

if __name__ == '__main__': main()