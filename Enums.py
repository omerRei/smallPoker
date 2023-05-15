from enum import Enum


class Position(Enum):
    SMALL_BLIND = 0
    BIG_BLIND = 1
    CHECK = 2
    CALL = 3
    RAISE = 4


class Action(Enum):
    FOLD = 0
    CHECK = 1
    CALL = 2
    MIN_RAISE = 3
    BIG_RAISE = 4
