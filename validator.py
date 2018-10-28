import copy, random, hashlib
from distributions import normal_distribution
import network
from vote_strategy import vote, default_vote
import math
from simulate import *

class Validator():
    def __init__(self, pos, network):
        # Map from height to {node_id: latest_bet}
        self.received_signatures = []
        # List of received blocks
        self.received_blocks = []
        # Own probability estimates
        self.probs = []
        # All objects that this validator has received; basically a database
        self.received_objects = {}
        # Time when the object was received
        self.time_received = {}
        # The validator's ID, and its position in the queue
        self.pos = self.id = pos
        # The offset of this validator's clock vs. real time
        self.time_offset = normal_distribution(0, 100)()
        # The highest height that this validator has seen
        self.max_height = 0
        # The validator's hash chain
        self.finalized_hashes = []
        # Finalized states
        self.finalized_states = []
        # The highest height that the validator has finalized
        self.max_finalized_height = -1
        # The network object
        self.network = network
        # Last time signed
        self.last_time_signed = 0
        # Next height to mine
        self.next_height = self.pos

    # Get the local time from the point of view of this validator, using the
    # validator's offset from real time
    def get_time(self):
        return self.network.time + self.time_offset

    # Broadcast an object to the network
    def broadcast(self, obj):
        self.network.broadcast(self, obj)

    # Create a signature
    def sign(self):
        # Initialize the probability array, the core of the signature
        best_guesses = [None] * len(self.received_blocks)
        sign_from = max(0, self.max_finalized_height - 30)
        for i, b in list(enumerate(self.received_blocks))[sign_from:]:
            # Compute this validator's own initial vote based on when the block
            # was received, compared to what time the block should have arrived
            received_time = self.time_received[b.hash] if b is not None else None
            my_opinion = default_vote(BLKTIME * i, received_time, self.get_time(), blktime=BLKTIME)
            # Get others' bets on this height
            votes = self.received_signatures[i].values() if i < len(self.received_signatures) else []
            votes = [x for x in votes if x != 0]
            # Fill in the not-yet-received votes with this validator's default bet
            votes += [my_opinion] * (NUM_VALIDATORS - len(votes))
            vote_from_signatures = int(vote(votes))
            # Add the bet to the list
            bg = min(vote_from_signatures, 10 if self.received_blocks[i] is not None else my_opinion)
            best_guesses[i] = bg
            # Request a block if we should have it, and should have had it for
            # a long time, but don't
            if vote_from_signatures > 3 and self.received_blocks[i] is None:
                self.broadcast(BlockRequest(self.id, i))
            elif i < len(self.received_blocks) - 50 and self.received_blocks[i] is None:
                if random.random() < 0.05:
                    self.broadcast(BlockRequest(self.id, i))
            # Block finalized
            if best_guesses[i] >= 10:
                while len(self.finalized_hashes) <= i:
                    self.finalized_hashes.append(None)
                self.finalized_hashes[i] = self.received_blocks[i].hash
            # Absense of the block finalized
            elif best_guesses[i] <= -10:
                while len(self.finalized_hashes) <= i:
                    self.finalized_hashes.append(None)
                self.finalized_hashes[i] = False
        # Add to the list of finalized states
        while self.max_finalized_height < len(self.finalized_hashes) - 1 \
                and self.finalized_hashes[self.max_finalized_height + 1] is not None:
            self.max_finalized_height += 1
            last_state = self.finalized_states[-1] if len(self.finalized_states) else GENESIS_STATE
            self.finalized_states.append(state_transition(last_state, self.received_blocks[self.max_finalized_height]))

        self.probs = self.probs[:sign_from] + best_guesses[sign_from:]
        log('Making signature: %r' % self.probs[-10:], lvl=1)
        sign_from_state = self.finalized_states[sign_from - 1] if sign_from > 0 else GENESIS_STATE
        s = Signature(self.pos, self.probs[sign_from:], sign_from_state, sign_from)
        all_signatures.append(s)
        return s

    def on_receive(self, obj):
        # Ignore objects that we already know about
        if obj.hash in self.received_objects:
            return
        # When receiving a block
        if isinstance(obj, Block):
            log('received block: %d %d' % (obj.height, obj.hash), lvl=2)
            while len(self.received_blocks) <= obj.height:
                self.received_blocks.append(None)
            self.received_blocks[obj.height] = obj
            self.time_received[obj.hash] = self.get_time()
            # Upon receiving a new block, make a new signature
            s = self.sign()
            self.network.broadcast(self, s)
            self.on_receive(s)
            self.network.broadcast(self, obj)
        # When receiving a signature
        elif isinstance(obj, Signature):
            while len(self.received_signatures) <= len(obj.probs) + obj.sign_from:
                self.received_signatures.append({})
            for i, p in enumerate(obj.probs):
                self.received_signatures[i + obj.sign_from][obj.signer] = p
            self.network.broadcast(self, obj)
        # Received a block request, respond if we have it
        elif isinstance(obj, BlockRequest):
            if obj.ask_height < len(self.received_blocks):
                if self.received_blocks[obj.ask_height] is not None:
                    self.network.direct_send(obj.sender, self.received_blocks[obj.ask_height])
        self.received_objects[obj.hash] = obj
        self.time_received[obj.hash] = self.get_time()

    # Run every tick
    def tick(self):
        mytime = self.get_time()
        target_time = BLKTIME * self.next_height
        if mytime >= target_time:
            o = Block(self.pos, self.next_height)
            self.next_height += NUM_VALIDATORS
            log('making block: %d %d' % (o.height, o.hash), lvl=1)
            if random.random() < 0.9:
                self.network.broadcast(self, o)
            while len(self.received_blocks) <= o.height:
                self.received_blocks.append(None)
            self.received_blocks[o.height] = o
            self.received_objects[o.hash] = o
            self.time_received[o.hash] = mytime
            return o


# A signture specifies an initial height ("sign_from"), a finalized
# state from all blocks before that height and a list of probability
# bets from that height up to the latest height
class Signature():
    def __init__(self, signer, probs, finalized_state, sign_from):
        # The ID of the signer
        self.signer = signer
        # List of probability bets, expressed in log odds
        self.probs = probs
        # Hash of the signature (for db storage purposes)
        self.hash = random.randrange(10**14)
        # Finalized state
        self.finalized_state = finalized_state
        # Finalized height
        self.sign_from = sign_from

    def get_height(self):
        return self.sign_from + len(self.probs)


# Right now, a block simply specifies a proposer and a height.
class Block():
    def __init__(self, maker, height):
        # The producer of the block
        self.maker = maker
        # The height of the block
        self.height = height
        # Hash of the signature (for db storage purposes)
        self.hash = random.randrange(10**20) + 10**21 + 10**23 * self.height


# A request to receive a block at a particular height
class BlockRequest():
    def __init__(self, sender, height):
        self.sender = sender
        self.ask_height = height
        self.hash = random.randrange(10**14)


# Toy state transition function (in production, do sequential
# apply_transaction here)
def state_transition(state, block):
    return state if block is None else (state ** 3 + block.hash ** 5) % 10**40