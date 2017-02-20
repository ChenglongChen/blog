import time, os

import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data

dir = os.path.dirname(os.path.realpath(__file__))
mnist = input_data.read_data_sets('MNIST_data', one_hot=True)

# Convolutionnel model
# We want to have approximatively the same reprensatitivity between neural layers
# and the Softmax layer
# Number of parameters: (3 * 3 * 1 * 784) + (14 * 14 * 200 * 10) = 393800
# Dimensionality: R^784 -> R^39200 -> R_10, 39200 neurons but only 200 hundred features per spatial point

# Placeholder
x = tf.placeholder(tf.float32, shape=[None, 784])
y_true = tf.placeholder(tf.float32, shape=[None, 10])

sparsity_constraint = tf.placeholder(tf.float32)

x_img = tf.reshape(x, [-1, 28, 28, 1])
with tf.variable_scope('NeuralLayer'):
    # We would like 200 feature map, remember that weights are shared inside each feature map
    # The only difference with FC layers, is that we look for a precise feature everywhere in the image
    W1 = tf.get_variable('W1', shape=[3, 3, 1, 200], initializer=tf.random_normal_initializer(stddev=1e-1))
    b1 = tf.get_variable('b1', shape=[200], initializer=tf.constant_initializer(0.1))

    z1 = tf.nn.conv2d(x_img, W1, strides=[1, 2, 2, 1], padding='SAME') + b1
    a = tf.nn.relu(z1)

    # We graph the average density of neurons activation
    average_density = tf.reduce_mean(tf.reduce_sum(tf.cast((a > 0), tf.float32), axis=[1, 2, 3]))
    tf.summary.scalar('AverageDensity', average_density)

a_vec_size = 14 * 14 * 200 

with tf.variable_scope('SoftmaxLayer'):
    a_vec = tf.reshape(a, [-1, a_vec_size])

    W_s = tf.get_variable('W_s', shape=[a_vec_size, 10], initializer=tf.random_normal_initializer(stddev=1e-1))
    b_s = tf.get_variable('b_s', shape=[10], initializer=tf.constant_initializer(0.1))

    out = tf.matmul(a_vec, W_s) + b_s
    y = tf.nn.softmax(out)

with tf.variable_scope('Loss'):
    epsilon = 1e-7 # After some training, y can be 0 on some classes which lead to NaN 
    cross_entropy = tf.reduce_mean(-tf.reduce_sum(y_true * tf.log(y + epsilon), axis=[1]))
    # We add our sparsity constraint on the activations
    # loss = cross_entropy + sparsity_constraint * (tf.reduce_sum(a1) + tf.reduce_sum(a2) + tf.reduce_sum(a))
    loss = cross_entropy + sparsity_constraint * tf.reduce_sum(a)

    tf.summary.scalar('loss', loss) # Graph the loss

# We merge summaries before the accuracy summary to avoid 
# graphing the accuracy with training data
summaries = tf.summary.merge_all()

with tf.variable_scope('Accuracy'):
    correct_prediction = tf.equal(tf.argmax(y, 1), tf.argmax(y_true, 1))
    accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
    acc_summary = tf.summary.scalar('accuracy', accuracy) 


# Training
adam_train = tf.train.AdamOptimizer(learning_rate=1e-3)
train_op = adam_train.minimize(loss)
sess = None
# We iterate over different sparsity constraint
for sc in [0, 1e-5, 5e-5, 1e-4, 5e-4]:
    result_folder = dir + '/results/' + str(int(time.time())) + '-cnn-sc' + str(sc)
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        sw = tf.summary.FileWriter(result_folder, sess.graph)
        
        for i in range(20000):
            batch = mnist.train.next_batch(100)
            current_loss, summary, _ = sess.run([loss, summaries, train_op], feed_dict={
                x: batch[0],
                y_true: batch[1],
                sparsity_constraint: sc
            })
            sw.add_summary(summary, i + 1)

            if (i + 1) % 100 == 0:
                acc, acc_sum = sess.run([accuracy, acc_summary], feed_dict={
                    x: mnist.test.images, 
                    y_true: mnist.test.labels
                })
                sw.add_summary(acc_sum, i + 1)
                print('batch: %d, loss: %f, accuracy: %f' % (i + 1, current_loss, acc))