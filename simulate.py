# Number of validators
NUM_VALIDATORS = 20
# Block time
BLKTIME = 40
# 0 for no netsplits
# 1 for simulating a netsplit where 20% of validators jump off
# the network
# 2 for simulating the above netsplit, plus a 50-50 netsplit,
# plus reconvergence
NETSPLITS = 2
# Check the equality of finalized states
CHECK_INTEGRITY = True
# The genesis state root
GENESIS_STATE = 0
logging_level = 0
STEPS=10000


import network
from validator import *
import sys


validator_list = []
future = {}
discarded = {}
finalized_blocks = {}
all_signatures = []
now = [0]

def log(s, lvl):
    if logging_level >= lvl:
        print(s)

def get_opinions(n):
    o = []
    maxheight = 0
    for x in n.agents:
        maxheight = max(maxheight, len(x.probs))
    for h in range(maxheight):
        p = ''
        q = ''
        for x in n.agents:
            if len(x.probs) <= h:
                p += '_'
            elif x.probs[h] <= -10:
                p += '-'
            elif x.probs[h] >= 10:
                p += '+'
            else:
                p += str(x.probs[h])+','
            q += 'n' if len(x.received_blocks) <= h or x.received_blocks[h] is None else 'y'
        o.append((h, p, q))
    return o

if __name__ == '__main__':
    logging_level = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n = network.NetworkSimulator()
    for i in range(NUM_VALIDATORS):
        n.agents.append(Validator(i, n))
    n.generate_peers(3)
    for i in range(STEPS):
        n.tick()
        if i % 500 == 0:
            minmax = 99999999999999999
            for x in n.agents:
                minmax = min(minmax, x.max_finalized_height - 10)
            print(get_opinions(n)[max(minmax, 0):])
            finalized0 = [(v.max_finalized_height, v.finalized_hashes) for v in n.agents]
            if CHECK_INTEGRITY:
                finalized = sorted(finalized0, key=lambda x: len(x[1]))
                for j in range(len(n.agents) - 1):
                    for k in range(len(finalized[j][1])):
                        if finalized[j][1][k] is not None and finalized[j+1][1][k] is not None:
                            if finalized[j][1][k] != finalized[j+1][1][k]:
                                print(finalized[j])
                                print(finalized[j+1])
                                raise Exception("Finalization mismatch: %r %r" % (finalized[j][1][k], finalized[j+1][1][k]))
            print('Finalized status: %r' % [x[0] for x in finalized0])
            _all = finalized0[0][1]
            _pos = len([x for x in _all if x])
            _neg = len([x for x in _all if not x])
            print('Finalized blocks: %r (%r positive, %r negaitve)' % (len(_all), _pos, _neg))
        