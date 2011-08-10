"""
Copyright 2011 Andreas van Cranenburgh <andreas@unstable.nl>
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from math import exp, log
from array import array
from itertools import chain
from heapq import heappush, heappop, heapify

print "plcfrs in shedskin mode"

def parse(sent, grammar, tags, start, exhaustive):
    """ parse sentence, a list of tokens, optionally with gold tags, and
    produce a chart, either exhaustive or up until the viterbi parse.
    """
    unary = grammar.unary
    lbinary = grammar.lbinary
    rbinary = grammar.rbinary
    lexical = grammar.lexical
    toid = grammar.toid
    tolabel = grammar.tolabel
    if start == -1: start = toid['S']
    goal = ChartItem(start, (1 << len(sent)) - 1)
    maxA = 0
    Cx = [{} for _ in toid]
    C = {}
    A = agenda()

    # scan: assign part-of-speech tags
    Epsilon = toid["Epsilon"]
    for i, w in enumerate(sent):
        recognized = False
        for terminal in lexical.get(w, []):
            if not tags or tags[i] == tolabel[terminal.lhs].split("@")[0]:
                Ih = ChartItem(terminal.lhs, 1 << i)
                I = ChartItem(Epsilon, i)
                z = terminal.prob
                A[Ih] = Edge(z, z, z, I, None)
                C[Ih] = []
                recognized = True
        if not recognized and tags and tags[i] in toid:
            Ih = ChartItem(toid[tags[i]], 1 << i)
            I = ChartItem(Epsilon, i)
            A[Ih] = Edge(0.0, 0.0, 0.0, I, None)
            C[Ih] = []
            recognized = True
        elif not recognized:
            print "not covered:", tags[i] if tags else w
            return C, None

    # parsing
    while A:
        Ih, edge = A.popitem()
        C[Ih].append(edge)
        Cx[Ih.label][Ih] = edge

        if Ih == goal:
            if exhaustive: continue
            else: break 
        for I1h, edge in deduced_from(Ih, edge.inside, Cx,
                    unary, lbinary, rbinary):
            if I1h not in C and I1h not in A:
                # haven't seen this item before, add to agenda
                A[I1h] = edge
                C[I1h] = []
            elif I1h in A and edge < A[I1h]:
                # either item has lower score, update agenda
                C[I1h].append(A[I1h])
                A[I1h] = edge
            elif exhaustive:
                # item is suboptimal, only add to exhaustive chart
                C[I1h].append(edge)

        if len(A) > maxA: maxA = len(A)
        if len(A) % 1000 == 0:
            print "max agenda size %d, now %d, chart items %d (%d labels), edges %d, blocked %d" % (maxA, len(A), len(C), len(filter(None, Cx)), sum(map(len, C.values())), 0)
    print "max agenda size %d, now %d, chart items %d (%d labels), edges %d, blocked %d" % (maxA, len(A), len(C), len(filter(None, Cx)), sum(map(len, C.values())), 0)
    if goal not in C: goal = None
    return (C, goal)

def deduced_from(Ih, x, Cx, unary, lbinary, rbinary):
    result = []
    for rule in unary[Ih.label]:
        result.append((ChartItem(rule.lhs, Ih.vec),
            Edge(x+rule.prob, x+rule.prob, rule.prob, Ih, None)))
    for rule in lbinary[Ih.label]:
        for I1h, edge in Cx[rule.rhs2].iteritems():
            if Ih.vec & I1h.vec == 0 and concat(rule, Ih.vec, I1h.vec):
                result.append((ChartItem(rule.lhs, Ih.vec ^ I1h.vec),
                    Edge(x+edge.inside+rule.prob, x+edge.inside+rule.prob,
                            rule.prob, Ih, I1h)))
    for rule in rbinary[Ih.label]:
        for I1h, edge in Cx[rule.rhs1].iteritems():
            if I1h.vec & Ih.vec == 0 and concat(rule, I1h.vec, Ih.vec):
                result.append((ChartItem(rule.lhs, I1h.vec ^ Ih.vec),
                    Edge(x+edge.inside+rule.prob, x+edge.inside+rule.prob,
                            rule.prob, I1h, Ih)))
    return result

def concat(rule, lvec, rvec):
    lpos = nextset(lvec, 0)
    rpos = nextset(rvec, 0)
    #this algorithm was taken from rparse, FastYFComposer.
    for x in range(len(rule.args)):
        m = rule.lengths[x] - 1
        for n in range(m + 1):
            if testbit(rule.args[x], n):
                # check if there are any bits left, and
                # if any bits on the right should have gone before
                # ones on this side
                if rpos == -1 or (lpos != -1 and lpos <= rpos):
                    return False
                # jump to next gap
                rpos = nextunset(rvec, rpos)
                if lpos != -1 and lpos < rpos:
                    return False
                # there should be a gap if and only if
                # this is the last element of this argument
                if n == m:
                    if testbit(lvec, rpos):
                        return False
                elif not testbit(lvec, rpos):
                    return False
                #jump to next argument
                rpos = nextset(rvec, rpos)
            else:
                # vice versa to the above
                if lpos == -1 or (rpos != -1 and rpos <= lpos):
                    return False
                lpos = nextunset(lvec, lpos)
                if rpos != -1 and rpos < lpos:
                    return False
                if n == m:
                    if testbit(rvec, lpos):
                        return False
                elif not testbit(rvec, lpos):
                    return False
                lpos = nextset(lvec, lpos)
            #else: raise ValueError("non-binary element in yieldfunction")
    if lpos != -1 or rpos != -1:
        return False
    # everything looks all right
    return True

def mostprobablederivation(chart, start, tolabel):
    """ produce a string representation of the viterbi parse in bracket
    notation"""
    edge = min(chart[start])
    return getmpd(chart, start, tolabel), edge.inside

def getmpd(chart, start, tolabel):
    edge = min(chart[start])
    if edge.right and edge.right.label: #binary
        return "(%s %s %s)" % (tolabel[start.label],
                    getmpd(chart, edge.left, tolabel),
                    getmpd(chart, edge.right, tolabel))
    else: #unary or terminal
        return "(%s %s)" % (tolabel[start.label],
                    getmpd(chart, edge.left, tolabel)
                        if edge.left.label else str(edge.left.vec))

def binrepr(a, sent):
    return "".join(reversed(bin(a.vec)[2:].rjust(len(sent), "0")))

def pprint_chart(chart, sent, tolabel):
    print "chart:"
    for n, a in sorted((bitcount(a.vec), a) for a in chart):
        if not chart[a]: continue
        print "%s[%s] =>" % (tolabel[a.label], binrepr(a, sent))
        for edge in chart[a]:
            print "%g\t%g" % (exp(-edge.inside), exp(-edge.prob)),
            if edge.left.label:
                print "\t%s[%s]" % (tolabel[edge.left.label],
                                    binrepr(edge.left, sent)),
            else:
                print "\t", repr(sent[edge.left.vec]),
            if edge.right:
                print "\t%s[%s]" % (tolabel[edge.right.label],
                                    binrepr(edge.right, sent)),
            print
        print

def do(sent, grammar):
    print "sentence", sent
    chart, start = parse(sent.split(), grammar, None, -1, False)
    pprint_chart(chart, sent.split(), grammar.tolabel)
    if start:
        t, p = mostprobablederivation(chart, start, grammar.tolabel)
        print exp(-p), t, '\n'
    else:
        print "no parse"
    return start is not None

def read_srcg_grammar(rulefile, lexiconfile):
    """ Reads a grammar as produced by write_srcg_grammar. """
    srules = [line[:len(line)-1].split('\t') for line in open(rulefile)]
    slexicon = [line[:len(line)-1].split('\t') for line in open(lexiconfile)]
    rules = [((tuple(a[:len(a)-2]), tuple(tuple(map(int, b))
            for b in a[len(a)-2].split(","))), float(a[len(a)-1])) for a in srules]
    lexicon = [((tuple(a[:len(a)-2]), a[len(a)-2]), float(a[len(a)-1])) for a in slexicon]
    return rules, lexicon

def splitgrammar(grammar, lexicon):
    """ split the grammar into various lookup tables, mapping nonterminal
    labels to numeric identifiers. Also negates log-probabilities to
    accommodate min-heaps.
    Can only represent ordered SRCG rules (monotone LCFRS). """
    # get a list of all nonterminals; make sure Epsilon and ROOT are first, and
    # assign them unique IDs
    nonterminals = list(enumerate(["Epsilon", "ROOT"]
        + sorted(set(nt for (rule, yf), weight in grammar for nt in rule)
            - set(["Epsilon", "ROOT"]))))
    toid = dict((lhs, n) for n, lhs in nonterminals)
    tolabel = dict((n, lhs) for n, lhs in nonterminals)
    bylhs = [[] for _ in nonterminals]
    unary = [[] for _ in nonterminals]
    lbinary = [[] for _ in nonterminals]
    rbinary = [[] for _ in nonterminals]
    lexical = {}
    arity = array('B', [0] * len(nonterminals))
    for (tag, word), w in lexicon:
        t = Terminal(toid[tag[0]], toid[tag[1]], 0, word, abs(w))
        assert arity[t.lhs] in (0, 1)
        arity[t.lhs] = 1
        lexical.setdefault(word, []).append(t)
    for (rule, yf), w in grammar:
        args, lengths = yfarray(yf)
        assert yf == arraytoyf(args, lengths) # unbinarized rule => error
        #cyclic unary productions
        if len(rule) == 2 and w == 0.0: w += 0.00000001
        r = Rule(toid[rule[0]], toid[rule[1]],
            toid[rule[2]] if len(rule) == 3 else 0, args, lengths, abs(w))
        if arity[r.lhs] == 0:
            arity[r.lhs] = len(args)
        assert arity[r.lhs] == len(args)
        if len(rule) == 2:
            unary[r.rhs1].append(r)
            bylhs[r.lhs].append(r)
        elif len(rule) == 3:
            lbinary[r.rhs1].append(r)
            rbinary[r.rhs2].append(r)
            bylhs[r.lhs].append(r)
        else: raise ValueError("grammar not binarized: %r" % r)
    #assert 0 not in arity[1:]
    return Grammar(unary, lbinary, rbinary, lexical, bylhs, toid, tolabel)

def yfarray(yf):
    """ convert a yield function represented as a 2D sequence to an array
    object. """
    # I for 32 bits (int), H for 16 bits (short), B for 8 bits (char)
    vectype = 'I'; vecsize = 32 #8 * array(vectype).itemsize
    lentype = 'H'; lensize = 16 #8 * array(lentype).itemsize
    assert len(yf) <= lensize                   #arity too high?
    assert all(len(a) <= vecsize for a in yf)   #too many variables?
    initializer = [sum(1 << n for n, b in enumerate(a) if b) for a in yf]
    args = array('I', initializer)
    lengths = array('H', map(len, yf))
    return args, lengths

def arraytoyf(args, lengths):
    return tuple(tuple(1 if a & (1 << m) else 0 for m in range(n))
                            for n, a in zip(lengths, args))

# bit operations
def nextset(a, pos):
    """ First set bit, starting from pos """
    result = pos
    while (not (a >> result) & 1) and a >> result:
        result += 1
    return result if a >> result else -1

def nextunset(a, pos):
    """ First unset bit, starting from pos """
    result = pos
    while (a >> result) & 1:
        result += 1
    return result

def bitcount(a):
    """ Number of set bits (1s) """
    count = 0
    while a:
        a &= a - 1
        count += 1
    return count

def testbit(a, offset):
    """ Mask a particular bit, return nonzero if set """
    return a & (1 << offset)

# various data types
class Grammar(object):
    __slots__ = ('unary', 'lbinary', 'rbinary', 'lexical',
                    'bylhs', 'toid', 'tolabel')
    def __init__(self, unary, lbinary, rbinary, lexical, bylhs, toid, tolabel):
        self.unary = unary
        self.lbinary = lbinary
        self.rbinary = rbinary
        self.lexical = lexical
        self.bylhs = bylhs
        self.toid = toid
        self.tolabel = tolabel

class ChartItem:
    __slots__ = ("label", "vec", "_hash")
    def __init__(self, label, vec):
        self.label = label      #the category of this item (NP/PP/VP etc)
        self.vec = vec          #bitvector describing the spans of this item
        self._hash = hash((self.label, self.vec))
    def __hash__(self):
        return self._hash
    def __eq__(self, other):
        if other is None: return False
        return self.label == other.label and self.vec == other.vec

class Edge:
    __slots__ = ('score', 'inside', 'prob', 'left', 'right')
    def __init__(self, score, inside, prob, left, right):
        self.score = score; self.inside = inside; self.prob = prob
        self.left = left; self.right = right
    def __lt__(self, other):
        # the ordering only depends on inside probability
        # (or on estimate of outside score when added)
        return self.score < other.score
    def __gt__(self, other):
        return self.score > other.score
    def __ge__(self, other):
        return self.score >= other.score
    def __eq__(self, other):
        return (self.inside == other.inside
                and self.prob == other.prob
                and self.left == other.right
                and self.right == other.right)

class Terminal:
    __slots__ = ('lhs', 'rhs1', 'rhs2', 'word', 'prob')
    def __init__(self, lhs, rhs1, rhs2, word, prob):
        self.lhs = lhs; self.rhs1 = rhs1; self.rhs2 = rhs2
        self.word = word; self.prob = prob

class Rule:
    __slots__ = ('lhs', 'rhs1', 'rhs2', 'prob',
                'args', 'lengths', '_args', 'lengths')
    def __init__(self, lhs, rhs1, rhs2, args, lengths, prob):
        self.lhs = lhs; self.rhs1 = rhs1; self.rhs2 = rhs2
        self.args = args; self.lengths = lengths; self.prob = prob
        self._args = self.args; self._lengths = self.lengths

#the agenda (priority queue)
class Entry(object):
    __slots__ = ('key', 'value', 'count')
    def __init__(self, key, value, count):
        self.key = key          #the `task'
        self.value = value      #the priority
        self.count = count      #unqiue identifier to resolve ties
    def __eq__(self, other):
        return self.count == other.count
    def __lt__(self, other):
        return self.value < other.value or (self.value == other.value
                and self.count < other.count)
    def __le__(self, other):
        return self.value <= other.value or (self.value == other.value
                and self.count < other.count)

INVALID = 0
class agenda(object):
    def __init__(self):
        self.heap = []                      # the priority queue list
        self.mapping = {}                   # mapping of keys to entries
        self.counter = 1                    # unique sequence count

    def __setitem__(self, key, value):
        if key in self.mapping:
            oldentry = self.mapping[key]
            entry = Entry(key, value, oldentry.count)
            self.mapping[key] = entry
            heappush(self.heap, entry)
            oldentry.count = INVALID
        else:
            entry = Entry(key, value, self.counter)
            self.counter += 1
            self.mapping[key] = entry
            heappush(self.heap, entry)

    def __getitem__(self, key):
        return self.mapping[key].value

    def __contains__(self, key):
        return key in self.mapping

    def __len__(self):
        return len(self.mapping)

    def popitem(self):
        entry = heappop(self.heap)
        while entry.count is INVALID:
            entry = heappop(self.heap)
        del self.mapping[entry.key]
        return entry.key, entry.value


def heavytest():
    try: rules, lexicon = read_srcg_grammar("rules.srcg", "lexicon.srcg")
    except IOError:
        print "large grammar not found."
        return
    grammar = splitgrammar(rules, lexicon)
    wordstags = "Diese/PDAT Ansicht/NN vertrat/VVFIN am/APPRART Donnerstag/NN ein/ART leitender/ADJA Arzt/NN der/ART Heidelberger/ADJA Rehabilitationsklinik/NN ,/$, Wolfgang/NE Huber/NE ,/$, im/APPRART sogenannten/ADJA Holzschutzmittelprozess/NN vor/APPR dem/ART Frankfurter/ADJA Landgericht/NN ./$."

    '''
    output of Cython version for this sentence:
    59. [len=23] Diese/PDAT Ansicht/NN vertrat/VVFIN am/APPRART Donnerstag/NN ein/ART leitender/ADJA Arzt/NN der/ART Heidelberger/ADJA Rehabilitationsklinik/NN ,/$, Wolfgang/NE Huber/NE ,/$, im/APPRART sogenannten/ADJA Holzschutzmittelprozess/NN vor/APPR dem/ART Frankfurter/ADJA Landgericht/NN ./$.
    max agenda size 220276, now 52815, chart items 633631 (1753 labels), edges 1708636, blocked 0

    cand-gold PP[3-17], PP[15-17] gold-cand PP[3-4], PP[15-21]
          (ROOT (S (NP (PDAT 0) (NN 1)) (VVFIN 2) (PP (APPRART 3) (NN 4) (NP (ART 5) (ADJA 6) (NN 7) (NP (ART 8) (ADJA 9) (NN 10)) ($, 11) (MPN (NE 12) (NE 13))) ($, 14) (PP (APPRART 15) (ADJA 16) (NN 17))) (PP (APPR 18) (ART 19) (ADJA 20) (NN 21))) ($. 22))
    283.67s cpu time elapsed
    GOLD: (ROOT (S (NP (PDAT 0) (NN 1)) (VVFIN 2) (PP (APPRART 3) (NN 4)) (NP (ART 5) (ADJA 6) (NN 7) (NP (ART 8) (ADJA 9) (NN 10)) ($, 11) (MPN (NE 12) (NE 13))) ($, 14) (PP (APPRART 15) (ADJA 16) (NN 17) (PP (APPR 18) (ART 19) (ADJA 20) (NN 21)))) ($. 22))
    srcg ex 42.37 lp 70.54 lr 70.96 lf 70.75'''
    sent = [a.split("/")[0] for a in wordstags.split()]
    tags = [a.split("/")[1] for a in wordstags.split()]
    chart, start = parse(sent, grammar, tags, grammar.toid['ROOT'], False)
    assert start
    t, p = mostprobablederivation(chart, start, grammar.tolabel)
    print exp(-p), t, '\n'

def main():
    rules = [
        ((('S','VP2','VMFIN'),    ((0,1,0),)),   log(1.0)),
        ((('VP2','VP2','VAINF'),  ((0,),(0,1))), log(0.5)),
        ((('VP2','PROAV','VVPP'), ((0,),(1,))),  log(0.5)),
        ((('VP2','VP2'),          ((0,),(0,))),  log(0.1))]
    lexicon = [
        ((('PROAV', 'Epsilon'), 'Daruber'),     0.0),
        ((('VAINF', 'Epsilon'), 'werden'),      0.0),
        ((('VMFIN', 'Epsilon'), 'muss'),        0.0),
        ((('VVPP', 'Epsilon'),  'nachgedacht'), 0.0)]
    grammar = splitgrammar(rules, lexicon)

    chart, start = parse("Daruber muss nachgedacht werden".split(),
          grammar, "PROAV VMFIN VVPP VAINF".split(), grammar.toid['S'], False)
    pprint_chart(chart, "Daruber muss nachgedacht werden".split(),
          grammar.tolabel)
    assert (mostprobablederivation(chart, start, grammar.tolabel) ==
        ('(S (VP2 (VP2 (PROAV 0) (VVPP 2)) (VAINF 3)) (VMFIN 1))', -log(0.25)))
    assert do("Daruber muss nachgedacht werden", grammar)
    assert do("Daruber muss nachgedacht werden werden", grammar)
    assert do("Daruber muss nachgedacht werden werden werden", grammar)
    print "ungrammatical sentence:"
    assert not do("werden nachgedacht muss Daruber", grammar)
    print "(as expected)\n"
    heavytest()
    print 'it worked'

if __name__ == '__main__':
    main()
