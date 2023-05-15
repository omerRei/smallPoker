from Enums import Position


class Player:
    def __init__(self, stack_size, is_small_blind):
        self.stack_size = stack_size
        self.hand = []
        self.total_bet = 0
        self.previous_bet = 0
        self.position = Position.SMALL_BLIND
        self.is_small_blind = is_small_blind
        self.is_fold = False
        self.already_played = False

    def receive_cards(self, cards):
        self.hand = cards

    def get_hand(self):
        return self.hand

    def place_bet(self, amount):
        self.previous_bet = self.total_bet
        if amount < self.stack_size:
            self.total_bet += amount
            self.stack_size -= amount
        else:
            self.total_bet += self.stack_size
            amount = self.stack_size
            self.stack_size = 0
        return amount

