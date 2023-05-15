import gym
import numpy as np
from gym import spaces

from Player import Player
from Enums import Position, Action
from treys import Deck, Evaluator, Card
from tensorflow import keras
from PokerEnv import *


def convert_observation_to_input(observation):
    temp_array = np.array([])
    for obs in observation:
        temp_array = np.hstack([temp_array, obs.flatten()])
    return temp_array


def create_cards_dictionary():
    chars = ["h", "d", "c", "s"]
    nums = [str(x) for x in range(2, 10)] + ["T", "J", "Q", "K", "A"]
    index = 0
    dictionary = {}
    for n in nums:
        for c in chars:
            combo = n + c
            dictionary[Card.new(combo)] = (index, combo)
            index += 1
    final_dic = {}
    auxiliary_dic = {"T":10, "J":11, "Q":12, "K":13, "A":1,"h":1, "d":2, "c":3, "s":4}
    for num_key, tup in dictionary.items():
        card_value = tup[1][0]
        if card_value in auxiliary_dic:
            card_value = auxiliary_dic[card_value]
        card_colour = auxiliary_dic[tup[1][1]]
        final_dic[num_key] = (int(card_value), card_colour)
    return final_dic


def get_position_representation(cur_player, other_player):
    position_representation = np.zeros((2, 5), dtype=np.float32)
    position_representation[0, cur_player.position.value] = 1
    position_representation[0, other_player.position.value] = 1
    return position_representation


def create_observation_space():
    return spaces.Tuple((
        spaces.Box(low=0, high=1, shape=(2, 17), dtype=bool),
        # Hole cards for player (binary encoded)  shape=(2, 17) 13 for cards + 4 for shape
        spaces.Box(low=0, high=1, shape=(5, 17), dtype=bool),  # Community cards (binary encoded)
        spaces.Box(low=0, high=INITIAL_STACK_SIZE, shape=(2,), dtype=int),  # Stack sizes for both players
        spaces.Box(low=0, high=INITIAL_STACK_SIZE, shape=(2,), dtype=int),  # Current bets for both players
    ))


class PokerAgentEnv(gym.Env):
    def __init__(self):
        super(PokerAgentEnv, self).__init__()
        self.action_space = spaces.Discrete(5)
        self.pokerEnv = PokerEnv()
        self.observation_space = create_observation_space()
        try:
            self.opponent_model = keras.models.load_model('old_model.h5')
        except:
            self.opponent_model = None
        self.cards_dictionary = create_cards_dictionary()

    def reset(self):
        self.pokerEnv.reset()
        return self.get_observation(self.pokerEnv.player, self.pokerEnv.opponent)

    def step(self, action):
        reward = 0
        done, actual_action, temp_reward = self.pokerEnv.execute_player_action(self.pokerEnv.player, self.pokerEnv.opponent, action)
        reward += temp_reward
        if not done:
            opponent_action = self.get_other_player_action(self.pokerEnv.opponent, self.pokerEnv.player)
            done, actual_action, temp_reward =\
                self.pokerEnv.execute_player_action(self.pokerEnv.opponent, self.pokerEnv.player, opponent_action)
            reward += temp_reward
        observation = self.get_observation(self.pokerEnv.player, self.pokerEnv.opponent)
        return observation, reward, done, {}

    def get_player_valid_actions(self):
        return self.pokerEnv.get_player_valid_actions(other_player=self.pokerEnv.opponent)

    def get_other_player_action(self, cur_player, other_player):
        valid_actions = self.pokerEnv.get_player_valid_actions(other_player=other_player)
        if self.opponent_model is None:
            return np.random.choice(valid_actions)
        observation = self.get_observation(cur_player, other_player)
        other_player_observation = np.array([observation.reshape(1, -1)])
        q_values = self.opponent_model.predict(other_player_observation, verbose=0)
        mask = np.ones(self.action_space.n)
        mask[valid_actions] = 0
        masked_q_values = q_values - (mask * 1e9)
        # Choose action with highest Q-value among valid actions
        action = np.argmax(masked_q_values)
        return action

    def update_opponent_model(self, model):
        self.opponent_model = model

    def get_observation(self, cur_player, other_player):
        # Convert the player's hand into one-hot encoded representation
        hand_observation = self.get_cards_representation(cur_player.get_hand(), 2)

        # Convert the player's hand into one-hot encoded representation
        positions_observation = get_position_representation(cur_player, other_player)

        # Convert the community cards into one-hot encoded representation
        community_cards_observation = self.get_cards_representation(self.pokerEnv.community_cards, 5)

        # Normalize the pot size
        pot_size_observation = np.array([self.pokerEnv.pot / INITIAL_STACK_SIZE * 2])

        # Normalize the stack sizes for both players
        stack_sizes_observation = np.array(
            [cur_player.stack_size / (INITIAL_STACK_SIZE * 2), other_player.stack_size / (INITIAL_STACK_SIZE * 2)])

        # Normalize the amount to call
        call_observation = np.array((other_player.total_bet - cur_player.total_bet)/INITIAL_STACK_SIZE)

        # Combine the different parts of the observation into a tuple
        observation = (
            hand_observation,
            positions_observation,
            community_cards_observation,
            pot_size_observation,
            stack_sizes_observation,
            call_observation,
        )
        return convert_observation_to_input(observation)

    def get_cards_representation(self, cur_cards, mum_of_cards):
        card_representation = np.zeros((mum_of_cards, 17), dtype=np.float32)
        for i, card in enumerate(cur_cards):
            card_representation[i, self.cards_dictionary[card][0] - 1] = 1
            card_representation[i, 13 + self.cards_dictionary[card][1] - 1] = 1
        return card_representation


