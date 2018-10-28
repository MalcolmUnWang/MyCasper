import random
from math import floor

def default_vote(scheduled_time, received_time, now, **kwargs):
    if received_time is None:
        time_delta = now - scheduled_time
        my_opinion_prob = 1 if time_delta < kwargs["blktime"] * 4 else 4.0 / (4 + time_delta * 1.0 / kwargs["blktime"])
        return 0 if random.random() < my_opinion_prob else -1
    else:
        time_delta = received_time * 0.9 + now * 0.1 - scheduled_time
        my_opinion_prob = 1 if abs(time_delta) < kwargs["blktime"] * 4 else 4.0 / (4 + abs(time_delta) * 1.0 / kwargs["blktime"])
        return 1 if random.random() < my_opinion_prob else -1
    

def vote(probs):
    if len(probs) == 0:
        return 0
    probs = sorted(probs)
    if probs[floor(len(probs)/3)] >= 1:
        return probs[floor(len(probs)/3)] + 1
    elif probs[floor(len(probs)*2/3)] <= -1:
        return probs[floor(len(probs)*2/3)] - 1
    else:
        return probs[floor(len(probs)/2)]