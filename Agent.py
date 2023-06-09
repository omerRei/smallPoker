import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from PokerAgentEnv import PokerAgentEnv


# Configuration paramaters for the whole setup
gamma = 0.99  # Discount factor for past rewards
epsilon = 1.0  # Epsilon greedy parameter
epsilon_min = 0.25  # Minimum epsilon greedy parameter
epsilon_max = 1.0  # Maximum epsilon greedy parameter
epsilon_interval = epsilon_max - epsilon_min  # Rate at which to reduce chance of random action being taken
batch_size = 32  # Size of batch taken from replay buffer
max_steps_per_episode = 50

# Use the Baseline Atari environment because of Deepmind helper functions
env = PokerAgentEnv()

def build_model(states, actions):
    model = tf.keras.Sequential()
    model.add(layers.Dense(64, activation='relu', input_shape=(1, states[0])))
    model.add(layers.Dense(20, activation='relu'))
    model.add(layers.Dense(actions, activation='linear'))
    model.add(layers.Flatten())
    return model

state = np.array(env.reset())
num_actions = env.action_space.n
model = build_model(state.shape, num_actions)
model_target = build_model(state.shape, num_actions)

optimizer = keras.optimizers.Adam(learning_rate=0.001, clipnorm=1.0)

# Experience replay buffers
action_history = []
state_history = []
state_next_history = []
rewards_history = []
done_history = []
episode_reward_history = []
running_reward = 0
episode_count = 1
frame_count = 0
previous_running_reward = 0
# Number of frames to take random action and observe output
epsilon_random_frames = 5000
# Number of frames for exploration
epsilon_greedy_frames = 10000.0
# Maximum replay length
# Note: The Deepmind paper suggests 1000000 however this causes memory issues
max_memory_length = 50000
# Train the model after x actions
update_after_actions = 32
# How often to update the target network
update_target_network = 5000
# Using huber loss for stability
loss_function = keras.losses.Huber()
while True:

    if episode_count%10 == 0:
        print("run reward:", running_reward, "frame:", frame_count, "episode:", episode_count)

    state = np.array(env.reset())
    episode_reward = 0

    for timestep in range(1, max_steps_per_episode):
        frame_count += 1

        # Use epsilon-greedy for exploration
        if frame_count < epsilon_random_frames or epsilon > np.random.rand():
            # Take random action
            valid_actions = env.get_player_valid_actions()
            action = np.random.choice(valid_actions)
        else:
            # Predict action Q-values
            # From environment state
            state_tensor = tf.convert_to_tensor(state)
            state_tensor = tf.expand_dims(tf.expand_dims(state_tensor, 0), 0)
            action_probs = model(state_tensor, training=False)
            # Get allowed actions
            valid_actions = env.get_player_valid_actions()
            # Mask invalid actions by setting their Q-values to a large negative number
            mask = np.ones(env.action_space.n)
            mask[valid_actions] = 0
            masked_q_values = q_values - (mask * 1e9)
            # Choose action with highest Q-value among valid actions
            action = np.argmax(masked_q_values)
            # Take best action
            action = tf.argmax(action_probs[0]).numpy()

        # Decay probability of taking random action
        epsilon -= epsilon_interval / epsilon_greedy_frames
        epsilon = max(epsilon, epsilon_min)

        # Apply the sampled action in our environment
        state_next, reward, done, _ = env.step(action)
        state_next = np.array(state_next)

        episode_reward += reward

        # Save actions and states in replay buffer
        action_history.append(action)
        state_history.append(state)
        state_next_history.append(state_next)
        done_history.append(done)
        rewards_history.append(reward)
        state = state_next

        # Update every fourth frame and once batch size is over 32
        if frame_count % update_after_actions == 0 and len(done_history) > batch_size:

            # Get indices of samples for replay buffers
            indices = np.random.choice(range(len(done_history)), size=batch_size)

            # Using list comprehension to sample from replay buffer
            state_sample = np.array([state_history[i] for i in indices])
            state_next_sample = np.array([state_next_history[i] for i in indices])
            rewards_sample = [rewards_history[i] for i in indices]
            action_sample = [action_history[i] for i in indices]
            done_sample = tf.convert_to_tensor(
                [float(done_history[i]) for i in indices]
            )

            # Build the updated Q-values for the sampled future states
            # Use the target model for stability
            future_rewards = model_target.predict(state_next_sample.reshape(batch_size, 1, state.shape[0]), verbose=0)
            # Q value = reward + discount factor * expected future reward
            updated_q_values = rewards_sample + gamma * tf.reduce_max(future_rewards, axis=1)

            # If final frame set the last value to -1
            updated_q_values = updated_q_values * (1 - done_sample) - done_sample

            # Create a mask so we only calculate loss on the updated Q-values
            masks = tf.one_hot(action_sample, num_actions)

            with tf.GradientTape() as tape:
                # Train the model on the states and updated Q-values
                q_values = model(state_sample.reshape(batch_size, 1, state.shape[0]))
                # Apply the masks to the Q-values to get the Q-value for action taken
                q_action = tf.reduce_sum(tf.multiply(q_values, masks), axis=1)
                # Calculate loss between new Q-value and old Q-value
                loss = loss_function(updated_q_values, q_action)

            # Backpropagation
            grads = tape.gradient(loss, model.trainable_variables)
            optimizer.apply_gradients(zip(grads, model.trainable_variables))

        if frame_count % update_target_network == 0:
            # update the opponent model
            new_opponent_model = build_model(state.shape, num_actions)
            new_opponent_model.set_weights(model.get_weights())
            env.update_opponent_model(new_opponent_model)
            # update the the target network with new weights
            model_target.set_weights(model.get_weights())
            # Log details
            template = "running reward: {:.2f} at episode {}, frame count {}"
            print(template.format(running_reward, episode_count, frame_count))
            if running_reward > previous_running_reward:
                model.save("model.h5")
            previous_running_reward = running_reward
        # Limit the state and reward history
        if len(rewards_history) > max_memory_length:
            del rewards_history[:1]
            del state_history[:1]
            del state_next_history[:1]
            del action_history[:1]
            del done_history[:1]

        if done:
            break

    # Update running reward to check condition for solving
    episode_reward_history.append(episode_reward)
    if len(episode_reward_history) > 100:
        del episode_reward_history[:1]
    running_reward = np.mean(episode_reward_history)

    episode_count += 1

    if episode_count > 10000:
        model.save("ohlala.h5")
        break
